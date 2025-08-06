"""Positions API endpoints."""

from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from dxtrade.models import PaginatedResponse
from dxtrade.models import Position
from dxtrade.rest.base import BaseAPI


class PositionsAPI(BaseAPI):
    """API for position management."""
    
    async def get_positions(
        self,
        account_id: Optional[str] = None,
        *,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        timeout: Optional[float] = None,
    ) -> PaginatedResponse:
        """Get positions with optional filtering.
        
        Args:
            account_id: Optional account filter
            symbol: Optional symbol filter
            limit: Maximum number of positions
            offset: Pagination offset
            timeout: Request timeout
            
        Returns:
            Paginated list of positions
        """
        params = {"limit": limit, "offset": offset}
        if account_id:
            params["account_id"] = account_id
        if symbol:
            params["symbol"] = symbol
        
        return await self._get_paginated("/positions", Position, params=params, timeout=timeout)
    
    async def get_position(
        self,
        position_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Position:
        """Get position by ID.
        
        Args:
            position_id: Position identifier
            timeout: Request timeout
            
        Returns:
            Position information
        """
        return await self._get_data(f"/positions/{position_id}", Position, timeout=timeout)
    
    async def get_position_by_symbol(
        self,
        account_id: str,
        symbol: str,
        *,
        timeout: Optional[float] = None,
    ) -> Optional[Position]:
        """Get position by account and symbol.
        
        Args:
            account_id: Account identifier
            symbol: Instrument symbol
            timeout: Request timeout
            
        Returns:
            Position information or None if no position
        """
        try:
            return await self._get_data(
                f"/accounts/{account_id}/positions/{symbol}",
                Position,
                timeout=timeout
            )
        except Exception:
            # Position doesn't exist
            return None
    
    async def close_position(
        self,
        position_id: str,
        *,
        volume: Optional[float] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Position:
        """Close a position (full or partial).
        
        Args:
            position_id: Position identifier
            volume: Optional partial close volume (if None, closes entire position)
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Updated position after close
        """
        close_data = {}
        if volume is not None:
            close_data["volume"] = volume
        
        return await self._post_data(
            f"/positions/{position_id}/close",
            Position,
            json=close_data if close_data else None,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def close_position_by_symbol(
        self,
        account_id: str,
        symbol: str,
        *,
        volume: Optional[float] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[Position]:
        """Close position by account and symbol.
        
        Args:
            account_id: Account identifier
            symbol: Instrument symbol
            volume: Optional partial close volume
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Updated position after close or None if no position
        """
        close_data = {}
        if volume is not None:
            close_data["volume"] = volume
        
        try:
            return await self._post_data(
                f"/accounts/{account_id}/positions/{symbol}/close",
                Position,
                json=close_data if close_data else None,
                timeout=timeout,
                idempotency_key=idempotency_key,
            )
        except Exception:
            # Position doesn't exist
            return None
    
    async def close_all_positions(
        self,
        account_id: str,
        *,
        symbol: Optional[str] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> List[Position]:
        """Close all positions for an account.
        
        Args:
            account_id: Account identifier
            symbol: Optional symbol filter
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            List of closed positions
        """
        close_data = {"account_id": account_id}
        if symbol:
            close_data["symbol"] = symbol
        
        response = await self._request(
            "POST",
            "/positions/close-all",
            json=close_data,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
        return await self._parse_list_response(response, Position)
    
    async def modify_position(
        self,
        position_id: str,
        *,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Position:
        """Modify position stop loss or take profit.
        
        Args:
            position_id: Position identifier
            stop_loss: New stop loss price (None to remove)
            take_profit: New take profit price (None to remove)
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Modified position
        """
        updates = {}
        if stop_loss is not None:
            updates["stop_loss"] = stop_loss
        if take_profit is not None:
            updates["take_profit"] = take_profit
        
        return await self._patch_data(
            f"/positions/{position_id}",
            Position,
            json=updates,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def get_position_summary(
        self,
        account_id: str,
        *,
        currency: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, float]:
        """Get position summary for account.
        
        Args:
            account_id: Account identifier
            currency: Optional currency filter
            timeout: Request timeout
            
        Returns:
            Position summary metrics
        """
        params = {}
        if currency:
            params["currency"] = currency
        
        response = await self._request(
            "GET",
            f"/accounts/{account_id}/positions/summary",
            params=params,
            timeout=timeout,
        )
        data = response.json()
        
        return data.get("data", {}) if isinstance(data, dict) else data
    
    async def get_exposure_summary(
        self,
        account_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Get exposure summary by instrument and currency.
        
        Args:
            account_id: Account identifier
            timeout: Request timeout
            
        Returns:
            Exposure summary by symbol and currency
        """
        response = await self._request(
            "GET",
            f"/accounts/{account_id}/exposure",
            timeout=timeout,
        )
        data = response.json()
        
        return data.get("data", {}) if isinstance(data, dict) else data