# DXTrade Python SDK

[![Python Version](https://img.shields.io/pypi/pyversions/dxtrade-sdk)](https://pypi.org/project/dxtrade-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python SDK for the DXTrade trading platform, providing both high-level client functionality and low-level transport layer for building bridges and middleware.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Transport Layer for Bridges](#transport-layer-for-bridges)
- [API Reference](#api-reference)
- [Broker Configuration](#broker-configuration)
- [WebSocket Features](#websocket-features)
- [Error Handling](#error-handling)
- [Development](#development)
- [PyPI Publishing](#pypi-publishing)
- [Changelog](#changelog)
- [Support](#support)
- [License](#license)

## Features

### Core Features
- 🔐 **Session token authentication** with automatic renewal
- 📊 **Real-time market data streaming** via WebSocket
- 📈 **Portfolio updates** and position tracking
- 🔄 **Automatic ping/pong session management**
- 🌉 **Transport layer** for building bridges (RabbitMQ, Kafka, Redis)
- ⚡ **Async/await support** with modern Python
- 🛡️ **Robust error handling** and reconnection logic
- 🔧 **Environment-based configuration**

### WebSocket Features
- Real-time market quotes streaming
- Portfolio and position updates
- Order status updates
- Automatic session extension via ping/pong
- 4-tier connection fallback system for compatibility
- Multi-channel support for different data streams

### Transport Layer
- Minimal overhead (~200 lines vs 2000+ for full SDK)
- Raw data passthrough for maximum flexibility
- Direct WebSocket forwarding to message brokers
- Session token reuse across connections
- Perfect for building bridges to RabbitMQ, Kafka, Redis, etc.

## Installation

```bash
pip install dxtrade-sdk
```

### Requirements
- Python 3.10+
- aiohttp>=3.8.0
- websockets>=12.0
- python-dotenv>=1.0.0

## Quick Start

### Stream Market Data

```python
import asyncio
import os
from dxtrade import create_transport

async def main():
    transport = create_transport()
    
    def handle_quote(msg):
        if msg.get('type') == 'MarketData':
            events = msg.get('payload', {}).get('events', [])
            for event in events:
                symbol = event.get('symbol')
                bid = event.get('bid')
                ask = event.get('ask')
                print(f"📈 {symbol}: Bid={bid} Ask={ask}")
    
    async with transport:
        # Authenticate
        await transport.authenticate()
        print("✅ Authenticated")
        
        # Connect to market data WebSocket
        ws_url = os.getenv('DXTRADE_WS_MARKET_DATA_URL', 
                          'wss://your-broker.com/dxsca-web/md?format=JSON')
        await transport.subscribe("quotes", handle_quote, ws_url)
        print("✅ Connected to market data")
        
        # Subscribe to symbols
        account = os.getenv('DXTRADE_ACCOUNT', 'your-account')
        await transport.send_market_data_subscription(
            symbols=["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"],
            account=account
        )
        print("📡 Subscribed to symbols")
        
        # Stream for 60 seconds
        await asyncio.sleep(60)

asyncio.run(main())
```

## Configuration

### Environment Variables

Create a `.env` file in your project root:

```env
# ============================================================================
# REQUIRED: Authentication
# ============================================================================
DXTRADE_USERNAME=your_username
DXTRADE_PASSWORD=your_password

# ============================================================================
# REQUIRED: Server URLs
# ============================================================================
# Base URL for REST API
DXTRADE_BASE_URL=https://your-broker.com/dxsca-web

# WebSocket URL for market data streaming
DXTRADE_WS_MARKET_DATA_URL=wss://your-broker.com/dxsca-web/md?format=JSON

# WebSocket URL for portfolio/account updates
DXTRADE_WS_PORTFOLIO_URL=wss://your-broker.com/dxsca-web/ws?format=JSON

# ============================================================================
# OPTIONAL: Account Configuration
# ============================================================================
# Your DXTrade account identifier (e.g., "default:demo", "main:live")
DXTRADE_ACCOUNT=default:demo

# Account name suffix if not providing full account ID
DXTRADE_ACCOUNT_NAME=demo

# Domain prefix for account (defaults to "default")
DXTRADE_DOMAIN=default

# ============================================================================
# OPTIONAL: Connection Settings
# ============================================================================
# Request timeout in seconds (default: 30)
DXTRADE_TIMEOUT=30

# WebSocket ping interval in seconds (default: 45)
DXTRADE_WS_PING_INTERVAL=45

# ============================================================================
# OPTIONAL: Logging
# ============================================================================
# Log level (DEBUG, INFO, WARNING, ERROR)
DXTRADE_LOG_LEVEL=INFO
```

### Example Configurations

#### Demo Account
```env
DXTRADE_USERNAME=demo_user
DXTRADE_PASSWORD=demo_password
DXTRADE_BASE_URL=https://demo.your-broker.com/dxsca-web
DXTRADE_WS_MARKET_DATA_URL=wss://demo.your-broker.com/dxsca-web/md?format=JSON
DXTRADE_WS_PORTFOLIO_URL=wss://demo.your-broker.com/dxsca-web/ws?format=JSON
DXTRADE_ACCOUNT=default:demo
```

#### Live Account
```env
DXTRADE_USERNAME=live_user
DXTRADE_PASSWORD=live_password
DXTRADE_BASE_URL=https://trading.your-broker.com/dxsca-web
DXTRADE_WS_MARKET_DATA_URL=wss://trading.your-broker.com/dxsca-web/md?format=JSON
DXTRADE_WS_PORTFOLIO_URL=wss://trading.your-broker.com/dxsca-web/ws?format=JSON
DXTRADE_ACCOUNT=main:live
```

## Usage Examples

### Stream Market Data

See the [examples/stream_market_data.py](examples/stream_market_data.py) for a complete example.

### Build a Bridge to Message Queue

```python
import asyncio
import os
from dxtrade import create_transport

class DXTradeBridge:
    """Bridge DXTrade data to your message queue."""
    
    def __init__(self):
        self.transport = create_transport()
    
    async def forward_to_queue(self, message, channel):
        """Forward message to your message queue."""
        # Example: RabbitMQ
        # await rabbitmq_channel.publish(
        #     exchange='dxtrade',
        #     routing_key=channel,
        #     body=json.dumps(message)
        # )
        
        # Example: Kafka
        # await kafka_producer.send(f'dxtrade.{channel}', message)
        
        # Example: Redis
        # await redis_client.publish(f'dxtrade:{channel}', json.dumps(message))
        
        print(f"📤 Forward to {channel}: {message.get('type')}")
    
    async def run(self):
        async with self.transport:
            # Authenticate
            await self.transport.authenticate()
            print("✅ Authenticated with DXTrade")
            
            # Market data handler
            async def handle_market_data(msg):
                await self.forward_to_queue(msg, "market_data")
            
            # Portfolio handler
            async def handle_portfolio(msg):
                await self.forward_to_queue(msg, "portfolio")
            
            # Connect WebSockets
            ws_market = os.getenv('DXTRADE_WS_MARKET_DATA_URL')
            ws_portfolio = os.getenv('DXTRADE_WS_PORTFOLIO_URL')
            
            await self.transport.subscribe("quotes", handle_market_data, ws_market)
            await self.transport.subscribe("portfolio", handle_portfolio, ws_portfolio)
            
            # Subscribe to data
            account = os.getenv('DXTRADE_ACCOUNT')
            await self.transport.send_market_data_subscription(
                symbols=["EUR/USD", "GBP/USD"],
                account=account
            )
            
            await self.transport.send_portfolio_subscription(
                account=account
            )
            
            print("🌉 Bridge running - forwarding messages to queue")
            
            # Keep running
            while True:
                await asyncio.sleep(60)

# Run the bridge
bridge = DXTradeBridge()
asyncio.run(bridge.run())
```

## Transport Layer for Bridges

The SDK is specifically designed to work as a transport layer for building bridges to message queues and other systems.

### Why Use Transport Layer?

- **Minimal Overhead**: Lightweight implementation focused on data transport
- **Raw Data Access**: Direct access to DXTrade messages without abstraction
- **Flexible Integration**: Easy to integrate with any message queue or database
- **Session Reuse**: Efficient session token management across connections
- **Multi-Channel Support**: Handle different data streams simultaneously

### Bridge Architecture

```
DXTrade API → Transport Layer → Your Bridge → Message Queue
                                              ↓
                                         RabbitMQ/Kafka/Redis
                                              ↓
                                         Your Application
```

### Complete Bridge Example

See [examples/bridge_example.py](examples/bridge_example.py) for a full implementation.

## API Reference

### DXTradeTransport

The main transport class handles all communication with DXTrade.

#### Methods

```python
# Authentication
await transport.authenticate() -> str  # Returns session token

# WebSocket Subscriptions
await transport.subscribe(channel: str, callback: Callable, ws_url: str)
await transport.unsubscribe(channel: str)

# Market Data
await transport.send_market_data_subscription(
    symbols: list,
    account: str = None,
    event_types: list = None
)

# Portfolio
await transport.send_portfolio_subscription(
    account: str = None,
    event_types: list = None
)

# Generic Message
await transport.send_message(channel: str, message: dict)

# REST API (if endpoints are configured)
await transport.get_accounts()
await transport.get_positions()
await transport.get_orders()
```

### Message Types

#### Market Data Message
```json
{
    "type": "MarketData",
    "payload": {
        "events": [
            {
                "symbol": "EUR/USD",
                "bid": 1.1234,
                "ask": 1.1235,
                "timestamp": "2024-01-01T00:00:00Z"
            }
        ]
    }
}
```

#### Portfolio Message
```json
{
    "type": "AccountPortfolio",
    "payload": {
        "positions": [...],
        "orders": [...],
        "account": "your-account"
    }
}
```

#### Session Management (Automatic)
```json
// Server sends
{"type": "PingRequest"}

// SDK automatically responds
{"type": "Ping"}
```

## Broker Configuration

The SDK is **platform-agnostic** and works with any DXTrade broker through environment configuration.

### Supported Brokers

The SDK can work with any broker using the DXTrade platform. Simply configure the appropriate URLs in your environment variables.

### Custom Endpoints

If your broker uses non-standard endpoints, you can override them:

```env
# Custom API endpoints
DXTRADE_LOGIN_URL=https://your-broker.com/custom/login
DXTRADE_LOGOUT_URL=https://your-broker.com/custom/logout
DXTRADE_ACCOUNTS_URL=https://your-broker.com/api/accounts
DXTRADE_ORDERS_URL=https://your-broker.com/api/orders
DXTRADE_POSITIONS_URL=https://your-broker.com/api/positions
```

### Feature Flags

Enable or disable features based on your broker's capabilities:

```env
# Feature toggles
DXTRADE_FEATURE_WEBSOCKET=true
DXTRADE_FEATURE_AUTO_RECONNECT=true
DXTRADE_FEATURE_PING_PONG=true
```

## WebSocket Features

### Compatibility

The SDK includes a 4-tier fallback system for WebSocket connections to ensure compatibility across different websockets library versions:

1. `additional_headers` parameter (v12.0+)
2. `extra_headers` parameter (v10.0-11.x)
3. Subprotocol authentication (v9.0+)
4. Post-connection authentication (v8.0+)

### Automatic Session Management

The SDK automatically handles DXTrade's ping/pong session extension:
- Server sends `PingRequest` periodically
- SDK automatically responds with `Ping`
- Session stays active without manual intervention

### Multi-Channel Support

Connect to multiple WebSocket channels simultaneously:
- Market data channel for quotes
- Portfolio channel for account updates
- Custom channels for specific data streams

## Error Handling

The SDK includes comprehensive error handling:

- **Automatic Reconnection**: WebSocket disconnections trigger automatic reconnection
- **Session Renewal**: Expired sessions are automatically renewed
- **Graceful Degradation**: Falls back through multiple connection strategies
- **Detailed Logging**: Comprehensive logging for debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues and Solutions

#### Authentication Fails
- Verify `DXTRADE_USERNAME` and `DXTRADE_PASSWORD` are correct
- Check `DXTRADE_BASE_URL` points to the correct server
- Ensure your account has API access enabled

#### WebSocket Connection Issues
- Verify `DXTRADE_WS_MARKET_DATA_URL` is correct
- Check network connectivity and firewall settings
- Ensure WebSocket protocol is not blocked

#### No Market Data Received
- Verify market is open for the symbols you're subscribing to
- Check symbol names match your broker's format
- Ensure account has permissions for market data

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/dxtrade-sdk/dxtrade-python-sdk.git
cd dxtrade-python-sdk

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dxtrade

# Run specific test file
pytest tests/test_transport.py
```

### Code Quality

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/
```

## PyPI Publishing

### Prerequisites

1. Create accounts at [PyPI](https://pypi.org) and [TestPyPI](https://test.pypi.org)
2. Install build tools: `pip install build twine`
3. Generate API tokens from your PyPI account settings

### Publishing Process

1. **Update version** in `pyproject.toml` and `src/dxtrade/__init__.py`
2. **Update CHANGELOG.md** with release notes
3. **Build the package**:
   ```bash
   python -m build
   ```
4. **Test on TestPyPI**:
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```
5. **Publish to PyPI**:
   ```bash
   python -m twine upload dist/*
   ```

### Version Management

Follow semantic versioning:
- **Patch** (1.0.X): Bug fixes, minor updates
- **Minor** (1.X.0): New features, backward compatible
- **Major** (X.0.0): Breaking changes

## Changelog

### [1.0.0] - 2025-01-06

#### Added
- Initial public release of DXTrade Python SDK
- High-level SDK with full async/await support
- Type-safe operations using Pydantic models
- Comprehensive WebSocket streaming capabilities
- Transport layer for bridge/middleware integration
- Session management with automatic token refresh
- Rate limiting and exponential backoff retry logic
- Support for multiple DXTrade brokers
- Full test suite with pytest
- Comprehensive documentation and examples

#### Features
- **Authentication**: Secure login with session token management
- **REST API**: Complete coverage of DXTrade REST endpoints
- **WebSocket Streaming**: Real-time data feeds
- **Transport Layer**: Raw data passthrough for integrations

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

## Testing

The SDK has been tested with:
- DXTrade Platform
- Various WebSocket library versions (8.0-15.0)
- Python 3.10, 3.11, 3.12, 3.13

## Support

- 📧 Email: support@dxtrade-sdk.com
- 🐛 Issues: [GitHub Issues](https://github.com/dxtrade-sdk/dxtrade-python-sdk/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/dxtrade-sdk/dxtrade-python-sdk/discussions)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Security

- Never commit credentials to version control
- Use environment variables for all sensitive data
- Rotate API tokens regularly
- Report security issues privately via email

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Disclaimer

This SDK is not officially affiliated with or endorsed by DXTrade. Use at your own risk. Trading involves substantial risk of loss and is not suitable for every investor.

---

**Built with ❤️ for the trading community**