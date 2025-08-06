"""DXTrade Python SDK - Minimal transport and SDK for DXTrade APIs."""

__version__ = "1.0.0"

# Transport layer - core functionality that works
from .transport import DXTradeTransport, create_transport

# Basic exports for now
__all__ = [
    "DXTradeTransport",
    "create_transport",
    "__version__",
]