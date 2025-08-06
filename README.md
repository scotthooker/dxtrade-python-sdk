# DXtrade Python SDK

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Production-ready Python SDK for DXtrade's REST and WebSocket APIs with asyncio-first design.

## ✨ Features

- **🚀 Asyncio-first design** - Built for high-performance async applications
- **🔐 Multiple auth methods** - Bearer token, HMAC, and session authentication
- **🔄 Auto-reconnecting WebSocket** - Reliable real-time data streaming with backoff
- **⚡ Smart retry logic** - Exponential backoff with full jitter
- **🛡️ Rate limiting** - Built-in rate limiting with Retry-After support
- **🔑 Idempotency keys** - Automatic idempotency for safe retries
- **⏰ Clock drift detection** - Automatic server time synchronization
- **📊 Comprehensive models** - Fully typed Pydantic models for all API entities
- **🧪 Extensive testing** - 90%+ test coverage with integration tests
- **📖 Rich documentation** - Comprehensive examples and API reference

## 📦 Installation

```bash
pip install dxtrade
```

For development features:
```bash
pip install "dxtrade[dev]"
```

## 🚀 Quick Start

### Basic REST API Usage

```python
import asyncio
from dxtrade import DXtradeClient

async def main():
    # Create client with bearer token
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here"
    )
    
    async with client:
        # Get server time
        server_time = await client.get_server_time()
        print(f"Server time: {server_time.timestamp}")
        
        # Get accounts
        accounts = await client.accounts.get_accounts()
        print(f"Found {len(accounts)} accounts")
        
        # Get current prices
        prices = await client.get_current_prices(["EURUSD", "GBPUSD"])
        for price in prices:
            print(f"{price.symbol}: {price.bid}/{price.ask}")
        
        # Create a market order
        order = await client.create_market_order(
            symbol="EURUSD",
            side="buy", 
            volume=0.01
        )
        print(f"Created order: {order.order_id}")

asyncio.run(main())
```

### WebSocket Streaming

```python
import asyncio
from dxtrade import DXtradeClient
from dxtrade.models import EventType, PriceEvent

async def main():
    client = DXtradeClient.create_with_bearer_token(
        base_url="https://api.dxtrade.com",
        token="your_bearer_token_here",
        websocket_url="wss://push.dxtrade.com/v1/stream"
    )
    
    async with client:
        # Connect to WebSocket
        await client.push.connect()
        
        # Subscribe to price updates
        subscription_id = await client.push.subscribe_prices(["EURUSD", "GBPUSD"])
        
        # Handle price events
        def on_price_update(event: PriceEvent):
            price = event.data
            print(f"{price.symbol}: {price.bid}/{price.ask}")
        
        client.push.on(EventType.PRICE, on_price_update)
        
        # Stream for 30 seconds
        await asyncio.sleep(30)

asyncio.run(main())
```

## 🔐 Authentication Methods

### Bearer Token
```python
client = DXtradeClient.create_with_bearer_token(
    base_url="https://api.dxtrade.com",
    token="your_bearer_token"
)
```

### HMAC Authentication
```python
client = DXtradeClient.create_with_hmac(
    base_url="https://api.dxtrade.com",
    api_key="your_api_key",
    secret_key="your_secret_key",
    passphrase="your_passphrase"  # Optional
)
```

### Session Authentication
```python
client = DXtradeClient.create_with_session(
    base_url="https://api.dxtrade.com", 
    username="your_username",
    password="your_password"
)
```

## 📈 Trading Operations

### Market Orders
```python
# Market buy order
order = await client.create_market_order(
    symbol="EURUSD",
    side="buy",
    volume=0.1,
    stop_loss=1.0800,  # Optional
    take_profit=1.0900  # Optional
)
```

### Limit Orders
```python
# Limit sell order
order = await client.create_limit_order(
    symbol="EURUSD", 
    side="sell",
    volume=0.1,
    price=1.0850,
    time_in_force="gtc"
)
```

### Advanced Order Types
```python
from dxtrade.models import OCOOrderRequest, BracketOrderRequest

# One-Cancels-Other order
oco = OCOOrderRequest(
    symbol="EURUSD",
    side="buy",
    volume=0.1,
    price=1.0850,      # Limit price
    stop_price=1.0800  # Stop price
)
orders = await client.orders.create_oco_order(oco)

# Bracket order (Entry + Stop Loss + Take Profit)
bracket = BracketOrderRequest(
    symbol="EURUSD",
    side="buy", 
    volume=0.1,
    price=1.0825,       # Entry
    stop_loss=1.0800,   # Stop loss
    take_profit=1.0900  # Take profit
)
orders = await client.orders.create_bracket_order(bracket)
```

## 📊 Market Data

### Real-time Prices
```python
# Get current prices
price = await client.instruments.get_price("EURUSD")
print(f"EURUSD: {price.bid}/{price.ask}")

# Get multiple prices
prices = await client.instruments.get_prices(["EURUSD", "GBPUSD", "USDJPY"])
```

### Historical Data
```python
from datetime import datetime, timedelta

# Get candle data
end_time = datetime.utcnow()
start_time = end_time - timedelta(hours=24)

candles = await client.instruments.get_candles(
    symbol="EURUSD",
    interval="1h", 
    start=start_time,
    end=end_time,
    limit=24
)

# Get tick data
ticks = await client.instruments.get_ticks(
    symbol="EURUSD",
    limit=1000
)
```

