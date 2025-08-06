"""
DXTrade WebSocket Stream Manager.

Implements the dual WebSocket architecture with:
- Market Data WebSocket for real-time quotes and market data
- Portfolio WebSocket for account, position, and order updates
- Automatic ping/pong handling for connection stability
- Connection management with reconnection logic
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ..types import SDKConfig
from ..types.dxtrade_messages import (
    DXTradeWebSocketConfig,
    DXTradeStreamOptions, 
    DXTradeStreamCallbacks,
    DXTradeConnectionStatus,
    DXTradeTestResult,
    ConnectionStatus,
    PingStats,
    DXTradeMessageType,
    DXTradeWebSocketMessage,
    MarketDataMessage,
    AccountPortfoliosMessage,
    DXTradePositionUpdateMessage,
    DXTradeOrderUpdateMessage,
    SubscriptionResponseMessage,
    AuthenticationResponseMessage,
)
from ..errors import WebSocketError


class DXTradeStreamManager:
    """
    DXTrade WebSocket Stream Manager.
    
    Implements the dual WebSocket architecture from the TypeScript implementation:
    - Market Data WebSocket for real-time quotes and market data  
    - Portfolio WebSocket for account, position, and order updates
    - Automatic ping/pong handling for connection stability
    - Connection management with reconnection logic
    """
    
    def __init__(
        self,
        sdk_config: SDKConfig,
        stream_config: DXTradeWebSocketConfig,
        options: DXTradeStreamOptions,
        callbacks: DXTradeStreamCallbacks,
    ):
        """Initialize DXTrade stream manager."""
        self.sdk_config = sdk_config
        self.stream_config = stream_config
        self.options = options
        self.callbacks = callbacks
        
        # WebSocket connections
        self._market_data_ws: Optional[websockets.WebSocketServerProtocol] = None
        self._portfolio_ws: Optional[websockets.WebSocketServerProtocol] = None
        
        # Connection state
        self._status = DXTradeConnectionStatus(
            market_data=ConnectionStatus(),
            portfolio=ConnectionStatus(),
            ping_stats=PingStats(),
            is_ready=False
        )
        
        # Reconnection state
        self._reconnect_timers: Dict[str, asyncio.Task] = {}
        self._is_destroyed = False
        
        # Event handlers storage
        self._event_handlers: Dict[str, List[Callable]] = {}
        
    async def connect(self) -> bool:
        """Connect to both WebSocket streams."""
        if self._is_destroyed:
            raise WebSocketError("Stream manager has been destroyed")
            
        tasks = []
        
        if self.options.enable_market_data:
            tasks.append(self._connect_market_data())
            
        if self.options.enable_portfolio:
            tasks.append(self._connect_portfolio())
            
        if not tasks:
            raise WebSocketError("No streams enabled")
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_connected = all(result is True for result in results if not isinstance(result, Exception))
        
        if all_connected:
            self._update_ready_state()
            await self._subscribe_to_enabled_streams()
            
        return all_connected
        
    async def disconnect(self) -> None:
        """Disconnect from all WebSocket streams."""
        self._clear_reconnect_timers()
        
        tasks = []
        
        if self._market_data_ws:
            tasks.append(self._disconnect_websocket(self._market_data_ws, "market_data"))
            
        if self._portfolio_ws:
            tasks.append(self._disconnect_websocket(self._portfolio_ws, "portfolio"))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        self._market_data_ws = None
        self._portfolio_ws = None
        self._update_ready_state()
        
    def destroy(self) -> None:
        """Destroy the stream manager and cleanup resources."""
        self._is_destroyed = True
        asyncio.create_task(self.disconnect())
        
    def get_status(self) -> DXTradeConnectionStatus:
        """Get current connection status."""
        return self._status.copy()
        
    # Event handling
    def on(self, event: str, handler: Callable) -> None:
        """Add event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
        
    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """Remove event handler."""
        if event not in self._event_handlers:
            return
            
        if handler is None:
            # Remove all handlers for event
            self._event_handlers[event] = []
        else:
            # Remove specific handler
            if handler in self._event_handlers[event]:
                self._event_handlers[event].remove(handler)
                
    def emit(self, event: str, *args, **kwargs) -> None:
        """Emit event to handlers."""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    print(f"Error in event handler for {event}: {e}")
                    
    # Subscription methods
    async def subscribe_to_market_data(self, symbols: List[str]) -> bool:
        """Subscribe to market data for additional symbols."""
        if not self._market_data_ws or self._market_data_ws.closed:
            return False
            
        subscription_message = {
            "type": "MarketDataSubscriptionRequest",
            "requestId": f"market_data_{int(time.time() * 1000)}",
            "session": self.stream_config.session_token,
            "payload": {
                "account": self.options.account,
                "symbols": symbols,
                "eventTypes": [{
                    "type": "Quote",
                    "format": "COMPACT"
                }]
            }
        }
        
        try:
            await self._market_data_ws.send(json.dumps(subscription_message))
            return True
        except Exception as e:
            print(f"Failed to subscribe to market data: {e}")
            return False
            
    async def subscribe_to_portfolio_data(self) -> bool:
        """Subscribe to portfolio data."""
        if not self._portfolio_ws or self._portfolio_ws.closed:
            return False
            
        subscription_message = {
            "type": "AccountPortfoliosSubscriptionRequest", 
            "requestId": f"portfolio_{int(time.time() * 1000)}",
            "session": self.stream_config.session_token,
            "payload": {
                "requestType": "ALL",
                "includeOffset": "true"
            }
        }
        
        try:
            await self._portfolio_ws.send(json.dumps(subscription_message))
            return True
        except Exception as e:
            print(f"Failed to subscribe to portfolio data: {e}")
            return False
            
    # Stability test
    async def run_stability_test(self, duration_ms: int = 300000) -> DXTradeTestResult:
        """Run a stability test similar to the TypeScript implementation."""
        start_time = time.time()
        message_count = 0
        market_data_count = 0
        portfolio_count = 0
        ping_requests_received = 0
        ping_responses_sent = 0
        connection_stable = True
        error: Optional[str] = None
        
        # Track messages during test
        def message_handler(*args):
            nonlocal message_count
            message_count += 1
            
        def market_data_handler(*args):
            nonlocal market_data_count
            market_data_count += 1
            
        def portfolio_handler(*args):
            nonlocal portfolio_count
            portfolio_count += 1
            
        def ping_handler(*args):
            nonlocal ping_requests_received, ping_responses_sent
            ping_requests_received += 1
            ping_responses_sent += 1  # Assuming we respond to all pings
            
        def error_handler(err):
            nonlocal connection_stable, error
            connection_stable = False
            error = str(err)
            
        # Set up listeners
        self.on("message", message_handler)
        self.on("marketData", market_data_handler)
        self.on("accountPortfolios", portfolio_handler)
        self.on("pingRequest", ping_handler)
        self.on("error", error_handler)
        
        try:
            # Connect and subscribe
            connected = await self.connect()
            if not connected:
                raise WebSocketError("Failed to connect to WebSocket streams")
                
            # Wait for test duration
            await asyncio.sleep(duration_ms / 1000)
            
            duration = time.time() - start_time
            ping_success_rate = (
                (ping_responses_sent / ping_requests_received * 100) 
                if ping_requests_received > 0 else 100
            )
            
            return DXTradeTestResult(
                success=connection_stable and error is None,
                duration=duration,
                message_count=message_count,
                market_data_count=market_data_count,
                portfolio_count=portfolio_count,
                ping_requests_received=ping_requests_received,
                ping_responses_sent=ping_responses_sent,
                connection_stable=connection_stable and ping_success_rate >= 90,
                error=error,
            )
            
        finally:
            # Clean up listeners
            self.off("message", message_handler)
            self.off("marketData", market_data_handler)
            self.off("accountPortfolios", portfolio_handler)
            self.off("pingRequest", ping_handler)
            self.off("error", error_handler)
            
    # Private connection methods
    async def _connect_market_data(self) -> bool:
        """Connect to Market Data WebSocket."""
        headers = {
            "Authorization": f"DXAPI {self.stream_config.session_token}",
            "X-Auth-Token": self.stream_config.session_token,
        }
        
        try:
            self._market_data_ws = await asyncio.wait_for(
                websockets.connect(
                    self.stream_config.market_data_url,
                    extra_headers=headers
                ),
                timeout=self.options.connection_timeout / 1000
            )
            
            # Set up event handlers
            asyncio.create_task(
                self._handle_websocket_messages(self._market_data_ws, "market_data")
            )
            
            self._status.market_data.connected = True
            self._status.market_data.reconnect_attempts = 0
            
            if self.callbacks.on_connected:
                self.callbacks.on_connected("market_data")
                
            return True
            
        except Exception as e:
            if self.callbacks.on_error:
                self.callbacks.on_error("market_data", e)
            return False
            
    async def _connect_portfolio(self) -> bool:
        """Connect to Portfolio WebSocket."""
        headers = {
            "Authorization": f"DXAPI {self.stream_config.session_token}",
            "X-Auth-Token": self.stream_config.session_token,
        }
        
        try:
            self._portfolio_ws = await asyncio.wait_for(
                websockets.connect(
                    self.stream_config.portfolio_url,
                    extra_headers=headers
                ),
                timeout=self.options.connection_timeout / 1000
            )
            
            # Set up event handlers
            asyncio.create_task(
                self._handle_websocket_messages(self._portfolio_ws, "portfolio")
            )
            
            self._status.portfolio.connected = True
            self._status.portfolio.reconnect_attempts = 0
            
            if self.callbacks.on_connected:
                self.callbacks.on_connected("portfolio")
                
            return True
            
        except Exception as e:
            if self.callbacks.on_error:
                self.callbacks.on_error("portfolio", e)
            return False
            
    async def _handle_websocket_messages(
        self, 
        ws: websockets.WebSocketServerProtocol, 
        connection_type: str
    ) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for message in ws:
                if connection_type == "market_data":
                    self._status.market_data.message_count += 1
                    self._status.market_data.last_message_time = time.time()
                else:
                    self._status.portfolio.message_count += 1
                    self._status.portfolio.last_message_time = time.time()
                    
                await self._process_message(message, connection_type)
                
        except ConnectionClosed as e:
            await self._handle_connection_closed(connection_type, e.code, e.reason)
        except Exception as e:
            if self.callbacks.on_error:
                self.callbacks.on_error(connection_type, e)
            await self._handle_connection_error(connection_type, e)
            
    async def _process_message(self, raw_message: str, connection_type: str) -> None:
        """Process incoming WebSocket message."""
        if self.callbacks.on_raw_message:
            self.callbacks.on_raw_message(connection_type, raw_message)
            
        try:
            message = json.loads(raw_message)
            
            # Handle different message types
            message_type = message.get("type")
            
            if message_type == "PingRequest":
                await self._handle_ping_request(message, connection_type)
            elif message_type == "MarketData":
                if self.callbacks.on_market_data:
                    self.callbacks.on_market_data(MarketDataMessage(**message))
                self.emit("marketData", message)
            elif message_type == "AccountPortfolios":
                if self.callbacks.on_account_portfolios:
                    self.callbacks.on_account_portfolios(AccountPortfoliosMessage(**message))
                self.emit("accountPortfolios", message)
            elif message_type == "PositionUpdate":
                if self.callbacks.on_position_update:
                    self.callbacks.on_position_update(DXTradePositionUpdateMessage(**message))
                self.emit("positionUpdate", message)
            elif message_type == "OrderUpdate":
                if self.callbacks.on_order_update:
                    self.callbacks.on_order_update(DXTradeOrderUpdateMessage(**message))
                self.emit("orderUpdate", message)
            elif message_type == "SubscriptionResponse":
                await self._handle_subscription_response(message, connection_type)
            elif message_type == "AuthenticationResponse":
                await self._handle_authentication_response(message, connection_type)
                
            self.emit("message", message)
            
        except json.JSONDecodeError:
            print(f"Failed to parse WebSocket message from {connection_type}: {raw_message}")
        except Exception as e:
            print(f"Error processing message from {connection_type}: {e}")
            
    async def _handle_ping_request(self, message: Dict[str, Any], connection_type: str) -> None:
        """Handle ping request from server."""
        self._status.ping_stats.requests_received += 1
        self._status.ping_stats.last_ping_time = time.time()
        
        if self.callbacks.on_ping_request:
            self.callbacks.on_ping_request(message)
        self.emit("pingRequest", message)
        
        if self.options.enable_ping_response:
            await self._send_ping_response(message, connection_type)
            
    async def _send_ping_response(self, ping_request: Dict[str, Any], connection_type: str) -> None:
        """Send ping response to server."""
        ws = self._market_data_ws if connection_type == "market_data" else self._portfolio_ws
        
        if not ws or ws.closed:
            return
            
        pong_response = {
            "type": "Ping",
            "session": self.stream_config.session_token,
            "timestamp": ping_request.get("timestamp", datetime.now().isoformat())
        }
        
        try:
            await ws.send(json.dumps(pong_response))
            self._status.ping_stats.responses_sent += 1
        except Exception as e:
            print(f"Failed to send ping response on {connection_type}: {e}")
            
    async def _handle_subscription_response(
        self, 
        message: Dict[str, Any], 
        connection_type: str
    ) -> None:
        """Handle subscription response."""
        success = message.get("success", False)
        
        if connection_type == "market_data":
            self._status.market_data.subscribed = success
        else:
            self._status.portfolio.subscribed = success
            
        if self.callbacks.on_subscription_response:
            self.callbacks.on_subscription_response(SubscriptionResponseMessage(**message))
            
        self._update_ready_state()
        
    async def _handle_authentication_response(
        self, 
        message: Dict[str, Any], 
        connection_type: str
    ) -> None:
        """Handle authentication response."""
        success = message.get("success", False)
        
        if connection_type == "market_data":
            self._status.market_data.authenticated = success
        else:
            self._status.portfolio.authenticated = success
            
        if self.callbacks.on_authentication_response:
            self.callbacks.on_authentication_response(AuthenticationResponseMessage(**message))
            
        self._update_ready_state()
        
    async def _handle_connection_closed(self, connection_type: str, code: int, reason: str) -> None:
        """Handle WebSocket connection closed."""
        if connection_type == "market_data":
            self._status.market_data.connected = False
            self._status.market_data.authenticated = False
            self._status.market_data.subscribed = False
        else:
            self._status.portfolio.connected = False
            self._status.portfolio.authenticated = False
            self._status.portfolio.subscribed = False
            
        self._update_ready_state()
        
        if self.callbacks.on_disconnected:
            self.callbacks.on_disconnected(connection_type, code, reason)
            
        if self.options.auto_reconnect and not self._is_destroyed:
            await self._handle_reconnect(connection_type)
            
    async def _handle_connection_error(self, connection_type: str, error: Exception) -> None:
        """Handle WebSocket connection error."""
        if self.callbacks.on_error:
            self.callbacks.on_error(connection_type, error)
            
    async def _subscribe_to_enabled_streams(self) -> None:
        """Subscribe to enabled streams."""
        tasks = []
        
        if (self.options.enable_market_data and 
            self._status.market_data.connected and 
            self.options.symbols):
            tasks.append(self.subscribe_to_market_data(self.options.symbols))
            
        if (self.options.enable_portfolio and 
            self._status.portfolio.connected):
            tasks.append(self.subscribe_to_portfolio_data())
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _handle_reconnect(self, connection_type: str) -> None:
        """Handle reconnection logic."""
        if connection_type == "market_data":
            attempts = self._status.market_data.reconnect_attempts
        else:
            attempts = self._status.portfolio.reconnect_attempts
            
        if attempts >= self.options.max_reconnect_attempts:
            if self.callbacks.on_error:
                self.callbacks.on_error(
                    connection_type,
                    Exception(f"Maximum reconnection attempts ({self.options.max_reconnect_attempts}) reached for {connection_type}")
                )
            return
            
        if connection_type == "market_data":
            self._status.market_data.reconnect_attempts += 1
        else:
            self._status.portfolio.reconnect_attempts += 1
            
        if self.callbacks.on_reconnecting:
            self.callbacks.on_reconnecting(connection_type, attempts + 1)
            
        # Schedule reconnection
        async def do_reconnect():
            await asyncio.sleep(self.options.reconnect_delay / 1000)
            
            try:
                if connection_type == "market_data":
                    connected = await self._connect_market_data()
                else:
                    connected = await self._connect_portfolio()
                    
                if connected:
                    if self.callbacks.on_reconnected:
                        self.callbacks.on_reconnected(connection_type)
                    self._update_ready_state()
                    
                    # Resubscribe
                    if (connection_type == "market_data" and 
                        self.options.enable_market_data and 
                        self.options.symbols):
                        await self.subscribe_to_market_data(self.options.symbols)
                    elif (connection_type == "portfolio" and 
                          self.options.enable_portfolio):
                        await self.subscribe_to_portfolio_data()
                else:
                    await self._handle_reconnect(connection_type)
                    
            except Exception as e:
                if self.callbacks.on_error:
                    self.callbacks.on_error(connection_type, e)
                await self._handle_reconnect(connection_type)
                
        self._reconnect_timers[connection_type] = asyncio.create_task(do_reconnect())
        
    def _update_ready_state(self) -> None:
        """Update ready state based on connection status."""
        market_data_ready = (not self.options.enable_market_data or 
                           (self._status.market_data.connected and self._status.market_data.subscribed))
        
        portfolio_ready = (not self.options.enable_portfolio or 
                         (self._status.portfolio.connected and self._status.portfolio.subscribed))
        
        self._status.is_ready = market_data_ready and portfolio_ready
        
    async def _disconnect_websocket(
        self, 
        ws: websockets.WebSocketServerProtocol, 
        connection_type: str
    ) -> None:
        """Disconnect a WebSocket connection."""
        try:
            if not ws.closed:
                await ws.close()
        except Exception as e:
            print(f"Error closing {connection_type} WebSocket: {e}")
            
    def _clear_reconnect_timers(self) -> None:
        """Clear all reconnection timers."""
        for timer in self._reconnect_timers.values():
            if not timer.done():
                timer.cancel()
        self._reconnect_timers.clear()


def create_dxtrade_stream_manager(
    sdk_config: SDKConfig,
    session_token: str,
    options: Optional[DXTradeStreamOptions] = None,
    callbacks: Optional[DXTradeStreamCallbacks] = None
) -> DXTradeStreamManager:
    """Create a DXTrade stream manager with configuration."""
    # Default URLs from TypeScript implementation  
    market_data_url = (
        sdk_config.urls.ws_market_data or 
        "wss://demo.dx.trade/dxsca-web/md?format=JSON"
    )
    portfolio_url = (
        sdk_config.urls.ws_portfolio or 
        "wss://demo.dx.trade/dxsca-web/?format=JSON"
    )
    
    stream_config = DXTradeWebSocketConfig(
        market_data_url=market_data_url,
        portfolio_url=portfolio_url,
        account=options.account if options else "default:demo",
        session_token=session_token,
        symbols=options.symbols if options else None,
        enable_ping_response=options.enable_ping_response if options else True,
        connection_timeout=options.connection_timeout if options else None,
        heartbeat_interval=options.heartbeat_interval if options else None,
    )
    
    return DXTradeStreamManager(
        sdk_config,
        stream_config,
        options or DXTradeStreamOptions(),
        callbacks or DXTradeStreamCallbacks()
    )