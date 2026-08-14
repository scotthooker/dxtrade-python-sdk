"""High-level helpers built on the DXTrade transport layer.

These utilities wrap the raw transport methods with the common orchestration
needed to stream market data and open/close positions on any DXTrade broker:
account discovery, symbol resolution, client order codes, protective stops
and flat-state verification. They trade convenience for control — use the
transport directly when you need full control.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from .transport import DXTradeTransport

logger = logging.getLogger(__name__)

#: Order statuses that are no longer active.
FINAL_STATUSES = ("COMPLETED", "CANCELED", "EXPIRED", "REJECTED")

#: Default order time-in-force for market orders.
DEFAULT_TIF = "GTC"


def order_code(prefix: str = "vt") -> str:
    """Generate a unique client order code.

    The DXTrade API requires ``orderCode`` to be client-generated and unique
    per account.

    Args:
        prefix: Short prefix for the generated code

    Returns:
        Unique order code, e.g. ``vt-3f2a9c1d0b4e``
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def find_account_code(users: Any) -> str:
    """Extract the first account code from a ``/users`` response.

    DXTrade account codes look like ``default:12345``. The exact ``/users``
    response shape varies between brokers, so several shapes are handled.

    Args:
        users: Raw ``/users`` response (dict or list)

    Returns:
        First account code found (e.g. ``default:12345``)

    Raises:
        ValueError: No account code could be located
    """

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


