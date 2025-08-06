"""
Environment variable configuration loader for DXTrade SDK.

This module provides functionality to load SDK configuration from environment
variables, allowing for easy deployment across different brokers and environments
without code changes.
"""

import os
import logging
from typing import Optional, Dict, Any
from .config import (
    SDKConfig, 
    AuthConfig, 
    AuthType, 
    Environment,
    Features, 
    Endpoints, 
    WebSocketConfig,
    RateLimitConfig,
    RetryConfig
)

logger = logging.getLogger(__name__)


def load_config_from_env() -> SDKConfig:
    """
    Load SDK configuration from environment variables.
    
    Environment variables:
        Core Configuration:
            DXTRADE_ENVIRONMENT: Trading environment (demo/live)
            DXTRADE_BASE_URL: Base API URL
            DXTRADE_TIMEOUT: Request timeout in milliseconds
            DXTRADE_USER_AGENT: User agent string
            
        Authentication (one of these sets):
            Credentials:
                DXTRADE_USERNAME: Username
                DXTRADE_PASSWORD: Password
                DXTRADE_DOMAIN: Domain (default: 'default')
            
            Session:
                DXTRADE_SESSION_TOKEN: Session token
            
            Bearer:
                DXTRADE_BEARER_TOKEN: Bearer token
            
            HMAC:
                DXTRADE_API_KEY: API key
                DXTRADE_API_SECRET: API secret
                DXTRADE_API_PASSPHRASE: Optional passphrase
        
        Features:
            DXTRADE_FEATURE_CLOCK_SYNC: Enable clock sync (true/false)
            DXTRADE_FEATURE_WEBSOCKET: Enable WebSocket (true/false)
            DXTRADE_FEATURE_AUTO_RECONNECT: Enable auto-reconnect (true/false)
            DXTRADE_FEATURE_RATE_LIMITING: Enable rate limiting (true/false)
            DXTRADE_FEATURE_AUTOMATIC_RETRY: Enable automatic retry (true/false)
        
        Endpoints:
            DXTRADE_ENDPOINT_LOGIN: Login endpoint
            DXTRADE_ENDPOINT_MARKET_DATA: Market data endpoint
            DXTRADE_ENDPOINT_ACCOUNT: Account endpoint
            DXTRADE_ENDPOINT_ORDERS: Orders endpoint
            DXTRADE_ENDPOINT_WS_MARKET_DATA: WebSocket market data path
            DXTRADE_ENDPOINT_WS_PORTFOLIO: WebSocket portfolio path
            ... (all other endpoints)
        
        WebSocket:
            DXTRADE_WS_URL: WebSocket base URL
            DXTRADE_WS_MARKET_DATA_PATH: Market data path
            DXTRADE_WS_PORTFOLIO_PATH: Portfolio path
            DXTRADE_WS_FORMAT: Data format (default: JSON)
            DXTRADE_WS_PING_INTERVAL: Ping interval in seconds
            DXTRADE_WS_RECONNECT_ATTEMPTS: Max reconnection attempts
        
        Rate Limiting:
            DXTRADE_RATE_LIMIT_ENABLED: Enable rate limiting (true/false)
            DXTRADE_RATE_LIMIT_PER_SECOND: Requests per second
            DXTRADE_RATE_LIMIT_PER_MINUTE: Requests per minute
            DXTRADE_RATE_LIMIT_BURST_SIZE: Burst size
        
        Retry:
            DXTRADE_RETRY_ENABLED: Enable retry (true/false)
            DXTRADE_RETRY_MAX_ATTEMPTS: Max retry attempts
            DXTRADE_RETRY_BASE_DELAY: Base delay in seconds
            DXTRADE_RETRY_MAX_DELAY: Max delay in seconds
        
        Logging:
            DXTRADE_LOG_LEVEL: Log level (DEBUG/INFO/WARNING/ERROR)
            DXTRADE_LOG_REQUESTS: Log requests (true/false)
            DXTRADE_LOG_RESPONSES: Log responses (true/false)
        
        Account:
            DXTRADE_ACCOUNT: Account identifier (e.g., "default:demo", "main:live")
    
    Returns:
        SDKConfig: Configuration object loaded from environment
    """
    config = SDKConfig()
    
    # Core configuration
    if env_val := os.getenv('DXTRADE_ENVIRONMENT'):
        try:
            config.environment = Environment(env_val.lower())
        except ValueError:
            logger.warning(f"Invalid environment value: {env_val}, using default: {config.environment.value}")
    
    if base_url := os.getenv('DXTRADE_BASE_URL'):
        config.base_url = base_url.rstrip('/')  # Remove trailing slash
    
    if timeout := os.getenv('DXTRADE_TIMEOUT'):
        try:
            config.timeout = int(timeout)
        except ValueError:
            logger.warning(f"Invalid timeout value: {timeout}, using default: {config.timeout}")
    
    if user_agent := os.getenv('DXTRADE_USER_AGENT'):
        config.user_agent = user_agent
    
    # Authentication
    config.auth = _load_auth_from_env()
    
    # Features
    config.features = _load_features_from_env()
    
    # Endpoints
    config.endpoints = _load_endpoints_from_env()
    
    # WebSocket
    if os.getenv('DXTRADE_WS_URL') or config.features.websocket:
        config.websocket = _load_websocket_from_env()
    
    # Rate limiting
    config.rate_limit = _load_rate_limit_from_env()
    
    # Retry
    config.retry = _load_retry_from_env()
    
    # Logging
    if log_level := os.getenv('DXTRADE_LOG_LEVEL'):
        config.log_level = log_level.upper()
    
    config.log_requests = _parse_bool(os.getenv('DXTRADE_LOG_REQUESTS', 'false'))
    config.log_responses = _parse_bool(os.getenv('DXTRADE_LOG_RESPONSES', 'false'))
    
    # Account configuration
    if account := os.getenv('DXTRADE_ACCOUNT'):
        config.account = account
    
    return config


