"""
Common type definitions for DXTrade SDK.

Provides base types, configuration models, and shared data structures used
throughout the SDK.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Environment(str, Enum):
    """Environment types for API endpoints."""
    DEMO = "demo"
    LIVE = "live"


class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


# Authentication Configuration
class SessionAuth(BaseModel):
    """Session-based authentication configuration."""
    type: Literal["session"] = "session"
    token: str = Field(..., description="Session token for authentication")


class BearerAuth(BaseModel):
    """Bearer token authentication configuration."""
    type: Literal["bearer"] = "bearer"
    token: str = Field(..., description="Bearer token for authentication")


class HmacAuth(BaseModel):
    """HMAC authentication configuration."""
    type: Literal["hmac"] = "hmac"
    api_key: str = Field(..., description="API key for HMAC authentication")
    secret: str = Field(..., description="Secret key for HMAC authentication")


class CredentialsAuth(BaseModel):
    """Username/password authentication configuration."""
    type: Literal["credentials"] = "credentials"
    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="Password for authentication")
    domain: Optional[str] = Field(None, description="Optional domain for authentication")


# Union type for all authentication configurations
AuthConfig = Union[SessionAuth, BearerAuth, HmacAuth, CredentialsAuth]


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    requests: int = Field(100, ge=1, description="Maximum requests per window")
    window: int = Field(60000, ge=1000, description="Time window in milliseconds")


class FeaturesConfig(BaseModel):
    """Features configuration."""
    clock_sync: bool = Field(True, description="Enable clock synchronization")
    websocket: bool = Field(True, description="Enable WebSocket connections")
    auto_reconnect: bool = Field(True, description="Enable automatic reconnection")


class URLsConfig(BaseModel):
    """Explicit URL configuration (preferred method)."""
    # Authentication URLs
    login: Optional[str] = Field(None, description="Login endpoint URL")
    logout: Optional[str] = Field(None, description="Logout endpoint URL")
    refresh_token: Optional[str] = Field(None, description="Token refresh endpoint URL")
    
    # Market Data URLs
    quotes: Optional[str] = Field(None, description="Quotes endpoint URL")
    candles: Optional[str] = Field(None, description="Candles endpoint URL")
    instruments: Optional[str] = Field(None, description="Instruments endpoint URL")
    market_data: Optional[str] = Field(None, description="Market data endpoint URL")
    
    # Account & Portfolio URLs
    account: Optional[str] = Field(None, description="Account endpoint URL")
    accounts: Optional[str] = Field(None, description="Accounts endpoint URL")
    portfolio: Optional[str] = Field(None, description="Portfolio endpoint URL")
    balance: Optional[str] = Field(None, description="Balance endpoint URL")
    metrics: Optional[str] = Field(None, description="Metrics endpoint URL")
    positions: Optional[str] = Field(None, description="Positions endpoint URL")
    
    # Trading URLs
    orders: Optional[str] = Field(None, description="Orders endpoint URL")
    orders_history: Optional[str] = Field(None, description="Order history endpoint URL")
    trades: Optional[str] = Field(None, description="Trades endpoint URL")
    history: Optional[str] = Field(None, description="History endpoint URL")
    
    # System URLs
    time: Optional[str] = Field(None, description="Time endpoint URL")
    status: Optional[str] = Field(None, description="Status endpoint URL")
    version: Optional[str] = Field(None, description="Version endpoint URL")
    conversion_rates: Optional[str] = Field(None, description="Conversion rates endpoint URL")
    
    # WebSocket endpoints
    ws_market_data: Optional[str] = Field(None, description="Market data WebSocket URL")
    ws_portfolio: Optional[str] = Field(None, description="Portfolio WebSocket URL")


class EndpointsConfig(BaseModel):
    """Legacy endpoint paths configuration (fallback)."""
    login: str = Field("/login", description="Login endpoint path")
    market_data: str = Field("/marketdata", description="Market data endpoint path")
    time: str = Field("/time", description="Time endpoint path")
    account: str = Field("/account", description="Account endpoint path")
    ws_market_data: str = Field("/md", description="Market data WebSocket path")
    ws_portfolio: str = Field("/?format=JSON", description="Portfolio WebSocket path")


class WebSocketConfig(BaseModel):
    """Legacy WebSocket configuration (fallback)."""
    base_url: Optional[str] = Field(None, description="WebSocket base URL")
    market_data_path: str = Field("/md", description="Market data WebSocket path")
    portfolio_path: str = Field("/?format=JSON", description="Portfolio WebSocket path")
    ping_interval: Optional[int] = Field(None, description="Ping interval in milliseconds")
    reconnect_attempts: Optional[int] = Field(None, description="Number of reconnect attempts")
    reconnect_delay: Optional[int] = Field(None, description="Reconnect delay in milliseconds")


class SDKConfig(BaseModel):
    """Main SDK configuration."""
    model_config = ConfigDict(extra="allow")
    
    environment: Environment = Field(Environment.DEMO, description="Environment (demo/live)")
    auth: AuthConfig = Field(..., description="Authentication configuration")
    base_url: Optional[str] = Field(None, description="Base API URL")
    timeout: int = Field(30000, ge=1000, le=60000, description="Request timeout in milliseconds")
    retries: int = Field(3, ge=0, le=10, description="Number of retry attempts")
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    urls: URLsConfig = Field(default_factory=URLsConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    websocket: Optional[WebSocketConfig] = Field(None, description="WebSocket configuration")


class RequestConfig(BaseModel):
    """HTTP request configuration."""
    method: HTTPMethod = Field(HTTPMethod.GET, description="HTTP method")
    url: str = Field(..., description="Request URL")
    headers: Optional[Dict[str, str]] = Field(None, description="Request headers")
    params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    data: Optional[Any] = Field(None, description="Request body data")
    timeout: Optional[int] = Field(None, description="Request timeout in milliseconds")
    retries: Optional[int] = Field(None, description="Number of retry attempts")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")


class ClockSync(BaseModel):
    """Clock synchronization configuration."""
    enabled: bool = Field(True, description="Enable clock synchronization")
    max_drift: int = Field(5000, description="Maximum allowed drift in milliseconds")
    sync_interval: int = Field(300000, description="Sync interval in milliseconds")


class RateLimiterState(BaseModel):
    """Rate limiter state."""
    requests: List[float] = Field(default_factory=list, description="Request timestamps")
    reset_time: Optional[float] = Field(None, description="Next reset time")


class BackoffConfig(BaseModel):
    """Exponential backoff configuration."""
    initial_delay: int = Field(1000, description="Initial delay in milliseconds")
    max_delay: int = Field(30000, description="Maximum delay in milliseconds")
    multiplier: float = Field(2.0, description="Backoff multiplier")
    jitter: bool = Field(True, description="Enable jitter")
    max_attempts: int = Field(5, description="Maximum retry attempts")


class ApiResponse(BaseModel):
    """Generic API response type."""
    success: bool = Field(..., description="Success indicator")
    data: Optional[Any] = Field(None, description="Response data")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: Optional[float] = Field(None, description="Response timestamp")
    errors: Optional[List[Dict[str, str]]] = Field(None, description="Error details")


class BaseResponse(BaseModel):
    """Base response schema for all DXTrade API responses."""
    success: bool = Field(..., description="Success indicator")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: Optional[float] = Field(None, description="Response timestamp")


class PaginatedResponse(BaseModel):
    """Paginated response schema."""
    data: List[Any] = Field(..., description="Response data array")
    pagination: Optional[Dict[str, int]] = Field(None, description="Pagination info")
    
    class PaginationInfo(BaseModel):
        """Pagination information."""
        page: int = Field(..., description="Current page number")
        limit: int = Field(..., description="Items per page")
        total: int = Field(..., description="Total items")
        total_pages: int = Field(..., description="Total pages")