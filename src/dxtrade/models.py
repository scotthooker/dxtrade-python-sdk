"""Pydantic models for DXtrade API entities."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import Union

from pydantic import BaseModel
from pydantic import Field
from pydantic import ConfigDict


class DXtradeBaseModel(BaseModel):
    """Base model with common configuration."""
    
    model_config = ConfigDict(
        # Use enum values instead of enum objects
        use_enum_values=True,
        # Validate field assignment
        validate_assignment=True,
        # Allow population by field name and alias
        populate_by_name=True,
        # Forbid extra fields unless explicitly allowed
        extra="forbid",
        # Use arbitrary types like Decimal
        arbitrary_types_allowed=True,
    )


# ============================================================================
# Enums
# ============================================================================

class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    OCO = "oco"  # One-Cancels-Other
    BRACKET = "bracket"


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """Time in force enumeration."""
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    DAY = "day"  # Good for Day


class PositionSide(str, Enum):
    """Position side enumeration."""
    LONG = "long"
    SHORT = "short"


class InstrumentType(str, Enum):
    """Instrument type enumeration."""
    FOREX = "forex"
    CFD = "cfd"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"
    STOCK = "stock"


class MarketStatus(str, Enum):
    """Market status enumeration."""
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    POST_MARKET = "post_market"


class EventType(str, Enum):
    """Push API event type enumeration."""
    PRICE = "price"
    ORDER = "order"
    POSITION = "position"
    ACCOUNT = "account"
    HEARTBEAT = "heartbeat"


class AuthType(str, Enum):
    """Authentication type enumeration."""
    BEARER_TOKEN = "bearer_token"
    HMAC = "hmac"
    SESSION = "session"


# ============================================================================
# Authentication Models
# ============================================================================

class Credentials(DXtradeBaseModel):
    """Base credentials model."""
    pass


class BearerTokenCredentials(Credentials):
    """Bearer token authentication credentials."""
    token: str = Field(..., description="Bearer token")


class HMACCredentials(Credentials):
    """HMAC authentication credentials."""
    api_key: str = Field(..., description="API key")
    secret_key: str = Field(..., description="Secret key", repr=False)
    passphrase: Optional[str] = Field(None, description="Passphrase", repr=False)


class SessionCredentials(Credentials):
    """Session-based authentication credentials."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password", repr=False)
    session_token: Optional[str] = Field(None, description="Session token")


# ============================================================================
# Account Models
# ============================================================================

class Balance(DXtradeBaseModel):
    """Account balance information."""
    currency: str = Field(..., description="Currency code")
    balance: Decimal = Field(..., description="Current balance")
    available: Decimal = Field(..., description="Available balance")
    used: Decimal = Field(..., description="Used balance") 
    reserved: Decimal = Field(..., description="Reserved balance")


class Account(DXtradeBaseModel):
    """Account information."""
    account_id: str = Field(..., description="Unique account identifier")
    account_name: str = Field(..., description="Account display name")
    account_type: str = Field(..., description="Account type")
    currency: str = Field(..., description="Base currency")
    balance: Decimal = Field(..., description="Account balance")
    equity: Decimal = Field(..., description="Account equity")
    margin: Decimal = Field(..., description="Used margin")
    free_margin: Decimal = Field(..., description="Free margin")
    margin_level: Optional[Decimal] = Field(None, description="Margin level percentage")
    balances: List[Balance] = Field(default_factory=list, description="Multi-currency balances")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ============================================================================
# Instrument Models
# ============================================================================

class TradingHours(DXtradeBaseModel):
    """Trading hours information."""
    timezone: str = Field(..., description="Timezone")
    monday: List[str] = Field(default_factory=list, description="Monday trading hours")
    tuesday: List[str] = Field(default_factory=list, description="Tuesday trading hours")
    wednesday: List[str] = Field(default_factory=list, description="Wednesday trading hours")
    thursday: List[str] = Field(default_factory=list, description="Thursday trading hours")
    friday: List[str] = Field(default_factory=list, description="Friday trading hours")
    saturday: List[str] = Field(default_factory=list, description="Saturday trading hours")
    sunday: List[str] = Field(default_factory=list, description="Sunday trading hours")


