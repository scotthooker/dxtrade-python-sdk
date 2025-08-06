"""WebSocket streaming examples for DXtrade Python SDK."""

import asyncio
from typing import List

from dxtrade import DXtradeClient
from dxtrade.models import AccountEvent
from dxtrade.models import EventType
from dxtrade.models import OrderEvent
from dxtrade.models import PositionEvent
from dxtrade.models import PriceEvent


async def basic_price_streaming():
    """Basic price streaming example."""
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    async with client:
        # Connect to WebSocket
        await client.push.connect()
        
        # Subscribe to price updates for specific symbols
        price_subscription = await client.push.subscribe_prices(["EURUSD", "GBPUSD", "USDJPY"])
        print(f"Subscribed to prices with ID: {price_subscription}")
        
        # Set up event handler
        def on_price_update(event: PriceEvent) -> None:
            price = event.data
            spread = float(price.ask) - float(price.bid)
            print(f"{price.symbol}: {price.bid}/{price.ask} (spread: {spread:.5f})")
        
        # Register the handler
        client.push.on(EventType.PRICE, on_price_update)
        
        # Stream for 30 seconds
        print("Streaming prices for 30 seconds...")
        await asyncio.sleep(30)
        
        # Unsubscribe
        await client.push.unsubscribe(price_subscription)
        print("Unsubscribed from price updates")


async def account_monitoring():
    """Monitor account, order, and position updates."""
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    async with client:
        # Get account ID
        accounts = await client.accounts.get_accounts()
        if not accounts:
            print("No accounts found")
            return
        
        account_id = accounts[0].account_id
        print(f"Monitoring account: {account_id}")
        
        # Connect to WebSocket
        await client.push.connect()
        
        # Subscribe to account updates
        account_sub = await client.push.subscribe_account(account_id)
        order_sub = await client.push.subscribe_orders(account_id)
        position_sub = await client.push.subscribe_positions(account_id)
        
        # Event handlers
        async def on_account_update(event: AccountEvent) -> None:
            account = event.data
            print(f"Account Update - Balance: {account.balance}, Equity: {account.equity}")
        
        async def on_order_update(event: OrderEvent) -> None:
            order = event.data
            print(f"Order Update - {order.order_id}: {order.status} ({order.symbol} {order.side} {order.volume})")
        
        async def on_position_update(event: PositionEvent) -> None:
            position = event.data
            print(f"Position Update - {position.symbol}: P&L {position.unrealized_pnl}")
        
        # Register handlers
        client.push.on(EventType.ACCOUNT, on_account_update)
        client.push.on(EventType.ORDER, on_order_update)
        client.push.on(EventType.POSITION, on_position_update)
        
        # Monitor for 60 seconds
        print("Monitoring account activity for 60 seconds...")
        await asyncio.sleep(60)
        
        # Cleanup
        await client.push.unsubscribe(account_sub)
        await client.push.unsubscribe(order_sub)
        await client.push.unsubscribe(position_sub)


async def event_iterator_example():
    """Use the async event iterator."""
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    async with client:
        # Connect and subscribe
        await client.push.connect()
        await client.push.subscribe_prices(["EURUSD", "GBPUSD"])
        
        # Use async iterator to process events
        print("Processing events with async iterator...")
        
        event_count = 0
        async for event in client.push.events():
            if event.type == EventType.PRICE:
                price_event: PriceEvent = event
                price = price_event.data
                print(f"Received price update: {price.symbol} = {price.bid}/{price.ask}")
            
            elif event.type == EventType.HEARTBEAT:
                print("♥ Heartbeat received")
            
            event_count += 1
            if event_count >= 50:  # Stop after 50 events
                break
        
        print(f"Processed {event_count} events")


async def advanced_streaming_with_reconnection():
    """Demonstrate advanced streaming with automatic reconnection."""
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream",
        # WebSocket specific configuration
        websocket_max_retries=10,  # More retry attempts
        websocket_retry_backoff_factor=1.0,  # Longer backoff
        heartbeat_interval=15.0,  # More frequent heartbeats
    )
    
    # Track connection state
    connection_count = 0
    message_count = 0
    
    def on_price_update(event: PriceEvent) -> None:
        nonlocal message_count
        message_count += 1
        
        if message_count % 100 == 0:  # Log every 100th message
            price = event.data
            print(f"Message #{message_count}: {price.symbol} = {price.bid}/{price.ask}")
    
    async with client:
        # Monitor connection status
        original_connect = client.push.connect
        
        async def monitored_connect():
            nonlocal connection_count
            connection_count += 1
            print(f"WebSocket connection attempt #{connection_count}")
            return await original_connect()
        
        client.push.connect = monitored_connect
        
        # Connect and subscribe
        await client.push.connect()
        await client.push.subscribe_prices()  # Subscribe to all prices
        
        # Register handler
        client.push.on(EventType.PRICE, on_price_update)
        
        # Stream for a longer period to test reconnection
        print("Streaming with auto-reconnection for 5 minutes...")
        print("Try disconnecting your network to test reconnection...")
        
        await asyncio.sleep(300)  # 5 minutes
        
        print(f"Streaming completed:")
        print(f"- Total connections: {connection_count}")
        print(f"- Messages received: {message_count}")


