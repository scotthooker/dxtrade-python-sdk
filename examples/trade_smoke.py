#!/usr/bin/env python3
"""
Example: Open and close a small position using the high-level utils.

Usage:
    # Dry run (discovery + sizing only, no order)
    PYTHONPATH=src venv/Scripts/python.exe examples/trade_smoke.py --dry-run

    # Open 0.001 BTC buy, hold 30s, close, verify flat
    PYTHONPATH=src venv/Scripts/python.exe examples/trade_smoke.py --symbol BTCUSDT

    # Open with a $10 stop loss, hold 60s, close
    PYTHONPATH=src venv/Scripts/python.exe examples/trade_smoke.py \
        --symbol BTCUSDT --stop-loss 10 --hold 60

WARNING: this trades real money on the account configured in .env.
"""

import argparse
import asyncio
import json
import sys

# Windows consoles default to cp1252, which cannot encode the emoji used in
# the output; reconfigure stdout so printing never raises.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dxtrade import create_transport
from dxtrade.utils import account_is_flat
from dxtrade.utils import close_position
from dxtrade.utils import flatten
from dxtrade.utils import open_position
from dxtrade.utils import resolve_account


async def main() -> None:
    parser = argparse.ArgumentParser(description="Open/close a small DXTrade position.")
    parser.add_argument(
        "--symbol", default="BTCUSDT", help="Symbol to trade (default: BTCUSDT)"
    )
    parser.add_argument("--side", default="BUY", choices=["BUY", "SELL"])
    parser.add_argument(
        "--quantity",
        type=float,
        default=None,
        help="Quantity (default: instrument minimum)",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=None,
        help="Max loss in account currency (optional)",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=30.0,
        help="Seconds to hold before closing (default: 30)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only discover and size; place no orders"
    )
    args = parser.parse_args()

    transport = create_transport()
    try:
        account = await resolve_account(transport)
        print(f"🔑 Account: {account}")

        if args.dry_run:
            print("🧪 DRY RUN — no orders will be placed")
        else:
            opened = await open_position(
                transport,
                symbol=args.symbol,
                side=args.side,
                quantity=args.quantity,
                stop_loss=args.stop_loss,
                account=account,
            )
            position = opened["position"]
            print(
                f"✅ Opened {position.get('side')} {position.get('symbol')} "
                f"qty={position.get('quantity')} @ {position.get('openPrice')} "
                f"(code {position.get('positionCode')})"
            )
            if opened["stop_order"]:
                print(f"🛑 Stop loss order placed: {json.dumps(opened['stop_order'])}")
            elif args.stop_loss:
                print("⚠️  Stop loss was requested but not confirmed")

            print(f"⏱️  Holding {args.hold}s...")
            await asyncio.sleep(args.hold)

            closed = await close_position(
                transport, account=account, position_code=position["positionCode"]
            )
            print(
                f"✅ Closed position {position['positionCode']}: {json.dumps(closed['order'])}"
            )

            await flatten(transport, account=account)
            flat = await account_is_flat(transport, account=account)
            print(f"✅ Account flat: {flat}")
            if not flat:
                print("❌ Account NOT flat — check positions/orders")
    finally:
        await transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
        sys.exit(0)
