"""
Unified WebSocket Stream for DXTrade.

Provides a unified interface for both market data and portfolio WebSocket streams
with automatic connection management and data aggregation.
"""

import asyncio
import json
from typing import Any, Dict, Optional, Callable, List

from ..types import SDKConfig
from .stream_manager import DXTradeStreamManager, create_dxtrade_stream_manager
from ..types.dxtrade_messages import DXTradeStreamOptions, DXTradeStreamCallbacks
from ..errors import WebSocketError


class StreamOptions:
    """Options for unified WebSocket stream."""
    
    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        account: Optional[str] = None,
        enable_market_data: bool = True,
        enable_portfolio: bool = True,
        auto_reconnect: bool = True,
        connection_timeout: int = 30000,
        max_reconnect_attempts: int = 5,
    ):
        """Initialize stream options."""
        self.symbols = symbols or ["EUR/USD", "XAU/USD", "GBP/USD", "USD/JPY"]
        self.account = account
        self.enable_market_data = enable_market_data
        self.enable_portfolio = enable_portfolio
        self.auto_reconnect = auto_reconnect
        self.connection_timeout = connection_timeout
        self.max_reconnect_attempts = max_reconnect_attempts


class StreamCallbacks:
    """Callbacks for unified WebSocket stream."""
    
    def __init__(
        self,
        on_quote: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_account_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_position_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_order_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_connected: Optional[Callable[[str], None]] = None,
        on_disconnected: Optional[Callable[[str, int, str], None]] = None,
        on_error: Optional[Callable[[str, Exception], None]] = None,
        on_reconnected: Optional[Callable[[str], None]] = None,
    ):
        """Initialize stream callbacks."""
        self.on_quote = on_quote
        self.on_account_update = on_account_update
        self.on_position_update = on_position_update
        self.on_order_update = on_order_update
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.on_error = on_error
        self.on_reconnected = on_reconnected