async def multi_symbol_analysis():
    """Advanced example: Multi-symbol price analysis."""
    
    class PriceAnalyzer:
        def __init__(self, symbols: List[str], window_size: int = 20):
            self.symbols = symbols
            self.window_size = window_size
            self.price_history = {symbol: [] for symbol in symbols}
            self.stats = {symbol: {} for symbol in symbols}
        
        def update_price(self, symbol: str, bid: float, ask: float):
            if symbol not in self.price_history:
                return
            
            mid_price = (bid + ask) / 2
            self.price_history[symbol].append(mid_price)
            
            # Keep only recent prices
            if len(self.price_history[symbol]) > self.window_size:
                self.price_history[symbol] = self.price_history[symbol][-self.window_size:]
            
            # Calculate statistics
            prices = self.price_history[symbol]
            if len(prices) >= 2:
                self.stats[symbol] = {
                    'avg': sum(prices) / len(prices),
                    'min': min(prices),
                    'max': max(prices),
                    'change': prices[-1] - prices[0] if len(prices) > 1 else 0,
                    'volatility': self._calculate_volatility(prices)
                }
        
        def _calculate_volatility(self, prices: List[float]) -> float:
            if len(prices) < 2:
                return 0.0
            
            changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            avg_change = sum(changes) / len(changes)
            variance = sum((change - avg_change) ** 2 for change in changes) / len(changes)
            return variance ** 0.5
        
        def print_stats(self):
            print("\n=== Price Analysis ===")
            for symbol, stats in self.stats.items():
                if stats:
                    print(f"{symbol}: Avg={stats['avg']:.5f}, "
                          f"Change={stats['change']:+.5f}, "
                          f"Vol={stats['volatility']:.5f}")
    
    # Initialize client and analyzer
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]
    analyzer = PriceAnalyzer(symbols, window_size=50)
    
    def on_price_update(event: PriceEvent) -> None:
        price = event.data
        analyzer.update_price(
            price.symbol,
            float(price.bid),
            float(price.ask)
        )
    
    async with client:
        # Connect and subscribe
        await client.push.connect()
        await client.push.subscribe_prices(symbols)
        
        # Register handler
        client.push.on(EventType.PRICE, on_price_update)
        
        print(f"Analyzing prices for {symbols}")
        print("Collecting data for analysis...")
        
        # Collect data and print stats periodically
        for i in range(12):  # 2 minutes total
            await asyncio.sleep(10)
            analyzer.print_stats()
        
        print("\nAnalysis complete!")


async def error_handling_and_monitoring():
    """Demonstrate WebSocket error handling and monitoring."""
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    # Connection monitoring
    connection_events = []
    error_count = 0
    
    def on_price_update(event: PriceEvent) -> None:
        # Simulate some processing that might fail
        try:
            price = event.data
            # Your price processing logic here
            pass
        except Exception as e:
            nonlocal error_count
            error_count += 1
            print(f"Error processing price update: {e}")
    
    async with client:
        try:
            # Monitor connection attempts
            original_handle_reconnect = client.push._handle_reconnect
            
            async def monitored_reconnect():
                connection_events.append("reconnect_attempt")
                print("Attempting to reconnect...")
                return await original_handle_reconnect()
            
            client.push._handle_reconnect = monitored_reconnect
            
            # Connect and subscribe
            await client.push.connect()
            connection_events.append("connected")
            
            await client.push.subscribe_prices(["EURUSD"])
            
            # Register handler
            client.push.on(EventType.PRICE, on_price_update)
            
            # Monitor for connection health
            print("Monitoring WebSocket connection health...")
            
            for i in range(30):  # 30 seconds
                await asyncio.sleep(1)
                
                if client.push.connected:
                    if i % 10 == 0:
                        print(f"Connection healthy at {i}s")
                else:
                    print("Connection lost, waiting for reconnection...")
            
            print(f"\nMonitoring summary:")
            print(f"- Connection events: {connection_events}")
            print(f"- Processing errors: {error_count}")
            
        except Exception as e:
            print(f"WebSocket error: {e}")


if __name__ == "__main__":
    # Choose which example to run
    print("=== DXtrade WebSocket Streaming Examples ===\n")
    
    print("1. Basic Price Streaming")
    asyncio.run(basic_price_streaming())
    
    # Uncomment to run other examples
    # print("\n2. Account Monitoring")
    # asyncio.run(account_monitoring())
    
    # print("\n3. Event Iterator")
    # asyncio.run(event_iterator_example())
    
    # print("\n4. Advanced Streaming with Reconnection")
    # asyncio.run(advanced_streaming_with_reconnection())
    
    # print("\n5. Multi-Symbol Analysis")
    # asyncio.run(multi_symbol_analysis())
    
    # print("\n6. Error Handling and Monitoring")
    # asyncio.run(error_handling_and_monitoring())