class Instrument(DXtradeBaseModel):
    """Financial instrument information."""
    symbol: str = Field(..., description="Instrument symbol")
    name: str = Field(..., description="Instrument display name")
    type: InstrumentType = Field(..., description="Instrument type")
    base_currency: Optional[str] = Field(None, description="Base currency")
    quote_currency: Optional[str] = Field(None, description="Quote currency")
    tick_size: Decimal = Field(..., description="Minimum price increment")
    tick_value: Decimal = Field(..., description="Value per tick")
    contract_size: Decimal = Field(..., description="Contract size")
    min_volume: Decimal = Field(..., description="Minimum order volume")
    max_volume: Decimal = Field(..., description="Maximum order volume")
    volume_step: Decimal = Field(..., description="Volume increment")
    margin_rate: Decimal = Field(..., description="Margin requirement rate")
    swap_long: Optional[Decimal] = Field(None, description="Swap rate for long positions")
    swap_short: Optional[Decimal] = Field(None, description="Swap rate for short positions")
    trading_hours: Optional[TradingHours] = Field(None, description="Trading hours")
    market_status: MarketStatus = Field(..., description="Current market status")
    digits: int = Field(..., description="Number of decimal places")
    enabled: bool = Field(True, description="Whether trading is enabled")


class Price(DXtradeBaseModel):
    """Price information."""
    symbol: str = Field(..., description="Instrument symbol")
    bid: Decimal = Field(..., description="Bid price")
    ask: Decimal = Field(..., description="Ask price")
    spread: Decimal = Field(..., description="Bid-ask spread")
    timestamp: datetime = Field(..., description="Price timestamp")


class Tick(DXtradeBaseModel):
    """Tick data."""
    symbol: str = Field(..., description="Instrument symbol")
    bid: Decimal = Field(..., description="Bid price")
    ask: Decimal = Field(..., description="Ask price")
    volume: Optional[Decimal] = Field(None, description="Volume")
    timestamp: datetime = Field(..., description="Tick timestamp")


class Candle(DXtradeBaseModel):
    """OHLCV candle data."""
    symbol: str = Field(..., description="Instrument symbol")
    timestamp: datetime = Field(..., description="Candle timestamp")
    open: Decimal = Field(..., description="Open price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Close price")
    volume: Decimal = Field(..., description="Volume")


# ============================================================================
# Order Models
# ============================================================================

class OrderRequest(DXtradeBaseModel):
    """Order creation/modification request."""
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Order side")
    type: OrderType = Field(..., description="Order type")
    volume: Decimal = Field(..., description="Order volume")
    price: Optional[Decimal] = Field(None, description="Limit price")
    stop_price: Optional[Decimal] = Field(None, description="Stop price")
    time_in_force: TimeInForce = Field(TimeInForce.GTC, description="Time in force")
    stop_loss: Optional[Decimal] = Field(None, description="Stop loss price")
    take_profit: Optional[Decimal] = Field(None, description="Take profit price")
    client_order_id: Optional[str] = Field(None, description="Client-provided order ID")
    comment: Optional[str] = Field(None, description="Order comment")


class OCOOrderRequest(DXtradeBaseModel):
    """One-Cancels-Other order request."""
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Order side")
    volume: Decimal = Field(..., description="Order volume")
    price: Decimal = Field(..., description="Limit price")
    stop_price: Decimal = Field(..., description="Stop price")
    time_in_force: TimeInForce = Field(TimeInForce.GTC, description="Time in force")
    client_order_id: Optional[str] = Field(None, description="Client-provided order ID")
    comment: Optional[str] = Field(None, description="Order comment")


