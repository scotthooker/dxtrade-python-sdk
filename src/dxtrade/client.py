"""DXTrade Python SDK - Main client implementation.

Production-ready SDK for DXTrade REST and WebSocket APIs with:
- Comprehensive async/await patterns
- Typed responses using Pydantic
- Exponential backoff and retry logic
- Rate limiting and idempotency
- WebSocket state management
- Automatic reconnection
- Comprehensive error handling
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .config import DXTradeConfig, SDKConfig
from .transport import DXTradeTransport, create_transport
from .rest.accounts import AccountsAPI
from .rest.instruments import InstrumentsAPI
from .rest.orders import OrdersAPI
from .rest.positions import PositionsAPI
from .websocket.stream_manager import DXTradeStreamManager
from .websocket.unified_stream import UnifiedWebSocketStream
from .errors import DXtradeError, ConfigError
from .types.common import Environment, AuthConfig
from .types.websocket import StreamOptions, StreamCallbacks
from .types.dxtrade_messages import DXTradeStreamOptions, DXTradeStreamCallbacks

logger = logging.getLogger(__name__)


class DXTradeClient:
    """Main DXTrade SDK client.
    
    Provides access to REST APIs and WebSocket streams for DXTrade platform.
    
    Example:
        ```python
        from dxtrade import DXTradeClient
        
        # Create client with session authentication
        client = DXTradeClient(
            environment="demo",
            auth={"type": "session", "token": "your-session-token"}
        )
        
        # Connect to APIs
        await client.connect()
        
        # Use REST APIs
        accounts = await client.accounts.get_accounts()
        positions = await client.positions.get_positions()
        
        # Start WebSocket stream
        stream = await client.start_stream()
        
        # Subscribe to market data
        await stream.subscribe_quotes(["EURUSD", "GBPUSD"])
        
        # Clean up
        await client.disconnect()
        ```
    """
    
    def __init__(
        self,
        config: Optional[DXTradeConfig] = None,
        environment: Optional[Environment] = None,
        auth: Optional[AuthConfig] = None,
        base_url: Optional[str] = None,
        timeout: int = 30000,
        retries: int = 3,
        **kwargs
    ):
        """Initialize DXTrade client.
        
        Args:
            config: Complete configuration object (takes precedence)
            environment: Trading environment ("demo" or "live")
            auth: Authentication configuration
            base_url: Base URL for REST API
            timeout: Request timeout in milliseconds
            retries: Number of retry attempts
            **kwargs: Additional configuration options
        """
        # Build configuration
        if config:
            self.config = config
        else:
            if not auth:
                raise ConfigError("Authentication configuration is required")
            
            self.config = DXTradeConfig(
                environment=environment or "demo",
                auth=auth,
                base_url=base_url or self._get_default_base_url(environment or "demo"),
                timeout=timeout,
                retries=retries,
                **kwargs
            )
        
        # Initialize HTTP client
        self.http = HttpClient(self.config)
        
        # Initialize REST API modules
        self.accounts = AccountsAPI(self.http)
        self.instruments = InstrumentsAPI(self.http)
        self.orders = OrdersAPI(self.http)
        self.positions = PositionsAPI(self.http)
        
        # WebSocket manager (initialized on demand)
        self._stream_manager: Optional[DXTradeStreamManager] = None
        self._unified_stream: Optional[UnifiedWebSocketStream] = None
        
        # Connection state
        self._connected = False
        self._session_token: Optional[str] = None
    
    async def connect(self) -> None:
        """Connect to DXTrade APIs.
        
        Establishes connection and performs authentication if needed.
        """
        try:
            # For session-based auth, the token is already configured
            if self.config.auth["type"] == "session":
                self._session_token = self.config.auth.get("token")
            
            # For credentials-based auth, perform login
            elif self.config.auth["type"] == "credentials":
                await self._authenticate()
            
            self._connected = True
            logger.info("Successfully connected to DXTrade APIs")
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from DXTrade APIs.
        
        Closes WebSocket connections and cleans up resources.
        """
        try:
            # Close WebSocket streams
            if self._stream_manager:
                await self._stream_manager.disconnect()
                self._stream_manager = None
            
            if self._unified_stream:
                await self._unified_stream.close()
                self._unified_stream = None
            
            self._connected = False
            logger.info("Disconnected from DXTrade APIs")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if client is ready for trading.
        
        Returns:
            True if client is connected and authenticated
        """
        return self._connected and (self._session_token is not None or 
                                   self.config.auth["type"] != "credentials")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive client status.
        
        Returns:
            Dictionary with status information for all components
        """
        status = {
            "http": {
                "rate_limit_status": self.http.get_rate_limit_status(),
                "stats": self.http.get_stats()
            },
            "ready": self.is_ready(),
            "connected": self._connected
        }
        
        if self._stream_manager:
            status["websocket"] = self._stream_manager.get_status()
        
        return status
    
    def create_stream(
        self,
        options: Optional[DXTradeStreamOptions] = None,
        callbacks: Optional[DXTradeStreamCallbacks] = None
    ) -> DXTradeStreamManager:
        """Create DXTrade WebSocket stream manager.
        
        This is the recommended way to manage DXTrade WebSocket connections.
        
        Args:
            options: Stream configuration options
            callbacks: Event callback handlers
            
        Returns:
            DXTradeStreamManager instance
            
        Example:
            ```python
            stream = client.create_stream(
                options={"subscribe_quotes": ["EURUSD", "GBPUSD"]},
                callbacks={
                    "on_quote": lambda quote: print(f"Quote: {quote}"),
                    "on_error": lambda error: print(f"Error: {error}")
                }
            )
            await stream.connect()
            ```
        """
        if not self._session_token and self.config.auth["type"] == "session":
            self._session_token = self.config.auth.get("token")
        
        if not self._session_token:
            raise ConfigError("Session token not available. Ensure client is authenticated first.")
        
        self._stream_manager = DXTradeStreamManager(
            config=self.config,
            session_token=self._session_token,
            options=options or {},
            callbacks=callbacks or {}
        )
        
        return self._stream_manager
    
    async def start_stream(
        self,
        options: Optional[DXTradeStreamOptions] = None,
        callbacks: Optional[DXTradeStreamCallbacks] = None
    ) -> DXTradeStreamManager:
        """Start DXTrade WebSocket stream and connect immediately.
        
        Convenience method that creates and connects the stream manager.
        
        Args:
            options: Stream configuration options
            callbacks: Event callback handlers
            
        Returns:
            Connected DXTradeStreamManager instance
            
        Example:
            ```python
            stream = await client.start_stream(
                options={"subscribe_quotes": ["EURUSD"]},
                callbacks={"on_quote": print}
            )
            ```
        """
        stream = self.create_stream(options, callbacks)
        connected = await stream.connect()
        
        if not connected:
            raise DXtradeError("Failed to connect to DXTrade WebSocket streams")
        
        return stream
    
    def create_unified_stream(
        self,
        options: Optional[StreamOptions] = None,
        callbacks: Optional[StreamCallbacks] = None
    ) -> UnifiedWebSocketStream:
        """Create unified WebSocket stream for real-time data.
        
        Provides dual WebSocket connections (market data + portfolio).
        
        Args:
            options: Stream configuration options
            callbacks: Event callback handlers
            
        Returns:
            UnifiedWebSocketStream instance
        """
        if not self._session_token and self.config.auth["type"] == "session":
            self._session_token = self.config.auth.get("token")
        
        if not self._session_token:
            raise ConfigError("Session token not available. Ensure client is authenticated first.")
        
        self._unified_stream = UnifiedWebSocketStream(
            config=self.config,
            session_token=self._session_token,
            options=options or {},
            callbacks=callbacks or {}
        )
        
        return self._unified_stream
    
    async def start_unified_stream(
        self,
        options: Optional[StreamOptions] = None,
        callbacks: Optional[StreamCallbacks] = None
    ) -> UnifiedWebSocketStream:
        """Start unified WebSocket stream (Python compatibility helper).
        
        Returns the same structure as TypeScript version for compatibility.
        
        Args:
            options: Stream configuration options
            callbacks: Event callback handlers
            
        Returns:
            Connected UnifiedWebSocketStream instance
        """
        stream = self.create_unified_stream(options, callbacks)
        await stream.connect()
        return stream
    
    async def run_stream_test(
        self,
        duration_ms: int = 300000,  # 5 minutes default
        options: Optional[DXTradeStreamOptions] = None,
        callbacks: Optional[DXTradeStreamCallbacks] = None
    ) -> Dict[str, Any]:
        """Run a DXTrade WebSocket stability test.
        
        Useful for validating connection stability and ping/pong handling.
        
        Args:
            duration_ms: Test duration in milliseconds
            options: Stream configuration options
            callbacks: Event callback handlers
            
        Returns:
            Test results with statistics
        """
        stream = self.create_stream(options, callbacks)
        return await stream.run_stability_test(duration_ms)
    
    def set_session_token(self, token: str) -> None:
        """Update authentication token for session-based auth.
        
        Args:
            token: New session token
        """
        self._session_token = token
        self.http.set_session_token(token)
        
        # Update config if using session auth
        if self.config.auth["type"] == "session":
            self.config.auth["token"] = token
    
    def clear_session_token(self) -> None:
        """Clear session token."""
        self._session_token = None
        self.http.clear_session_token()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all services.
        
        Returns:
            Dictionary with health status for each component
        """
        results = {
            "http": {"healthy": False},
            "overall": False
        }
        
        # Test HTTP client
        try:
            start = datetime.now()
            # Try a simple endpoint
            await self.http.get("/health")
            latency = (datetime.now() - start).total_seconds() * 1000
            results["http"] = {
                "healthy": True,
                "latency": latency
            }
        except Exception as e:
            results["http"] = {
                "healthy": False,
                "error": str(e)
            }
        
        # Test WebSocket if available
        if self._stream_manager:
            try:
                ws_status = self._stream_manager.get_status()
                results["websocket"] = {
                    "healthy": ws_status.get("connected", False),
                    "connected": ws_status.get("connected", False),
                    "authenticated": ws_status.get("authenticated", False)
                }
            except Exception as e:
                results["websocket"] = {
                    "healthy": False,
                    "connected": False,
                    "authenticated": False,
                    "error": str(e)
                }
        
        # Overall health
        results["overall"] = results["http"]["healthy"] and \
                           results.get("websocket", {}).get("healthy", True)
        
        return results
    
    async def _authenticate(self) -> None:
        """Perform authentication for credentials-based auth."""
        if self.config.auth["type"] != "credentials":
            return
        
        # Perform login
        auth_data = self.config.auth
        response = await self.http.post("/login", {
            "username": auth_data["username"],
            "password": auth_data["password"],
            "domain": auth_data.get("domain", "default")
        })
        
        if response.get("sessionToken"):
            self._session_token = response["sessionToken"]
            self.http.set_session_token(self._session_token)
        else:
            raise DXtradeError("Authentication failed: no session token received")
    
    def _get_default_base_url(self, environment: Environment) -> str:
        """Get default base URL for environment.
        
        Args:
            environment: Trading environment
            
        Returns:
            Default base URL
        """
        if environment == "demo":
            return "https://demo-api.dx.trade/api/v1"
        else:
            return "https://api.dx.trade/api/v1"
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._stream_manager:
            asyncio.create_task(self._stream_manager.disconnect())
        if self._unified_stream:
            asyncio.create_task(self._unified_stream.close())
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


def create_client(
    environment: Environment = "demo",
    auth: Optional[AuthConfig] = None,
    **kwargs
) -> DXTradeClient:
    """Factory function to create DXTrade client.
    
    Args:
        environment: Trading environment ("demo" or "live")
        auth: Authentication configuration
        **kwargs: Additional configuration options
        
    Returns:
        DXTradeClient instance
        
    Example:
        ```python
        from dxtrade import create_client
        
        client = create_client(
            environment="demo",
            auth={"type": "session", "token": "your-token"}
        )
        ```
    """
    return DXTradeClient(environment=environment, auth=auth, **kwargs)


def create_demo_client(auth: AuthConfig, **kwargs) -> DXTradeClient:
    """Create demo client with sensible defaults.
    
    Args:
        auth: Authentication configuration
        **kwargs: Additional configuration options
        
    Returns:
        DXTradeClient instance configured for demo environment
    """
    return create_client(environment="demo", auth=auth, **kwargs)


def create_live_client(auth: AuthConfig, **kwargs) -> DXTradeClient:
    """Create live client with sensible defaults.
    
    Args:
        auth: Authentication configuration
        **kwargs: Additional configuration options
        
    Returns:
        DXTradeClient instance configured for live environment
    """
    return create_client(environment="live", auth=auth, **kwargs)


def create_rest_only_client(
    environment: Environment = "demo",
    auth: Optional[AuthConfig] = None,
    **kwargs
) -> DXTradeClient:
    """Create REST-only client (no WebSocket).
    
    Args:
        environment: Trading environment
        auth: Authentication configuration
        **kwargs: Additional configuration options
        
    Returns:
        DXTradeClient instance without WebSocket support
    """
    kwargs["enable_websocket"] = False
    return create_client(environment=environment, auth=auth, **kwargs)