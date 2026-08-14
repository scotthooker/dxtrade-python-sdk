"""Live WebSocket (Push API) tests against a real broker via the SDK transport.

These tests require a broker ``.env`` in the repository root with ``DXTRADE_*``
variables set (e.g. Velotrade). They are skipped otherwise and never run in CI.
"""

import asyncio
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from dxtrade import create_transport

load_dotenv()

pytestmark = pytest.mark.skipif(
    not Path(".env").exists() or not os.getenv("DXTRADE_USERNAME"),
    reason="requires a broker .env with DXTRADE_USERNAME",
)

# Velotrade connection values (see TEST_PLAN_VELOTRADE.md §2)
MARKET_DATA_URL = "wss://dx.velotrade.com/dxsca-web/md?format=JSON"
PORTFOLIO_URL = "wss://dx.velotrade.com/dxsca-web/?format=JSON"


def _extract_account_code(users: Any) -> str:
    """Best-effort extraction of the first account code from a /users response."""

    def find_in(item: Any) -> str:
        if isinstance(item, dict):
            for key in ("accountCode", "account", "id"):
                value = item.get(key)
                if isinstance(value, str) and value.startswith("default:"):
                    return value
            for key in ("accounts", "users", "userDetails", "accountList"):
                value = item.get(key)
                if isinstance(value, list):
                    for entry in value:
                        found = find_in(entry)
                        if found:
                            return found
        elif isinstance(item, list):
            for entry in item:
                found = find_in(entry)
                if found:
                    return found
        return ""

    code = find_in(users)
    if not code:
        raise ValueError("Could not find an account code in /users response")
    return code


def _extract_symbols(instruments: Any) -> list[str]:
    """Best-effort extraction of instrument symbols from an instruments query."""
    if isinstance(instruments, dict):
        for key in ("instrumentDetails", "instruments", "symbols"):
            value = instruments.get(key)
            if isinstance(value, list):
                if all(isinstance(item, dict) and "symbol" in item for item in value):
                    return [item["symbol"] for item in value]
                if all(isinstance(item, str) for item in value):
                    return value
        for _key, value in instruments.items():
            if (
                isinstance(value, list)
                and value
                and isinstance(value[0], dict)
                and "symbol" in value[0]
            ):
                return [item["symbol"] for item in value]
    elif isinstance(instruments, list):
        return [
            item["symbol"]
            for item in instruments
            if isinstance(item, dict) and "symbol" in item
        ]
    return []


