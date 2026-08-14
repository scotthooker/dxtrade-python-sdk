#!/usr/bin/env python3
"""
Example: Stream real-time quotes using the high-level utils.

Usage:
    PYTHONPATH=src venv/Scripts/python.exe examples/stream_quotes.py
    PYTHONPATH=src venv/Scripts/python.exe examples/stream_quotes.py \
        --symbols BTCUSDT ETHUSDT --duration 15
"""

import argparse
import asyncio
import sys

# Windows consoles default to cp1252, which cannot encode the emoji used in
# the output; reconfigure stdout so printing never raises.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dxtrade import create_transport
from dxtrade.utils import stream_quotes


async def main() -> None:
    parser = argparse.ArgumentParser(description="Stream DXTrade quotes.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Symbols to stream (default: auto-discovered)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Stream duration in seconds (default: 30)",
    )
    args = parser.parse_args()

    transport = create_transport()
    try:

        def on_quote(event):
            print(
                f"📈 {event.get('symbol')}: bid={event.get('bid')} ask={event.get('ask')}"
            )

        events = await stream_quotes(
            transport,
            symbols=args.symbols,
            duration=args.duration,
            on_quote=on_quote,
        )
        print(f"✅ Streamed {len(events)} quote events in {args.duration}s")
    finally:
        await transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
        sys.exit(0)