def as_list(payload: Any, key: str) -> list[dict[str, Any]]:
    """Normalise a positions/orders/metrics response into a list of dicts.

    The DXTrade REST API returns these resources either as a bare list or as
    ``{key: [...]}``; this helper handles both.

    Args:
        payload: Raw response (dict or list)
        key: Expected list key (e.g. ``positions``, ``orders``, ``metrics``)

    Returns:
        List of dict entries
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get(key, [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def instrument_items(instruments: Any) -> list[dict[str, Any]]:
    """Extract instrument records from an instruments query response."""
    if isinstance(instruments, dict):
        for key in ("instrumentDetails", "instruments", "symbols"):
            value = instruments.get(key)
            if isinstance(value, list):
                return [i for i in value if isinstance(i, dict)]
        for _key, value in instruments.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return [i for i in value if isinstance(i, dict)]
    elif isinstance(instruments, list):
        return [i for i in instruments if isinstance(i, dict)]
    return []


def find_instrument(instruments: Any, symbol: str) -> dict[str, Any]:
    """Find the instrument record for a symbol in an instruments response.

    Args:
        instruments: Raw instruments query response
        symbol: Exact symbol to find

    Returns:
        Instrument record

    Raises:
        ValueError: Instrument not present in the response
    """
    for item in instrument_items(instruments):
        if item.get("symbol") == symbol:
            return item
    raise ValueError(f"instrument {symbol!r} not in query response")


def _match_symbol(hint: str, symbols: list[str]) -> str | None:
    """Match a user symbol hint against exact platform symbols.

    Handles common naming differences, e.g. ``BTCUSDT`` -> ``BTCUSD``.

    Args:
        hint: User-provided symbol hint
        symbols: Platform symbols to match against

    Returns:
        Matching platform symbol, or None
    """
    hint_upper = hint.upper()
    for symbol in symbols:
        if symbol.upper() == hint_upper:
            return symbol
    # BTCUSDT vs BTCUSD style one-letter quote mismatch
    if hint_upper.endswith("T"):
        for symbol in symbols:
            if symbol.upper() == hint_upper[:-1]:
                return symbol
    for symbol in symbols:
        symbol_upper = symbol.upper()
        if hint_upper in symbol_upper or symbol_upper in hint_upper:
            return symbol
    return None


async def resolve_account(transport: DXTradeTransport) -> str:
    """Ensure authentication and return the first accessible account code.

    Args:
        transport: Authenticated transport (logs in first if needed)

    Returns:
        Full account code (e.g. ``default:12345``)
    """
    if not transport.auth_handler.get_session_token():
        await transport.authenticate()
    users = await transport.get_users()
    return find_account_code(users)


async def resolve_symbol(transport: DXTradeTransport, account: str, hint: str) -> str:
    """Resolve a symbol hint to the exact platform symbol.

    Queries the account's instruments with the hint and common variants
    (e.g. ``BTCUSDT`` also queries ``BTCUSD``, ``BTC/USD`` also queries
    ``BTCUSD``).

    Args:
        transport: Authenticated transport
        account: Full account code
        hint: User-provided symbol hint

    Returns:
        Exact platform symbol

    Raises:
        ValueError: The symbol could not be resolved
    """
    candidates = [hint]
    upper = hint.upper()
    if upper.endswith("USDT"):
        candidates.append(hint[:-1])
    if "/" in hint:
        candidates.append(hint.replace("/", ""))
    candidates = list(dict.fromkeys(candidates))  # de-duplicate, keep order

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            instruments = await transport.query_instruments(
                symbols=[candidate], account=account
            )
        except Exception as exc:
            last_error = exc
            continue
        matched = _match_symbol(
            hint, [item.get("symbol", "") for item in instrument_items(instruments)]
        )
        if matched:
            return matched
        last_error = ValueError(f"no match for {candidate!r}")

    raise ValueError(
        f"could not resolve symbol {hint!r} on account {account}: {last_error}"
    )


async def discover_symbols(
    transport: DXTradeTransport,
    account: str,
    limit: int = 5,
    query_limit: int = 50,
) -> list[str]:
    """Discover a few tradable symbols for an account.

    Args:
        transport: Authenticated transport
        account: Full account code
        limit: Maximum number of symbols to return
        query_limit: Maximum instruments to fetch

    Returns:
        List of platform symbols
    """
    instruments = await transport.query_instruments(account=account, limit=query_limit)
    symbols = [
        item.get("symbol", "")
        for item in instrument_items(instruments)
        if item.get("symbol")
    ]
    return symbols[:limit]


def _quote(market_data: Any) -> tuple[float | None, float | None]:
    """Extract (bid, ask) from a POST /marketdata response."""
    events = market_data.get("events", []) if isinstance(market_data, dict) else []
    for event in events:
        if isinstance(event, dict) and event.get("type") == "Quote":
            return event.get("bid"), event.get("ask")
    return None, None


async def wait_for_position(
    transport: DXTradeTransport,
    account: str,
    symbol: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """Wait for a position to appear on the account.

    Args:
        transport: Authenticated transport
        account: Full account code
        symbol: Optional symbol filter
        timeout: Maximum wait in seconds

    Returns:
        The position record, or None on timeout
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        positions = as_list(await transport.get_account_positions(account), "positions")
        match = next(
            (p for p in positions if not symbol or p.get("symbol") == symbol),
            None,
        )
        if match:
            return match
        await asyncio.sleep(0.5)
    return None


async def wait_no_position(
    transport: DXTradeTransport,
    account: str,
    position_code: str,
    timeout: float = 15.0,
) -> bool:
    """Wait until a specific position is gone.

    Args:
        transport: Authenticated transport
        account: Full account code
        position_code: Position code to watch
        timeout: Maximum wait in seconds

    Returns:
        True if the position disappeared, False on timeout
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        positions = as_list(await transport.get_account_positions(account), "positions")
        if not any(str(p.get("positionCode")) == str(position_code) for p in positions):
            return True
        await asyncio.sleep(0.5)
    return False


async def stream_quotes(
    transport: DXTradeTransport,
    symbols: list[str] | None = None,
    account: str | None = None,
    duration: float = 30.0,
    on_quote: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Stream real-time quotes for a duration.

    Symbols default to a small set discovered for the account. Quote events
    (each a dict with ``symbol``/``bid``/``ask``/``time``) are collected and
    returned; ``on_quote`` is also called per event when provided.

    Args:
        transport: Transport (authenticated on demand)
        symbols: Optional symbol hints to stream
        account: Optional full account code (discovered if omitted)
        duration: How long to stream, in seconds
        on_quote: Optional callback per quote event

    Returns:
        List of quote events received during the stream

    Raises:
        TimeoutError: The market data channel did not connect
    """
    account = account or await resolve_account(transport)
    if symbols:
        symbols = [await resolve_symbol(transport, account, s) for s in symbols]
    else:
        symbols = await discover_symbols(transport, account, limit=5)
    if not symbols:
        raise ValueError("no symbols to stream")

    received: list[dict[str, Any]] = []

    def callback(message: Any) -> None:
        if isinstance(message, dict) and message.get("type") == "MarketData":
            for event in message.get("payload", {}).get("events", []):
                if isinstance(event, dict):
                    received.append(event)
                    if on_quote:
                        on_quote(event)

    await transport.subscribe("quotes", callback)
    connected = await transport.wait_for_channel("quotes", timeout=30.0)
    if not connected:
        await transport.unsubscribe("quotes")
        raise TimeoutError("market data channel did not connect")
    try:
        await transport.send_market_data_subscription(symbols, account)
        await asyncio.sleep(duration)
    finally:
        await transport.unsubscribe("quotes")

    logger.info(f"stream_quotes: {len(received)} quote events for {symbols}")
    return received


