"""
Type definitions for DXTrade Python SDK.

This module provides comprehensive type definitions mirroring the TypeScript SDK
structure while maintaining Python conventions and type safety.
"""

from .common import *
from .trading import *
from .websocket import *
from .dxtrade_messages import *

__all__ = [
    # Common types
    "Environment",
    "AuthConfig",
    "SessionAuth",
    "BearerAuth", 
    "HmacAuth",
    "CredentialsAuth",
    "SDKConfig",
    "HTTPMethod",
    "RequestConfig",
    "ApiResponse",
    "BackoffConfig",
    "ClockSync",
    "RateLimiterState",
    
    # Trading types
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "TimeInForce",
    "PositionSide",
    "InstrumentType",
    "Account",
    "Instrument",
    "Quote",
    "OrderRequest",
    "Order",
    "Position",
    "Trade",
    "MarketDataRequest",
    "OrderBookEntry",
    "OrderBook",
    "Candlestick",
    
    # WebSocket types
    "ConnectionState",
    "MessageType",
    "SubscriptionType",
    "WebSocketConfig",
    "WebSocketMessage",
    "SubscriptionRequest",
    "UnsubscriptionRequest",
    "HeartbeatMessage",
    "AuthMessage",
    "ErrorMessage",
    "QuoteUpdateMessage",
    "OrderBookUpdateMessage",
    "TradeUpdateMessage",
    "OrderUpdateMessage",
    "PositionUpdateMessage",
    "AccountUpdateMessage",
    "SubscriptionState",
    
    # DXTrade-specific WebSocket types
    "DXTradeMessageType",
    "DXTradeWebSocketMessage",
    "DXTradeWebSocketConfig",
    "DXTradeStreamOptions",
    "DXTradeStreamCallbacks",
    "DXTradeConnectionStatus",
    "DXTradeTestResult",
    "PingRequestMessage",
    "PingResponseMessage",
    "MarketDataSubscriptionRequest",
    "AccountPortfoliosSubscriptionRequest",
    "MarketDataMessage",
    "AccountPortfoliosMessage",
    "DXTradePositionUpdateMessage",
    "DXTradeOrderUpdateMessage",
    "SubscriptionResponseMessage",
    "ErrorResponseMessage",
    "AuthenticationResponseMessage",
]