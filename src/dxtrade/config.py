"""
Platform-agnostic configuration system for DXTrade SDK.

This module provides configuration classes that allow the SDK to work with
any DXTrade broker without code changes. All broker-specific settings are
handled through configuration objects or environment variables.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class Environment(Enum):
    """Trading environment types."""
    DEMO = 'demo'
    LIVE = 'live'


class AuthType(Enum):
    """Authentication method types."""
    CREDENTIALS = 'credentials'
    SESSION = 'session'
    BEARER = 'bearer'
    HMAC = 'hmac'


@dataclass
class Features:
    """Feature flags for SDK functionality."""
    clock_sync: bool = True
    websocket: bool = True
    auto_reconnect: bool = True
    rate_limiting: bool = True
    automatic_retry: bool = True
    
    def to_dict(self) -> Dict[str, bool]:
        """Convert features to dictionary."""
        return {
            'clock_sync': self.clock_sync,
            'websocket': self.websocket,
            'auto_reconnect': self.auto_reconnect,
            'rate_limiting': self.rate_limiting,
            'automatic_retry': self.automatic_retry
        }


@dataclass
class Endpoints:
    """Configurable API endpoints - supports explicit URLs or paths."""
    # Authentication endpoints
    login: str = '/login'
    logout: str = '/logout'
    refresh_token: str = '/refresh'
    
    # Market data endpoints
    market_data: str = '/marketdata'
    quotes: str = '/quotes'
    candles: str = '/candles'
    instruments: str = '/instruments'
    
    # Account endpoints
    account: str = '/account'
    accounts: str = '/accounts'
    portfolio: str = '/portfolio'
    balance: str = '/balance'
    metrics: str = '/accounts/metrics'
    
    # Trading endpoints
    orders: str = '/orders'
    orders_history: str = '/accounts/orders/history'
    positions: str = '/accounts/positions'
    trades: str = '/trades'
    history: str = '/history'
    
    # System endpoints
    time: str = '/time'
    status: str = '/status'
    version: str = '/version'
    conversion_rates: str = '/conversionRates'
    
    # WebSocket endpoints (legacy paths)
    ws_market_data: str = '/md'
    ws_portfolio: str = '/'
    
    def get_endpoint(self, name: str, base_url: Optional[str] = None) -> str:
        """Get endpoint by name with fallback."""
        endpoint = getattr(self, name, f'/{name}')
        
        # If it's already a complete URL, return as-is
        if endpoint.startswith(('http://', 'https://')):
            return endpoint
        
        # If we have a base URL, construct the full URL
        if base_url:
            return f"{base_url.rstrip('/')}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
        
        # Return the path/endpoint as-is
        return endpoint


@dataclass
class WebSocketConfig:
    """WebSocket-specific configuration."""
    # Explicit URLs (preferred)
    market_data_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    
    # Legacy configuration (fallback)
    base_url: Optional[str] = None
    market_data_path: str = '/md'
    portfolio_path: str = '/'
    format: str = 'JSON'
    ping_interval: int = 45  # seconds
    reconnect_attempts: int = 5
    reconnect_delay: float = 1.0  # seconds
    max_message_size: int = 1024 * 1024  # 1MB
    
    def get_market_data_url(self, base_url: Optional[str] = None) -> str:
        """Get complete market data WebSocket URL."""
        # Use explicit URL if available
        if self.market_data_url:
            return self.market_data_url
        
        # Fallback to constructing URL from base + path
        if not base_url and not self.base_url:
            raise ValueError("No market data WebSocket URL available")
        
        ws_base = self.base_url or base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        # Ensure path has format parameter
        path = self.market_data_path
        if '?' not in path:
            path = f"{path}?format={self.format}"
        elif 'format=' not in path:
            path = f"{path}&format={self.format}"
        return f"{ws_base}/ws{path}"
    
    def get_portfolio_url(self, base_url: Optional[str] = None) -> str:
        """Get complete portfolio WebSocket URL."""
        # Use explicit URL if available
        if self.portfolio_url:
            return self.portfolio_url
        
        # Fallback to constructing URL from base + path
        if not base_url and not self.base_url:
            raise ValueError("No portfolio WebSocket URL available")
        
        ws_base = self.base_url or base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        # Ensure path has format parameter
        path = self.portfolio_path
        if '?' not in path:
            path = f"{path}?format={self.format}"
        elif 'format=' not in path:
            path = f"{path}&format={self.format}"
        return f"{ws_base}/ws{path}"


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    burst_size: int = 10
    retry_after_header: str = 'Retry-After'
    rate_limit_header: str = 'X-RateLimit-Limit'
    remaining_header: str = 'X-RateLimit-Remaining'


@dataclass
class RetryConfig:
    """Retry behavior configuration."""
    enabled: bool = True
    max_attempts: int = 3
    base_delay: float = 0.5  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True
    retry_on_server_error: bool = True  # 5xx errors


@dataclass
class AuthConfig:
    """Authentication configuration."""
    type: AuthType
    
    # Credentials auth
    username: Optional[str] = None
    password: Optional[str] = None
    domain: str = 'default'
    
    # Session auth
    session_token: Optional[str] = None
    auto_refresh: bool = True
    refresh_before_expiry: int = 300  # seconds
    
    # Bearer auth
    bearer_token: Optional[str] = None
    
    # HMAC auth
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None
    
    def validate(self) -> None:
        """Validate authentication configuration."""
        if self.type == AuthType.CREDENTIALS:
            if not self.username or not self.password:
                raise ValueError("Username and password required for credentials auth")
        elif self.type == AuthType.SESSION:
            if not self.session_token and not (self.username and self.password):
                raise ValueError("Session token or credentials required for session auth")
        elif self.type == AuthType.BEARER:
            if not self.bearer_token:
                raise ValueError("Bearer token required for bearer auth")
        elif self.type == AuthType.HMAC:
            if not self.api_key or not self.api_secret:
                raise ValueError("API key and secret required for HMAC auth")


@dataclass
class SDKConfig:
    """Main SDK configuration."""
    # Core settings
    environment: Environment = Environment.DEMO
    base_url: Optional[str] = None
    timeout: int = 30000  # milliseconds
    user_agent: str = 'dxtrade-python-sdk/2.0.0'
    
    # Authentication
    auth: AuthConfig = field(default_factory=lambda: AuthConfig(type=AuthType.CREDENTIALS))
    
    # Features
    features: Features = field(default_factory=Features)
    
    # Endpoints
    endpoints: Endpoints = field(default_factory=Endpoints)
    
    # WebSocket
    websocket: Optional[WebSocketConfig] = field(default_factory=WebSocketConfig)
    
    # Rate limiting
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    
    # Retry behavior
    retry: RetryConfig = field(default_factory=RetryConfig)
    
    # Logging
    log_level: str = 'INFO'
    log_requests: bool = False
    log_responses: bool = False
    
    # Account configuration
    account: Optional[str] = None
    
    def validate(self) -> None:
        """Validate the complete configuration."""
        if not self.base_url:
            raise ValueError("base_url is required")
        
        if not self.base_url.startswith(('http://', 'https://')):
            raise ValueError("base_url must start with http:// or https://")
        
        self.auth.validate()
        
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        
        if self.features.websocket and not self.websocket:
            self.websocket = WebSocketConfig()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'environment': self.environment.value,
            'base_url': self.base_url,
            'timeout': self.timeout,
            'user_agent': self.user_agent,
            'auth': {
                'type': self.auth.type.value,
                'username': self.auth.username,
                'domain': self.auth.domain,
                # Don't include sensitive data
            },
            'features': self.features.to_dict(),
            'log_level': self.log_level,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SDKConfig':
        """Create configuration from dictionary."""
        config = cls()
        
        if 'environment' in data:
            config.environment = Environment(data['environment'])
        
        if 'base_url' in data:
            config.base_url = data['base_url']
        
        if 'timeout' in data:
            config.timeout = data['timeout']
        
        if 'auth' in data:
            auth_data = data['auth']
            auth_type = AuthType(auth_data.get('type', 'credentials'))
            config.auth = AuthConfig(
                type=auth_type,
                username=auth_data.get('username'),
                password=auth_data.get('password'),
                domain=auth_data.get('domain', 'default'),
                session_token=auth_data.get('session_token'),
                bearer_token=auth_data.get('bearer_token'),
                api_key=auth_data.get('api_key'),
                api_secret=auth_data.get('api_secret'),
                passphrase=auth_data.get('passphrase')
            )
        
        if 'features' in data:
            config.features = Features(**data['features'])
        
        if 'endpoints' in data:
            config.endpoints = Endpoints(**data['endpoints'])
        
        if 'websocket' in data:
            config.websocket = WebSocketConfig(**data['websocket'])
        
        return config


# Alias for backward compatibility
DXTradeConfig = SDKConfig