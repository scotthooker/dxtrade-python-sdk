# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-06

### Added
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

### Features
- **Authentication**: Secure login with session token management
- **REST API**: Complete coverage of DXTrade REST endpoints
  - Account management
  - Order placement and management
  - Position tracking
  - Market data retrieval
  - Instrument information
- **WebSocket Streaming**: Real-time data feeds
  - Market quotes
  - Order updates
  - Position changes
  - Portfolio updates
- **Transport Layer**: Raw data passthrough for integrations
  - Minimal overhead implementation
  - Direct WebSocket forwarding
  - Message broker integration support

### Technical Details
- Python 3.10+ support
- Async/await throughout
- Type hints for all public APIs
- Pydantic models for data validation
- Comprehensive error handling
- Environment-based configuration
- MIT licensed

## [0.9.0-beta] - 2025-01-01 (Pre-release)

### Added
- Beta version with core functionality
- Basic REST API implementation
- WebSocket connection management
- Initial transport layer design

### Changed
- Refactored authentication flow
- Improved error handling

### Fixed
- WebSocket ping/pong implementation
- Session token expiration handling
- Connection stability issues

## [0.1.0-alpha] - 2024-12-01 (Internal)

### Added
- Initial proof of concept
- Basic authentication
- Simple REST API calls
- Prototype WebSocket connection

---

## Version History Summary

- **1.0.0**: First stable public release with full SDK and transport layer
- **0.9.0-beta**: Feature-complete beta for testing
- **0.1.0-alpha**: Initial internal development version

## Upgrade Guide

### From 0.x to 1.0.0

The 1.0.0 release includes breaking changes from beta versions:

1. **Import changes**: 
   ```python
   # Old (beta)
   from dxtrade.client import Client
   
   # New (1.0.0)
   from dxtrade import DXTradeClient
   ```

2. **Configuration**: Environment variables now use `DXTRADE_` prefix consistently

3. **Async context managers**: All clients now support async context manager protocol

For detailed migration instructions, see the [Migration Guide](docs/MIGRATION.md).