async def _wait_for_channel(transport, channel: str, timeout: float = 45.0):
    """Wait until the transport has an open WebSocket for the channel."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if channel in transport._websockets:
            return
        await asyncio.sleep(0.25)
    raise TimeoutError(f"WebSocket channel '{channel}' did not connect")


def _make_callback(ready: asyncio.Event, received: list[dict]) -> Callable:
    """Build a message callback that records messages and flags a type."""

    def callback(message: Any) -> None:
        received.append(message)
        if isinstance(message, dict):
            ready.set()

    return callback


class TestMarketDataPush:
    """Live market-data Push tests."""

    async def test_market_data_subscription_streams_quotes(self):
        """Subscribe to quotes and receive MarketData events for our symbols."""
        transport = create_transport()
        try:
            token = await transport.authenticate()
            assert token

            users = await transport.get_users()
            account = _extract_account_code(users)

            instruments = await transport.query_instruments(account=account, limit=100)
            symbols = _extract_symbols(instruments)[:5]
            assert symbols, "no symbols discovered from instruments query"

            received: list[dict] = []
            ready = asyncio.Event()

            await transport.subscribe(
                "quotes", _make_callback(ready, received), ws_url=MARKET_DATA_URL
            )
            await _wait_for_channel(transport, "quotes")

            await transport.send_market_data_subscription(symbols, account)

            await asyncio.wait_for(ready.wait(), timeout=60)

            market = next(
                m
                for m in received
                if isinstance(m, dict) and m.get("type") == "MarketData"
            )
            events = market.get("payload", {}).get("events", [])
            assert events, "MarketData message carried no events"

            quoted = {e.get("symbol") for e in events if isinstance(e, dict)}
            assert quoted & set(
                symbols
            ), f"no events for requested symbols {symbols}; got {quoted}"
            assert any(
                isinstance(e, dict) and ("bid" in e or "ask" in e) for e in events
            ), "no bid/ask fields in quote events"
        finally:
            await transport.close()


class TestPortfolioPush:
    """Live portfolio Push tests."""

    async def test_portfolio_subscription_receives_snapshot(self):
        """Spec-shaped portfolio subscription returns an AccountPortfolios snapshot."""
        transport = create_transport()
        try:
            await transport.authenticate()
            users = await transport.get_users()
            account = _extract_account_code(users)

            received: list[dict] = []
            ready = asyncio.Event()

            await transport.subscribe(
                "portfolio", _make_callback(ready, received), ws_url=PORTFOLIO_URL
            )
            await _wait_for_channel(transport, "portfolio")

            await transport.send_portfolio_subscription(account)

            await asyncio.wait_for(ready.wait(), timeout=60)

            portfolios = next(
                m
                for m in received
                if isinstance(m, dict) and m.get("type") == "AccountPortfolios"
            )
            payload = portfolios.get("payload", {})
            assert isinstance(payload.get("portfolios"), list)
        finally:
            await transport.close()

    async def test_portfolio_legacy_payload_rejected(self):
        """The pre-fix SDK payload shape is rejected by the server (gap G5)."""
        transport = create_transport()
        try:
            await transport.authenticate()
            users = await transport.get_users()
            account = _extract_account_code(users)

            received: list[dict] = []
            ready = asyncio.Event()

            await transport.subscribe(
                "portfolio", _make_callback(ready, received), ws_url=PORTFOLIO_URL
            )
            await _wait_for_channel(transport, "portfolio")

            # Old SDK shape: payload {account, eventTypes} — no requestType/accounts.
            legacy = {
                "type": "AccountPortfoliosSubscriptionRequest",
                "requestId": "legacy-payload-test",
                "session": transport.auth_handler.get_session_token(),
                "payload": {
                    "account": account,
                    "eventTypes": [{"type": "Position", "format": "COMPACT"}],
                },
            }
            await transport.send_message("portfolio", legacy)

            try:
                await asyncio.wait_for(ready.wait(), timeout=15)
            except asyncio.TimeoutError:
                pytest.fail(
                    "no response to legacy payload within 15s "
                    "(unexpected: expected a Reject)"
                )

            reply = next(
                (m for m in received if isinstance(m, dict)),
                None,
            )
            assert reply is not None
            assert (
                reply.get("type") == "Reject"
            ), f"expected Reject for legacy payload, got: {reply}"
        finally:
            await transport.close()


class TestPingPong:
    """Live ping/pong observation and stats."""

    async def test_ping_stats_tracked_on_active_channels(self):
        """Ping stats structures exist for active channels after streaming."""
        transport = create_transport()
        try:
            await transport.authenticate()
            users = await transport.get_users()
            account = _extract_account_code(users)
            instruments = await transport.query_instruments(account=account, limit=100)
            symbols = _extract_symbols(instruments)[:3]
            assert symbols

            received: list[dict] = []
            ready = asyncio.Event()

            await transport.subscribe(
                "quotes", _make_callback(ready, received), ws_url=MARKET_DATA_URL
            )
            await _wait_for_channel(transport, "quotes")
            await transport.send_market_data_subscription(symbols, account)

            # Stream for up to 45s to give the server a chance to PingRequest.
            try:
                await asyncio.wait_for(ready.wait(), timeout=45)
            except asyncio.TimeoutError:
                pass

            stats = transport.get_ping_stats("quotes")
            assert isinstance(stats, dict)
            assert "ping_requests_received" in stats
            assert "ping_responses_sent" in stats

            health = transport.get_session_health()
            assert health["active_channels"] >= 1
            assert health["ping_response_success_rate"] >= 0.0
        finally:
            await transport.close()
