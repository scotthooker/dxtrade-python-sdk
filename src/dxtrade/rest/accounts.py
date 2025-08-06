"""Accounts API endpoints."""

from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from dxtrade.models import Account
from dxtrade.models import Balance
from dxtrade.rest.base import BaseAPI


class AccountsAPI(BaseAPI):
    """API for account management and balance retrieval."""
    
    async def get_accounts(
        self,
        *,
        timeout: Optional[float] = None,
    ) -> List[Account]:
        """Get all accounts for the authenticated user.
        
        Args:
            timeout: Request timeout
            
        Returns:
            List of accounts
        """
        return await self._get_list("/accounts", Account, timeout=timeout)
    
    async def get_account(
        self,
        account_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Account:
        """Get account by ID.
        
        Args:
            account_id: Account identifier
            timeout: Request timeout
            
        Returns:
            Account information
        """
        return await self._get_data(f"/accounts/{account_id}", Account, timeout=timeout)
    
    async def get_account_balances(
        self,
        account_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> List[Balance]:
        """Get balances for an account.
        
        Args:
            account_id: Account identifier
            timeout: Request timeout
            
        Returns:
            List of balances by currency
        """
        return await self._get_list(
            f"/accounts/{account_id}/balances",
            Balance,
            timeout=timeout
        )
    
    async def get_account_balance(
        self,
        account_id: str,
        currency: str,
        *,
        timeout: Optional[float] = None,
    ) -> Balance:
        """Get balance for specific currency.
        
        Args:
            account_id: Account identifier
            currency: Currency code
            timeout: Request timeout
            
        Returns:
            Balance information
        """
        return await self._get_data(
            f"/accounts/{account_id}/balances/{currency}",
            Balance,
            timeout=timeout
        )
    
    async def get_account_summary(
        self,
        account_id: str,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, float]:
        """Get account summary with key metrics.
        
        Args:
            account_id: Account identifier
            timeout: Request timeout
            
        Returns:
            Account summary data
        """
        response = await self._request("GET", f"/accounts/{account_id}/summary", timeout=timeout)
        data = response.json()
        
        # Return the summary data directly (not wrapped in a model for flexibility)
        return data.get("data", {}) if isinstance(data, dict) else data