def _close_side(side: str) -> str:
    """Return the closing side opposite to an open side."""
    return "SELL" if side == "BUY" else "BUY"


async def open_position(
    transport: DXTradeTransport,
    symbol: str,
    side: str = "BUY",
    quantity: float | None = None,
    stop_loss: float | None = None,
    stop_loss_price: float | None = None,
    account: str | None = None,
    fill_timeout: float = 30.0,
) -> dict[str, Any]:
    """Open a market position, optionally with a protective stop loss.

    Quantity defaults to the instrument's minimum order size. ``stop_loss``
    is a maximum loss in account currency (converted to a price using the
    current quote); ``stop_loss_price`` is an absolute price level and takes
    precedence when both are given.

    The protective stop is placed as a closing STOP order without a quantity,
    which is what the DXTrade API requires for closing STOP/LIMIT orders.

    Args:
        transport: Transport (authenticated on demand)
        symbol: Symbol hint (e.g. ``BTCUSDT``)
        side: ``BUY`` or ``SELL``
        quantity: Position size in base units (defaults to minimum)
        stop_loss: Optional max loss in account currency
        stop_loss_price: Optional absolute stop price
        account: Optional full account code (discovered if omitted)
        fill_timeout: Max seconds to wait for the position to fill

    Returns:
        Dict with ``order`` (placement reply), ``position`` (filled
        position record) and ``stop_order`` (stop placement reply or None)

    Raises:
        RuntimeError: The order did not fill
        ValueError: Invalid arguments or unresolvable symbol
    """
    account = account or await resolve_account(transport)
    symbol = await resolve_symbol(transport, account, symbol)
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError(f"side must be BUY or SELL, got {side!r}")

    instruments = await transport.query_instruments(symbols=[symbol], account=account)
    instrument = find_instrument(instruments, symbol)
    if quantity is None:
        quantity = instrument.get("minOrderSize")
    if not quantity:
        raise ValueError("no minOrderSize for instrument and no quantity given")

    market_data = await transport.get_market_data([symbol], account=account)
    bid, ask = _quote(market_data)
    reference = ask if side == "BUY" else bid
    if not reference:
        raise RuntimeError("no quote received to size the order")

    stop_price = stop_loss_price
    if stop_loss is not None and stop_price is None:
        delta = stop_loss / quantity
        stop_price = reference - delta if side == "BUY" else reference + delta
        stop_price = round(stop_price, 2)

    open_order = {
        "orderCode": order_code(),
        "type": "MARKET",
        "instrument": symbol,
        "quantity": quantity,
        "positionEffect": "OPEN",
        "side": side,
        "tif": DEFAULT_TIF,
    }
    placed = await transport.place_order(account, open_order)

    position = await wait_for_position(transport, account, symbol, timeout=fill_timeout)
    if not position:
        raise RuntimeError(f"order {placed} did not fill: no position appeared")

    result: dict[str, Any] = {
        "order": placed,
        "position": position,
        "stop_order": None,
    }
    if stop_price is not None:
        stop_order = {
            "orderCode": order_code("vt-stop"),
            "type": "STOP",
            "instrument": symbol,
            "positionEffect": "CLOSE",
            "positionCode": position["positionCode"],
            "side": _close_side(side),
            "stopPrice": stop_price,
            "tif": DEFAULT_TIF,
        }
        result["stop_order"] = await transport.place_order(account, stop_order)
    return result


