"""
Positions REST API client.

Provides methods for managing trading positions and portfolio information.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

from ..core.http_client import HTTPClient
from ..types.trading import Position, PositionSide
from ..errors import ValidationError


class PositionQuery:
    """Position query parameters."""
    
    def __init__(
        self,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        side: Optional[PositionSide] = None,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        """Initialize position query."""
        self.account_id = account_id
        self.symbol = symbol
        self.side = side
        self.status = status
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
        if self.side:
            params["side"] = self.side.value
        if self.status:
            params["status"] = self.status
        if self.from_date:
            params["fromDate"] = int(self.from_date.timestamp())
        if self.to_date:
            params["toDate"] = int(self.to_date.timestamp())
        if self.page:
            params["page"] = self.page
        if self.limit:
            params["limit"] = self.limit
        return params


class PositionModification:
    """Position modification parameters."""
    
    def __init__(
        self,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        comment: Optional[str] = None,
    ):
        """Initialize position modification."""
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.comment = comment
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to request data."""
        data = {}
        if self.stop_loss is not None:
            data["stopLoss"] = str(self.stop_loss)
        if self.take_profit is not None:
            data["takeProfit"] = str(self.take_profit)
        if self.comment is not None:
            data["comment"] = self.comment
        return data


class PositionCloseRequest:
    """Position close request parameters."""
    
    def __init__(
        self,
        volume: Optional[Decimal] = None,  # None means close entire position
        price: Optional[Decimal] = None,   # Market order if None
        comment: Optional[str] = None,
    ):
        """Initialize position close request."""
        self.volume = volume
        self.price = price
        self.comment = comment
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to request data."""
        data = {}
        if self.volume is not None:
            data["volume"] = str(self.volume)
        if self.price is not None:
            data["price"] = str(self.price)
        if self.comment is not None:
            data["comment"] = self.comment
        return data


class PositionStatistics:
    """Position statistics information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.position_id: str = data["positionId"]
        self.symbol: str = data["symbol"]
        self.duration: int = data["duration"]  # Duration in seconds
        self.max_profit: Decimal = Decimal(str(data["maxProfit"]))
        self.max_loss: Decimal = Decimal(str(data["maxLoss"]))
        self.current_profit: Decimal = Decimal(str(data["currentProfit"]))
        self.profit_factor: Decimal = Decimal(str(data.get("profitFactor", "0")))
        self.win_rate: Decimal = Decimal(str(data.get("winRate", "0")))
        self.total_commission: Decimal = Decimal(str(data.get("totalCommission", "0")))
        self.total_swap: Decimal = Decimal(str(data.get("totalSwap", "0")))


class PositionRisk:
    """Position risk information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.position_id: str = data["positionId"]
        self.symbol: str = data["symbol"]
        self.risk_score: Decimal = Decimal(str(data["riskScore"]))
        self.margin_used: Decimal = Decimal(str(data["marginUsed"]))
        self.margin_available: Decimal = Decimal(str(data["marginAvailable"]))
        self.margin_call_level: Decimal = Decimal(str(data["marginCallLevel"]))
        self.stop_out_level: Decimal = Decimal(str(data["stopOutLevel"]))
        self.risk_warnings: List[str] = data.get("riskWarnings", [])


class PortfolioSummary:
    """Portfolio summary information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.account_id: str = data["accountId"]
        self.total_positions: int = data["totalPositions"]
        self.total_volume: Decimal = Decimal(str(data["totalVolume"]))
        self.total_margin_used: Decimal = Decimal(str(data["totalMarginUsed"]))
        self.total_unrealized_pnl: Decimal = Decimal(str(data["totalUnrealizedPnl"]))
        self.total_realized_pnl: Decimal = Decimal(str(data["totalRealizedPnl"]))
        self.total_commission: Decimal = Decimal(str(data["totalCommission"]))
        self.total_swap: Decimal = Decimal(str(data["totalSwap"]))
        self.currency: str = data["currency"]
        self.last_update: datetime = datetime.fromtimestamp(data["lastUpdate"])
        
        # Positions by symbol
        self.positions_by_symbol: Dict[str, int] = data.get("positionsBySymbol", {})
        
        # Positions by side
        self.long_positions: int = data.get("longPositions", 0)
        self.short_positions: int = data.get("shortPositions", 0)


