"""Unit tests for the transport layer's DXTrade REST API methods.

The aiohttp session is mocked — these tests never touch the network.
"""

import json
import time
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from dxtrade.config import AuthConfig
from dxtrade.config import AuthType
from dxtrade.config import SDKConfig
from dxtrade.transport import DXTradeTransport

BASE_URL = "https://broker.example/dxsca-web"
SESSION_TOKEN = "test-session-token"


def _mock_response(status=200, payload=None, content_type="application/json"):
    """Build an aiohttp-style response mock usable in an async context."""
    response = AsyncMock()
    response.status = status
    response.headers = {"content-type": content_type}
    response.raise_for_status = MagicMock()
    if payload is not None:
        response.json = AsyncMock(return_value=payload)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


@pytest.fixture
def transport():
    """Transport with a real config, an active token and a mocked session."""
    config = SDKConfig(
        base_url=BASE_URL,
        auth=AuthConfig(
            type=AuthType.CREDENTIALS,
            username="test_user",
            password="test_password",
            domain="default",
        ),
    )
    transport_ = DXTradeTransport(config)
    transport_.auth_handler._session_token = SESSION_TOKEN
    transport_.auth_handler._token_expires_at = time.time() + 3600
    transport_.auth_handler._last_login = time.time()
    # MagicMock (not AsyncMock): the transport uses
    # "async with session.request(...)", which needs a plain call returning
    # an async context manager rather than a coroutine.
    transport_._session = MagicMock()
    return transport_


def _expected_headers():
    return {
        "X-Auth-Token": SESSION_TOKEN,
        "Authorization": f"DXAPI {SESSION_TOKEN}",
    }


class TestEncodeAccount:
    """Test account code URL encoding."""

    def test_encodes_colon(self):
        """The colon in an account code must be percent-encoded."""
        assert DXTradeTransport._encode_account("default:12345") == "default%3A12345"

    def test_plain_account_unchanged(self):
        """Account codes without special characters are unchanged."""
        assert DXTradeTransport._encode_account("abc") == "abc"


class TestUsers:
    """Test account discovery."""

    async def test_get_users(self, transport):
        """GET /users with the session auth headers."""
        payload = {"users": [{"accountCode": "default:12345"}]}
        transport._session.request.return_value = _mock_response(payload=payload)

        result = await transport.get_users()

        assert result == payload
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/users",
            headers=_expected_headers(),
        )


class TestAccountScoped:
    """Test account-scoped REST resources."""

    async def test_get_account_metrics(self, transport):
        """GET /accounts/{encoded}/metrics."""
        transport._session.request.return_value = _mock_response(
            payload={"account": "default:12345"}
        )

        result = await transport.get_account_metrics("default:12345")

        assert result == {"account": "default:12345"}
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/accounts/default%3A12345/metrics",
            headers=_expected_headers(),
        )

    async def test_get_account_portfolio(self, transport):
        """GET /accounts/{encoded}/portfolio."""
        transport._session.request.return_value = _mock_response(
            payload={"portfolios": []}
        )

        result = await transport.get_account_portfolio("default:12345")

        assert result == {"portfolios": []}
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/accounts/default%3A12345/portfolio",
            headers=_expected_headers(),
        )

    async def test_get_account_positions(self, transport):
        """GET /accounts/{encoded}/positions."""
        transport._session.request.return_value = _mock_response(payload=[])

        result = await transport.get_account_positions("default:12345")

        assert result == []
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/accounts/default%3A12345/positions",
            headers=_expected_headers(),
        )

    async def test_get_account_orders(self, transport):
        """GET /accounts/{encoded}/orders."""
        transport._session.request.return_value = _mock_response(payload=[])

        result = await transport.get_account_orders("default:12345")

        assert result == []
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/accounts/default%3A12345/orders",
            headers=_expected_headers(),
        )

    async def test_get_account_orders_history(self, transport):
        """GET /accounts/{encoded}/orders/history."""
        transport._session.request.return_value = _mock_response(payload=[])

        result = await transport.get_account_orders_history("default:12345")

        assert result == []
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/accounts/default%3A12345/orders/history",
            headers=_expected_headers(),
        )


