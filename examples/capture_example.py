#!/usr/bin/env python3
"""
Example: Using the Capture class for streaming and trading.

Usage:
    PYTHONPATH=src venv/Scripts/python.exe examples/capture_example.py
"""

import asyncio
from dxtrade import Capture

DEFAULT_SYMBOLS = ["CL", "NATGAS", "XAU", "XAG", "AAPL", "BABA", "AXTI", "AMD", "AMZN"]


async def main():
    async with Capture(
        symbols=DEFAULT_SYMBOLS,
        data_dir="data/quotes",
        write_parquet=True,
    ) as cap:
        await cap.subscribe()
        print("📡 Streaming quotes...")

        # Stream for 30 seconds
        await asyncio.sleep(30)

        # Query captured data
        print("\n🟦 Last prices:")
        print(cap.last_prices())

        # Save snapshot
        cap.to_parquet("data/quotes/snapshot.parquet")
        print("📦 Saved parquet snapshot")

        await cap.unsubscribe()
        print("⏹️  Done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
