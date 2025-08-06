"""Basic usage examples for DXtrade Python SDK."""

import asyncio
from decimal import Decimal

from dxtrade import DXtradeClient
from dxtrade.models import OrderSide
from dxtrade.models import OrderType
from dxtrade.models import TimeInForce


async def basic_client_usage():
    """Demonstrate basic client usage with different auth methods."""
    
    # Create client with bearer token
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    async with client:
        # Get server time
        server_time = await client.get_server_time()
        print(f"Server time: {server_time.timestamp}")
        
        # Get accounts
        accounts = await client.accounts.get_accounts()
        print(f"Found {len(accounts)} accounts")
        
        if accounts:
            account_id = accounts[0].account_id
            
            # Get account summary
            summary = await client.get_account_summary(account_id)
            print(f"Account balance: {summary}")
            
            # Get current prices
            prices = await client.get_current_prices(["EURUSD", "GBPUSD"])
            for price in prices:
                print(f"{price.symbol}: {price.bid}/{price.ask}")


async def hmac_authentication():
    """Demonstrate HMAC authentication."""
    
    client = DXtradeClient.create_with_hmac(
        base_url="https://api.dxtrade.com",
        api_key="your_api_key",
        secret_key="your_secret_key",
        passphrase="your_passphrase"  # Optional
    )
    
    async with client:
        # Get instruments
        instruments = await client.instruments.get_instruments(
            instrument_type="forex",
            enabled_only=True
        )
        print(f"Found {len(instruments)} forex instruments")


async def session_authentication():
    """Demonstrate session authentication."""
    
    client = DXtradeClient.create_with_session(
        base_url="https://api.dxtrade.com",
        username="your_username",
        password="your_password"
    )
    
    async with client:
        # Session will be established automatically on first request
        accounts = await client.accounts.get_accounts()
        print(f"Logged in, found {len(accounts)} accounts")


async def trading_operations():
    """Demonstrate trading operations."""
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here"
    )
    
    async with client:
        # Get instruments
        eurusd = await client.instruments.get_instrument("EURUSD")
        print(f"EURUSD info: {eurusd.name}, min volume: {eurusd.min_volume}")
        
        # Get current price
        price = await client.instruments.get_price("EURUSD")
        print(f"EURUSD price: {price.bid}/{price.ask}")
        
        # Create a market buy order
        order = await client.create_market_order(
            symbol="EURUSD",
            side="buy",
            volume=0.01,  # Minimum lot size
            stop_loss=float(price.bid) - 0.0050,  # 50 pips stop loss
            take_profit=float(price.ask) + 0.0100,  # 100 pips take profit
        )
        print(f"Created order: {order.order_id}")
        
        # Create a limit sell order
        limit_order = await client.create_limit_order(
            symbol="EURUSD",
            side="sell",
            volume=0.01,
            price=float(price.ask) + 0.0020,  # 20 pips above current price
            time_in_force=TimeInForce.GTC,
            client_order_id="my_custom_id_123"
        )
        print(f"Created limit order: {limit_order.order_id}")
        
        # Get open orders
        open_orders = await client.get_open_orders()
        print(f"Open orders: {len(open_orders.data)}")
        
        # Get positions
        positions = await client.get_open_positions()
        print(f"Open positions: {len(positions.data)}")
        
        # Cancel the limit order
        cancelled_order = await client.orders.cancel_order(limit_order.order_id)
        print(f"Cancelled order: {cancelled_order.order_id}")


async def advanced_order_types():
    """Demonstrate advanced order types."""
    from dxtrade.models import BracketOrderRequest, OCOOrderRequest
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here"
    )
    
    async with client:
        # OCO Order (One-Cancels-Other)
        oco_order = OCOOrderRequest(
            symbol="EURUSD",
            side=OrderSide.BUY,
            volume=Decimal("0.1"),
            price=Decimal("1.0850"),  # Buy limit
            stop_price=Decimal("1.0800"),  # Buy stop
        )
        
        oco_orders = await client.orders.create_oco_order(oco_order)
        print(f"Created OCO orders: {[o.order_id for o in oco_orders]}")
        
        # Bracket Order (Entry + Stop Loss + Take Profit)
        bracket_order = BracketOrderRequest(
            symbol="GBPUSD",
            side=OrderSide.BUY,
            volume=Decimal("0.1"),
            price=Decimal("1.2500"),  # Entry price
            stop_loss=Decimal("1.2450"),  # Stop loss
            take_profit=Decimal("1.2600"),  # Take profit
        )
        
        bracket_orders = await client.orders.create_bracket_order(bracket_order)
        print(f"Created bracket orders: {[o.order_id for o in bracket_orders]}")


