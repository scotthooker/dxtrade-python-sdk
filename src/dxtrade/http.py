"""Async HTTP client with retry/backoff and rate limiting."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

import httpx

from dxtrade.auth import AuthHandler
from dxtrade.errors import DXtradeHTTPError
from dxtrade.errors import DXtradeRateLimitError
from dxtrade.errors import DXtradeTimeoutError
from dxtrade.models import HTTPConfig
from dxtrade.utils import ClockDriftDetector
from dxtrade.utils import IdempotencyManager
from dxtrade.utils import RateLimiter
from dxtrade.utils import RetryConfig
from dxtrade.utils import handle_rate_limit_response
from dxtrade.utils import is_retryable_error
from dxtrade.utils import parse_rate_limit_headers
from dxtrade.utils import utc_now

logger = logging.getLogger(__name__)


class DXtradeHTTPClient:
    """Async HTTP client with retry, rate limiting, and authentication."""
    
    def __init__(
        self,
        config: HTTPConfig,
        auth_handler: Optional[AuthHandler] = None,
    ) -> None:
        """Initialize HTTP client.
        
        Args:
            config: HTTP configuration
            auth_handler: Authentication handler
        """
        self.config = config
        self.auth_handler = auth_handler
        
        # Initialize components
        self._rate_limiter: Optional[RateLimiter] = None
        if config.rate_limit:
            self._rate_limiter = RateLimiter(config.rate_limit)
        
        self._idempotency_manager = IdempotencyManager()
        self._clock_drift_detector = ClockDriftDetector()
        self._retry_config = RetryConfig(
            max_retries=config.max_retries,
            base_delay=config.retry_backoff_factor,
        )
        
        # HTTP client configuration
        timeout = httpx.Timeout(config.timeout)
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=30.0,
        )
        
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=timeout,
            limits=limits,
            headers={"User-Agent": config.user_agent},
            follow_redirects=True,
        )
        
        self._session_lock = asyncio.Lock()
    
    async def __aenter__(self) -> DXtradeHTTPClient:
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry and rate limiting.
        
        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            data: Request data
            json: JSON data
            headers: Additional headers
            timeout: Request timeout
            retries: Max retries for this request
            idempotency_key: Idempotency key
            
        Returns:
            HTTP response
            
        Raises:
            DXtradeHTTPError: HTTP error
            DXtradeRateLimitError: Rate limit exceeded
            DXtradeTimeoutError: Request timeout
        """
        # Apply rate limiting
        if self._rate_limiter:
            try:
                await self._rate_limiter.acquire()
            except DXtradeRateLimitError:
                # Rate limiter says to wait - respect that
                raise
        
        # Generate idempotency key if needed
        if idempotency_key is None:
            request_data = None
            if json:
                request_data = httpx._content.encode_json(json)
            elif data:
                if isinstance(data, (bytes, str)):
                    request_data = data
                else:
                    request_data = str(data)
            idempotency_key = self._idempotency_manager.generate_key(
                method, url, request_data.encode() if isinstance(request_data, str) else request_data
            )
        
        # Check for cached response
        if idempotency_key:
            cached_response = self._idempotency_manager.get_cached_response(idempotency_key)
            if cached_response:
                logger.debug(f"Returning cached response for {method} {url}")
                return cached_response
        
        # Prepare request
        request_headers = headers.copy() if headers else {}
        if idempotency_key:
            request_headers["Idempotency-Key"] = idempotency_key
        
        # Set timeout
        request_timeout = timeout or self.config.timeout
        
        # Determine retry count
        max_retries = retries if retries is not None else self._retry_config.max_retries
        
        # Make request with retries
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                # Build request
                request = self._client.build_request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json,
                    headers=request_headers,
                    timeout=request_timeout,
                )
                
                # Authenticate request
                if self.auth_handler:
                    request = await self.auth_handler.authenticate(request, self._client)
                
                # Execute request
                response = await self._client.send(request)
                
                # Handle rate limiting
                await handle_rate_limit_response(response)
                
                # Update server time for clock drift detection
                if "Date" in response.headers:
                    try:
                        server_date = httpx._utils.parse_header_date(response.headers["Date"])
                        self._clock_drift_detector.update_server_time(server_date)
                        self._clock_drift_detector.check_drift()
                    except Exception as e:
                        logger.debug(f"Failed to parse server date: {e}")
                
                # Check for HTTP errors
                if response.status_code >= 400:
                    await self._handle_http_error(response)
                
                # Cache successful response
                if idempotency_key and 200 <= response.status_code < 300:
                    self._idempotency_manager.cache_response(idempotency_key, response)
                
                # Log successful request
                logger.debug(
                    f"{method} {url} -> {response.status_code} "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                
                return response
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                if attempt >= max_retries or not is_retryable_error(e):
                    break
                
                # Calculate delay for next attempt
                delay = self._retry_config.calculate_delay(attempt)
                
                logger.warning(
                    f"{method} {url} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        if isinstance(last_exception, httpx.TimeoutException):
            raise DXtradeTimeoutError(
                f"Request timeout after {max_retries + 1} attempts",
                timeout=request_timeout,
            ) from last_exception
        
        raise DXtradeHTTPError(
            f"Request failed after {max_retries + 1} attempts: {last_exception}",
            status_code=0,
        ) from last_exception
    
    async def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP error response.
        
        Args:
            response: HTTP error response
            
        Raises:
            DXtradeHTTPError: HTTP error
            DXtradeRateLimitError: Rate limit error
        """
        # Parse rate limit info
        rate_limit_info = parse_rate_limit_headers(response.headers)
        
        try:
            error_data = response.json()
        except Exception:
            error_data = {"message": response.text or f"HTTP {response.status_code}"}
        
        error_message = error_data.get("message", f"HTTP {response.status_code}")
        error_code = error_data.get("error_code", "HTTP_ERROR")
        details = error_data.get("details", {})
        
        # Handle rate limiting
        if response.status_code == 429:
            raise DXtradeRateLimitError(
                error_message,
                retry_after=rate_limit_info.get("retry_after"),
                limit=rate_limit_info.get("limit"),
                remaining=rate_limit_info.get("remaining"),
                details=details,
            )
        
        # Handle other HTTP errors
        raise DXtradeHTTPError(
            error_message,
            status_code=response.status_code,
            response_text=response.text,
            error_code=error_code,
            details=details,
        )
    
    # Convenience methods
    async def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Make GET request.
        
        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout
            
        Returns:
            HTTP response
        """
        return await self.request("GET", url, params=params, headers=headers, timeout=timeout)
    
    async def post(
        self,
        url: str,
        *,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Make POST request.
        
        Args:
            url: Request URL
            data: Request data
            json: JSON data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            HTTP response
        """
        return await self.request(
            "POST", url, data=data, json=json, headers=headers,
            timeout=timeout, idempotency_key=idempotency_key
        )
    
    async def put(
        self,
        url: str,
        *,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Make PUT request.
        
        Args:
            url: Request URL
            data: Request data
            json: JSON data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            HTTP response
        """
        return await self.request(
            "PUT", url, data=data, json=json, headers=headers,
            timeout=timeout, idempotency_key=idempotency_key
        )
    
    async def patch(
        self,
        url: str,
        *,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Make PATCH request.
        
        Args:
            url: Request URL
            data: Request data
            json: JSON data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            HTTP response
        """
        return await self.request(
            "PATCH", url, data=data, json=json, headers=headers,
            timeout=timeout, idempotency_key=idempotency_key
        )
    
    async def delete(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Make DELETE request.
        
        Args:
            url: Request URL
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            HTTP response
        """
        return await self.request(
            "DELETE", url, headers=headers, timeout=timeout,
            idempotency_key=idempotency_key
        )