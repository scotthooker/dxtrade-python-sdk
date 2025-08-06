"""
Trading-related type definitions for DXTrade SDK.

Provides models for accounts, instruments, orders, positions, and market data.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    OCO = "OCO"
    BRACKET = "BRACKET"
    TRAILING_STOP = "TRAILING_STOP"


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING_CANCEL = "PENDING_CANCEL"
    PENDING_REPLACE = "PENDING_REPLACE"


class TimeInForce(str, Enum):
    """Time in force enumeration."""
    GTC = "GTC"  # Good Till Canceled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    DAY = "DAY"  # Day order


class PositionSide(str, Enum):
    """Position side enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"


class InstrumentType(str, Enum):
    """Instrument type enumeration."""
    FOREX = "FOREX"
    CFD = "CFD"
    CRYPTO = "CRYPTO"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    STOCKS = "STOCKS"
    INDICES = "INDICES"
    COMMODITIES = "COMMODITIES"


class Account(BaseModel):
    """Account information."""
    account_id: str = Field(..., description="Account identifier")
    name: str = Field(..., description="Account name")
    type: str = Field(..., description="Account type")
    currency: str = Field(..., description="Account base currency")
    balance: Decimal = Field(..., description="Account balance")
    equity: Decimal = Field(..., description="Account equity")
    margin: Decimal = Field(..., description="Used margin")
    free_margin: Decimal = Field(..., description="Free margin")
    margin_level: Optional[Decimal] = Field(None, description="Margin level percentage")
    leverage: Decimal = Field(..., description="Account leverage")
    status: str = Field(..., description="Account status")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last update time")


class Instrument(BaseModel):
    """Instrument information."""
    symbol: str = Field(..., description="Instrument symbol")
    name: str = Field(..., description="Instrument name")
    type: InstrumentType = Field(..., description="Instrument type")
    base_currency: str = Field(..., description="Base currency")
    quote_currency: str = Field(..., description="Quote currency")
    pip_size: Decimal = Field(..., description="Pip size")
    min_size: Decimal = Field(..., description="Minimum position size")
    max_size: Decimal = Field(..., description="Maximum position size")
    step_size: Decimal = Field(..., description="Position size step")
    price_precision: int = Field(..., description="Price decimal places")
    volume_precision: int = Field(..., description="Volume decimal places")
    margin_rate: Decimal = Field(..., description="Margin rate")
    long_swap: Decimal = Field(..., description="Long position swap rate")
    short_swap: Decimal = Field(..., description="Short position swap rate")
    tradeable: bool = Field(..., description="Whether instrument is tradeable")
    market_hours: Optional[Dict[str, Any]] = Field(None, description="Market hours info")


class Quote(BaseModel):
    """Real-time quote information."""
    symbol: str = Field(..., description="Instrument symbol")
    bid: Decimal = Field(..., description="Bid price")
    ask: Decimal = Field(..., description="Ask price")
    spread: Decimal = Field(..., description="Bid-ask spread")
    timestamp: datetime = Field(..., description="Quote timestamp")
    volume: Optional[Decimal] = Field(None, description="Volume")


class OrderRequest(BaseModel):
    """Order request parameters."""
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Order side")
    type: OrderType = Field(..., description="Order type")
    volume: Decimal = Field(..., description="Order volume")
    price: Optional[Decimal] = Field(None, description="Limit price")
    stop_price: Optional[Decimal] = Field(None, description="Stop price")
    time_in_force: TimeInForce = Field(TimeInForce.GTC, description="Time in force")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    comment: Optional[str] = Field(None, description="Order comment")


class Order(BaseModel):
    """Order information."""
    order_id: str = Field(..., description="Order identifier")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Order side")
    type: OrderType = Field(..., description="Order type")
    status: OrderStatus = Field(..., description="Order status")
    volume: Decimal = Field(..., description="Order volume")
    filled_volume: Decimal = Field(..., description="Filled volume")
    remaining_volume: Decimal = Field(..., description="Remaining volume")
    price: Optional[Decimal] = Field(None, description="Order price")
    stop_price: Optional[Decimal] = Field(None, description="Stop price")
    average_fill_price: Optional[Decimal] = Field(None, description="Average fill price")
    time_in_force: TimeInForce = Field(..., description="Time in force")
    commission: Decimal = Field(..., description="Commission charged")
    swap: Decimal = Field(..., description="Swap charged")
    comment: Optional[str] = Field(None, description="Order comment")
    created_at: datetime = Field(..., description="Order creation time")
    updated_at: datetime = Field(..., description="Last update time")
    expires_at: Optional[datetime] = Field(None, description="Order expiration time")


class Position(BaseModel):
    """Position information."""
    position_id: str = Field(..., description="Position identifier")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: PositionSide = Field(..., description="Position side")
    volume: Decimal = Field(..., description="Position volume")
    open_price: Decimal = Field(..., description="Position open price")
    current_price: Decimal = Field(..., description="Current market price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")
    realized_pnl: Decimal = Field(..., description="Realized profit/loss")
    commission: Decimal = Field(..., description="Commission charged")
    swap: Decimal = Field(..., description="Swap charged")
    margin_used: Decimal = Field(..., description="Margin used")
    comment: Optional[str] = Field(None, description="Position comment")
    created_at: datetime = Field(..., description="Position creation time")
    updated_at: datetime = Field(..., description="Last update time")


class Trade(BaseModel):
    """Trade execution information."""
    trade_id: str = Field(..., description="Trade identifier")
    order_id: str = Field(..., description="Related order identifier")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Instrument symbol")
    side: OrderSide = Field(..., description="Trade side")
    volume: Decimal = Field(..., description="Trade volume")
    price: Decimal = Field(..., description="Trade price")
    commission: Decimal = Field(..., description="Commission charged")
    swap: Decimal = Field(..., description="Swap charged")
    profit: Decimal = Field(..., description="Trade profit/loss")
    comment: Optional[str] = Field(None, description="Trade comment")
    executed_at: datetime = Field(..., description="Trade execution time")


class MarketDataRequest(BaseModel):
    """Market data request parameters."""
    symbol: str = Field(..., description="Instrument symbol")
    from_date: Optional[datetime] = Field(None, description="Start date")
    to_date: Optional[datetime] = Field(None, description="End date")
    timeframe: Optional[str] = Field(None, description="Timeframe (M1, M5, H1, D1, etc.)")
    limit: Optional[int] = Field(None, description="Maximum number of records")


class OrderBookEntry(BaseModel):
    """Order book entry."""
    price: Decimal = Field(..., description="Price level")
    volume: Decimal = Field(..., description="Volume at price level")
    orders: int = Field(..., description="Number of orders at price level")


class OrderBook(BaseModel):
    """Order book information."""
    symbol: str = Field(..., description="Instrument symbol")
    bids: List[OrderBookEntry] = Field(..., description="Bid side entries")
    asks: List[OrderBookEntry] = Field(..., description="Ask side entries")
    timestamp: datetime = Field(..., description="Order book timestamp")


class Candlestick(BaseModel):
    """Candlestick/OHLC data."""
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Timeframe")
    timestamp: datetime = Field(..., description="Candle timestamp")
    open: Decimal = Field(..., description="Open price")
    high: Decimal = Field(..., description="High price")
    low: Decimal = Field(..., description="Low price")
    close: Decimal = Field(..., description="Close price")
    volume: Decimal = Field(..., description="Volume")
    tick_volume: Optional[Decimal] = Field(None, description="Tick volume")