def _load_auth_from_env() -> AuthConfig:
    """Load authentication configuration from environment."""
    # Determine auth type based on available credentials
    if username := os.getenv('DXTRADE_USERNAME'):
        return AuthConfig(
            type=AuthType.CREDENTIALS,
            username=username,
            password=os.getenv('DXTRADE_PASSWORD', ''),
            domain=os.getenv('DXTRADE_DOMAIN', 'default')
        )
    elif session_token := os.getenv('DXTRADE_SESSION_TOKEN'):
        return AuthConfig(
            type=AuthType.SESSION,
            session_token=session_token,
            auto_refresh=_parse_bool(os.getenv('DXTRADE_SESSION_AUTO_REFRESH', 'true')),
            refresh_before_expiry=int(os.getenv('DXTRADE_SESSION_REFRESH_BEFORE', '300'))
        )
    elif bearer_token := os.getenv('DXTRADE_BEARER_TOKEN'):
        return AuthConfig(
            type=AuthType.BEARER,
            bearer_token=bearer_token
        )
    elif api_key := os.getenv('DXTRADE_API_KEY'):
        return AuthConfig(
            type=AuthType.HMAC,
            api_key=api_key,
            api_secret=os.getenv('DXTRADE_API_SECRET', ''),
            passphrase=os.getenv('DXTRADE_API_PASSPHRASE')
        )
    else:
        # Default to credentials with empty values
        return AuthConfig(type=AuthType.CREDENTIALS)


def _load_features_from_env() -> Features:
    """Load feature flags from environment."""
    return Features(
        clock_sync=_parse_bool(os.getenv('DXTRADE_FEATURE_CLOCK_SYNC', 'true')),
        websocket=_parse_bool(os.getenv('DXTRADE_FEATURE_WEBSOCKET', 'true')),
        auto_reconnect=_parse_bool(os.getenv('DXTRADE_FEATURE_AUTO_RECONNECT', 'true')),
        rate_limiting=_parse_bool(os.getenv('DXTRADE_FEATURE_RATE_LIMITING', 'true')),
        automatic_retry=_parse_bool(os.getenv('DXTRADE_FEATURE_AUTOMATIC_RETRY', 'true'))
    )


