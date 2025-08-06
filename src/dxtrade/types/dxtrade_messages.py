"""
DXTrade-specific WebSocket message types.

Provides models for DXTrade's proprietary WebSocket message format and protocols.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from .trading import Order, Position


class DXTradeMessageType(str, Enum):
    """DXTrade WebSocket message types."""
    PING_REQUEST = "PingRequest"
    PING_RESPONSE = "Ping"
    MARKET_DATA_SUBSCRIPTION_REQUEST = "MarketDataSubscriptionRequest"
    ACCOUNT_PORTFOLIOS_SUBSCRIPTION_REQUEST = "AccountPortfoliosSubscriptionRequest"
    MARKET_DATA = "MarketData"
    ACCOUNT_PORTFOLIOS = "AccountPortfolios"
    POSITION_UPDATE = "PositionUpdate"
    ORDER_UPDATE = "OrderUpdate"
    SUBSCRIPTION_RESPONSE = "SubscriptionResponse"
    ERROR_RESPONSE = "ErrorResponse"
    AUTHENTICATION_RESPONSE = "AuthenticationResponse"


class DXTradeWebSocketConfig(BaseModel):
    """DXTrade WebSocket configuration."""
    market_data_url: str = Field(..., description="Market data WebSocket URL")
    portfolio_url: str = Field(..., description="Portfolio WebSocket URL")
    account: str = Field(..., description="Account identifier")
    session_token: str = Field(..., description="Session authentication token")
    symbols: Optional[List[str]] = Field(None, description="Symbols to subscribe to")
    enable_ping_response: Optional[bool] = Field(True, description="Enable ping response")
    connection_timeout: Optional[int] = Field(None, description="Connection timeout")
    heartbeat_interval: Optional[int] = Field(None, description="Heartbeat interval")


class DXTradeStreamOptions(BaseModel):
    """DXTrade stream options."""
    symbols: Optional[List[str]] = Field(None, description="Symbols to subscribe to")
    account: Optional[str] = Field(None, description="Account identifier")
    enable_market_data: bool = Field(True, description="Enable market data stream")
    enable_portfolio: bool = Field(True, description="Enable portfolio stream")
    enable_ping_response: bool = Field(True, description="Enable ping response")
    connection_timeout: int = Field(30000, description="Connection timeout in milliseconds")
    heartbeat_interval: int = Field(30000, description="Heartbeat interval in milliseconds")
    max_reconnect_attempts: int = Field(5, description="Maximum reconnection attempts")
    reconnect_delay: int = Field(3000, description="Reconnect delay in milliseconds")
    auto_reconnect: bool = Field(True, description="Enable automatic reconnection")


class ConnectionStatus(BaseModel):
    """Connection status for a single WebSocket."""
    connected: bool = Field(False, description="Connection status")
    authenticated: bool = Field(False, description="Authentication status")
    subscribed: bool = Field(False, description="Subscription status")
    message_count: int = Field(0, description="Message count")
    reconnect_attempts: int = Field(0, description="Reconnection attempts")
    last_message_time: Optional[float] = Field(None, description="Last message timestamp")


class PingStats(BaseModel):
    """Ping/Pong statistics."""
    requests_received: int = Field(0, description="Ping requests received")
    responses_sent: int = Field(0, description="Ping responses sent")
    last_ping_time: Optional[float] = Field(None, description="Last ping timestamp")


class DXTradeConnectionStatus(BaseModel):
    """DXTrade connection status."""
    market_data: ConnectionStatus = Field(default_factory=ConnectionStatus)
    portfolio: ConnectionStatus = Field(default_factory=ConnectionStatus)
    ping_stats: PingStats = Field(default_factory=PingStats)
    is_ready: bool = Field(False, description="Overall ready status")


class DXTradeTestResult(BaseModel):
    """DXTrade stability test result."""
    success: bool = Field(..., description="Test success status")
    duration: float = Field(..., description="Test duration in seconds")
    message_count: int = Field(..., description="Total messages received")
    market_data_count: int = Field(..., description="Market data messages received")
    portfolio_count: int = Field(..., description="Portfolio messages received")
    ping_requests_received: int = Field(..., description="Ping requests received")
    ping_responses_sent: int = Field(..., description="Ping responses sent")
    connection_stable: bool = Field(..., description="Connection stability")
    error: Optional[str] = Field(None, description="Error message if any")


# Base message structure
class DXTradeWebSocketMessage(BaseModel):
    """Base DXTrade WebSocket message."""
    type: DXTradeMessageType = Field(..., description="Message type")


# Specific message types
class PingRequestMessage(DXTradeWebSocketMessage):
    """Ping request message from server."""
    type: DXTradeMessageType = Field(DXTradeMessageType.PING_REQUEST, description="Message type")
    timestamp: Optional[str] = Field(None, description="Ping timestamp")


class PingResponseMessage(DXTradeWebSocketMessage):
    """Ping response message to server."""
    type: DXTradeMessageType = Field(DXTradeMessageType.PING_RESPONSE, description="Message type")
    session: str = Field(..., description="Session token")
    timestamp: str = Field(..., description="Response timestamp")


class MarketDataSubscriptionRequest(DXTradeWebSocketMessage):
    """Market data subscription request."""
    type: DXTradeMessageType = Field(DXTradeMessageType.MARKET_DATA_SUBSCRIPTION_REQUEST, description="Message type")
    request_id: str = Field(..., description="Request identifier")
    session: str = Field(..., description="Session token")
    payload: Dict[str, Any] = Field(..., description="Subscription payload")


class AccountPortfoliosSubscriptionRequest(DXTradeWebSocketMessage):
    """Account portfolios subscription request."""
    type: DXTradeMessageType = Field(DXTradeMessageType.ACCOUNT_PORTFOLIOS_SUBSCRIPTION_REQUEST, description="Message type")
    request_id: str = Field(..., description="Request identifier")
    session: str = Field(..., description="Session token")
    payload: Dict[str, Any] = Field(..., description="Subscription payload")


class MarketDataMessage(DXTradeWebSocketMessage):
    """Market data update message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.MARKET_DATA, description="Message type")
    data: Dict[str, Any] = Field(..., description="Market data")


