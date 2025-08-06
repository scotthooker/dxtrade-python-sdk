# DXTrade SDK Examples

This directory contains examples demonstrating how to use the DXTrade Python SDK.

## Examples

### stream_market_data.py
Basic example showing how to:
- Authenticate with DXTrade
- Connect to WebSocket market data feed
- Subscribe to multiple symbols
- Handle incoming quotes in real-time

```bash
python stream_market_data.py
```

### bridge_example.py
Advanced example demonstrating:
- Using the SDK as a transport layer
- Building bridges to message queues (RabbitMQ, Kafka, Redis)
- Handling both market data and portfolio updates
- Forwarding messages to external systems

```bash
python bridge_example.py
```

## Prerequisites

1. Install the SDK:
```bash
pip install dxtrade-sdk
```

2. Create a `.env` file with your credentials:
```env
DXTRADE_USERNAME=your_username
DXTRADE_PASSWORD=your_password
DXTRADE_BASE_URL=https://your-broker.com/dxsca-web
DXTRADE_WS_MARKET_DATA_URL=wss://your-broker.com/dxsca-web/md?format=JSON
DXTRADE_WS_PORTFOLIO_URL=wss://your-broker.com/dxsca-web/ws?format=JSON
DXTRADE_ACCOUNT=your_account_id
```

## Running the Examples

Each example can be run independently:

```bash
# Stream market data
python examples/stream_market_data.py

# Run the bridge example
python examples/bridge_example.py
```

## Notes

- Replace `your-broker.com` with your actual DXTrade broker URL
- The account parameter should match your DXTrade account ID
- Market data streaming requires an active trading session
- Ensure your account has API access enabled

## Troubleshooting

### Authentication Issues
- Verify credentials in `.env` file
- Check account has API access enabled
- Ensure base URL is correct for your broker

### Connection Problems
- Verify network connectivity
- Check WebSocket URL configuration
- Review firewall/proxy settings

### No Data Received
- Ensure market is open
- Verify symbol names are correct
- Check account permissions

## Support

For issues or questions:
- Check the [main documentation](../README.md)
- Open an issue on [GitHub](https://github.com/dxtrade-sdk/dxtrade-python-sdk/issues)