class BracketOrderRequest(DXtradeBaseModel):
    """Bracket order request."""
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Order side")
    volume: Decimal = Field(..., description="Order volume")
    price: Optional[Decimal] = Field(None, description="Entry price")
    stop_loss: Decimal = Field(..., description="Stop loss price")
    take_profit: Decimal = Field(..., description="Take profit price")
    time_in_force: TimeInForce = Field(TimeInForce.GTC, description="Time in force")
    client_order_id: Optional[str] = Field(None, description="Client-provided order ID")
    comment: Optional[str] = Field(None, description="Order comment")


class Order(DXtradeBaseModel):
    """Order information."""
    order_id: str = Field(..., description="Unique order identifier")
    client_order_id: Optional[str] = Field(None, description="Client-provided order ID")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Order side")
    type: OrderType = Field(..., description="Order type")
    status: OrderStatus = Field(..., description="Order status")
    volume: Decimal = Field(..., description="Order volume")
    filled_volume: Decimal = Field(Decimal("0"), description="Filled volume")
    remaining_volume: Decimal = Field(..., description="Remaining volume")
    price: Optional[Decimal] = Field(None, description="Order price")
    stop_price: Optional[Decimal] = Field(None, description="Stop price")
    avg_fill_price: Optional[Decimal] = Field(None, description="Average fill price")
    time_in_force: TimeInForce = Field(..., description="Time in force")
    stop_loss: Optional[Decimal] = Field(None, description="Stop loss price")
    take_profit: Optional[Decimal] = Field(None, description="Take profit price")
    comment: Optional[str] = Field(None, description="Order comment")
    created_at: datetime = Field(..., description="Order creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    expires_at: Optional[datetime] = Field(None, description="Order expiration timestamp")


# ============================================================================
# Position Models
# ============================================================================

class Position(DXtradeBaseModel):
    """Position information."""
    position_id: str = Field(..., description="Unique position identifier")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: PositionSide = Field(..., description="Position side")
    volume: Decimal = Field(..., description="Position volume")
    entry_price: Decimal = Field(..., description="Average entry price")
    current_price: Decimal = Field(..., description="Current market price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")
    realized_pnl: Decimal = Field(..., description="Realized profit/loss")
    swap: Decimal = Field(Decimal("0"), description="Swap/rollover charges")
    commission: Decimal = Field(Decimal("0"), description="Commission charges")
    margin: Decimal = Field(..., description="Used margin")
    comment: Optional[str] = Field(None, description="Position comment")
    opened_at: datetime = Field(..., description="Position open timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ============================================================================
# Trade Models
# ============================================================================

class Trade(DXtradeBaseModel):
    """Trade execution information."""
    trade_id: str = Field(..., description="Unique trade identifier")
    order_id: str = Field(..., description="Associated order identifier")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Trade side")
    volume: Decimal = Field(..., description="Trade volume")
    price: Decimal = Field(..., description="Execution price")
    commission: Decimal = Field(Decimal("0"), description="Commission charged")
    swap: Decimal = Field(Decimal("0"), description="Swap charged")
    comment: Optional[str] = Field(None, description="Trade comment")
    executed_at: datetime = Field(..., description="Execution timestamp")


# ============================================================================
# Push API Event Models
# ============================================================================

class PushEvent(DXtradeBaseModel):
    """Base push API event."""
    type: EventType = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Event data")


class PriceEvent(PushEvent):
    """Price update event."""
    type: Literal[EventType.PRICE] = Field(EventType.PRICE, description="Event type")
    data: Price = Field(..., description="Price data")


class OrderEvent(PushEvent):
    """Order update event."""
    type: Literal[EventType.ORDER] = Field(EventType.ORDER, description="Event type")
    data: Order = Field(..., description="Order data")


class PositionEvent(PushEvent):
    """Position update event."""
    type: Literal[EventType.POSITION] = Field(EventType.POSITION, description="Event type")
    data: Position = Field(..., description="Position data")


class AccountEvent(PushEvent):
    """Account update event."""
    type: Literal[EventType.ACCOUNT] = Field(EventType.ACCOUNT, description="Event type")
    data: Account = Field(..., description="Account data")


class HeartbeatEvent(PushEvent):
    """Heartbeat event."""
    type: Literal[EventType.HEARTBEAT] = Field(EventType.HEARTBEAT, description="Event type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Heartbeat data")


# ============================================================================
# API Response Models
# ============================================================================

class APIResponse(DXtradeBaseModel):
    """Generic API response."""
    success: bool = Field(..., description="Request success status")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(..., description="Response timestamp")


class ErrorResponse(APIResponse):
    """API error response."""
    success: Literal[False] = Field(False, description="Request success status")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")


class DataResponse(APIResponse):
    """API data response."""
    success: Literal[True] = Field(True, description="Request success status")
    data: Any = Field(..., description="Response data")


class PaginatedResponse(DataResponse):
    """Paginated API response."""
    data: List[Any] = Field(..., description="Response data")
    pagination: Dict[str, Union[int, str, None]] = Field(..., description="Pagination info")


# ============================================================================
# Configuration Models
# ============================================================================

class HTTPConfig(DXtradeBaseModel):
    """HTTP client configuration."""
    base_url: str = Field(..., description="Base API URL")
    timeout: float = Field(30.0, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    retry_backoff_factor: float = Field(0.3, description="Retry backoff factor")
    rate_limit: Optional[int] = Field(None, description="Rate limit (requests per second)")
    user_agent: str = Field("dxtrade-python-sdk/1.0.0", description="User agent string")


class WebSocketConfig(DXtradeBaseModel):
    """WebSocket client configuration."""
    url: str = Field(..., description="WebSocket URL")
    max_retries: int = Field(5, description="Maximum reconnection attempts")
    retry_backoff_factor: float = Field(0.5, description="Reconnection backoff factor")
    heartbeat_interval: float = Field(30.0, description="Heartbeat interval in seconds")
    max_message_size: int = Field(1024 * 1024, description="Maximum message size in bytes")
    ping_interval: Optional[float] = Field(20.0, description="Ping interval in seconds")
    ping_timeout: Optional[float] = Field(10.0, description="Ping timeout in seconds")


class ClientConfig(DXtradeBaseModel):
    """DXtrade client configuration."""
    http: HTTPConfig = Field(..., description="HTTP configuration")
    websocket: Optional[WebSocketConfig] = Field(None, description="WebSocket configuration")
    auth_type: AuthType = Field(..., description="Authentication type")
    credentials: Credentials = Field(..., description="Authentication credentials")
    clock_drift_threshold: float = Field(30.0, description="Clock drift threshold in seconds")
    enable_idempotency: bool = Field(True, description="Enable idempotency keys")


# ============================================================================
# Utility Models
# ============================================================================

class Subscription(DXtradeBaseModel):
    """Push API subscription."""
    id: str = Field(..., description="Subscription ID")
    event_type: EventType = Field(..., description="Event type")
    symbol: Optional[str] = Field(None, description="Symbol filter")
    account_id: Optional[str] = Field(None, description="Account filter")
    active: bool = Field(True, description="Subscription status")


class RateLimitInfo(DXtradeBaseModel):
    """Rate limit information."""
    limit: int = Field(..., description="Rate limit")
    remaining: int = Field(..., description="Remaining requests")
    reset: datetime = Field(..., description="Reset timestamp")
    retry_after: Optional[int] = Field(None, description="Retry after seconds")


class ServerTime(DXtradeBaseModel):
    """Server time information."""
    timestamp: datetime = Field(..., description="Server timestamp")
    timezone: str = Field(..., description="Server timezone")


# Union types for convenience
AnyOrder = Union[Order, OCOOrderRequest, BracketOrderRequest]
AnyEvent = Union[PriceEvent, OrderEvent, PositionEvent, AccountEvent, HeartbeatEvent]
AnyCredentials = Union[BearerTokenCredentials, HMACCredentials, SessionCredentials]