class UnifiedWebSocketStream:
    """
    Unified WebSocket stream for DXTrade.
    
    Provides a single interface for both market data and portfolio WebSocket
    connections with automatic data routing and connection management.
    """
    
    def __init__(
        self,
        config: SDKConfig,
        session_token: str,
        options: StreamOptions,
        callbacks: StreamCallbacks,
    ):
        """Initialize unified WebSocket stream."""
        self.config = config
        self.session_token = session_token
        self.options = options
        self.callbacks = callbacks
        
        # Internal stream manager
        self._stream_manager: Optional[DXTradeStreamManager] = None
        self._is_connected = False
        
    async def connect(self) -> bool:
        """Connect to WebSocket streams."""
        if self._stream_manager:
            await self._stream_manager.disconnect()
            
        # Convert options to DXTradeStreamOptions
        dx_options = DXTradeStreamOptions(
            symbols=self.options.symbols,
            account=self.options.account,
            enable_market_data=self.options.enable_market_data,
            enable_portfolio=self.options.enable_portfolio,
            auto_reconnect=self.options.auto_reconnect,
            connection_timeout=self.options.connection_timeout,
            max_reconnect_attempts=self.options.max_reconnect_attempts,
        )
        
        # Convert callbacks to DXTradeStreamCallbacks
        dx_callbacks = DXTradeStreamCallbacks(
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            on_error=self._on_error,
            on_market_data=self._on_market_data,
            on_account_portfolios=self._on_account_portfolios,
            on_position_update=self._on_position_update,
            on_order_update=self._on_order_update,
            on_reconnected=self._on_reconnected,
        )
        
        # Create and connect stream manager
        self._stream_manager = create_dxtrade_stream_manager(
            self.config,
            self.session_token,
            dx_options,
            dx_callbacks
        )
        
        self._is_connected = await self._stream_manager.connect()
        return self._is_connected
        
    async def disconnect(self) -> None:
        """Disconnect from WebSocket streams."""
        if self._stream_manager:
            await self._stream_manager.disconnect()
        self._is_connected = False
        
    def is_connected(self) -> bool:
        """Check if stream is connected."""
        return self._is_connected
        
    def get_status(self) -> Dict[str, Any]:
        """Get stream status."""
        if not self._stream_manager:
            return {
                "connected": False,
                "ready": False,
                "market_data": {"connected": False},
                "portfolio": {"connected": False},
            }
            
        status = self._stream_manager.get_status()
        return {
            "connected": self._is_connected,
            "ready": status.is_ready,
            "market_data": {
                "connected": status.market_data.connected,
                "message_count": status.market_data.message_count,
            },
            "portfolio": {
                "connected": status.portfolio.connected,
                "message_count": status.portfolio.message_count,
            },
            "ping_stats": {
                "requests_received": status.ping_stats.requests_received,
                "responses_sent": status.ping_stats.responses_sent,
            }
        }
        
    async def subscribe_to_symbols(self, symbols: List[str]) -> bool:
        """Subscribe to additional market data symbols."""
        if not self._stream_manager:
            return False
        return await self._stream_manager.subscribe_to_market_data(symbols)
        
    def destroy(self) -> None:
        """Destroy stream and cleanup resources."""
        if self._stream_manager:
            self._stream_manager.destroy()
            
    # Internal callback handlers
    def _on_connected(self, connection_type: str) -> None:
        """Handle connection event."""
        if self.callbacks.on_connected:
            self.callbacks.on_connected(connection_type)
            
    def _on_disconnected(self, connection_type: str, code: int, reason: str) -> None:
        """Handle disconnection event."""
        self._is_connected = False
        if self.callbacks.on_disconnected:
            self.callbacks.on_disconnected(connection_type, code, reason)
            
    def _on_error(self, connection_type: str, error: Exception) -> None:
        """Handle error event."""
        if self.callbacks.on_error:
            self.callbacks.on_error(connection_type, error)
            
    def _on_reconnected(self, connection_type: str) -> None:
        """Handle reconnection event."""
        self._is_connected = True
        if self.callbacks.on_reconnected:
            self.callbacks.on_reconnected(connection_type)
            
    def _on_market_data(self, message) -> None:
        """Handle market data message."""
        # Extract quote data from market data message
        if hasattr(message, 'data') and self.callbacks.on_quote:
            self.callbacks.on_quote(message.data)
            
    def _on_account_portfolios(self, message) -> None:
        """Handle account portfolios message."""
        # Route to account update callback
        if hasattr(message, 'data') and self.callbacks.on_account_update:
            self.callbacks.on_account_update(message.data)
            
    def _on_position_update(self, message) -> None:
        """Handle position update message."""
        if hasattr(message, 'position') and self.callbacks.on_position_update:
            # Convert position to dict
            position_data = message.position.dict() if hasattr(message.position, 'dict') else message.position
            self.callbacks.on_position_update(position_data)
            
    def _on_order_update(self, message) -> None:
        """Handle order update message."""
        if hasattr(message, 'order') and self.callbacks.on_order_update:
            # Convert order to dict
            order_data = message.order.dict() if hasattr(message.order, 'dict') else message.order
            self.callbacks.on_order_update(order_data)


def start_unified_websocket_stream(
    config: SDKConfig,
    session_token: str,
    options: Optional[StreamOptions] = None,
    callbacks: Optional[StreamCallbacks] = None,
):
    """
    Start unified WebSocket stream (compatibility helper for TypeScript API).
    
    Returns a structure similar to the TypeScript version for compatibility.
    """
    stream = UnifiedWebSocketStream(
        config,
        session_token,
        options or StreamOptions(),
        callbacks or StreamCallbacks()
    )
    
    # Return TypeScript-compatible structure
    return {
        "client": stream,
        "stream": stream,
        "connect": stream.connect,
        "disconnect": stream.disconnect,
        "destroy": stream.destroy,
    }