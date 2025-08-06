"""Orders API endpoints."""

from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from dxtrade.models import BracketOrderRequest
from dxtrade.models import OCOOrderRequest
from dxtrade.models import Order
from dxtrade.models import OrderRequest
from dxtrade.models import OrderStatus
from dxtrade.models import PaginatedResponse
from dxtrade.models import Trade
from dxtrade.rest.base import BaseAPI


class OrdersAPI(BaseAPI):
    """API for order management and trade history."""
    
    async def get_orders(
        self,
        account_id: Optional[str] = None,
        *,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
        timeout: Optional[float] = None,
    ) -> PaginatedResponse:
        """Get orders with optional filtering.
        
        Args:
            account_id: Optional account filter
            symbol: Optional symbol filter
            status: Optional status filter
            limit: Maximum number of orders
            offset: Pagination offset
            timeout: Request timeout
            
        Returns:
            Paginated list of orders
        """
        params = {"limit": limit, "offset": offset}
        if account_id:
            params["account_id"] = account_id
        if symbol:
            params["symbol"] = symbol
        if status:
            params["status"] = status.value
        
        return await self._get_paginated("/orders", Order, params=params, timeout=timeout)
    
    async def get_order(
        self,
        order_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Order:
        """Get order by ID.
        
        Args:
            order_id: Order identifier
            timeout: Request timeout
            
        Returns:
            Order information
        """
        return await self._get_data(f"/orders/{order_id}", Order, timeout=timeout)
    
    async def create_order(
        self,
        order: OrderRequest,
        *,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Order:
        """Create a new order.
        
        Args:
            order: Order request
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Created order
        """
        order_data = order.model_dump(exclude_unset=True)
        return await self._post_data(
            "/orders",
            Order,
            json=order_data,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def create_oco_order(
        self,
        order: OCOOrderRequest,
        *,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> List[Order]:
        """Create a One-Cancels-Other order.
        
        Args:
            order: OCO order request
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            List of created orders (usually 2)
        """
        order_data = order.model_dump(exclude_unset=True)
        return await self._post_data(
            "/orders/oco",
            List[Order],  # type: ignore
            json=order_data,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def create_bracket_order(
        self,
        order: BracketOrderRequest,
        *,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> List[Order]:
        """Create a bracket order.
        
        Args:
            order: Bracket order request
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            List of created orders (parent + stop loss + take profit)
        """
        order_data = order.model_dump(exclude_unset=True)
        return await self._post_data(
            "/orders/bracket",
            List[Order],  # type: ignore
            json=order_data,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def modify_order(
        self,
        order_id: str,
        *,
        volume: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Order:
        """Modify an existing order.
        
        Args:
            order_id: Order identifier
            volume: New volume
            price: New limit price
            stop_price: New stop price
            stop_loss: New stop loss price
            take_profit: New take profit price
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Modified order
        """
        updates = {}
        if volume is not None:
            updates["volume"] = volume
        if price is not None:
            updates["price"] = price
        if stop_price is not None:
            updates["stop_price"] = stop_price
        if stop_loss is not None:
            updates["stop_loss"] = stop_loss
        if take_profit is not None:
            updates["take_profit"] = take_profit
        
        return await self._patch_data(
            f"/orders/{order_id}",
            Order,
            json=updates,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def cancel_order(
        self,
        order_id: str,
        *,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Order:
        """Cancel an order.
        
        Args:
            order_id: Order identifier
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Cancelled order
        """
        return await self._delete_data(
            f"/orders/{order_id}",
            Order,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def cancel_all_orders(
        self,
        *,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> List[Order]:
        """Cancel multiple orders.
        
        Args:
            account_id: Optional account filter
            symbol: Optional symbol filter
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            List of cancelled orders
        """
        params = {}
        if account_id:
            params["account_id"] = account_id
        if symbol:
            params["symbol"] = symbol
        
        response = await self._request(
            "DELETE",
            "/orders",
            params=params,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
        return await self._parse_list_response(response, Order)
    
    async def get_trades(
        self,
        account_id: Optional[str] = None,
        *,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        timeout: Optional[float] = None,
    ) -> PaginatedResponse:
        """Get trade history.
        
        Args:
            account_id: Optional account filter
            symbol: Optional symbol filter
            order_id: Optional order filter
            limit: Maximum number of trades
            offset: Pagination offset
            timeout: Request timeout
            
        Returns:
            Paginated list of trades
        """
        params = {"limit": limit, "offset": offset}
        if account_id:
            params["account_id"] = account_id
        if symbol:
            params["symbol"] = symbol
        if order_id:
            params["order_id"] = order_id
        
        return await self._get_paginated("/trades", Trade, params=params, timeout=timeout)
    
    async def get_trade(
        self,
        trade_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Trade:
        """Get trade by ID.
        
        Args:
            trade_id: Trade identifier
            timeout: Request timeout
            
        Returns:
            Trade information
        """
        return await self._get_data(f"/trades/{trade_id}", Trade, timeout=timeout)
    
    async def get_order_fills(
        self,
        order_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> List[Trade]:
        """Get fills for an order.
        
        Args:
            order_id: Order identifier
            timeout: Request timeout
            
        Returns:
            List of trades that filled the order
        """
        return await self._get_list(f"/orders/{order_id}/fills", Trade, timeout=timeout)