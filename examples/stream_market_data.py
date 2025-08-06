#!/usr/bin/env python3
"""
Example: Stream real-time market data from DXTrade.

This example shows how to:
1. Authenticate with DXTrade
2. Connect to WebSocket market data feed
3. Subscribe to multiple symbols
4. Handle incoming quotes
"""

import asyncio
import logging
import os
from dxtrade import create_transport

logging.basicConfig(level=logging.INFO)

async def main():
    # Create transport instance
    transport = create_transport()
    
    # Define message handler
    def handle_quote(msg):
        if isinstance(msg, dict) and msg.get('type') == 'MarketData':
            events = msg.get('payload', {}).get('events', [])
            for event in events:
                symbol = event.get('symbol')
                bid = event.get('bid')
                ask = event.get('ask')
                if symbol and bid and ask:
                    print(f"📈 {symbol}: Bid={bid} Ask={ask}")
    
    # Use transport in context manager for automatic cleanup
    async with transport:
        # 1. Authenticate
        token = await transport.authenticate()
        print(f"✅ Authenticated")
        
        # 2. Connect WebSocket (uses env var or fallback)
        ws_url = os.getenv('DXTRADE_WS_MARKET_DATA_URL', 
                          'wss://your-broker.com/dxsca-web/md?format=JSON')
        await transport.subscribe("quotes", handle_quote, ws_url)
        print("✅ WebSocket connected")
        
        # 3. Subscribe to symbols
        account = os.getenv('DXTRADE_ACCOUNT', 'your-account')
        await transport.send_market_data_subscription(
            symbols=["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"],
            account=account
        )
        print("📡 Subscribed to market data")
        
        # 4. Stream for 30 seconds
        print("⏱️ Streaming for 30 seconds...")
        await asyncio.sleep(30)
        
        # Cleanup handled automatically by context manager
        print("✅ Done")

if __name__ == "__main__":
    asyncio.run(main())