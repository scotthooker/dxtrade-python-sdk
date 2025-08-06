"""
HTTP client for DXTrade REST API.

Provides a robust HTTP client with authentication, rate limiting, retries,
and comprehensive error handling.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

import aiohttp
from pydantic import ValidationError

from ..errors import (
    DXtradeError,
    DXtradeHTTPError as HTTPError,
    DXtradeAuthenticationError as AuthError,
    DXtradeConnectionError as NetworkError,
    DXtradeRateLimitError as RateLimitError,
    DXtradeTimeoutError as TimeoutError,
    DXtradeValidationError
)
from ..config import (
    SDKConfig,
    AuthConfig,
    CredentialsAuth,
    HTTPMethod,
    ApiResponse,
)


class HTTPClient:
    """HTTP client for DXTrade REST API."""
    
    def __init__(self, config: SDKConfig):
        """Initialize HTTP client with configuration."""
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_token: Optional[str] = None
        self._rate_limit_window: Dict[str, float] = {}
        self._request_counts: Dict[str, int] = {}
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def close(self):
        """Close HTTP client and cleanup resources."""
        if self._session:
            await self._session.close()
            self._session = None
            
    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout / 1000)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self._get_default_headers(),
                raise_for_status=False
            )
            
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers."""
        headers = {
            "User-Agent": "DXTrade-Python-SDK/3.0.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Add authentication headers
        auth = self.config.auth
        if isinstance(auth, (SessionAuth, BearerAuth)):
            headers["Authorization"] = f"Bearer {auth.token}"
        elif isinstance(auth, HmacAuth):
            # HMAC auth will be handled per-request
            pass
            
        return headers
        
    def _get_base_url(self) -> str:
        """Get base URL for requests."""
        if self.config.base_url:
            return self.config.base_url
            
        # Default URLs based on environment
        if self.config.environment.value == "demo":
            return "https://demo-api.dx.trade/api/v1"
        else:
            return "https://api.dx.trade/api/v1"
            
    async def _check_rate_limit(self) -> None:
        """Check rate limiting constraints."""
        now = time.time()
        window_key = str(int(now / (self.config.rate_limit.window / 1000)))
        
        # Reset count if we're in a new window
        if window_key not in self._rate_limit_window:
            self._rate_limit_window.clear()
            self._request_counts.clear()
            self._rate_limit_window[window_key] = now
            
        current_count = self._request_counts.get(window_key, 0)
        if current_count >= self.config.rate_limit.requests:
            raise RateLimitError(
                f"Rate limit exceeded: {current_count} requests in window",
                retry_after=self.config.rate_limit.window / 1000
            )
            
        self._request_counts[window_key] = current_count + 1
        
    async def _sign_hmac_request(
        self, 
        method: str,
        url: str, 
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Sign request with HMAC authentication."""
        # TODO: Implement HMAC signing logic
        # This will depend on the specific HMAC requirements of DXTrade API
        return {}
        
    async def request(
        self,
        method: HTTPMethod,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None
    ) -> ApiResponse:
        """Make HTTP request with error handling and retries."""
        await self._ensure_session()
        
        # Build full URL
        base_url = self._get_base_url()
        url = urljoin(base_url, endpoint.lstrip('/'))
        
        # Prepare headers
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
            
        # Add HMAC signature if using HMAC auth
        if isinstance(self.config.auth, HmacAuth):
            hmac_headers = await self._sign_hmac_request(method.value, url, data)
            request_headers.update(hmac_headers)
            
        # Use session token if available
        if self._session_token:
            request_headers["Authorization"] = f"Bearer {self._session_token}"
            
        # Set up retry logic
        max_retries = retries if retries is not None else self.config.retries
        last_error: Optional[Exception] = None
        
        for attempt in range(max_retries + 1):
            try:
                # Check rate limits
                await self._check_rate_limit()
                
                # Make request
                async with self._session.request(
                    method.value,
                    url,
                    params=params,
                    json=data,
                    headers=request_headers,
                    timeout=aiohttp.ClientTimeout(total=timeout or self.config.timeout / 1000)
                ) as response:
                    
                    # Handle response
                    response_data = await self._handle_response(response)
                    return response_data
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                
                if attempt == max_retries:
                    break
                    
                # Wait before retry with exponential backoff
                wait_time = (2 ** attempt) * 1.0
                await asyncio.sleep(wait_time)
                
        # Handle final error
        if isinstance(last_error, asyncio.TimeoutError):
            raise TimeoutError(f"Request timed out after {max_retries + 1} attempts")
        elif isinstance(last_error, aiohttp.ClientError):
            raise NetworkError(f"Network error after {max_retries + 1} attempts: {last_error}")
        else:
            raise DXTradeError(f"Request failed after {max_retries + 1} attempts")
            
    async def _handle_response(self, response: aiohttp.ClientResponse) -> ApiResponse:
        """Handle HTTP response and extract data."""
        try:
            content = await response.text()
            
            # Try to parse JSON
            if response.content_type == 'application/json':
                try:
                    json_data = await response.json()
                except:
                    json_data = None
            else:
                json_data = None
                
            # Handle HTTP errors
            if response.status >= 400:
                error_msg = f"HTTP {response.status}: {response.reason}"
                if json_data and isinstance(json_data, dict):
                    error_msg = json_data.get('message', error_msg)
                    
                if response.status == 401:
                    raise AuthError(error_msg)
                elif response.status == 429:
                    retry_after = response.headers.get('Retry-After', '60')
                    raise RateLimitError(error_msg, retry_after=int(retry_after))
                else:
                    raise HTTPError(error_msg, status_code=response.status)
                    
            # Build successful response
            return ApiResponse(
                success=True,
                data=json_data,
                message=None,
                timestamp=time.time()
            )
            
        except (aiohttp.ClientError, ValidationError) as e:
            raise DXTradeValidationError(f"Failed to parse response: {e}")
            
    # Convenience methods
    async def get(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ApiResponse:
        """Make GET request."""
        return await self.request(HTTPMethod.GET, endpoint, params=params, **kwargs)
        
    async def post(
        self, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ApiResponse:
        """Make POST request."""
        return await self.request(HTTPMethod.POST, endpoint, data=data, **kwargs)
        
    async def put(
        self, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ApiResponse:
        """Make PUT request."""
        return await self.request(HTTPMethod.PUT, endpoint, data=data, **kwargs)
        
    async def delete(
        self, 
        endpoint: str,
        **kwargs
    ) -> ApiResponse:
        """Make DELETE request."""
        return await self.request(HTTPMethod.DELETE, endpoint, **kwargs)
        
    # Authentication methods
    def set_session_token(self, token: str) -> None:
        """Set session token for authentication."""
        self._session_token = token
        
    def get_session_token(self) -> Optional[str]:
        """Get current session token."""
        return self._session_token
        
    def clear_session_token(self) -> None:
        """Clear session token."""
        self._session_token = None
        
    # Status methods
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        now = time.time()
        window_key = str(int(now / (self.config.rate_limit.window / 1000)))
        current_count = self._request_counts.get(window_key, 0)
        
        return {
            "requests_made": current_count,
            "requests_limit": self.config.rate_limit.requests,
            "window_ms": self.config.rate_limit.window,
            "reset_time": (int(window_key) + 1) * (self.config.rate_limit.window / 1000)
        }
        
    def get_clock_sync_status(self) -> Dict[str, Any]:
        """Get clock sync status (placeholder for future implementation)."""
        return {
            "enabled": self.config.features.clock_sync,
            "drift_ms": 0,
            "last_sync": None,
            "next_sync": None
        }