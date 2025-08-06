#!/usr/bin/env python3
"""
Example: Using DXTrade SDK as a transport layer for a bridge.

This example shows how to:
1. Use the transport layer for raw message passing
2. Forward messages to another system (e.g., RabbitMQ, Kafka, Redis)
3. Handle both REST and WebSocket data
"""

import asyncio
import json
import logging
import os
from dxtrade import create_transport

logging.basicConfig(level=logging.INFO)

class DXTradeBridge:
    """Example bridge that forwards DXTrade data to another system."""
    
    def __init__(self):
        self.transport = create_transport()
        self.message_count = 0
    
    async def forward_to_queue(self, message: dict, channel: str):
        """
        Forward message to your message queue system.
        Replace this with actual RabbitMQ, Kafka, Redis, etc.
        """
        self.message_count += 1
        
        # Example: Format for your queue system
        queue_message = {
            "source": "dxtrade",
            "channel": channel,
            "timestamp": message.get("timestamp"),
            "type": message.get("type"),
            "data": message
        }
        
        # TODO: Replace with actual queue publishing
        # await rabbitmq_channel.publish(queue_message)
        # await kafka_producer.send(topic, queue_message)
        # await redis_client.publish(channel, json.dumps(queue_message))
        
        if self.message_count <= 5:
            print(f"📤 Forwarding to queue: {message.get('type', 'Unknown')}")
    
    async def run(self):
        """Run the bridge."""
        async with self.transport:
            # Authenticate
            token = await self.transport.authenticate()
            print(f"✅ Authenticated with DXTrade")
            
            # Example 1: Forward REST API data
            positions = await self.transport.get_positions()
            if positions:
                await self.forward_to_queue(positions, "positions")
            
            # Example 2: Stream and forward WebSocket data
            
            # Market data handler
            async def handle_market_data(msg):
                if isinstance(msg, dict):
                    await self.forward_to_queue(msg, "market_data")
            
            # Portfolio handler
            async def handle_portfolio(msg):
                if isinstance(msg, dict):
                    await self.forward_to_queue(msg, "portfolio")
            
            # Connect to market data WebSocket
            ws_market = os.getenv('DXTRADE_WS_MARKET_DATA_URL',
                                 'wss://your-broker.com/dxsca-web/md?format=JSON')
            await self.transport.subscribe("quotes", handle_market_data, ws_market)
            
            # Connect to portfolio WebSocket
            ws_portfolio = os.getenv('DXTRADE_WS_PORTFOLIO_URL',
                                    'wss://your-broker.com/dxsca-web/ws?format=JSON')
            await self.transport.subscribe("portfolio", handle_portfolio, ws_portfolio)
            
            # Subscribe to data
            account = os.getenv('DXTRADE_ACCOUNT', 'your-account')
            await self.transport.send_market_data_subscription(
                symbols=["EUR/USD", "GBP/USD"],
                account=account
            )
            
            await self.transport.send_portfolio_subscription(
                account=account
            )
            
            print("🌉 Bridge running - forwarding messages to queue...")
            print("   Market Data → queue/market_data")
            print("   Portfolio → queue/portfolio")
            
            # Run for 60 seconds
            await asyncio.sleep(60)
            
            print(f"\n📊 Bridge Statistics:")
            print(f"   Messages forwarded: {self.message_count}")

async def main():
    bridge = DXTradeBridge()
    await bridge.run()

if __name__ == "__main__":
    asyncio.run(main())