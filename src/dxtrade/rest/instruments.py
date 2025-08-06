"""Instruments and market data API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional

from dxtrade.models import Candle
from dxtrade.models import Instrument
from dxtrade.models import Price
from dxtrade.models import ServerTime
from dxtrade.models import Tick
from dxtrade.rest.base import BaseAPI


class InstrumentsAPI(BaseAPI):
    """API for instrument information and market data."""
    
    async def get_instruments(
        self,
        *,
        instrument_type: Optional[str] = None,
        enabled_only: bool = True,
        timeout: Optional[float] = None,
    ) -> List[Instrument]:
        """Get available trading instruments.
        
        Args:
            instrument_type: Filter by instrument type
            enabled_only: Only return enabled instruments
            timeout: Request timeout
            
        Returns:
            List of instruments
        """
        params = {}
        if instrument_type:
            params["type"] = instrument_type
        if enabled_only:
            params["enabled"] = "true"
        
        return await self._get_list("/instruments", Instrument, params=params, timeout=timeout)
    
    async def get_instrument(
        self,
        symbol: str,
        *,
        timeout: Optional[float] = None,
    ) -> Instrument:
        """Get instrument by symbol.
        
        Args:
            symbol: Instrument symbol
            timeout: Request timeout
            
        Returns:
            Instrument information
        """
        return await self._get_data(f"/instruments/{symbol}", Instrument, timeout=timeout)
    
    async def search_instruments(
        self,
        query: str,
        *,
        limit: int = 50,
        timeout: Optional[float] = None,
    ) -> List[Instrument]:
        """Search instruments by name or symbol.
        
        Args:
            query: Search query
            limit: Maximum number of results
            timeout: Request timeout
            
        Returns:
            List of matching instruments
        """
        params = {"q": query, "limit": limit}
        return await self._get_list("/instruments/search", Instrument, params=params, timeout=timeout)
    
    async def get_prices(
        self,
        symbols: Optional[List[str]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> List[Price]:
        """Get current prices for symbols.
        
        Args:
            symbols: List of symbols (if None, gets all)
            timeout: Request timeout
            
        Returns:
            List of current prices
        """
        params = {}
        if symbols:
            params["symbols"] = ",".join(symbols)
        
        return await self._get_list("/market/prices", Price, params=params, timeout=timeout)
    
    async def get_price(
        self,
        symbol: str,
        *,
        timeout: Optional[float] = None,
    ) -> Price:
        """Get current price for symbol.
        
        Args:
            symbol: Instrument symbol
            timeout: Request timeout
            
        Returns:
            Current price
        """
        return await self._get_data(f"/market/prices/{symbol}", Price, timeout=timeout)
    
    async def get_ticks(
        self,
        symbol: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        timeout: Optional[float] = None,
    ) -> List[Tick]:
        """Get historical tick data.
        
        Args:
            symbol: Instrument symbol
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of ticks
            timeout: Request timeout
            
        Returns:
            List of historical ticks
        """
        params = {"limit": limit}
        if start:
            params["start"] = int(start.timestamp() * 1000)
        if end:
            params["end"] = int(end.timestamp() * 1000)
        
        return await self._get_list(
            f"/market/ticks/{symbol}",
            Tick,
            params=params,
            timeout=timeout
        )
    
    async def get_candles(
        self,
        symbol: str,
        interval: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
        timeout: Optional[float] = None,
    ) -> List[Candle]:
        """Get historical candle data.
        
        Args:
            symbol: Instrument symbol
            interval: Candle interval (1m, 5m, 1h, 1d, etc.)
            start: Start timestamp
            end: End timestamp
            limit: Maximum number of candles
            timeout: Request timeout
            
        Returns:
            List of historical candles
        """
        params = {"interval": interval, "limit": limit}
        if start:
            params["start"] = int(start.timestamp() * 1000)
        if end:
            params["end"] = int(end.timestamp() * 1000)
        
        return await self._get_list(
            f"/market/candles/{symbol}",
            Candle,
            params=params,
            timeout=timeout
        )
    
    async def get_server_time(
        self,
        *,
        timeout: Optional[float] = None,
    ) -> ServerTime:
        """Get server time information.
        
        Args:
            timeout: Request timeout
            
        Returns:
            Server time information
        """
        return await self._get_data("/market/time", ServerTime, timeout=timeout)
    
    async def get_market_status(
        self,
        symbol: Optional[str] = None,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, str]:
        """Get market status for symbol or all markets.
        
        Args:
            symbol: Optional specific symbol
            timeout: Request timeout
            
        Returns:
            Market status information
        """
        endpoint = "/market/status"
        params = {}
        if symbol:
            endpoint = f"/market/status/{symbol}"
        
        response = await self._request("GET", endpoint, params=params, timeout=timeout)
        data = response.json()
        
        return data.get("data", {}) if isinstance(data, dict) else data
    
    async def get_trading_hours(
        self,
        symbol: str,
        *,
        date: Optional[datetime] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, List[str]]:
        """Get trading hours for symbol.
        
        Args:
            symbol: Instrument symbol
            date: Optional specific date
            timeout: Request timeout
            
        Returns:
            Trading hours information
        """
        params = {}
        if date:
            params["date"] = date.strftime("%Y-%m-%d")
        
        response = await self._request(
            "GET", f"/instruments/{symbol}/hours",
            params=params, timeout=timeout
        )
        data = response.json()
        
        return data.get("data", {}) if isinstance(data, dict) else data