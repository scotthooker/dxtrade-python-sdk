"""WebSocket Push API client with auto-reconnect."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any
from typing import AsyncIterator
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Union

import websockets
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed
from websockets.exceptions import InvalidURI
from websockets.exceptions import WebSocketException

from dxtrade.auth import AuthHandler
from dxtrade.errors import DXtradeConfigurationError
from dxtrade.errors import DXtradeDataError
from dxtrade.errors import DXtradeWebSocketError
from dxtrade.models import AccountEvent
from dxtrade.models import AnyEvent
from dxtrade.models import EventType
from dxtrade.models import HeartbeatEvent
from dxtrade.models import OrderEvent
from dxtrade.models import PositionEvent
from dxtrade.models import PriceEvent
from dxtrade.models import PushEvent
from dxtrade.models import Subscription
from dxtrade.models import WebSocketConfig
from dxtrade.utils import RetryConfig
from dxtrade.utils import utc_now

logger = logging.getLogger(__name__)

EventHandler = Callable[[AnyEvent], None]
AsyncEventHandler = Callable[[AnyEvent], asyncio.Task[None]]


class DXtradePushClient:
    """WebSocket client for DXtrade Push API with auto-reconnect."""
    
    def __init__(
        self,
        config: WebSocketConfig,
        auth_handler: Optional[AuthHandler] = None,
    ) -> None:
        """Initialize push client.
        
        Args:
            config: WebSocket configuration
            auth_handler: Authentication handler
        """
        self.config = config
        self.auth_handler = auth_handler
        
        # Connection state
        self._websocket: Optional[websockets.WebSocketServerProtocol] = None
        self._connected = False
        self._reconnect_attempts = 0
        self._last_heartbeat: Optional[float] = None
        
        # Retry configuration
        self._retry_config = RetryConfig(
            max_retries=config.max_retries,
            base_delay=config.retry_backoff_factor,
        )
        
        # Event handling
        self._event_handlers: Dict[EventType, List[Union[EventHandler, AsyncEventHandler]]] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._pending_subscriptions: Set[str] = set()
        
        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._message_handler_task: Optional[asyncio.Task[None]] = None
        self._connection_monitor_task: Optional[asyncio.Task[None]] = None
        
        # Message queue for backpressure management
        self._message_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._processing_messages = False
        
        # Connection control
        self._should_reconnect = True
        self._shutdown = False
        
    async def __aenter__(self) -> DXtradePushClient:
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._websocket is not None
    
    @property
    def subscriptions(self) -> Dict[str, Subscription]:
        """Get current subscriptions."""
        return self._subscriptions.copy()
    
    async def connect(self) -> None:
        """Connect to the WebSocket server."""
        if self._connected:
            return
        
        try:
            # Build connection URI
            uri = self.config.url
            if self.auth_handler:
                # Add auth parameters if needed
                # This would depend on the specific auth scheme
                pass
            
            # Connect with configuration
            connect_kwargs = {
                "ping_interval": self.config.ping_interval,
                "ping_timeout": self.config.ping_timeout,
                "max_size": self.config.max_message_size,
                "max_queue": 100,  # Limit queue size to prevent memory issues
            }
            
            logger.info(f"Connecting to WebSocket: {uri}")
            self._websocket = await websockets.connect(uri, **connect_kwargs)
            
            # Perform authentication if required
            if self.auth_handler:
                await self._authenticate()
            
            self._connected = True
            self._reconnect_attempts = 0
            self._last_heartbeat = time.time()
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Resubscribe to previous subscriptions
            await self._resubscribe()
            
            logger.info("WebSocket connected successfully")
            
        except Exception as e:
            self._connected = False
            self._websocket = None
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise DXtradeWebSocketError(f"Connection failed: {e}") from e
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._should_reconnect = False
        self._shutdown = True
        
        # Stop background tasks
        await self._stop_background_tasks()
        
        # Close WebSocket connection
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
            finally:
                self._websocket = None
        
        self._connected = False
        logger.info("WebSocket disconnected")
    
    async def _authenticate(self) -> None:
        """Authenticate the WebSocket connection."""
        if not self.auth_handler:
            return
        
        # Create a mock HTTP request for authentication
        # This would need to be adapted based on the actual auth scheme
        auth_message = {
            "type": "auth",
            "timestamp": int(time.time() * 1000),
        }
        
        # Add auth-specific fields
        # This is a simplified example - real implementation would depend on the auth scheme
        if hasattr(self.auth_handler, "get_auth_headers"):
            # This method doesn't exist in our current auth handlers
            # but shows how you might integrate WebSocket auth
            pass
        
        await self._send_message(auth_message)
        
        # Wait for auth response
        auth_timeout = 10.0
        try:
            response = await asyncio.wait_for(
                self._websocket.recv(), timeout=auth_timeout
            )
            auth_data = json.loads(response)
            
            if not auth_data.get("success"):
                raise DXtradeWebSocketError(
                    f"Authentication failed: {auth_data.get('message', 'Unknown error')}"
                )
                
        except asyncio.TimeoutError:
            raise DXtradeWebSocketError("Authentication timeout") from None
    
    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Send message to WebSocket server.
        
        Args:
            message: Message to send
            
        Raises:
            DXtradeWebSocketError: Connection error
        """
        if not self._websocket:
            raise DXtradeWebSocketError("Not connected")
        
        try:
            message_str = json.dumps(message)
            await self._websocket.send(message_str)
            logger.debug(f"Sent message: {message.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise DXtradeWebSocketError(f"Send failed: {e}") from e
    
    async def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Message handler
        self._message_handler_task = asyncio.create_task(self._message_handler())
        
        # Heartbeat sender
        if self.config.heartbeat_interval > 0:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_sender())
        
        # Connection monitor
        self._connection_monitor_task = asyncio.create_task(self._connection_monitor())
        
        # Start message processing
        if not self._processing_messages:
            asyncio.create_task(self._process_message_queue())
    
    async def _stop_background_tasks(self) -> None:
        """Stop background tasks."""
        tasks = [
            self._message_handler_task,
            self._heartbeat_task,
            self._connection_monitor_task,
        ]
        
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._message_handler_task = None
        self._heartbeat_task = None
        self._connection_monitor_task = None
    
    async def _message_handler(self) -> None:
        """Handle incoming WebSocket messages."""
        while self._connected and not self._shutdown:
            try:
                if not self._websocket:
                    break
                
                message = await self._websocket.recv()
                
                try:
                    data = json.loads(message)
                    await self._message_queue.put(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON received: {e}")
                except asyncio.QueueFull:
                    logger.warning("Message queue full, dropping message")
                    
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                if self._should_reconnect and not self._shutdown:
                    await self._handle_reconnect()
                break
            except Exception as e:
                logger.error(f"Message handler error: {e}")
                if not self._shutdown:
                    await asyncio.sleep(1)
    
    async def _process_message_queue(self) -> None:
        """Process messages from the queue."""
        self._processing_messages = True
        
        try:
            while not self._shutdown:
                try:
                    # Wait for message with timeout to allow shutdown
                    data = await asyncio.wait_for(
                        self._message_queue.get(), timeout=1.0
                    )
                    await self._handle_message(data)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        finally:
            self._processing_messages = False
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Handle a received message.
        
        Args:
            data: Parsed message data
        """
        try:
            # Parse message type
            message_type = data.get("type")
            if not message_type:
                logger.warning("Received message without type")
                return
            
            # Handle special message types
            if message_type == "heartbeat":
                self._last_heartbeat = time.time()
                event = HeartbeatEvent(
                    type=EventType.HEARTBEAT,
                    timestamp=utc_now(),
                    data=data.get("data", {}),
                )
            elif message_type == "subscription_ack":
                await self._handle_subscription_ack(data)
                return
            elif message_type == "error":
                await self._handle_error_message(data)
                return
            else:
                # Parse as event
                event = await self._parse_event(data)
            
            # Dispatch event to handlers
            await self._dispatch_event(event)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _parse_event(self, data: Dict[str, Any]) -> AnyEvent:
        """Parse message data into an event.
        
        Args:
            data: Message data
            
        Returns:
            Parsed event
            
        Raises:
            DXtradeDataError: Parsing error
        """
        event_type = data.get("type")
        
        try:
            if event_type == EventType.PRICE:
                return PriceEvent.model_validate(data)
            elif event_type == EventType.ORDER:
                return OrderEvent.model_validate(data)
            elif event_type == EventType.POSITION:
                return PositionEvent.model_validate(data)
            elif event_type == EventType.ACCOUNT:
                return AccountEvent.model_validate(data)
            elif event_type == EventType.HEARTBEAT:
                return HeartbeatEvent.model_validate(data)
            else:
                # Generic event
                return PushEvent.model_validate(data)
                
        except ValidationError as e:
            raise DXtradeDataError(f"Failed to parse {event_type} event: {e}") from e
    
    async def _dispatch_event(self, event: AnyEvent) -> None:
        """Dispatch event to registered handlers.
        
        Args:
            event: Event to dispatch
        """
        event_type = EventType(event.type)
        handlers = self._event_handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event_type}: {e}")
    
    async def _handle_subscription_ack(self, data: Dict[str, Any]) -> None:
        """Handle subscription acknowledgment.
        
        Args:
            data: Subscription ack data
        """
        sub_id = data.get("subscription_id")
        if sub_id:
            self._pending_subscriptions.discard(sub_id)
            logger.debug(f"Subscription acknowledged: {sub_id}")
    
    async def _handle_error_message(self, data: Dict[str, Any]) -> None:
        """Handle error message from server.
        
        Args:
            data: Error message data
        """
        error_code = data.get("error_code", "UNKNOWN")
        error_message = data.get("message", "Unknown error")
        logger.error(f"Server error [{error_code}]: {error_message}")
    
    async def _heartbeat_sender(self) -> None:
        """Send periodic heartbeat messages."""
        while self._connected and not self._shutdown:
            try:
                heartbeat_msg = {
                    "type": "heartbeat",
                    "timestamp": int(time.time() * 1000),
                }
                await self._send_message(heartbeat_msg)
                
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except Exception as e:
                logger.warning(f"Heartbeat send error: {e}")
                break
    
    async def _connection_monitor(self) -> None:
        """Monitor connection health."""
        while self._connected and not self._shutdown:
            try:
                # Check heartbeat timeout
                if self._last_heartbeat:
                    time_since_heartbeat = time.time() - self._last_heartbeat
                    heartbeat_timeout = self.config.heartbeat_interval * 3  # 3x interval
                    
                    if time_since_heartbeat > heartbeat_timeout:
                        logger.warning("Heartbeat timeout detected")
                        if self._should_reconnect and not self._shutdown:
                            await self._handle_reconnect()
                        break
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Connection monitor error: {e}")
                break
    
    async def _handle_reconnect(self) -> None:
        """Handle connection reconnection."""
        if not self._should_reconnect or self._shutdown:
            return
        
        self._connected = False
        
        for attempt in range(self._retry_config.max_retries):
            try:
                delay = self._retry_config.calculate_delay(attempt)
                logger.info(f"Reconnecting in {delay:.1f}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                
                if self._shutdown:
                    break
                
                await self.connect()
                logger.info("Reconnection successful")
                return
                
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")
                self._reconnect_attempts += 1
        
        logger.error("Max reconnection attempts reached")
        self._should_reconnect = False
    
    async def _resubscribe(self) -> None:
        """Resubscribe to previous subscriptions."""
        for subscription in self._subscriptions.values():
            if subscription.active:
                try:
                    await self._send_subscription_message(subscription)
                except Exception as e:
                    logger.warning(f"Failed to resubscribe to {subscription.id}: {e}")
    
    async def _send_subscription_message(self, subscription: Subscription) -> None:
        """Send subscription message.
        
        Args:
            subscription: Subscription to send
        """
        message = {
            "type": "subscribe",
            "subscription_id": subscription.id,
            "event_type": subscription.event_type.value,
        }
        
        if subscription.symbol:
            message["symbol"] = subscription.symbol
        if subscription.account_id:
            message["account_id"] = subscription.account_id
        
        await self._send_message(message)
        self._pending_subscriptions.add(subscription.id)
    
    # Public API methods
    
    def on(
        self,
        event_type: EventType,
        handler: Union[EventHandler, AsyncEventHandler],
    ) -> None:
        """Register event handler.
        
        Args:
            event_type: Event type to handle
            handler: Event handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        
        self._event_handlers[event_type].append(handler)
    
    def off(
        self,
        event_type: EventType,
        handler: Optional[Union[EventHandler, AsyncEventHandler]] = None,
    ) -> None:
        """Unregister event handler.
        
        Args:
            event_type: Event type
            handler: Specific handler to remove (if None, removes all)
        """
        if event_type not in self._event_handlers:
            return
        
        if handler is None:
            self._event_handlers[event_type].clear()
        else:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    async def subscribe_prices(
        self,
        symbols: Optional[List[str]] = None,
    ) -> str:
        """Subscribe to price updates.
        
        Args:
            symbols: List of symbols (if None, subscribes to all)
            
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=subscription_id,
            event_type=EventType.PRICE,
            symbol=",".join(symbols) if symbols else None,
            active=True,
        )
        
        self._subscriptions[subscription_id] = subscription
        
        if self._connected:
            await self._send_subscription_message(subscription)
        
        return subscription_id
    
    async def subscribe_orders(
        self,
        account_id: Optional[str] = None,
    ) -> str:
        """Subscribe to order updates.
        
        Args:
            account_id: Optional account filter
            
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=subscription_id,
            event_type=EventType.ORDER,
            account_id=account_id,
            active=True,
        )
        
        self._subscriptions[subscription_id] = subscription
        
        if self._connected:
            await self._send_subscription_message(subscription)
        
        return subscription_id
    
    async def subscribe_positions(
        self,
        account_id: Optional[str] = None,
    ) -> str:
        """Subscribe to position updates.
        
        Args:
            account_id: Optional account filter
            
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=subscription_id,
            event_type=EventType.POSITION,
            account_id=account_id,
            active=True,
        )
        
        self._subscriptions[subscription_id] = subscription
        
        if self._connected:
            await self._send_subscription_message(subscription)
        
        return subscription_id
    
    async def subscribe_account(
        self,
        account_id: str,
    ) -> str:
        """Subscribe to account updates.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Subscription ID
        """
        subscription_id = str(uuid.uuid4())
        
        subscription = Subscription(
            id=subscription_id,
            event_type=EventType.ACCOUNT,
            account_id=account_id,
            active=True,
        )
        
        self._subscriptions[subscription_id] = subscription
        
        if self._connected:
            await self._send_subscription_message(subscription)
        
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events.
        
        Args:
            subscription_id: Subscription ID to cancel
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return
        
        subscription.active = False
        
        if self._connected:
            unsubscribe_msg = {
                "type": "unsubscribe",
                "subscription_id": subscription_id,
            }
            await self._send_message(unsubscribe_msg)
        
        del self._subscriptions[subscription_id]
    
    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all events."""
        subscription_ids = list(self._subscriptions.keys())
        for subscription_id in subscription_ids:
            await self.unsubscribe(subscription_id)
    
    async def events(self) -> AsyncIterator[AnyEvent]:
        """Async iterator for events.
        
        Yields:
            Events as they arrive
        """
        event_queue: asyncio.Queue[AnyEvent] = asyncio.Queue()
        
        async def event_handler(event: AnyEvent) -> None:
            await event_queue.put(event)
        
        # Subscribe to all event types
        for event_type in EventType:
            self.on(event_type, event_handler)
        
        try:
            while not self._shutdown:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            # Cleanup handlers
            for event_type in EventType:
                self.off(event_type, event_handler)