class AccountPortfoliosMessage(DXTradeWebSocketMessage):
    """Account portfolios update message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.ACCOUNT_PORTFOLIOS, description="Message type")
    data: Dict[str, Any] = Field(..., description="Portfolio data")


class DXTradePositionUpdateMessage(DXTradeWebSocketMessage):
    """Position update message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.POSITION_UPDATE, description="Message type")
    position: Position = Field(..., description="Updated position")


class DXTradeOrderUpdateMessage(DXTradeWebSocketMessage):
    """Order update message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.ORDER_UPDATE, description="Message type")
    order: Order = Field(..., description="Updated order")


class SubscriptionResponseMessage(DXTradeWebSocketMessage):
    """Subscription response message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.SUBSCRIPTION_RESPONSE, description="Message type")
    request_id: str = Field(..., description="Request identifier")
    success: bool = Field(..., description="Subscription success")
    message: Optional[str] = Field(None, description="Response message")


class ErrorResponseMessage(DXTradeWebSocketMessage):
    """Error response message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.ERROR_RESPONSE, description="Message type")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


class AuthenticationResponseMessage(DXTradeWebSocketMessage):
    """Authentication response message."""
    type: DXTradeMessageType = Field(DXTradeMessageType.AUTHENTICATION_RESPONSE, description="Message type")
    success: bool = Field(..., description="Authentication success")
    message: Optional[str] = Field(None, description="Response message")


# Callback type definitions
class DXTradeStreamCallbacks(BaseModel):
    """DXTrade stream callback functions."""
    model_config = {"arbitrary_types_allowed": True}
    
    on_connected: Optional[Callable[[str], None]] = Field(None, description="Connection callback")
    on_disconnected: Optional[Callable[[str, int, str], None]] = Field(None, description="Disconnection callback")
    on_error: Optional[Callable[[str, Exception], None]] = Field(None, description="Error callback")
    on_raw_message: Optional[Callable[[str, str], None]] = Field(None, description="Raw message callback")
    on_market_data: Optional[Callable[[MarketDataMessage], None]] = Field(None, description="Market data callback")
    on_account_portfolios: Optional[Callable[[AccountPortfoliosMessage], None]] = Field(None, description="Portfolio callback")
    on_position_update: Optional[Callable[[DXTradePositionUpdateMessage], None]] = Field(None, description="Position update callback")
    on_order_update: Optional[Callable[[DXTradeOrderUpdateMessage], None]] = Field(None, description="Order update callback")
    on_ping_request: Optional[Callable[[Any], None]] = Field(None, description="Ping request callback")
    on_subscription_response: Optional[Callable[[SubscriptionResponseMessage], None]] = Field(None, description="Subscription response callback")
    on_authentication_response: Optional[Callable[[AuthenticationResponseMessage], None]] = Field(None, description="Authentication response callback")
    on_reconnecting: Optional[Callable[[str, int], None]] = Field(None, description="Reconnecting callback")
    on_reconnected: Optional[Callable[[str], None]] = Field(None, description="Reconnected callback")