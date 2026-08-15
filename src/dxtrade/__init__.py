"""DXTrade Python SDK - Minimal transport and SDK for DXTrade APIs."""

__version__ = "1.0.0"

# Transport layer - core functionality that works
from .transport import DXTradeTransport, create_transport

# High-level capture class for streaming and trading
from .capture import Capture, QuoteStore

# Public API surface
__all__ = [
    "DXTradeTransport",
    "create_transport",
    "Capture",
    "QuoteStore",
    "__version__",
]