### Instrument Information
```python
# Get all instruments
instruments = await client.instruments.get_instruments(
    instrument_type="forex",
    enabled_only=True
)

# Get specific instrument
eurusd = await client.instruments.get_instrument("EURUSD")
print(f"Min volume: {eurusd.min_volume}")
print(f"Tick size: {eurusd.tick_size}")
```

## 🔄 WebSocket Streaming

### Price Streaming
```python
# Subscribe to specific symbols
price_sub = await client.push.subscribe_prices(["EURUSD", "GBPUSD"])

# Subscribe to all prices
all_prices_sub = await client.push.subscribe_prices()

# Handle events
def on_price(event: PriceEvent):
    price = event.data
    print(f"{price.symbol}: {price.bid}/{price.ask}")

client.push.on(EventType.PRICE, on_price)
```

### Account Monitoring
```python
# Subscribe to account updates
account_sub = await client.push.subscribe_account("account_id")
order_sub = await client.push.subscribe_orders("account_id") 
position_sub = await client.push.subscribe_positions("account_id")

# Handle different event types
client.push.on(EventType.ACCOUNT, handle_account_update)
client.push.on(EventType.ORDER, handle_order_update)
client.push.on(EventType.POSITION, handle_position_update)
```

### Event Iterator
```python
# Process events with async iterator
async for event in client.push.events():
    if event.type == EventType.PRICE:
        handle_price(event.data)
    elif event.type == EventType.ORDER:
        handle_order(event.data)
```

## ⚙️ Configuration

### HTTP Configuration
```python
from dxtrade.models import ClientConfig, HTTPConfig, BearerTokenCredentials, AuthType

config = ClientConfig(
    http=HTTPConfig(
        base_url="https://api.dxtrade.com",
        timeout=60.0,
        max_retries=5,
        retry_backoff_factor=0.5,
        rate_limit=20,  # requests per second
        user_agent="MyApp/1.0.0"
    ),
    auth_type=AuthType.BEARER_TOKEN,
    credentials=BearerTokenCredentials(token="your_token"),
    clock_drift_threshold=30.0,
    enable_idempotency=True
)

client = DXtradeClient(config=config)
```

### WebSocket Configuration
```python
client = DXtradeClient(
    base_url="https://api.dxtrade.com",
    websocket_url="wss://push.dxtrade.com/v1/stream",
    auth_type=AuthType.BEARER_TOKEN,
    credentials=credentials,
    # WebSocket specific settings
    websocket_max_retries=10,
    websocket_retry_backoff_factor=1.0,
    heartbeat_interval=30.0,
    max_message_size=1024*1024
)
```

## 🛡️ Error Handling

```python
from dxtrade.errors import (
    DXtradeError, DXtradeHTTPError, DXtradeRateLimitError,
    DXtradeTimeoutError, DXtradeAuthenticationError
)

try:
    order = await client.create_market_order("EURUSD", "buy", 0.1)
    
except DXtradeAuthenticationError as e:
    print(f"Auth failed: {e}")
    
except DXtradeRateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
    
except DXtradeTimeoutError as e:
    print(f"Request timeout: {e.timeout}s")
    
except DXtradeHTTPError as e:
    print(f"HTTP {e.status_code}: {e.error_code}")
    
except DXtradeError as e:
    print(f"General error: {e}")
```

## 🧪 Testing

Run the test suite:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest --cov=dxtrade --cov-report=html

# Run specific test categories
pytest -m "unit"          # Unit tests only
pytest -m "integration"   # Integration tests only
pytest -m "not slow"      # Skip slow tests
```

## 🛠️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/dxtrade/python-sdk.git
cd python-sdk

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Quality Tools

```bash
# Format code
black src tests
ruff check --fix src tests

# Type checking
mypy src

# Run all quality checks
ruff check src tests
black --check src tests
mypy src
```

## 📚 API Reference

### Main Client
- `DXtradeClient` - Main client class with unified interface
- `DXtradeClient.create_with_bearer_token()` - Bearer token factory
- `DXtradeClient.create_with_hmac()` - HMAC factory
- `DXtradeClient.create_with_session()` - Session factory

### REST APIs
- `client.accounts` - Account management and balances
- `client.instruments` - Instrument data and market info
- `client.orders` - Order management and trade history
- `client.positions` - Position management

### WebSocket API
- `client.push` - WebSocket streaming client
- `client.push.subscribe_prices()` - Price updates
- `client.push.subscribe_orders()` - Order updates
- `client.push.subscribe_positions()` - Position updates
- `client.push.subscribe_account()` - Account updates

### Models
All API entities are represented as typed Pydantic models:
- `Account`, `Balance` - Account information
- `Instrument`, `Price`, `Tick`, `Candle` - Market data
- `Order`, `Trade` - Trading entities
- `Position` - Position information
- Event models for WebSocket streaming

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run quality checks (`ruff check`, `mypy`, `pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

- 📖 [Documentation](https://dxtrade-python-sdk.readthedocs.io/)
- 🐛 [Issue Tracker](https://github.com/dxtrade/python-sdk/issues)
- 💬 [Discussions](https://github.com/dxtrade/python-sdk/discussions)
- 📧 Email: support@dxtrade.com

## ⭐ Star History

If this SDK helps you, please consider starring the repository!

---

Built with ❤️ by the DXtrade team