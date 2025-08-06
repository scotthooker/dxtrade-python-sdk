"""
Minimal DXTrade Transport SDK - Pure connection, auth, and data passthrough.

This is a simplified transport layer that focuses on:
1. Authentication (session tokens)
2. Raw HTTP requests with auth headers
3. WebSocket subscriptions with raw message forwarding
4. No data modeling - returns raw JSON responses
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import urljoin

import aiohttp
import websockets
from dotenv import load_dotenv

from .env_config import load_config_from_env
from .auth import SessionHandler
from .models import SessionCredentials


logger = logging.getLogger(__name__)


class DXTradeTransport:
    """Minimal DXTrade transport client for raw API access."""
    
    def __init__(self, config=None):
        """Initialize transport client.
        
        Args:
            config: Optional SDK config, loads from env if None
        """
        if config is None:
            load_dotenv()
            config = load_config_from_env()
        
        self.config = config
        self.base_url = config.base_url
        self.websocket_url = getattr(config, 'websocket_url', None)
        
        # Session authentication
        self.credentials = SessionCredentials(
            username=config.auth.username,
            password=config.auth.password,
            domain=config.auth.domain
        )
        self.auth_handler = SessionHandler(self.credentials)
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket connections
        self._websockets: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._subscriptions: Dict[str, Callable] = {}
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        
        # Application-level ping/pong tracking
        self._ping_stats: Dict[str, Dict] = {}
        self._enable_ping_logging: bool = True
        
        # WebSocket connection strategy tracking
        self._successful_strategies: Dict[str, str] = {}
        
        # Log websockets library version for debugging
        self._log_websockets_version()
    
    def _log_websockets_version(self):
        """Log websockets library version for debugging compatibility issues."""
        try:
            version = getattr(websockets, '__version__', 'unknown')
            logger.info(f"🔌 Using websockets library version: {version}")
            
            # Log compatibility information
            if version != 'unknown':
                major_version = int(version.split('.')[0]) if version.split('.')[0].isdigit() else 0
                if major_version >= 11:
                    logger.debug("WebSocket library supports modern additional_headers parameter")
                elif major_version >= 9:
                    logger.debug("WebSocket library supports legacy extra_headers parameter")
                else:
                    logger.warning("WebSocket library version may have compatibility issues - consider upgrading to 11.0+")
                    
        except Exception as e:
            logger.debug(f"Could not determine websockets version: {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_session(self):
        """Ensure HTTP session exists."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
    
    async def close(self):
        """Close all connections."""
        # Close WebSocket connections
        for channel in list(self._websockets.keys()):
            await self.unsubscribe(channel)
        
        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None
    
    async def authenticate(self) -> str:
        """Authenticate and return session token.
        
        Returns:
            Session token string
            
        Raises:
            Exception: Authentication failed
        """
        await self._ensure_session()
        
        # Manual authentication since auth handler expects different client
        login_data = {
            "username": self.credentials.username,
            "password": self.credentials.password,
            "domain": self.credentials.domain or "default",
        }
        
        # Use explicit login URL if available
        login_url = getattr(self.config.endpoints, 'login', '/login')
        if not login_url.startswith('http'):
            login_url = urljoin(self.base_url + '/', login_url.lstrip('/'))
        
        logger.debug(f"Authenticating at {login_url}")
        
        async with self._session.post(login_url, json=login_data) as response:
            response.raise_for_status()
            data = await response.json()
            
            # Get sessionToken from response
            session_token = data.get("sessionToken")
            if not session_token:
                error_msg = data.get("message") or "Login failed - no session token received"
                raise Exception(error_msg)
            
            # Store token in auth handler
            self.auth_handler._session_token = session_token
            self.auth_handler._last_login = time.time()
            self.auth_handler._token_expires_at = time.time() + 3600  # 1 hour
            
            logger.info("Authentication successful")
            return session_token
    
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> Union[Dict[str, Any], list, str]:
        """Make raw HTTP request with authentication.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/accounts", "/orders")
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            Raw response data (JSON parsed if possible)
        """
        await self._ensure_session()
        
        # Ensure we have a valid session token
        token = self.auth_handler.get_session_token()
        if not token:
            token = await self.authenticate()
        
        # Build full URL
        if endpoint.startswith('http'):
            url = endpoint
        else:
            url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        # Add auth headers
        headers = kwargs.pop('headers', {})
        if token:
            headers['X-Auth-Token'] = token
        
        # Make request
        logger.debug(f"Making {method} request to {url}")
        async with self._session.request(method, url, headers=headers, **kwargs) as response:
            # Handle authentication errors
            if response.status == 401:
                logger.info("Got 401, refreshing session token")
                token = await self.authenticate()
                
                # Update headers with new token
                if token:
                    headers['X-Auth-Token'] = token
                
                # Retry with new token
                async with self._session.request(method, url, headers=headers, **kwargs) as retry_response:
                    return await self._parse_response(retry_response)
            
            return await self._parse_response(response)
    
    async def _parse_response(self, response: aiohttp.ClientResponse) -> Union[Dict, list, str]:
        """Parse response, returning raw data."""
        # Raise for HTTP errors
        response.raise_for_status()
        
        # Try to parse as JSON first
        content_type = response.headers.get('content-type', '')
        if 'json' in content_type:
            try:
                return await response.json()
            except Exception:
                pass
        
        # Fall back to text
        return await response.text()
    
    async def subscribe(self, channel: str, callback: Callable[[dict], None], ws_url: Optional[str] = None):
        """Subscribe to WebSocket channel with raw message forwarding.
        
        Args:
            channel: Channel name (e.g., "quotes", "portfolio")  
            callback: Function to call with raw messages
            ws_url: Override WebSocket URL
        """
        if channel in self._websockets:
            logger.warning(f"Already subscribed to channel: {channel}")
            return
        
        # Use provided URL or build from config
        if ws_url is None:
            if hasattr(self.config, 'websocket') and self.config.websocket:
                if channel == "quotes" or channel == "market_data":
                    ws_url = getattr(self.config.websocket, 'market_data_url', None)
                else:
                    ws_url = getattr(self.config.websocket, 'portfolio_url', None)
                    
                # Fallback to base URL construction
                if not ws_url and hasattr(self.config.websocket, 'base_url'):
                    ws_url = self.config.websocket.base_url
            
            if not ws_url:
                raise ValueError(f"No WebSocket URL configured for channel: {channel}")
        
        logger.info(f"Subscribing to {channel} at {ws_url}")
        
        # Store subscription
        self._subscriptions[channel] = callback
        
        # Start WebSocket connection task
        task = asyncio.create_task(self._websocket_handler(channel, ws_url))
        self._ws_tasks[channel] = task
    
    async def _establish_websocket_connection(self, ws_url: str, token: Optional[str], channel: str):
        """Establish WebSocket connection with multiple compatibility approaches.
        
        This method tries different WebSocket connection approaches in order of preference
        to ensure compatibility with different websockets library versions:
        
        1. Modern approach: additional_headers (websockets 11.0+)
        2. Legacy approach: extra_headers (websockets 9.0-10.x)  
        3. Fallback approach: subprotocol-based auth
        4. Last resort: post-connection authentication
        
        Args:
            ws_url: WebSocket URL to connect to
            token: Authentication token (if available)
            channel: Channel name for logging
            
        Returns:
            WebSocket connection or None if all approaches failed
        """
        connection_approaches = [
            ("additional_headers", self._connect_with_additional_headers),
            ("extra_headers", self._connect_with_extra_headers),
            ("subprotocol_auth", self._connect_with_subprotocol_auth),
            ("post_connection_auth", self._connect_with_post_connection_auth),
        ]
        
        last_error = None
        
        for approach_name, connect_func in connection_approaches:
            try:
                logger.debug(f"Trying WebSocket connection approach: {approach_name} for {channel}")
                websocket = await connect_func(ws_url, token)
                if websocket:
                    logger.info(f"✅ WebSocket connected using {approach_name} for {channel}")
                    # Track successful strategy for this channel
                    self._successful_strategies[channel] = approach_name
                    return websocket
                    
            except Exception as e:
                last_error = e
                logger.debug(f"WebSocket approach {approach_name} failed for {channel}: {e}")
                continue
        
        # All approaches failed
        logger.error(f"❌ All WebSocket connection approaches failed for {channel}")
        if last_error:
            logger.error(f"Last error: {last_error}")
        
        return None
    
    async def _connect_with_additional_headers(self, ws_url: str, token: Optional[str]):
        """Connect using additional_headers parameter (websockets 11.0+)."""
        try:
            headers = {}
            if token:
                headers['X-Auth-Token'] = token
                
            return await websockets.connect(ws_url, additional_headers=headers)
        except TypeError as e:
            if 'additional_headers' in str(e):
                raise Exception("additional_headers parameter not supported by this websockets version")
            raise
    
    async def _connect_with_extra_headers(self, ws_url: str, token: Optional[str]):
        """Connect using extra_headers parameter (websockets 9.0-10.x)."""  
        try:
            headers = {}
            if token:
                headers['X-Auth-Token'] = token
                
            return await websockets.connect(ws_url, extra_headers=headers)
        except TypeError as e:
            if 'extra_headers' in str(e):
                raise Exception("extra_headers parameter not supported by this websockets version")
            raise
    
    async def _connect_with_subprotocol_auth(self, ws_url: str, token: Optional[str]):
        """Connect using subprotocol for authentication (fallback approach)."""
        try:
            subprotocols = []
            if token:
                # Encode token in subprotocol (some servers support this)
                subprotocols = [f"auth.{token}"]
                
            return await websockets.connect(ws_url, subprotocols=subprotocols)
        except Exception as e:
            # Add context to subprotocol failures
            raise Exception(f"Subprotocol authentication failed: {e}")
    
    async def _connect_with_post_connection_auth(self, ws_url: str, token: Optional[str]):
        """Connect without headers and authenticate after connection (last resort)."""
        try:
            websocket = await websockets.connect(ws_url)
            
            if token:
                # Send authentication message after connection
                auth_message = {
                    "type": "authenticate", 
                    "token": token,
                    "channel": "auth"
                }
                await websocket.send(json.dumps(auth_message))
                
                # Wait for auth response with timeout
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    auth_response = json.loads(response) if isinstance(response, str) else response
                    
                    if isinstance(auth_response, dict) and auth_response.get('type') == 'auth_success':
                        logger.debug("Post-connection authentication successful")
                    else:
                        logger.warning(f"Unexpected auth response: {auth_response}")
                        
                except asyncio.TimeoutError:
                    logger.warning("No authentication response received (continuing anyway)")
                except Exception as e:
                    logger.warning(f"Post-connection auth error: {e} (continuing anyway)")
            
            return websocket
            
        except Exception as e:
            raise Exception(f"Post-connection authentication approach failed: {e}")
    
    async def _websocket_handler(self, channel: str, ws_url: str):
        """Handle WebSocket connection and messages."""
        try:
            # Get auth token
            token = self.auth_handler.get_session_token()
            if not token:
                token = await self.authenticate()
            
            # Connect to WebSocket with compatibility fallbacks
            websocket = await self._establish_websocket_connection(ws_url, token, channel)
            if not websocket:
                raise Exception(f"Failed to establish WebSocket connection for {channel}")
            
            # Use connection in context manager style
            async with websocket:
                self._websockets[channel] = websocket
                logger.info(f"Connected to WebSocket for channel: {channel}")
                
                # Initialize ping stats for this channel
                self._ping_stats[channel] = {
                    'ping_requests_received': 0,
                    'ping_responses_sent': 0,
                    'last_ping_request': None,
                    'last_ping_response': None,
                    'session_extensions': 0
                }
                
                # Don't auto-send subscription - let user control it
                # await self._send_dxtrade_subscription(websocket, channel, token)
                
                # Listen for messages
                async for message in websocket:
                    try:
                        # Parse message as JSON if possible
                        if isinstance(message, str):
                            try:
                                data = json.loads(message)
                            except json.JSONDecodeError:
                                data = message
                        else:
                            data = message
                        
                        # Handle application-level ping/pong for session management
                        if await self._handle_ping_pong(channel, data, websocket, token):
                            continue  # Skip forwarding ping/pong messages to user callback
                        
                        # Forward raw message to callback
                        callback = self._subscriptions.get(channel)
                        if callback:
                            try:
                                callback(data)
                            except Exception as e:
                                logger.error(f"Error in callback for {channel}: {e}")
                        
                    except Exception as e:
                        logger.error(f"Error processing message for {channel}: {e}")
                        
        except Exception as e:
            logger.error(f"WebSocket error for {channel}: {e}")
        finally:
            # Clean up
            self._websockets.pop(channel, None)
            self._subscriptions.pop(channel, None)
            self._ping_stats.pop(channel, None)
            self._successful_strategies.pop(channel, None)
    
    async def _handle_ping_pong(self, channel: str, data: Union[dict, str], websocket: websockets.WebSocketClientProtocol, token: str) -> bool:
        """Handle application-level ping/pong for DXTrade session management.
        
        Args:
            channel: WebSocket channel name
            data: Parsed message data
            websocket: WebSocket connection
            token: Session token for ping response
            
        Returns:
            True if message was a ping/pong that was handled, False otherwise
        """
        try:
            # Check if this is a PingRequest from server
            if isinstance(data, dict) and data.get("type") == "PingRequest":
                timestamp = datetime.now()
                
                # Update stats
                stats = self._ping_stats.get(channel, {})
                stats['ping_requests_received'] = stats.get('ping_requests_received', 0) + 1
                stats['last_ping_request'] = timestamp
                stats['session_extensions'] = stats.get('session_extensions', 0) + 1
                
                # Log ping request activity
                if self._enable_ping_logging:
                    logger.info(f"🔄 Received PingRequest on channel '{channel}' - extending session")
                    logger.debug(f"   Ping stats: {stats['ping_requests_received']} requests, {stats['session_extensions']} extensions")
                
                # Send DXTrade Ping response with session and timestamp
                ping_response = {
                    "type": "Ping",
                    "session": token,
                    "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"  # ISO format with milliseconds
                }
                await websocket.send(json.dumps(ping_response))
                
                # Update response stats
                stats['ping_responses_sent'] = stats.get('ping_responses_sent', 0) + 1
                stats['last_ping_response'] = timestamp
                
                # Log successful ping response
                if self._enable_ping_logging:
                    logger.info(f"✅ Sent Ping response on channel '{channel}' - session extended")
                
                return True  # Message was handled, don't forward to user callback
                
            # Check if this is a string-based ping request (alternative format)
            elif isinstance(data, str) and data.lower() in ["pingrequest", "ping_request"]:
                timestamp = datetime.now()
                
                # Update stats
                stats = self._ping_stats.get(channel, {})
                stats['ping_requests_received'] = stats.get('ping_requests_received', 0) + 1
                stats['last_ping_request'] = timestamp
                stats['session_extensions'] = stats.get('session_extensions', 0) + 1
                
                # Log ping request activity
                if self._enable_ping_logging:
                    logger.info(f"🔄 Received string PingRequest '{data}' on channel '{channel}' - extending session")
                
                # Send string-based Ping response
                await websocket.send("Ping")
                
                # Update response stats
                stats['ping_responses_sent'] = stats.get('ping_responses_sent', 0) + 1
                stats['last_ping_response'] = timestamp
                
                # Log successful ping response
                if self._enable_ping_logging:
                    logger.info(f"✅ Sent Ping response on channel '{channel}' - session extended")
                
                return True  # Message was handled, don't forward to user callback
            
            return False  # Not a ping/pong message
            
        except Exception as e:
            logger.error(f"Error handling ping/pong for channel '{channel}': {e}")
            return False
    
    async def unsubscribe(self, channel: str):
        """Unsubscribe from WebSocket channel."""
        # Cancel task
        task = self._ws_tasks.pop(channel, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket
        websocket = self._websockets.pop(channel, None)
        if websocket:
            await websocket.close()
        
        # Remove subscription
        self._subscriptions.pop(channel, None)
        
        logger.info(f"Unsubscribed from channel: {channel}")
    
    def enable_ping_logging(self, enabled: bool = True):
        """Enable or disable ping/pong activity logging.
        
        Args:
            enabled: Whether to log ping/pong activity
        """
        self._enable_ping_logging = enabled
        if enabled:
            logger.info("✅ DXTrade application-level ping/pong logging enabled")
        else:
            logger.info("❌ DXTrade application-level ping/pong logging disabled")
    
    def get_ping_stats(self, channel: Optional[str] = None) -> Union[Dict, Dict[str, Dict]]:
        """Get ping/pong statistics for session monitoring.
        
        Args:
            channel: Optional channel name. If None, returns stats for all channels.
            
        Returns:
            Dictionary with ping/pong statistics
        """
        if channel:
            return self._ping_stats.get(channel, {})
        return self._ping_stats.copy()
    
    def get_session_health(self) -> Dict[str, Any]:
        """Get overall session health metrics for monitoring bridge status.
        
        Returns:
            Dictionary with session health information
        """
        total_ping_requests = sum(stats.get('ping_requests_received', 0) for stats in self._ping_stats.values())
        total_ping_responses = sum(stats.get('ping_responses_sent', 0) for stats in self._ping_stats.values())
        total_extensions = sum(stats.get('session_extensions', 0) for stats in self._ping_stats.values())
        
        active_channels = len(self._websockets)
        healthy_channels = len([ch for ch, ws in self._websockets.items() if self._is_websocket_healthy(ws)])
        
        return {
            'active_channels': active_channels,
            'healthy_channels': healthy_channels,
            'session_health': healthy_channels / active_channels if active_channels > 0 else 1.0,
            'total_ping_requests_received': total_ping_requests,
            'total_ping_responses_sent': total_ping_responses,
            'total_session_extensions': total_extensions,
            'ping_response_success_rate': total_ping_responses / total_ping_requests if total_ping_requests > 0 else 1.0,
            'last_activity': max([stats.get('last_ping_response') for stats in self._ping_stats.values() 
                                if stats.get('last_ping_response')], default=None),
            'channels': list(self._websockets.keys()),
            'connection_strategies': self._successful_strategies.copy(),
            'websockets_version': getattr(websockets, '__version__', 'unknown')
        }
    
    def _is_websocket_healthy(self, websocket: websockets.WebSocketClientProtocol) -> bool:
        """Check if WebSocket connection is healthy.
        
        Returns:
            True if WebSocket is connected and healthy
        """
        try:
            # Check WebSocket state with version compatibility handling
            # websockets 15.0.1+ uses different state management
            if hasattr(websocket, 'state'):
                # websockets 11.0+
                try:
                    from websockets import ConnectionState
                    return websocket.state == ConnectionState.OPEN
                except ImportError:
                    # Fallback for different websockets versions
                    return websocket.state == 1  # OPEN = 1 in older versions
            elif hasattr(websocket, 'open'):
                # websockets 9.0-10.x
                return websocket.open
            else:
                # Fallback: check if connection is not lost
                return not getattr(websocket, 'closed', True)
        except Exception as e:
            logger.debug(f"Error checking WebSocket health: {e}")
            return False

    def get_connection_strategies(self) -> Dict[str, str]:
        """Get the successful connection strategies for each channel.
        
        Returns:
            Dictionary mapping channel names to connection strategy names
        """
        return self._successful_strategies.copy()
    
    def check_websockets_compatibility(self) -> Dict[str, Any]:
        """Check websockets library compatibility and provide recommendations.
        
        Returns:
            Dictionary with compatibility information and recommendations
        """
        try:
            version = getattr(websockets, '__version__', 'unknown')
            
            if version == 'unknown':
                return {
                    'version': 'unknown',
                    'status': 'warning',
                    'message': 'Cannot determine websockets library version',
                    'recommendations': ['Check websockets installation', 'Consider reinstalling websockets>=12.0']
                }
            
            major_version = int(version.split('.')[0]) if version.split('.')[0].isdigit() else 0
            minor_version = int(version.split('.')[1]) if len(version.split('.')) > 1 and version.split('.')[1].isdigit() else 0
            
            if major_version >= 12:
                return {
                    'version': version,
                    'status': 'excellent',
                    'message': 'Full compatibility with all connection approaches',
                    'recommendations': []
                }
            elif major_version >= 11:
                return {
                    'version': version,
                    'status': 'good',
                    'message': 'Good compatibility with modern connection approaches',
                    'recommendations': ['Consider upgrading to websockets>=12.0 for best compatibility']
                }
            elif major_version >= 9:
                return {
                    'version': version,
                    'status': 'partial',
                    'message': 'Limited compatibility - fallback connection methods will be used',
                    'recommendations': ['Upgrade to websockets>=12.0 for improved reliability', 'Some connection approaches may not work']
                }
            else:
                return {
                    'version': version,
                    'status': 'poor',
                    'message': 'Poor compatibility - connection issues likely',
                    'recommendations': ['Upgrade to websockets>=12.0 immediately', 'Current version may cause connection failures']
                }
                
        except Exception as e:
            return {
                'version': 'error',
                'status': 'error',
                'message': f'Error checking websockets compatibility: {e}',
                'recommendations': ['Check websockets installation', 'Reinstall websockets>=12.0']
            }
    
    async def _send_dxtrade_subscription(self, websocket: websockets.WebSocketClientProtocol, channel: str, session_token: str):
        """Send DXTrade-specific subscription message.
        
        Args:
            websocket: WebSocket connection
            channel: Channel name (e.g., "quotes", "portfolio")
            session_token: Session token for authentication
        """
        import uuid
        from datetime import datetime
        
        request_id = str(uuid.uuid4())
        
        # Get account from config or environment
        account = getattr(self.config, 'account', None)
        if not account:
            # Try to get from auth config or use default format
            domain = getattr(self.config.auth, 'domain', 'default')
            account_name = os.getenv('DXTRADE_ACCOUNT_NAME', 'demo')
            account = f"{domain}:{account_name}"
        
        try:
            if channel in ["quotes", "market_data"]:
                # Market Data Subscription Request
                subscription_message = {
                    "type": "MarketDataSubscriptionRequest",
                    "requestId": request_id,
                    "session": session_token,
                    "payload": {
                        "account": account,
                        "symbols": ["EUR/USD", "GBP/USD"],  # Default symbols - should be configurable
                        "eventTypes": [{"type": "Quote", "format": "COMPACT"}]
                    }
                }
            else:
                # Account/Portfolio Subscription Request 
                subscription_message = {
                    "type": "AccountPortfoliosSubscriptionRequest", 
                    "requestId": request_id,
                    "session": session_token,
                    "payload": {
                        "account": account,
                        "eventTypes": [{"type": "Position", "format": "COMPACT"}]
                    }
                }
            
            logger.info(f"📡 Sending DXTrade subscription for {channel}: {account}")
            logger.debug(f"Subscription message: {subscription_message}")
            
            await websocket.send(json.dumps(subscription_message))
            
        except Exception as e:
            logger.error(f"Error sending DXTrade subscription for {channel}: {e}")
            # Fallback to simple subscription
            fallback_message = {"type": "subscribe", "channel": channel}
            await websocket.send(json.dumps(fallback_message))
    
    async def send_market_data_subscription(self, symbols: list, account: Optional[str] = None, event_types: Optional[list] = None) -> Optional[dict]:
        """Send market data subscription with DXTrade format.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ["EUR/USD", "GBP/USD"])
            account: Account identifier (defaults to config account)
            event_types: Event types to subscribe to (defaults to Quote COMPACT)
            
        Returns:
            Response message if any
        """
        import uuid
        
        # Get session token
        token = self.auth_handler.get_session_token()
        if not token:
            raise ValueError("No session token available")
        
        # Use provided account or get from config
        if not account:
            account = getattr(self.config, 'account', None)
            if not account:
                domain = getattr(self.config.auth, 'domain', 'default')
                account_name = os.getenv('DXTRADE_ACCOUNT_NAME', 'demo')
                account = f"{domain}:{account_name}"
        
        # Default event types
        if not event_types:
            event_types = [{"type": "Quote", "format": "COMPACT"}]
        
        # Create subscription message
        subscription_message = {
            "type": "MarketDataSubscriptionRequest",
            "requestId": str(uuid.uuid4()),
            "session": token,
            "payload": {
                "account": account,
                "symbols": symbols,
                "eventTypes": event_types
            }
        }
        
        # Send via quotes channel
        websocket = self._websockets.get("quotes")
        if not websocket:
            raise ValueError("Not connected to market data channel")
        
        await websocket.send(json.dumps(subscription_message))
        logger.info(f"📡 Sent market data subscription: {symbols} on account {account}")
        
        return None
    
    async def send_portfolio_subscription(self, account: Optional[str] = None, event_types: Optional[list] = None) -> Optional[dict]:
        """Send portfolio subscription with DXTrade format.
        
        Args:
            account: Account identifier (defaults to config account)
            event_types: Event types to subscribe to (defaults to Position COMPACT)
            
        Returns:
            Response message if any
        """
        import uuid
        
        # Get session token
        token = self.auth_handler.get_session_token()
        if not token:
            raise ValueError("No session token available")
        
        # Use provided account or get from config
        if not account:
            account = getattr(self.config, 'account', None)
            if not account:
                domain = getattr(self.config.auth, 'domain', 'default')
                account_name = os.getenv('DXTRADE_ACCOUNT_NAME', 'demo')
                account = f"{domain}:{account_name}"
        
        # Default event types
        if not event_types:
            event_types = [{"type": "Position", "format": "COMPACT"}]
        
        # Create subscription message
        subscription_message = {
            "type": "AccountPortfoliosSubscriptionRequest",
            "requestId": str(uuid.uuid4()),
            "session": token,
            "payload": {
                "account": account,
                "eventTypes": event_types
            }
        }
        
        # Send via portfolio channel
        websocket = self._websockets.get("portfolio")
        if not websocket:
            raise ValueError("Not connected to portfolio channel")
        
        await websocket.send(json.dumps(subscription_message))
        logger.info(f"📡 Sent portfolio subscription on account {account}")
        
        return None

    async def send_message(self, channel: str, message: Union[dict, str]) -> Optional[dict]:
        """Send raw message to WebSocket channel.
        
        Args:
            channel: Channel name
            message: Message to send (dict will be JSON encoded)
            
        Returns:
            Response message if any
        """
        websocket = self._websockets.get(channel)
        if not websocket:
            raise ValueError(f"Not connected to channel: {channel}")
        
        # Encode message if needed
        if isinstance(message, dict):
            message = json.dumps(message)
        
        await websocket.send(message)
        
        # Wait for response (optional - might want to handle differently)
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            if isinstance(response, str):
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    return response
            return response
        except asyncio.TimeoutError:
            return None
    
    # Convenience methods for common operations
    async def get_accounts(self) -> Union[Dict, list]:
        """Get accounts (raw data)."""
        return await self.request("GET", "/accounts")
    
    async def get_orders(self, account_id: Optional[str] = None) -> Union[Dict, list]:
        """Get orders (raw data)."""
        endpoint = "/orders"
        params = {}
        if account_id:
            params['account_id'] = account_id
        return await self.request("GET", endpoint, params=params)
    
    async def create_order(self, order_data: dict) -> dict:
        """Create order (raw data)."""
        return await self.request("POST", "/orders", json=order_data)
    
    async def get_positions(self, account_id: Optional[str] = None) -> Union[Dict, list]:
        """Get positions (raw data)."""
        endpoint = "/positions"
        params = {}
        if account_id:
            params['account_id'] = account_id
        return await self.request("GET", endpoint, params=params)
    
    async def get_quotes(self, symbols: Optional[list] = None) -> Union[Dict, list]:
        """Get quotes (raw data)."""
        endpoint = "/quotes"
        params = {}
        if symbols:
            params['symbols'] = ','.join(symbols)
        return await self.request("GET", endpoint, params=params)
    
    async def get_server_time(self) -> Union[Dict, str]:
        """Get server time (raw data)."""
        return await self.request("GET", "/time")


# Convenience factory function
def create_transport(config=None) -> DXTradeTransport:
    """Create transport client from environment or config.
    
    Args:
        config: Optional configuration, loads from env if None
        
    Returns:
        DXTradeTransport client
    """
    return DXTradeTransport(config)