async def close_position(
    transport: DXTradeTransport,
    account: str | None = None,
    symbol: str | None = None,
    position_code: str | None = None,
) -> dict[str, Any]:
    """Close a position with a market order (full close).

    Exactly one open position must match: either ``position_code``, or
    ``symbol`` (or the only open position when neither is given).

    Args:
        transport: Transport (authenticated on demand)
        account: Optional full account code (discovered if omitted)
        symbol: Optional symbol filter
        position_code: Optional position code to close

    Returns:
        Dict with ``order`` (placement reply) and ``position`` (the record
        that was closed)

    Raises:
        ValueError: Zero or multiple matching positions
    """
    account = account or await resolve_account(transport)
    positions = as_list(await transport.get_account_positions(account), "positions")
    if position_code:
        matches = [
            p for p in positions if str(p.get("positionCode")) == str(position_code)
        ]
    else:
        matches = [p for p in positions if not symbol or p.get("symbol") == symbol]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one open position to close, found {len(matches)}"
        )

    position = matches[0]
    position_code = position["positionCode"]
    symbol = position["symbol"]
    close_order = {
        "orderCode": order_code("vt-close"),
        "type": "MARKET",
        "instrument": symbol,
        "positionEffect": "CLOSE",
        "positionCode": position_code,
        "side": _close_side(position.get("side", "BUY")),
        "tif": DEFAULT_TIF,
    }
    placed = await transport.place_order(account, close_order)
    await wait_no_position(transport, account, str(position_code), timeout=15.0)
    return {"order": placed, "position": position}


async def flatten(
    transport: DXTradeTransport, account: str | None = None
) -> dict[str, Any]:
    """Close all open positions and cancel all working orders.

    Args:
        transport: Transport (authenticated on demand)
        account: Optional full account code (discovered if omitted)

    Returns:
        Dict with ``closed`` (position codes), ``cancelled`` (order codes)
        and ``errors`` (any failures)
    """
    account = account or await resolve_account(transport)
    result: dict[str, Any] = {"closed": [], "cancelled": [], "errors": []}

    positions = as_list(await transport.get_account_positions(account), "positions")
    for position in positions:
        close_order = {
            "orderCode": order_code("vt-close"),
            "type": "MARKET",
            "instrument": position["symbol"],
            "positionEffect": "CLOSE",
            "positionCode": position["positionCode"],
            "side": _close_side(position.get("side", "BUY")),
            "tif": DEFAULT_TIF,
        }
        try:
            await transport.place_order(account, close_order)
            result["closed"].append(position["positionCode"])
        except Exception as exc:
            result["errors"].append(f"close {position['positionCode']}: {exc!r}")

    await asyncio.sleep(1)
    orders = as_list(await transport.get_account_orders(account), "orders")
    for order in orders:
        if order.get("status") in FINAL_STATUSES:
            continue
        ref = order.get("orderCode") or order.get("orderId")
        try:
            await transport.cancel_order(account, str(ref))
            result["cancelled"].append(ref)
        except Exception as exc:
            result["errors"].append(f"cancel {ref}: {exc!r}")

    return result


async def account_is_flat(
    transport: DXTradeTransport, account: str | None = None
) -> bool:
    """Check whether the account has no open positions or working orders.

    Args:
        transport: Transport (authenticated on demand)
        account: Optional full account code (discovered if omitted)

    Returns:
        True when ``openPositionsCount`` and ``openOrdersCount`` are both 0
    """
    account = account or await resolve_account(transport)
    metrics = as_list(await transport.get_account_metrics(account), "metrics")
    if not metrics:
        return False
    first = metrics[0]
    return (
        int(first.get("openPositionsCount") or 0) == 0
        and int(first.get("openOrdersCount") or 0) == 0
    )
