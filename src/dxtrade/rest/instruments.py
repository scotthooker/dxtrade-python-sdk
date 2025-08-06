"""
Instruments REST API client.

Provides methods for retrieving instrument information, market data, and quotes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

from ..core.http_client import HTTPClient
from ..types.trading import Instrument, Quote, Candlestick
from ..errors import ValidationError


class InstrumentFilter:
    """Instrument filter parameters."""
    
    def __init__(
        self,
        instrument_type: Optional[str] = None,
        currency: Optional[str] = None,
        tradeable_only: Optional[bool] = None,
        search: Optional[str] = None,
    ):
        """Initialize instrument filter."""
        self.instrument_type = instrument_type
        self.currency = currency
        self.tradeable_only = tradeable_only
        self.search = search
        
    def to_params(self) -> Dict[str, Any]:
        """Convert to request parameters."""
        params = {}
        if self.instrument_type:
            params["type"] = self.instrument_type
        if self.currency:
            params["currency"] = self.currency
        if self.tradeable_only is not None:
            params["tradeableOnly"] = self.tradeable_only
        if self.search:
            params["search"] = self.search
        return params


class MarketHours:
    """Market hours information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.symbol: str = data["symbol"]
        self.timezone: str = data["timezone"]
        self.sessions: List[Dict[str, Any]] = data.get("sessions", [])
        self.holidays: List[str] = data.get("holidays", [])
        self.is_trading_now: bool = data.get("isTradingNow", False)
        self.next_session_start: Optional[str] = data.get("nextSessionStart")
        self.next_session_end: Optional[str] = data.get("nextSessionEnd")


class InstrumentSpec:
    """Detailed instrument specification."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.symbol: str = data["symbol"]
        self.name: str = data["name"]
        self.description: Optional[str] = data.get("description")
        self.instrument_type: str = data["type"]
        self.base_currency: str = data["baseCurrency"]
        self.quote_currency: str = data["quoteCurrency"]
        
        # Trading parameters
        self.pip_size: Decimal = Decimal(str(data["pipSize"]))
        self.min_size: Decimal = Decimal(str(data["minSize"]))
        self.max_size: Decimal = Decimal(str(data["maxSize"]))
        self.step_size: Decimal = Decimal(str(data["stepSize"]))
        self.price_precision: int = data["pricePrecision"]
        self.volume_precision: int = data["volumePrecision"]
        
        # Margin and costs
        self.margin_rate: Decimal = Decimal(str(data["marginRate"]))
        self.long_swap: Decimal = Decimal(str(data["longSwap"]))
        self.short_swap: Decimal = Decimal(str(data["shortSwap"]))
        self.commission: Optional[Decimal] = (
            Decimal(str(data["commission"])) if data.get("commission") else None
        )
        
        # Status and availability
        self.tradeable: bool = data.get("tradeable", True)
        self.market_hours: Optional[MarketHours] = (
            MarketHours(data["marketHours"]) if data.get("marketHours") else None
        )


class HistoricalData:
    """Historical market data."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.symbol: str = data["symbol"]
        self.timeframe: str = data["timeframe"]
        self.candles: List[Candlestick] = [
            Candlestick(**candle) for candle in data.get("candles", [])
        ]
        self.count: int = len(self.candles)


class PriceStatistics:
    """Price statistics for an instrument."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.symbol: str = data["symbol"]
        self.period: str = data["period"]
        self.high: Decimal = Decimal(str(data["high"]))
        self.low: Decimal = Decimal(str(data["low"]))
        self.open: Decimal = Decimal(str(data["open"]))
        self.close: Decimal = Decimal(str(data["close"]))
        self.change: Decimal = Decimal(str(data["change"]))
        self.change_percent: Decimal = Decimal(str(data["changePercent"]))
        self.volume: Optional[Decimal] = (
            Decimal(str(data["volume"])) if data.get("volume") else None
        )
        self.timestamp: float = data["timestamp"]


class InstrumentsAPI:
    """Instruments REST API client."""
    
    def __init__(self, http_client: HTTPClient):
        """Initialize with HTTP client."""
        self.http = http_client
        
    async def get_instruments(
        self, 
        instrument_filter: Optional[InstrumentFilter] = None
    ) -> List[Instrument]:
        """Get available instruments."""
        params = instrument_filter.to_params() if instrument_filter else {}
        
        response = await self.http.get("/instruments", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve instruments")
            
        return [Instrument(**instrument) for instrument in response.data]
        
    async def get_instrument(self, symbol: str) -> Instrument:
        """Get instrument by symbol."""
        response = await self.http.get(f"/instruments/{symbol}")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve instrument")
            
        return Instrument(**response.data)
        
    async def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        """Get detailed instrument specification."""
        response = await self.http.get(f"/instruments/{symbol}/spec")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve instrument spec")
            
        return InstrumentSpec(response.data)
        
    async def get_quotes(self, symbols: List[str]) -> List[Quote]:
        """Get current quotes for symbols."""
        params = {"symbols": ",".join(symbols)}
        
        response = await self.http.get("/quotes", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve quotes")
            
        return [Quote(**quote) for quote in response.data]
        
    async def get_quote(self, symbol: str) -> Quote:
        """Get current quote for a symbol."""
        quotes = await self.get_quotes([symbol])
        if not quotes:
            raise ValidationError(f"No quote available for symbol {symbol}")
        return quotes[0]
        
    async def get_market_hours(self, symbol: str) -> MarketHours:
        """Get market hours for an instrument."""
        response = await self.http.get(f"/instruments/{symbol}/market-hours")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve market hours")
            
        return MarketHours(response.data)
        
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> HistoricalData:
        """Get historical OHLC data."""
        params = {"timeframe": timeframe}
        
        if from_date:
            params["fromDate"] = int(from_date.timestamp())
        if to_date:
            params["toDate"] = int(to_date.timestamp())
        if limit:
            params["limit"] = limit
            
        response = await self.http.get(f"/instruments/{symbol}/history", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve historical data")
            
        return HistoricalData({
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": response.data
        })
        
    async def get_price_statistics(
        self,
        symbol: str,
        period: str = "24h",
    ) -> PriceStatistics:
        """Get price statistics for an instrument."""
        params = {"period": period}
        
        response = await self.http.get(f"/instruments/{symbol}/stats", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve price statistics")
            
        return PriceStatistics(response.data)
        
    async def search_instruments(self, query: str) -> List[Instrument]:
        """Search instruments by name or symbol."""
        params = {"q": query}
        
        response = await self.http.get("/instruments/search", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to search instruments")
            
        return [Instrument(**instrument) for instrument in response.data]
        
    async def get_popular_instruments(
        self, 
        instrument_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Instrument]:
        """Get popular/most traded instruments."""
        params = {"limit": limit}
        if instrument_type:
            params["type"] = instrument_type
            
        response = await self.http.get("/instruments/popular", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve popular instruments")
            
        return [Instrument(**instrument) for instrument in response.data]
        
    async def get_conversion_rates(
        self, 
        from_currency: str,
        to_currency: str,
    ) -> Dict[str, Any]:
        """Get currency conversion rates."""
        params = {
            "from": from_currency,
            "to": to_currency
        }
        
        response = await self.http.get("/conversion-rates", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve conversion rates")
            
        return response.data