class TestInstruments:
    """Test instrument discovery."""

    async def test_query_instruments_account_scoped(self, transport):
        """Account-scoped query passes symbols/limit as query params."""
        transport._session.request.return_value = _mock_response(
            payload={"instrumentDetails": []}
        )

        result = await transport.query_instruments(
            symbols=["BTC", "ETH"], account="default:12345", limit=5
        )

        assert result == {"instrumentDetails": []}
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/accounts/default%3A12345/instruments/query",
            headers=_expected_headers(),
            params={"symbols": "BTC,ETH", "limit": 5},
        )

    async def test_query_instruments_global(self, transport):
        """Without an account, the global instruments query is used."""
        transport._session.request.return_value = _mock_response(payload={})

        result = await transport.query_instruments(symbols=["BTC"])

        assert result == {}
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/instruments/query",
            headers=_expected_headers(),
            params={"symbols": "BTC"},
        )

    async def test_query_instruments_no_args(self, transport):
        """No arguments still produces a valid request."""
        transport._session.request.return_value = _mock_response(payload={})

        result = await transport.query_instruments()

        assert result == {}
        transport._session.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/instruments/query",
            headers=_expected_headers(),
            params={},
        )


class TestMarketData:
    """Test REST market data snapshot."""

    async def test_get_market_data_defaults(self, transport):
        """POST /marketdata with default Quote/COMPACT event types."""
        transport._session.request.return_value = _mock_response(payload={"events": []})

        result = await transport.get_market_data(["EUR/USD"])

        assert result == {"events": []}
        transport._session.request.assert_called_once_with(
            "POST",
            f"{BASE_URL}/marketdata",
            headers=_expected_headers(),
            json={
                "symbols": ["EUR/USD"],
                "eventTypes": [{"type": "Quote", "format": "COMPACT"}],
            },
        )

    async def test_get_market_data_with_account_and_types(self, transport):
        """Account and custom event types are forwarded."""
        transport._session.request.return_value = _mock_response(payload={})

        await transport.get_market_data(
            ["EUR/USD"],
            event_types=[{"type": "Candle", "candleType": "5m", "format": "COMPACT"}],
            account="default:12345",
        )

        transport._session.request.assert_called_once_with(
            "POST",
            f"{BASE_URL}/marketdata",
            headers=_expected_headers(),
            json={
                "symbols": ["EUR/USD"],
                "eventTypes": [
                    {"type": "Candle", "candleType": "5m", "format": "COMPACT"}
                ],
                "account": "default:12345",
            },
        )


class TestPing:
    """Test session validation and token refresh."""

    async def test_ping_refreshes_token(self, transport):
        """A new sessionToken from /ping updates the stored token."""
        transport._session.request.return_value = _mock_response(
            payload={"sessionToken": "fresh-token"}
        )

        result = await transport.ping()

        assert result == {"sessionToken": "fresh-token"}
        assert transport.auth_handler.get_session_token() == "fresh-token"

    async def test_ping_without_token(self, transport):
        """A ping response without sessionToken leaves the token untouched."""
        transport._session.request.return_value = _mock_response(payload={})

        await transport.ping()

        assert transport.auth_handler.get_session_token() == SESSION_TOKEN


class TestLogout:
    """Test session invalidation."""

    async def test_logout_clears_token(self, transport):
        """POST /logout and clear the local token."""
        transport._session.request.return_value = _mock_response(payload={})

        await transport.logout()

        transport._session.request.assert_called_once_with(
            "POST",
            f"{BASE_URL}/logout",
            headers=_expected_headers(),
        )
        assert transport.auth_handler.get_session_token() is None


class TestSubscriptionMessages:
    """Test the Push subscription message builders."""

    async def test_market_data_subscription_shape(self, transport):
        """Market data subscription carries requestId, timestamp, session and payload."""
        websocket = AsyncMock()
        transport._websockets["quotes"] = websocket

        await transport.send_market_data_subscription(["EUR/USD"], "default:12345")

        sent = json.loads(websocket.send.call_args[0][0])
        assert sent["type"] == "MarketDataSubscriptionRequest"
        assert sent["requestId"]
        assert sent["timestamp"]
        assert sent["session"] == SESSION_TOKEN
        assert sent["payload"] == {
            "account": "default:12345",
            "symbols": ["EUR/USD"],
            "eventTypes": [{"type": "Quote", "format": "COMPACT"}],
        }

    async def test_portfolio_subscription_shape(self, transport):
        """Portfolio subscription uses the DXTrade spec payload (requestType/accounts)."""
        websocket = AsyncMock()
        transport._websockets["portfolio"] = websocket

        await transport.send_portfolio_subscription("default:12345")

        sent = json.loads(websocket.send.call_args[0][0])
        assert sent["type"] == "AccountPortfoliosSubscriptionRequest"
        assert sent["requestId"]
        assert sent["timestamp"]
        assert sent["session"] == SESSION_TOKEN
        assert sent["payload"] == {
            "requestType": "LIST",
            "accounts": ["default:12345"],
        }