class PositionsAPI:
    """Positions REST API client."""
    
    def __init__(self, http_client: HTTPClient):
        """Initialize with HTTP client."""
        self.http = http_client
        
    async def get_positions(
        self, 
        query: Optional[PositionQuery] = None
    ) -> Dict[str, Any]:
        """Get positions with optional filtering."""
        params = query.to_params() if query else {}
        
        response = await self.http.get("/positions", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve positions")
            
        positions = [Position(**position) for position in response.data.get("positions", [])]
        
        return {
            "positions": positions,
            "pagination": response.data.get("pagination")
        }
        
    async def get_position(self, position_id: str) -> Position:
        """Get position by ID."""
        response = await self.http.get(f"/positions/{position_id}")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve position")
            
        return Position(**response.data)
        
    async def modify_position(
        self,
        position_id: str,
        modification: PositionModification
    ) -> Position:
        """Modify position (e.g., set stop loss/take profit)."""
        data = modification.to_dict()
        
        response = await self.http.put(f"/positions/{position_id}", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to modify position")
            
        return Position(**response.data)
        
    async def close_position(
        self,
        position_id: str,
        close_request: Optional[PositionCloseRequest] = None
    ) -> Position:
        """Close position (partially or completely)."""
        data = close_request.to_dict() if close_request else {}
        
        response = await self.http.post(f"/positions/{position_id}/close", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to close position")
            
        return Position(**response.data)
        
    async def close_positions(
        self,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Position]:
        """Close multiple positions."""
        data = {}
        if account_id:
            data["accountId"] = account_id
        if symbol:
            data["symbol"] = symbol
            
        response = await self.http.post("/positions/close", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to close positions")
            
        return [Position(**position) for position in response.data]
        
    async def get_position_history(
        self,
        query: Optional[PositionQuery] = None
    ) -> Dict[str, Any]:
        """Get position history (closed positions)."""
        params = query.to_params() if query else {}
        
        response = await self.http.get("/positions/history", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve position history")
            
        positions = [Position(**position) for position in response.data.get("positions", [])]
        
        return {
            "positions": positions,
            "pagination": response.data.get("pagination")
        }
        
    async def get_position_statistics(self, position_id: str) -> PositionStatistics:
        """Get detailed position statistics."""
        response = await self.http.get(f"/positions/{position_id}/statistics")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve position statistics")
            
        return PositionStatistics(response.data)
        
    async def get_position_risk(self, position_id: str) -> PositionRisk:
        """Get position risk assessment."""
        response = await self.http.get(f"/positions/{position_id}/risk")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve position risk")
            
        return PositionRisk(response.data)
        
    async def get_portfolio_summary(self, account_id: str) -> PortfolioSummary:
        """Get portfolio summary for an account."""
        response = await self.http.get(f"/accounts/{account_id}/portfolio")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve portfolio summary")
            
        return PortfolioSummary(response.data)
        
    async def get_portfolio_performance(
        self,
        account_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get portfolio performance metrics."""
        params = {}
        if from_date:
            params["fromDate"] = int(from_date.timestamp())
        if to_date:
            params["toDate"] = int(to_date.timestamp())
            
        response = await self.http.get(f"/accounts/{account_id}/performance", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve portfolio performance")
            
        return response.data
        
    async def get_portfolio_risk(self, account_id: str) -> Dict[str, Any]:
        """Get overall portfolio risk assessment."""
        response = await self.http.get(f"/accounts/{account_id}/risk")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve portfolio risk")
            
        return response.data
        
    async def calculate_position_size(
        self,
        account_id: str,
        symbol: str,
        risk_percent: Decimal,
        stop_loss_distance: Decimal,
    ) -> Dict[str, Any]:
        """Calculate optimal position size based on risk parameters."""
        data = {
            "symbol": symbol,
            "riskPercent": str(risk_percent),
            "stopLossDistance": str(stop_loss_distance),
        }
        
        response = await self.http.post(f"/accounts/{account_id}/position-size", data=data)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to calculate position size")
            
        return response.data