def _load_endpoints_from_env() -> Endpoints:
    """Load endpoint configuration from environment."""
    endpoints = Endpoints()
    
    # Map environment variables to endpoint attributes
    endpoint_mapping = {
        'DXTRADE_ENDPOINT_LOGIN': 'login',
        'DXTRADE_ENDPOINT_LOGOUT': 'logout',
        'DXTRADE_ENDPOINT_REFRESH_TOKEN': 'refresh_token',
        'DXTRADE_ENDPOINT_MARKET_DATA': 'market_data',
        'DXTRADE_ENDPOINT_QUOTES': 'quotes',
        'DXTRADE_ENDPOINT_CANDLES': 'candles',
        'DXTRADE_ENDPOINT_INSTRUMENTS': 'instruments',
        'DXTRADE_ENDPOINT_ACCOUNT': 'account',
        'DXTRADE_ENDPOINT_ACCOUNTS': 'accounts',
        'DXTRADE_ENDPOINT_PORTFOLIO': 'portfolio',
        'DXTRADE_ENDPOINT_BALANCE': 'balance',
        'DXTRADE_ENDPOINT_ORDERS': 'orders',
        'DXTRADE_ENDPOINT_POSITIONS': 'positions',
        'DXTRADE_ENDPOINT_TRADES': 'trades',
        'DXTRADE_ENDPOINT_HISTORY': 'history',
        'DXTRADE_ENDPOINT_TIME': 'time',
        'DXTRADE_ENDPOINT_STATUS': 'status',
        'DXTRADE_ENDPOINT_VERSION': 'version',
        'DXTRADE_ENDPOINT_WS_MARKET_DATA': 'ws_market_data',
        'DXTRADE_ENDPOINT_WS_PORTFOLIO': 'ws_portfolio',
    }
    
    for env_var, attr_name in endpoint_mapping.items():
        if value := os.getenv(env_var):
            setattr(endpoints, attr_name, value)
    
    return endpoints


def _load_websocket_from_env() -> WebSocketConfig:
    """Load WebSocket configuration from environment."""
    ws_config = WebSocketConfig()
    
    if ws_url := os.getenv('DXTRADE_WS_URL'):
        ws_config.base_url = ws_url.rstrip('/')
    
    if market_data_path := os.getenv('DXTRADE_WS_MARKET_DATA_PATH'):
        ws_config.market_data_path = market_data_path
    
    if portfolio_path := os.getenv('DXTRADE_WS_PORTFOLIO_PATH'):
        ws_config.portfolio_path = portfolio_path
    
    if format_val := os.getenv('DXTRADE_WS_FORMAT'):
        ws_config.format = format_val
    
    if ping_interval := os.getenv('DXTRADE_WS_PING_INTERVAL'):
        try:
            ws_config.ping_interval = int(ping_interval)
        except ValueError:
            logger.warning(f"Invalid ping interval: {ping_interval}")
    
    if reconnect_attempts := os.getenv('DXTRADE_WS_RECONNECT_ATTEMPTS'):
        try:
            ws_config.reconnect_attempts = int(reconnect_attempts)
        except ValueError:
            logger.warning(f"Invalid reconnect attempts: {reconnect_attempts}")
    
    if reconnect_delay := os.getenv('DXTRADE_WS_RECONNECT_DELAY'):
        try:
            ws_config.reconnect_delay = float(reconnect_delay)
        except ValueError:
            logger.warning(f"Invalid reconnect delay: {reconnect_delay}")
    
    return ws_config


def _load_rate_limit_from_env() -> RateLimitConfig:
    """Load rate limiting configuration from environment."""
    rate_limit = RateLimitConfig()
    
    rate_limit.enabled = _parse_bool(os.getenv('DXTRADE_RATE_LIMIT_ENABLED', 'true'))
    
    if per_second := os.getenv('DXTRADE_RATE_LIMIT_PER_SECOND'):
        try:
            rate_limit.requests_per_second = int(per_second)
        except ValueError:
            logger.warning(f"Invalid rate limit per second: {per_second}")
    
    if per_minute := os.getenv('DXTRADE_RATE_LIMIT_PER_MINUTE'):
        try:
            rate_limit.requests_per_minute = int(per_minute)
        except ValueError:
            logger.warning(f"Invalid rate limit per minute: {per_minute}")
    
    if per_hour := os.getenv('DXTRADE_RATE_LIMIT_PER_HOUR'):
        try:
            rate_limit.requests_per_hour = int(per_hour)
        except ValueError:
            logger.warning(f"Invalid rate limit per hour: {per_hour}")
    
    if burst_size := os.getenv('DXTRADE_RATE_LIMIT_BURST_SIZE'):
        try:
            rate_limit.burst_size = int(burst_size)
        except ValueError:
            logger.warning(f"Invalid burst size: {burst_size}")
    
    return rate_limit