class TestSendMessage:
    """Test raw message sending without blocking on a reply."""

    async def test_send_message_sends_without_recv(self, transport):
        """send_message only sends; the handler loop owns recv."""
        websocket = AsyncMock()
        transport._websockets["quotes"] = websocket

        result = await transport.send_message(
            "quotes", {"type": "MarketDataSubscriptionRequest", "requestId": "abc"}
        )

        assert result is None
        websocket.send.assert_called_once_with(
            '{"type": "MarketDataSubscriptionRequest", "requestId": "abc"}'
        )
        websocket.recv.assert_not_called()

    async def test_send_message_requires_connected_channel(self, transport):
        """Sending to an unknown channel raises ValueError."""
        with pytest.raises(ValueError):
            await transport.send_message("nope", {"type": "x"})

    async def test_send_message_accepts_string(self, transport):
        """Raw string messages pass through unchanged."""
        websocket = AsyncMock()
        transport._websockets["quotes"] = websocket

        await transport.send_message("quotes", '{"type": "ping"}')

        websocket.send.assert_called_once_with('{"type": "ping"}')


class TestPingPongHandler:
    """Test the application-level ping/pong handler."""

    async def test_handles_ping_request(self, transport):
        """A PingRequest is answered with a Ping and not forwarded."""
        websocket = AsyncMock()
        forwarded = []
        transport._subscriptions["quotes"] = forwarded.append

        handled = await transport._handle_ping_pong(
            "quotes",
            {"type": "PingRequest", "session": SESSION_TOKEN, "timestamp": "t"},
            websocket,
            SESSION_TOKEN,
        )

        assert handled is True
        assert forwarded == [], "ping messages must not reach the user callback"
        sent = json.loads(websocket.send.call_args[0][0])
        assert sent["type"] == "Ping"
        assert sent["session"] == SESSION_TOKEN
        assert sent["timestamp"]

        stats = transport.get_ping_stats("quotes")
        assert stats["ping_requests_received"] == 1
        assert stats["ping_responses_sent"] == 1
        assert stats["session_extensions"] == 1

    async def test_ignores_regular_message(self, transport):
        """Regular messages are not treated as pings."""
        websocket = AsyncMock()

        handled = await transport._handle_ping_pong(
            "quotes", {"type": "MarketData", "payload": {}}, websocket, SESSION_TOKEN
        )

        assert handled is False
        websocket.send.assert_not_called()


class TestPlaceOrder:
    """Test order placement."""

    async def test_place_order_open(self, transport):
        """POST /accounts/{encoded}/orders with the order payload."""
        transport._session.request.return_value = _mock_response(
            payload={"orderId": 1, "status": "ACCEPTED"}
        )
        order = {
            "orderCode": "vt-abc123",
            "type": "MARKET",
            "instrument": "BTCUSDT",
            "quantity": 0.0001,
            "positionEffect": "OPEN",
            "side": "BUY",
            "tif": "GTC",
        }

        result = await transport.place_order("default:12345", order)

        assert result == {"orderId": 1, "status": "ACCEPTED"}
        expected_payload = dict(order)
        expected_payload["account"] = "default:12345"
        transport._session.request.assert_called_once_with(
            "POST",
            f"{BASE_URL}/accounts/default%3A12345/orders",
            headers=_expected_headers(),
            json=expected_payload,
        )

    async def test_place_order_close_position(self, transport):
        """A closing order carries positionEffect CLOSE and positionCode."""
        transport._session.request.return_value = _mock_response(payload={})
        close_order = {
            "orderCode": "vt-close1",
            "type": "MARKET",
            "instrument": "BTCUSDT",
            "positionEffect": "CLOSE",
            "positionCode": "pos-1",
            "side": "SELL",
            "tif": "GTC",
        }

        await transport.place_order("default:12345", close_order)

        expected_payload = dict(close_order)
        expected_payload["account"] = "default:12345"
        transport._session.request.assert_called_once_with(
            "POST",
            f"{BASE_URL}/accounts/default%3A12345/orders",
            headers=_expected_headers(),
            json=expected_payload,
        )
