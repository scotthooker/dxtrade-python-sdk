"""Diagnostic: place a small BTCUSD buy with a $10 stop loss, then close it.

Usage:
    # Discovery + size calculation only (no order placed)
    PYTHONPATH=src venv/Scripts/python.exe tests/_diag_trade.py --dry-run

    # Place a buy + protective stop, wait HOLD_SECONDS, close, verify flat
    PYTHONPATH=src venv/Scripts/python.exe tests/_diag_trade.py

This trades real money on the configured account. Not a pytest test.
The position is always closed (and working orders cancelled) in a finally
block, so a failure mid-way cannot leave the account open.
"""

import asyncio
import json
import sys
import uuid

MAX_LOSS_USD = 10.0
SYMBOL = "BTCUSD"
HOLD_SECONDS = 30


def extract_account_code(users):
    def find_in(item):
        if isinstance(item, dict):
            for key in ("accountCode", "account", "id"):
                v = item.get(key)
                if isinstance(v, str) and v.startswith("default:"):
                    return v
            for key in ("accounts", "users", "userDetails", "accountList"):
                v = item.get(key)
                if isinstance(v, list):
                    for e in v:
                        f = find_in(e)
                        if f:
                            return f
        elif isinstance(item, list):
            for e in item:
                f = find_in(e)
                if f:
                    return f
        return ""

    code = find_in(users)
    if not code:
        raise ValueError("no account code in /users")
    return code


def find_instrument(instruments):
    """Locate the instrument record from an instruments query."""
    items = []
    if isinstance(instruments, dict):
        for key in ("instrumentDetails", "instruments", "symbols"):
            v = instruments.get(key)
            if isinstance(v, list):
                items = v
                break
        if not items:
            for _key, v in instruments.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    items = v
                    break
    elif isinstance(instruments, list):
        items = instruments

    for item in items:
        if isinstance(item, dict) and item.get("symbol") == SYMBOL:
            return item
    raise ValueError(f"no {SYMBOL} instrument in query response")


def extract_quote_price(market_data):
    """Extract bid/ask from a POST /marketdata response."""
    events = market_data.get("events", []) if isinstance(market_data, dict) else []
    for ev in events:
        if isinstance(ev, dict) and ev.get("type") == "Quote":
            return ev.get("bid"), ev.get("ask")
    return None, None


def as_list(payload, key):
    """Normalise a positions/orders/metrics response into a list of dicts."""
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        items = payload.get(key, [])
        if isinstance(items, list):
            return [p for p in items if isinstance(p, dict)]
    return []


def order_code():
    return f"vt-{uuid.uuid4().hex[:12]}"


async def flatten(transport, account):
    """Close all positions and cancel working orders for the symbol."""
    positions = as_list(await transport.get_account_positions(account), "positions")
    for p in positions:
        if p.get("symbol") != SYMBOL:
            continue
        close = {
            "orderCode": order_code(),
            "type": "MARKET",
            "instrument": SYMBOL,
            "positionEffect": "CLOSE",
            "positionCode": p["positionCode"],
            "side": "SELL",
            "tif": "GTC",
        }
        try:
            await transport.place_order(account, close)
            print(f"    [cleanup] closed position {p['positionCode']}")
        except Exception as exc:  # noqa: BLE001
            print(f"    [cleanup] close FAILED {p['positionCode']}: {exc!r}")

    await asyncio.sleep(1)
    orders = as_list(await transport.get_account_orders(account), "orders")
    for o in orders:
        status = o.get("status")
        if status not in ("COMPLETED", "CANCELED", "EXPIRED", "REJECTED"):
            ref = o.get("orderCode") or o.get("orderId")
            try:
                await transport.cancel_order(account, str(ref))
                print(f"    [cleanup] cancelled order {ref}")
            except Exception as exc:  # noqa: BLE001
                print(f"    [cleanup] cancel FAILED {ref}: {exc!r}")


