"""
Accounts REST API client.

Provides methods for managing accounts, balances, history, and statistics.
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal

from ..core.http_client import HTTPClient
from ..types.trading import Account
from ..types.common import ApiResponse
from ..errors import ValidationError


class AccountBalance:
    """Account balance information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.account_id: str = data["accountId"]
        self.currency: str = data["currency"]
        self.balance: Decimal = Decimal(str(data["balance"]))
        self.available_balance: Decimal = Decimal(str(data["availableBalance"]))
        self.equity: Decimal = Decimal(str(data["equity"]))
        self.margin: Decimal = Decimal(str(data["margin"]))
        self.free_margin: Decimal = Decimal(str(data["freeMargin"]))
        self.margin_level: Optional[Decimal] = (
            Decimal(str(data["marginLevel"])) if data.get("marginLevel") else None
        )
        self.profit: Decimal = Decimal(str(data["profit"]))
        self.credit: Optional[Decimal] = (
            Decimal(str(data["credit"])) if data.get("credit") else None
        )
        self.commission: Optional[Decimal] = (
            Decimal(str(data["commission"])) if data.get("commission") else None
        )
        self.swap: Optional[Decimal] = (
            Decimal(str(data["swap"])) if data.get("swap") else None
        )
        self.timestamp: float = data["timestamp"]


class AccountSummary:
    """Account summary information."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.account_id: str = data["accountId"]
        self.total_equity: Decimal = Decimal(str(data["totalEquity"]))
        self.total_balance: Decimal = Decimal(str(data["totalBalance"]))
        self.total_margin: Decimal = Decimal(str(data["totalMargin"]))
        self.total_free_margin: Decimal = Decimal(str(data["totalFreeMargin"]))
        self.total_profit: Decimal = Decimal(str(data["totalProfit"]))
        self.margin_level: Decimal = Decimal(str(data["marginLevel"]))
        self.currency: str = data["currency"]
        self.leverage: Decimal = Decimal(str(data["leverage"]))
        self.open_positions: int = data["openPositions"]
        self.pending_orders: int = data["pendingOrders"]
        self.last_update: float = data["lastUpdate"]


class AccountHistoryEntry:
    """Account history entry."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize from API response data."""
        self.id: str = data["id"]
        self.account_id: str = data["accountId"]
        self.type: str = data["type"]
        self.amount: Decimal = Decimal(str(data["amount"]))
        self.currency: str = data["currency"]
        self.description: Optional[str] = data.get("description")
        self.reference: Optional[str] = data.get("reference")
        self.timestamp: float = data["timestamp"]


class AccountsAPI:
    """Accounts REST API client."""
    
    def __init__(self, http_client: HTTPClient):
        """Initialize with HTTP client."""
        self.http = http_client
        
    async def get_accounts(self) -> List[Account]:
        """Get all accounts for the authenticated user."""
        response = await self.http.get("/accounts")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve accounts")
            
        # Convert response data to Account objects
        accounts = []
        for account_data in response.data:
            accounts.append(Account(**account_data))
            
        return accounts
        
    async def get_account(self, account_id: str) -> Account:
        """Get account by ID."""
        response = await self.http.get(f"/accounts/{account_id}")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve account")
            
        return Account(**response.data)
        
    async def get_account_balance(self, account_id: str) -> AccountBalance:
        """Get account balance information."""
        response = await self.http.get(f"/accounts/{account_id}/balance")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve account balance")
            
        return AccountBalance(response.data)
        
    async def get_account_summary(self, account_id: str) -> AccountSummary:
        """Get account summary with aggregated information."""
        response = await self.http.get(f"/accounts/{account_id}/summary")
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve account summary")
            
        return AccountSummary(response.data)
        
    async def get_account_history(
        self,
        account_id: Optional[str] = None,
        history_type: Optional[str] = None,
        from_date: Optional[float] = None,
        to_date: Optional[float] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get account transaction history."""
        params = {}
        
        if account_id:
            params["accountId"] = account_id
        if history_type:
            params["type"] = history_type
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if page:
            params["page"] = page
        if limit:
            params["limit"] = limit
            
        response = await self.http.get("/accounts/history", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve account history")
            
        # Convert entries to AccountHistoryEntry objects
        entries = [AccountHistoryEntry(entry) for entry in response.data.get("entries", [])]
        
        return {
            "entries": entries,
            "pagination": response.data.get("pagination")
        }
        
    async def get_equity_curve(
        self,
        account_id: str,
        from_date: Optional[float] = None,
        to_date: Optional[float] = None,
        interval: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get account equity curve data."""
        params = {}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if interval:
            params["interval"] = interval
            
        response = await self.http.get(f"/accounts/{account_id}/equity-curve", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve equity curve")
            
        return response.data
        
    async def get_account_statistics(
        self,
        account_id: str,
        from_date: Optional[float] = None,
        to_date: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Get account statistics."""
        params = {}
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
            
        response = await self.http.get(f"/accounts/{account_id}/statistics", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to retrieve account statistics")
            
        return response.data
        
    async def calculate_margin_requirement(
        self,
        account_id: str,
        symbol: str,
        volume: Decimal,
        side: str,
    ) -> Dict[str, Any]:
        """Get account margin requirements for a potential position."""
        params = {
            "symbol": symbol,
            "volume": str(volume),
            "side": side,
        }
        
        response = await self.http.get(f"/accounts/{account_id}/margin-requirement", params=params)
        
        if not response.success or not response.data:
            raise ValidationError(response.message or "Failed to calculate margin requirement")
            
        return response.data
        
    async def get_info(self) -> ApiResponse:
        """Get account information - simplified for DXTrade API."""
        return await self.http.get("/accounts")