async def market_data_analysis():
    """Demonstrate market data retrieval and analysis."""
    from datetime import datetime, timedelta
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here"
    )
    
    async with client:
        symbol = "EURUSD"
        
        # Get historical candles (last 24 hours, 1-hour intervals)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        candles = await client.instruments.get_candles(
            symbol=symbol,
            interval="1h",
            start=start_time,
            end=end_time,
            limit=24
        )
        
        print(f"Retrieved {len(candles)} hourly candles for {symbol}")
        
        # Calculate simple statistics
        if candles:
            prices = [float(candle.close) for candle in candles]
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            print(f"24h stats - Avg: {avg_price:.5f}, Min: {min_price:.5f}, Max: {max_price:.5f}")
        
        # Get recent tick data
        ticks = await client.instruments.get_ticks(
            symbol=symbol,
            limit=100
        )
        print(f"Retrieved {len(ticks)} recent ticks for {symbol}")
        
        # Check market status
        market_status = await client.instruments.get_market_status(symbol)
        print(f"Market status for {symbol}: {market_status}")


async def error_handling_example():
    """Demonstrate error handling best practices."""
    from dxtrade.errors import (
        DXtradeError, DXtradeHTTPError, DXtradeRateLimitError,
        DXtradeTimeoutError, DXtradeAuthenticationError
    )
    
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="invalid_token"  # This will cause auth errors
    )
    
    async with client:
        try:
            # This will likely fail with authentication error
            accounts = await client.accounts.get_accounts()
            print(f"Success: {len(accounts)} accounts")
            
        except DXtradeAuthenticationError as e:
            print(f"Authentication failed: {e}")
            print(f"Error code: {e.error_code}")
            
        except DXtradeRateLimitError as e:
            print(f"Rate limited: {e}")
            print(f"Retry after: {e.retry_after} seconds")
            
        except DXtradeTimeoutError as e:
            print(f"Request timeout: {e}")
            print(f"Timeout duration: {e.timeout} seconds")
            
        except DXtradeHTTPError as e:
            print(f"HTTP error {e.status_code}: {e}")
            print(f"Response: {e.response_text}")
            
        except DXtradeError as e:
            print(f"General DXtrade error: {e}")
            print(f"Details: {e.details}")
            
        except Exception as e:
            print(f"Unexpected error: {e}")


async def configuration_examples():
    """Demonstrate different configuration options."""
    from dxtrade.models import ClientConfig, HTTPConfig, BearerTokenCredentials, AuthType
    
    # Custom HTTP configuration
    http_config = HTTPConfig(
        base_url="https://api.dxtrade.com",
        timeout=60.0,  # 60 second timeout
        max_retries=5,  # More aggressive retries
        retry_backoff_factor=0.5,  # Longer backoff
        rate_limit=20,  # 20 requests per second
        user_agent="MyTradingApp/2.0.0"
    )
    
    # Custom client configuration
    config = ClientConfig(
        http=http_config,
        auth_type=AuthType.BEARER_TOKEN,
        credentials=BearerTokenCredentials(token="your_token"),
        clock_drift_threshold=60.0,  # Allow 60s clock drift
        enable_idempotency=True  # Enable idempotency keys
    )
    
    client = DXtradeClient(config=config)
    
    async with client:
        # Client will use custom configuration
        server_time = await client.get_server_time()
        print(f"Server time with custom config: {server_time.timestamp}")


if __name__ == "__main__":
    # Run basic usage example
    print("=== Basic Client Usage ===")
    asyncio.run(basic_client_usage())
    
    # Uncomment to run other examples
    # print("\n=== HMAC Authentication ===")
    # asyncio.run(hmac_authentication())
    
    # print("\n=== Trading Operations ===")
    # asyncio.run(trading_operations())
    
    # print("\n=== Advanced Orders ===")
    # asyncio.run(advanced_order_types())
    
    # print("\n=== Market Data ===")
    # asyncio.run(market_data_analysis())
    
    # print("\n=== Error Handling ===")
    # asyncio.run(error_handling_example())
    
    # print("\n=== Custom Configuration ===")
    # asyncio.run(configuration_examples())