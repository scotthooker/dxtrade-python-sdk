"""
WebSocket-related type definitions for DXTrade SDK.

Provides models for WebSocket connections, subscriptions, and real-time updates.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from .trading import Order, Position, Quote


class ConnectionState(str, Enum):
    """WebSocket connection state."""
    CONNECTING = "CONNECTING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class MessageType(str, Enum):
    """WebSocket message types."""
    AUTH = "AUTH"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"
    HEARTBEAT = "HEARTBEAT"
    QUOTE_UPDATE = "QUOTE_UPDATE"
    ORDER_UPDATE = "ORDER_UPDATE"
    POSITION_UPDATE = "POSITION_UPDATE"
    ACCOUNT_UPDATE = "ACCOUNT_UPDATE"
    ORDER_BOOK_UPDATE = "ORDER_BOOK_UPDATE"
    TRADE_UPDATE = "TRADE_UPDATE"
    ERROR = "ERROR"


class SubscriptionType(str, Enum):
    """WebSocket subscription types."""
    QUOTES = "QUOTES"
    ORDERS = "ORDERS"
    POSITIONS = "POSITIONS"
    ACCOUNTS = "ACCOUNTS"
    ORDER_BOOK = "ORDER_BOOK"
    TRADES = "TRADES"
    MARKET_DATA = "MARKET_DATA"
    PORTFOLIO = "PORTFOLIO"


class WebSocketConfig(BaseModel):
    """WebSocket connection configuration."""
    url: str = Field(..., description="WebSocket URL")
    heartbeat_interval: int = Field(30000, description="Heartbeat interval in milliseconds")
    reconnect_delay: int = Field(1000, description="Initial reconnect delay in milliseconds")
    max_reconnect_delay: int = Field(30000, description="Maximum reconnect delay in milliseconds")
    max_reconnect_attempts: int = Field(5, description="Maximum reconnection attempts")
    ping_timeout: int = Field(10000, description="Ping timeout in milliseconds")
    pong_timeout: int = Field(5000, description="Pong timeout in milliseconds")
    max_queue_size: int = Field(1000, description="Maximum message queue size")
    enable_backfill: bool = Field(True, description="Enable data backfill")
    backfill_limit: int = Field(100, description="Backfill data limit")


class WebSocketMessage(BaseModel):
    """Base WebSocket message."""
    type: MessageType = Field(..., description="Message type")
    timestamp: datetime = Field(..., description="Message timestamp")
    data: Optional[Dict[str, Any]] = Field(None, description="Message data")


class SubscriptionRequest(BaseModel):
    """WebSocket subscription request."""
    type: SubscriptionType = Field(..., description="Subscription type")
    symbols: Optional[List[str]] = Field(None, description="Symbol list for subscription")
    params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")


class UnsubscriptionRequest(BaseModel):
    """WebSocket unsubscription request."""
    type: SubscriptionType = Field(..., description="Subscription type")
    symbols: Optional[List[str]] = Field(None, description="Symbol list for unsubscription")


class HeartbeatMessage(BaseModel):
    """WebSocket heartbeat message."""
    type: MessageType = Field(MessageType.HEARTBEAT, description="Message type")
    timestamp: datetime = Field(..., description="Heartbeat timestamp")
    ping: bool = Field(False, description="Is ping message")


class AuthMessage(BaseModel):
    """WebSocket authentication message."""
    type: MessageType = Field(MessageType.AUTH, description="Message type")
    token: str = Field(..., description="Authentication token")
    timestamp: datetime = Field(..., description="Authentication timestamp")


class ErrorMessage(BaseModel):
    """WebSocket error message."""
    type: MessageType = Field(MessageType.ERROR, description="Message type")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(..., description="Error timestamp")


class QuoteUpdateMessage(BaseModel):
    """Quote update message."""
    type: MessageType = Field(MessageType.QUOTE_UPDATE, description="Message type")
    quote: Quote = Field(..., description="Updated quote")
    timestamp: datetime = Field(..., description="Update timestamp")


class OrderBookUpdateMessage(BaseModel):
    """Order book update message."""
    type: MessageType = Field(MessageType.ORDER_BOOK_UPDATE, description="Message type")
    symbol: str = Field(..., description="Symbol")
    bids: List[Dict[str, Any]] = Field(..., description="Bid updates")
    asks: List[Dict[str, Any]] = Field(..., description="Ask updates")
    timestamp: datetime = Field(..., description="Update timestamp")


class TradeUpdateMessage(BaseModel):
    """Trade update message."""
    type: MessageType = Field(MessageType.TRADE_UPDATE, description="Message type")
    symbol: str = Field(..., description="Symbol")
    price: float = Field(..., description="Trade price")
    volume: float = Field(..., description="Trade volume")
    side: str = Field(..., description="Trade side")
    timestamp: datetime = Field(..., description="Trade timestamp")


class OrderUpdateMessage(BaseModel):
    """Order update message."""
    type: MessageType = Field(MessageType.ORDER_UPDATE, description="Message type")
    order: Order = Field(..., description="Updated order")
    timestamp: datetime = Field(..., description="Update timestamp")


class PositionUpdateMessage(BaseModel):
    """Position update message."""
    type: MessageType = Field(MessageType.POSITION_UPDATE, description="Message type")
    position: Position = Field(..., description="Updated position")
    timestamp: datetime = Field(..., description="Update timestamp")


class AccountUpdateMessage(BaseModel):
    """Account update message."""
    type: MessageType = Field(MessageType.ACCOUNT_UPDATE, description="Message type")
    account_id: str = Field(..., description="Account ID")
    balance: float = Field(..., description="Account balance")
    equity: float = Field(..., description="Account equity")
    margin: float = Field(..., description="Used margin")
    free_margin: float = Field(..., description="Free margin")
    timestamp: datetime = Field(..., description="Update timestamp")


class SubscriptionState(BaseModel):
    """WebSocket subscription state."""
    type: SubscriptionType = Field(..., description="Subscription type")
    symbols: List[str] = Field(..., description="Subscribed symbols")
    active: bool = Field(..., description="Subscription active status")
    last_update: Optional[datetime] = Field(None, description="Last update timestamp")


# Type aliases for callback functions
MessageCallback = Callable[[WebSocketMessage], None]
ErrorCallback = Callable[[Exception], None]
ConnectionCallback = Callable[[ConnectionState], None]
QuoteCallback = Callable[[Quote], None]
OrderCallback = Callable[[Order], None]
PositionCallback = Callable[[Position], None]