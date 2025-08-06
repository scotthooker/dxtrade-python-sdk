"""
Orders REST API client.

Provides methods for placing, modifying, and managing trading orders.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

from ..core.http_client import HTTPClient
from ..types.trading import Order, OrderRequest, OrderSide, OrderType, OrderStatus, TimeInForce
from ..errors import ValidationError


class OrderModification:
    """Order modification parameters."""
    
    def __init__(
        self,
        order_id: str,
        volume: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: Optional[TimeInForce] = None,
    ):
        """Initialize order modification."""
        self.order_id = order_id
        self.volume = volume
        self.price = price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to request data."""
        data = {}
        if self.volume is not None:
            data["volume"] = str(self.volume)
        if self.price is not None:
            data["price"] = str(self.price)
        if self.stop_price is not None:
            data["stopPrice"] = str(self.stop_price)
        if self.time_in_force is not None:
            data["timeInForce"] = self.time_in_force.value
        return data


class OrderQuery:
    """Order query parameters."""
    
    def __init__(
        self,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        side: Optional[OrderSide] = None,
        order_type: Optional[OrderType] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        """Initialize order query."""
        self.account_id = account_id
        self.symbol = symbol
        self.status = status
        self.side = side
        self.order_type = order_type
        self.from_date = from_date
        self.to_date = to_date
        self.page = page
        self.limit = limit
        
    def to_params(self) -> Dict[str, Any]:
        """Convert to request parameters."""
        params = {}
        if self.account_id:
            params["accountId"] = self.account_id
        if self.symbol:
            params["symbol"] = self.symbol
        if self.status:
            params["status"] = self.status.value
        if self.side:
            params["side"] = self.side.value
        if self.order_type:
            params["type"] = self.order_type.value
        if self.from_date:
            params["fromDate"] = int(self.from_date.timestamp())
        if self.to_date:
            params["toDate"] = int(self.to_date.timestamp())
        if self.page:
            params["page"] = self.page
        if self.limit:
            params["limit"] = self.limit
        return params


class OcoOrderRequest:
    """One-Cancels-Other (OCO) order request."""
    
    def __init__(
        self,
        account_id: str,
        symbol: str,
        volume: Decimal,
        first_order_side: OrderSide,
        first_order_price: Decimal,
        second_order_side: OrderSide,
        second_order_price: Decimal,
        time_in_force: TimeInForce = TimeInForce.GTC,
        comment: Optional[str] = None,
    ):
        """Initialize OCO order request."""
        self.account_id = account_id
        self.symbol = symbol
        self.volume = volume
        self.first_order_side = first_order_side
        self.first_order_price = first_order_price
        self.second_order_side = second_order_side
        self.second_order_price = second_order_price
        self.time_in_force = time_in_force
        self.comment = comment
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to request data."""
        return {
            "accountId": self.account_id,
            "symbol": self.symbol,
            "volume": str(self.volume),
            "firstOrder": {
                "side": self.first_order_side.value,
                "price": str(self.first_order_price),
            },
            "secondOrder": {
                "side": self.second_order_side.value,
                "price": str(self.second_order_price),
            },
            "timeInForce": self.time_in_force.value,
            "comment": self.comment,
        }


class BracketOrderRequest:
    """Bracket order request (entry + stop loss + take profit)."""
    
    def __init__(
        self,
        account_id: str,
        symbol: str,
        side: OrderSide,
        volume: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
        time_in_force: TimeInForce = TimeInForce.GTC,
        comment: Optional[str] = None,
    ):
        """Initialize bracket order request."""
        self.account_id = account_id
        self.symbol = symbol
        self.side = side
        self.volume = volume
        self.entry_price = entry_price
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.time_in_force = time_in_force
        self.comment = comment
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to request data."""
        return {
            "accountId": self.account_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "volume": str(self.volume),
            "entryPrice": str(self.entry_price),
            "stopLossPrice": str(self.stop_loss_price),
            "takeProfitPrice": str(self.take_profit_price),
            "timeInForce": self.time_in_force.value,
            "comment": self.comment,
        }


class OrderExecution:
    """Order execution information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.execution_id: str = data["executionId"]
        self.order_id: str = data["orderId"]
        self.symbol: str = data["symbol"]
        self.side: OrderSide = OrderSide(data["side"])
        self.volume: Decimal = Decimal(str(data["volume"]))
        self.price: Decimal = Decimal(str(data["price"]))
        self.commission: Decimal = Decimal(str(data.get("commission", "0")))
        self.swap: Decimal = Decimal(str(data.get("swap", "0")))
        self.executed_at: datetime = datetime.fromtimestamp(data["executedAt"])


class OrdersAPI:
    """Orders REST API client."""
    
    def __init__(self, http_client: HTTPClient):
        """Initialize with HTTP client."""
        self.http = http_client
        
    async def place_order(self, order_request: OrderRequest) -> Order:
        """Place a new order."""
        data = {
            "accountId": order_request.account_id,
            "symbol": order_request.symbol,
            "side": order_request.side.value,
            "type": order_request.type.value,
            "volume": str(order_request.volume),
            "timeInForce": order_request.time_in_force.value,
        }
        
        if order_request.price is not None:
            data["price"] = str(order_request.price)
        if order_request.stop_price is not None:
            data["stopPrice"] = str(order_request.stop_price)
        if order_request.client_order_id is not None:
            data["clientOrderId"] = order_request.client_order_id
        if order_request.comment is not None:
            data["comment"] = order_request.comment
            
        response = await self.http.post("/orders", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to place order")
            
        return Order(**response.data)
        
    async def get_orders(
        self, 
        query: Optional[OrderQuery] = None
    ) -> Dict[str, Any]:
        """Get orders with optional filtering."""
        params = query.to_params() if query else {}
        
        response = await self.http.get("/orders", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve orders")
            
        orders = [Order(**order) for order in response.data.get("orders", [])]
        
        return {
            "orders": orders,
            "pagination": response.data.get("pagination")
        }
        
    async def get_order(self, order_id: str) -> Order:
        """Get order by ID."""
        response = await self.http.get(f"/orders/{order_id}")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve order")
            
        return Order(**response.data)
        
    async def modify_order(
        self, 
        order_id: str,
        modification: OrderModification
    ) -> Order:
        """Modify an existing order."""
        data = modification.to_dict()
        
        response = await self.http.put(f"/orders/{order_id}", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to modify order")
            
        return Order(**response.data)
        
    async def cancel_order(self, order_id: str) -> Order:
        """Cancel an order."""
        response = await self.http.delete(f"/orders/{order_id}")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to cancel order")
            
        return Order(**response.data)
        
    async def cancel_orders(
        self, 
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Order]:
        """Cancel multiple orders."""
        data = {}
        if account_id:
            data["accountId"] = account_id
        if symbol:
            data["symbol"] = symbol
            
        response = await self.http.post("/orders/cancel", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to cancel orders")
            
        return [Order(**order) for order in response.data]
        
    async def place_oco_order(self, oco_request: OcoOrderRequest) -> List[Order]:
        """Place a One-Cancels-Other (OCO) order."""
        data = oco_request.to_dict()
        
        response = await self.http.post("/orders/oco", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to place OCO order")
            
        return [Order(**order) for order in response.data]
        
    async def place_bracket_order(self, bracket_request: BracketOrderRequest) -> List[Order]:
        """Place a bracket order (entry + stop loss + take profit)."""
        data = bracket_request.to_dict()
        
        response = await self.http.post("/orders/bracket", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to place bracket order")
            
        return [Order(**order) for order in response.data]
        
    async def get_order_history(
        self,
        query: Optional[OrderQuery] = None
    ) -> Dict[str, Any]:
        """Get order history."""
        params = query.to_params() if query else {}
        
        response = await self.http.get("/orders/history", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve order history")
            
        orders = [Order(**order) for order in response.data.get("orders", [])]
        
        return {
            "orders": orders,
            "pagination": response.data.get("pagination")
        }
        
    async def get_order_executions(self, order_id: str) -> List[OrderExecution]:
        """Get order execution details."""
        response = await self.http.get(f"/orders/{order_id}/executions")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve order executions")
            
        return [OrderExecution(exec_data) for exec_data in response.data]
        
    async def estimate_order_cost(self, order_request: OrderRequest) -> Dict[str, Any]:
        """Estimate order cost and margin requirements."""
        data = {
            "accountId": order_request.account_id,
            "symbol": order_request.symbol,
            "side": order_request.side.value,
            "type": order_request.type.value,
            "volume": str(order_request.volume),
        }
        
        if order_request.price is not None:
            data["price"] = str(order_request.price)
            
        response = await self.http.post("/orders/estimate", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to estimate order cost")
            
        return response.data