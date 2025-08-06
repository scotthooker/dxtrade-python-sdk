"""Main DXtrade client with unified interface."""

from __future__ import annotations

from typing import Optional

from dxtrade.auth import AuthFactory
from dxtrade.auth import AuthHandler
from dxtrade.errors import DXtradeConfigurationError
from dxtrade.http import DXtradeHTTPClient
from dxtrade.models import AnyCredentials
from dxtrade.models import AuthType
from dxtrade.models import ClientConfig
from dxtrade.models import HTTPConfig
from dxtrade.models import WebSocketConfig
from dxtrade.push import DXtradePushClient
from dxtrade.rest import AccountsAPI
from dxtrade.rest import InstrumentsAPI
from dxtrade.rest import OrdersAPI
from dxtrade.rest import PositionsAPI


class DXtradeClient:
    """Main DXtrade client with unified REST and WebSocket access."""
    
    def __init__(
        self,
        config: Optional[ClientConfig] = None,
        *,
        # HTTP configuration
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.3,
        rate_limit: Optional[int] = None,
        user_agent: str = "dxtrade-python-sdk/1.0.0",
        # WebSocket configuration
        websocket_url: Optional[str] = None,
        websocket_max_retries: int = 5,
        websocket_retry_backoff_factor: float = 0.5,
        heartbeat_interval: float = 30.0,
        max_message_size: int = 1024 * 1024,
        ping_interval: Optional[float] = 20.0,
        ping_timeout: Optional[float] = 10.0,
        # Authentication
        auth_type: Optional[AuthType] = None,
        credentials: Optional[AnyCredentials] = None,
        clock_drift_threshold: float = 30.0,
        enable_idempotency: bool = True,
    ) -> None:
        """Initialize DXtrade client.
        
        Args:
            config: Complete client configuration (overrides individual parameters)
            base_url: Base URL for REST API
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_backoff_factor: Retry backoff factor
            rate_limit: Rate limit (requests per second)
            user_agent: User agent string
            websocket_url: WebSocket URL for Push API
            websocket_max_retries: WebSocket max reconnection attempts
            websocket_retry_backoff_factor: WebSocket reconnection backoff factor
            heartbeat_interval: WebSocket heartbeat interval in seconds
            max_message_size: Maximum WebSocket message size
            ping_interval: WebSocket ping interval in seconds
            ping_timeout: WebSocket ping timeout in seconds
            auth_type: Authentication type
            credentials: Authentication credentials
            clock_drift_threshold: Clock drift threshold in seconds
            enable_idempotency: Enable idempotency keys
            
        Raises:
            DXtradeConfigurationError: Invalid configuration
        """
        # Build configuration if not provided
        if config is None:
            if not base_url:
                raise DXtradeConfigurationError("base_url is required")
            if not auth_type or not credentials:
                raise DXtradeConfigurationError("auth_type and credentials are required")
            
            http_config = HTTPConfig(
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                retry_backoff_factor=retry_backoff_factor,
                rate_limit=rate_limit,
                user_agent=user_agent,
            )
            
            websocket_config = None
            if websocket_url:
                websocket_config = WebSocketConfig(
                    url=websocket_url,
                    max_retries=websocket_max_retries,
                    retry_backoff_factor=websocket_retry_backoff_factor,
                    heartbeat_interval=heartbeat_interval,
                    max_message_size=max_message_size,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                )
            
            config = ClientConfig(
                http=http_config,
                websocket=websocket_config,
                auth_type=auth_type,
                credentials=credentials,
                clock_drift_threshold=clock_drift_threshold,
                enable_idempotency=enable_idempotency,
            )
        
        self.config = config
        
        # Create authentication handler
        self._auth_handler = AuthFactory.create_handler(
            config.auth_type,
            config.credentials,
        )
        
        # Initialize HTTP client
        self._http_client = DXtradeHTTPClient(
            config=config.http,
            auth_handler=self._auth_handler,
        )
        
        # Initialize REST API endpoints
        self.accounts = AccountsAPI(self._http_client)
        self.instruments = InstrumentsAPI(self._http_client)
        self.orders = OrdersAPI(self._http_client)
        self.positions = PositionsAPI(self._http_client)
        
        # Initialize WebSocket client (lazy)
        self._push_client: Optional[DXtradePushClient] = None
    
    @property
    def push(self) -> DXtradePushClient:
        """Get WebSocket push client.
        
        Returns:
            Push API client
            
        Raises:
            DXtradeConfigurationError: WebSocket not configured
        """
        if self._push_client is None:
            if not self.config.websocket:
                raise DXtradeConfigurationError(
                    "WebSocket URL not configured. "
                    "Set websocket_url parameter or websocket config."
                )
            
            self._push_client = DXtradePushClient(
                config=self.config.websocket,
                auth_handler=self._auth_handler,
            )
        
        return self._push_client
    
    @property
    def auth_handler(self) -> AuthHandler:
        """Get authentication handler."""
        return self._auth_handler
    
    async def __aenter__(self) -> DXtradeClient:
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close all client connections."""
        # Close HTTP client
        if self._http_client:
            await self._http_client.close()
        
        # Close WebSocket client if initialized
        if self._push_client:
            await self._push_client.disconnect()
    
    # Convenience methods for common operations
    
    async def login(self) -> bool:
        """Perform login for session-based authentication.
        
        This is automatically called when needed for session auth,
        but can be called manually to pre-authenticate.
        
        Returns:
            True if login successful
            
        Raises:
            DXtradeAuthenticationError: Login failed
        """
        from dxtrade.auth import SessionHandler
        
        if isinstance(self._auth_handler, SessionHandler):
            # Force refresh of session token
            await self._auth_handler._refresh_session_token(self._http_client._client)
            return True
        return False
    
    async def logout(self) -> None:
        """Perform logout for session-based authentication."""
        from dxtrade.auth import SessionHandler
        
        if isinstance(self._auth_handler, SessionHandler):
            await self._auth_handler.logout(self._http_client._client)
    
    async def get_server_time(self):
        """Get server time (convenience method)."""
        return await self.instruments.get_server_time()
    
    async def get_account_summary(self, account_id: str):
        """Get account summary (convenience method)."""
        return await self.accounts.get_account_summary(account_id)
    
    async def get_current_prices(self, symbols: Optional[list[str]] = None):
        """Get current prices (convenience method)."""
        return await self.instruments.get_prices(symbols)
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        account_id: Optional[str] = None,
        **kwargs,
    ):
        """Create market order (convenience method)."""
        from dxtrade.models import OrderRequest, OrderSide, OrderType
        
        order = OrderRequest(
            symbol=symbol,
            side=OrderSide(side),
            type=OrderType.MARKET,
            volume=volume,
            **kwargs,
        )
        return await self.orders.create_order(order)
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        **kwargs,
    ):
        """Create limit order (convenience method)."""
        from dxtrade.models import OrderRequest, OrderSide, OrderType
        
        order = OrderRequest(
            symbol=symbol,
            side=OrderSide(side),
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            **kwargs,
        )
        return await self.orders.create_order(order)
    
    async def get_open_orders(self, account_id: Optional[str] = None):
        """Get open orders (convenience method)."""
        from dxtrade.models import OrderStatus
        
        return await self.orders.get_orders(
            account_id=account_id,
            status=OrderStatus.OPEN,
        )
    
    async def get_open_positions(self, account_id: Optional[str] = None):
        """Get open positions (convenience method)."""
        return await self.positions.get_positions(account_id=account_id)
    
    async def close_all_positions(self, account_id: str):
        """Close all positions (convenience method)."""
        return await self.positions.close_all_positions(account_id)
    
    # Static factory methods
    
    @classmethod
    def create_with_bearer_token(
        cls,
        base_url: str,
        token: str,
        *,
        websocket_url: Optional[str] = None,
        **kwargs,
    ) -> DXtradeClient:
        """Create client with bearer token authentication.
        
        Args:
            base_url: Base URL for REST API
            token: Bearer token
            websocket_url: Optional WebSocket URL
            **kwargs: Additional configuration parameters
            
        Returns:
            Configured DXtrade client
        """
        from dxtrade.models import BearerTokenCredentials
        
        credentials = BearerTokenCredentials(token=token)
        
        return cls(
            base_url=base_url,
            websocket_url=websocket_url,
            auth_type=AuthType.BEARER_TOKEN,
            credentials=credentials,
            **kwargs,
        )
    
    @classmethod
    def create_with_hmac(
        cls,
        base_url: str,
        api_key: str,
        secret_key: str,
        *,
        passphrase: Optional[str] = None,
        websocket_url: Optional[str] = None,
        **kwargs,
    ) -> DXtradeClient:
        """Create client with HMAC authentication.
        
        Args:
            base_url: Base URL for REST API
            api_key: API key
            secret_key: Secret key
            passphrase: Optional passphrase
            websocket_url: Optional WebSocket URL
            **kwargs: Additional configuration parameters
            
        Returns:
            Configured DXtrade client
        """
        from dxtrade.models import HMACCredentials
        
        credentials = HMACCredentials(
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
        )
        
        return cls(
            base_url=base_url,
            websocket_url=websocket_url,
            auth_type=AuthType.HMAC,
            credentials=credentials,
            **kwargs,
        )
    
    @classmethod
    def create_with_session(
        cls,
        base_url: str,
        username: str,
        password: str,
        *,
        websocket_url: Optional[str] = None,
        **kwargs,
    ) -> DXtradeClient:
        """Create client with session authentication.
        
        Args:
            base_url: Base URL for REST API
            username: Username
            password: Password
            websocket_url: Optional WebSocket URL
            **kwargs: Additional configuration parameters
            
        Returns:
            Configured DXtrade client
        """
        from dxtrade.models import SessionCredentials
        
        credentials = SessionCredentials(
            username=username,
            password=password,
        )
        
        return cls(
            base_url=base_url,
            websocket_url=websocket_url,
            auth_type=AuthType.SESSION,
            credentials=credentials,
            **kwargs,
        )


# Convenience aliases for easy imports
DXClient = DXtradeClient  # Short alias