def _load_retry_from_env() -> RetryConfig:
    """Load retry configuration from environment."""
    retry = RetryConfig()
    
    retry.enabled = _parse_bool(os.getenv('DXTRADE_RETRY_ENABLED', 'true'))
    
    if max_attempts := os.getenv('DXTRADE_RETRY_MAX_ATTEMPTS'):
        try:
            retry.max_attempts = int(max_attempts)
        except ValueError:
            logger.warning(f"Invalid max retry attempts: {max_attempts}")
    
    if base_delay := os.getenv('DXTRADE_RETRY_BASE_DELAY'):
        try:
            retry.base_delay = float(base_delay)
        except ValueError:
            logger.warning(f"Invalid base delay: {base_delay}")
    
    if max_delay := os.getenv('DXTRADE_RETRY_MAX_DELAY'):
        try:
            retry.max_delay = float(max_delay)
        except ValueError:
            logger.warning(f"Invalid max delay: {max_delay}")
    
    retry.jitter = _parse_bool(os.getenv('DXTRADE_RETRY_JITTER', 'true'))
    retry.retry_on_timeout = _parse_bool(os.getenv('DXTRADE_RETRY_ON_TIMEOUT', 'true'))
    retry.retry_on_connection_error = _parse_bool(os.getenv('DXTRADE_RETRY_ON_CONNECTION', 'true'))
    retry.retry_on_server_error = _parse_bool(os.getenv('DXTRADE_RETRY_ON_SERVER_ERROR', 'true'))
    
    return retry


def _parse_bool(value: Optional[str]) -> bool:
    """Parse boolean from string."""
    if not value:
        return False
    return value.lower() in ('true', '1', 'yes', 'on')


def save_config_to_env_file(config: SDKConfig, filepath: str = '.env') -> None:
    """
    Save configuration to environment file.
    
    Args:
        config: Configuration to save
        filepath: Path to environment file
    """
    lines = []
    
    # Core configuration
    lines.append(f"DXTRADE_ENVIRONMENT={config.environment.value}")
    if config.base_url:
        lines.append(f"DXTRADE_BASE_URL={config.base_url}")
    lines.append(f"DXTRADE_TIMEOUT={config.timeout}")
    lines.append(f"DXTRADE_USER_AGENT={config.user_agent}")
    
    # Authentication
    if config.auth.type == AuthType.CREDENTIALS:
        if config.auth.username:
            lines.append(f"DXTRADE_USERNAME={config.auth.username}")
        if config.auth.password:
            lines.append(f"DXTRADE_PASSWORD={config.auth.password}")
        lines.append(f"DXTRADE_DOMAIN={config.auth.domain}")
    elif config.auth.type == AuthType.SESSION:
        if config.auth.session_token:
            lines.append(f"DXTRADE_SESSION_TOKEN={config.auth.session_token}")
    elif config.auth.type == AuthType.BEARER:
        if config.auth.bearer_token:
            lines.append(f"DXTRADE_BEARER_TOKEN={config.auth.bearer_token}")
    elif config.auth.type == AuthType.HMAC:
        if config.auth.api_key:
            lines.append(f"DXTRADE_API_KEY={config.auth.api_key}")
        if config.auth.api_secret:
            lines.append(f"DXTRADE_API_SECRET={config.auth.api_secret}")
        if config.auth.passphrase:
            lines.append(f"DXTRADE_API_PASSPHRASE={config.auth.passphrase}")
    
    # Features
    lines.append(f"DXTRADE_FEATURE_CLOCK_SYNC={str(config.features.clock_sync).lower()}")
    lines.append(f"DXTRADE_FEATURE_WEBSOCKET={str(config.features.websocket).lower()}")
    lines.append(f"DXTRADE_FEATURE_AUTO_RECONNECT={str(config.features.auto_reconnect).lower()}")
    
    # WebSocket
    if config.websocket:
        if config.websocket.base_url:
            lines.append(f"DXTRADE_WS_URL={config.websocket.base_url}")
        lines.append(f"DXTRADE_WS_MARKET_DATA_PATH={config.websocket.market_data_path}")
        lines.append(f"DXTRADE_WS_PORTFOLIO_PATH={config.websocket.portfolio_path}")
    
    # Logging
    lines.append(f"DXTRADE_LOG_LEVEL={config.log_level}")
    
    # Write to file
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))
        f.write('\n')
    
    logger.info(f"Configuration saved to {filepath}")