async def main():
    dry_run = "--dry-run" in sys.argv
    from dxtrade import create_transport  # noqa: E402

    transport = create_transport()
    position_code = None
    stop_code = None
    try:
        token = await transport.authenticate()
        print(f"[1] login ok, token {token[:12]}...")

        users = await transport.get_users()
        account = extract_account_code(users)
        print(f"[2] account: {account}")

        instruments = await transport.query_instruments(symbols=[SYMBOL], account=account)
        inst = find_instrument(instruments)
        print(f"[3] instrument: {json.dumps(inst, default=str)[:400]}")

        market_data = await transport.get_market_data([SYMBOL], account=account)
        bid, ask = extract_quote_price(market_data)
        print(f"[4] quote {SYMBOL}: bid={bid} ask={ask}")
        if not bid:
            raise RuntimeError("no quote received")

        qty = inst.get("minOrderSize")
        notional = qty * bid
        stop_distance = MAX_LOSS_USD / qty
        print(
            f"[5] size: qty={qty} (min={inst.get('minOrderSize')}) "
            f"notional~${notional:.2f}"
        )
        print(
            f"[5b] stop distance for ${MAX_LOSS_USD} loss on {qty} {SYMBOL}: "
            f"{stop_distance:,.2f} pts"
        )

        open_order = {
            "orderCode": order_code(),
            "type": "MARKET",
            "instrument": SYMBOL,
            "quantity": qty,
            "positionEffect": "OPEN",
            "side": "BUY",
            "tif": "GTC",
        }
        print(f"[6] open order: {json.dumps(open_order)}")

        if dry_run:
            print("[7] DRY RUN - no order placed")
            return

        # --- Place the buy ---
        placed = await transport.place_order(account, open_order)
        print(f"[7] open order reply: {json.dumps(placed, default=str)[:200]}")

        # --- Confirm fill via positions ---
        position = None
        for _ in range(60):
            positions = as_list(await transport.get_account_positions(account), "positions")
            position = next((p for p in positions if p.get("symbol") == SYMBOL), None)
            if position:
                break
            await asyncio.sleep(0.5)
        if not position:
            raise RuntimeError("BUY did not fill: no position appeared within 30s")
        position_code = position["positionCode"]

        entry = position.get("openPrice") or position.get("averagePrice")
        print(
            f"[8] position open: code={position_code} "
            f"qty={position.get('quantity')} side={position.get('side')} "
            f"entry={entry}"
        )

        # --- Protective stop loss: STOP SELL at entry - stop_distance ---
        # NOTE: closing STOP/LIMIT orders must NOT carry a quantity
        # (errorCode 33 otherwise).
        stop_price = round(float(entry) - stop_distance, 2)
        stop_code = order_code()
        stop_order = {
            "orderCode": stop_code,
            "type": "STOP",
            "instrument": SYMBOL,
            "positionEffect": "CLOSE",
            "positionCode": position_code,
            "side": "SELL",
            "stopPrice": stop_price,
            "tif": "GTC",
        }
        print(f"[9] stop order: {json.dumps(stop_order)}")
        stop_reply = await transport.place_order(account, stop_order)
        print(f"[9] stop order reply: {json.dumps(stop_reply, default=str)[:200]}")

        # --- Confirm the stop is working ---
        # The orders list does not reliably echo the stop's orderCode, so also
        # accept metrics.openOrdersCount >= 1 (any working order must be the
        # stop, since the market BUY fills immediately).
        stop_confirmed = False
        for _ in range(30):
            orders = as_list(await transport.get_account_orders(account), "orders")
            stop_working = next(
                (o for o in orders if o.get("orderCode") == stop_code), None
            )
            if stop_working:
                stop_confirmed = True
                break
            metrics = as_list(await transport.get_account_metrics(account), "metrics")
            if metrics and metrics[0].get("openOrdersCount", 0) >= 1:
                stop_confirmed = True
                break
            await asyncio.sleep(0.5)
        print(f"[10] stop confirmed: {stop_confirmed}")
        if not stop_confirmed:
            raise RuntimeError("STOP loss order not confirmed as working")

        # --- Hold ---
        print(f"[11] holding {HOLD_SECONDS}s...")
        await asyncio.sleep(HOLD_SECONDS)

        # --- Close the position (market SELL CLOSE, full close) ---
        close_order = {
            "orderCode": order_code(),
            "type": "MARKET",
            "instrument": SYMBOL,
            "positionEffect": "CLOSE",
            "positionCode": position_code,
            "side": "SELL",
            "tif": "GTC",
        }
        print(f"[12] close order: {json.dumps(close_order)}")
        closed = await transport.place_order(account, close_order)
        print(f"[12] close order reply: {json.dumps(closed, default=str)[:200]}")

        # --- Cancel the protective stop (no longer needed) ---
        # Expected to 400: protective stops auto-cancel when the position closes.
        await asyncio.sleep(1)
        try:
            cancel_reply = await transport.cancel_order(account, stop_code)
            print(f"[13] cancel stop reply: {json.dumps(cancel_reply, default=str)[:200]}")
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
            status = ""
            if "status=400" in detail:
                status = "400 (already auto-cancelled)"
            elif "status=" in detail:
                status = detail.split("status=")[1].split(",")[0]
            print(f"[13] cancel stop: {status or 'error'}")

        # --- Verify flat ---
        await asyncio.sleep(2)
        positions = as_list(await transport.get_account_positions(account), "positions")
        open_positions = [p for p in positions if p.get("symbol") == SYMBOL]
        orders = as_list(await transport.get_account_orders(account), "orders")
        working = [
            o
            for o in orders
            if o.get("instrument") == SYMBOL
            and o.get("status") not in ("COMPLETED", "CANCELED", "EXPIRED", "REJECTED")
        ]
        print(
            f"[14] after close: open positions={len(open_positions)}, "
            f"working orders={len(working)}"
        )

        metrics = as_list(await transport.get_account_metrics(account), "metrics")
        if metrics:
            m = metrics[0]
            print(
                f"[15] metrics: equity={m.get('equity')} balance={m.get('balance')} "
                f"openPL={m.get('openPL')} totalPL={m.get('totalPL')}"
            )
    finally:
        if not dry_run:
            print("[16] cleanup (flatten + cancel working orders)...")
            try:
                await flatten(transport, account)
            except Exception as exc:  # noqa: BLE001
                print(f"[16] cleanup error: {exc!r}")
        await transport.close()
        print("[17] transport closed")


if __name__ == "__main__":
    asyncio.run(main())
