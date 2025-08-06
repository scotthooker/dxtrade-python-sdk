"""Utility functions and classes for DXtrade SDK."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import TypeVar

import backoff
import httpx

from dxtrade.errors import DXtradeClockDriftError
from dxtrade.errors import DXtradeRateLimitError
from dxtrade.errors import DXtradeTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: int, burst: Optional[int] = None) -> None:
        """Initialize rate limiter.
        
        Args:
            rate: Requests per second
            burst: Maximum burst size (default: rate)
        """
        self.rate = rate
        self.burst = burst or rate
        self.tokens = float(self.burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Raises:
            DXtradeRateLimitError: Not enough tokens available
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(
                self.burst,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            
            # Calculate wait time
            wait_time = (tokens - self.tokens) / self.rate
            raise DXtradeRateLimitError(
                f"Rate limit exceeded, wait {wait_time:.2f}s",
                retry_after=int(wait_time) + 1,
                limit=self.rate,
                remaining=int(self.tokens),
            )


class IdempotencyManager:
    """Manages idempotency keys for requests."""
    
    def __init__(self) -> None:
        """Initialize idempotency manager."""
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = 3600  # 1 hour TTL

    def generate_key(self, method: str, url: str, data: Optional[bytes] = None) -> str:
        """Generate an idempotency key.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            
        Returns:
            Idempotency key
        """
        # For GET requests, don't use idempotency
        if method.upper() == "GET":
            return ""
        
        # Use UUID for unique operations
        return str(uuid.uuid4())

    def get_cached_response(self, key: str) -> Optional[Any]:
        """Get cached response for idempotency key.
        
        Args:
            key: Idempotency key
            
        Returns:
            Cached response or None
        """
        if not key:
            return None
            
        # Check if key exists and hasn't expired
        if key in self._cache:
            timestamp = self._timestamps.get(key, 0)
            if time.time() - timestamp < self._ttl:
                return self._cache[key]
            else:
                # Remove expired entry
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)
        
        return None

    def cache_response(self, key: str, response: Any) -> None:
        """Cache response for idempotency key.
        
        Args:
            key: Idempotency key
            response: Response to cache
        """
        if not key:
            return
            
        self._cache[key] = response
        self._timestamps[key] = time.time()

    def cleanup_expired(self) -> None:
        """Clean up expired cache entries."""
        now = time.time()
        expired_keys = [
            key for key, timestamp in self._timestamps.items()
            if now - timestamp >= self._ttl
        ]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)


class ClockDriftDetector:
    """Detects clock drift between client and server."""
    
    def __init__(self, threshold: float = 30.0) -> None:
        """Initialize clock drift detector.
        
        Args:
            threshold: Maximum allowed drift in seconds
        """
        self.threshold = threshold
        self._server_time_offset: Optional[float] = None

    def update_server_time(self, server_timestamp: datetime) -> None:
        """Update server time reference.
        
        Args:
            server_timestamp: Server timestamp
        """
        client_time = datetime.now(timezone.utc)
        self._server_time_offset = (server_timestamp - client_time).total_seconds()

    def check_drift(self) -> None:
        """Check for clock drift.
        
        Raises:
            DXtradeClockDriftError: Clock drift exceeds threshold
        """
        if self._server_time_offset is None:
            return
            
        if abs(self._server_time_offset) > self.threshold:
            raise DXtradeClockDriftError(
                f"Clock drift detected: {self._server_time_offset:.1f}s",
                drift=self._server_time_offset,
                threshold=self.threshold,
            )

    def get_server_time(self) -> datetime:
        """Get estimated server time.
        
        Returns:
            Estimated server time
        """
        client_time = datetime.now(timezone.utc)
        if self._server_time_offset is not None:
            server_time = client_time + timedelta(seconds=self._server_time_offset)
            return server_time
        return client_time


def exponential_backoff_with_jitter(
    base_delay: float = 0.3,
    max_delay: float = 60.0,
    max_retries: int = 3,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Exponential backoff decorator with full jitter.
    
    Args:
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        max_retries: Maximum number of retries
        jitter: Whether to add jitter
        
    Returns:
        Backoff decorator
    """
    def jitter_func(value: float) -> float:
        """Add full jitter to backoff value."""
        if not jitter:
            return value
        return random.uniform(0, value)
    
    return backoff.on_exception(
        backoff.expo,
        (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout),
        base=base_delay,
        max_value=max_delay,
        max_tries=max_retries + 1,  # backoff counts initial attempt
        jitter=jitter_func,
        logger=logger,
    )


def parse_retry_after(retry_after_header: Optional[str]) -> Optional[int]:
    """Parse Retry-After header value.
    
    Args:
        retry_after_header: Retry-After header value
        
    Returns:
        Retry after seconds or None
    """
    if not retry_after_header:
        return None
        
    try:
        # Try parsing as seconds
        return int(retry_after_header)
    except ValueError:
        # Try parsing as HTTP date (not implemented for brevity)
        return None


def parse_rate_limit_headers(headers: httpx.Headers) -> Dict[str, Any]:
    """Parse rate limit headers.
    
    Args:
        headers: HTTP response headers
        
    Returns:
        Rate limit information
    """
    rate_limit_info = {}
    
    # Standard headers
    if "X-RateLimit-Limit" in headers:
        rate_limit_info["limit"] = int(headers["X-RateLimit-Limit"])
    
    if "X-RateLimit-Remaining" in headers:
        rate_limit_info["remaining"] = int(headers["X-RateLimit-Remaining"])
    
    if "X-RateLimit-Reset" in headers:
        reset_timestamp = int(headers["X-RateLimit-Reset"])
        rate_limit_info["reset"] = datetime.fromtimestamp(reset_timestamp, timezone.utc)
    
    if "Retry-After" in headers:
        rate_limit_info["retry_after"] = parse_retry_after(headers["Retry-After"])
    
    return rate_limit_info


async def handle_rate_limit_response(response: httpx.Response) -> None:
    """Handle rate limit response.
    
    Args:
        response: HTTP response
        
    Raises:
        DXtradeRateLimitError: Rate limit exceeded
    """
    if response.status_code != 429:
        return
    
    rate_limit_info = parse_rate_limit_headers(response.headers)
    
    retry_after = rate_limit_info.get("retry_after")
    limit = rate_limit_info.get("limit")
    remaining = rate_limit_info.get("remaining")
    
    raise DXtradeRateLimitError(
        "Rate limit exceeded",
        retry_after=retry_after,
        limit=limit,
        remaining=remaining,
    )


def is_retryable_error(exception: Exception) -> bool:
    """Check if an error is retryable.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if retryable
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    
    if isinstance(exception, httpx.ConnectError):
        return True
    
    if isinstance(exception, httpx.HTTPStatusError):
        # Retry on server errors and rate limits
        return exception.response.status_code >= 500 or exception.response.status_code == 429
    
    return False


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.3,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retries
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Backoff multiplier
            jitter: Whether to add jitter
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt.
        
        Args:
            attempt: Attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Full jitter
            delay = random.uniform(0, delay)
        
        return delay


# Timing utilities
from datetime import timedelta


def utc_now() -> datetime:
    """Get current UTC datetime.
    
    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def timestamp_to_datetime(timestamp: float) -> datetime:
    """Convert timestamp to datetime.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        UTC datetime
    """
    return datetime.fromtimestamp(timestamp, timezone.utc)


def datetime_to_timestamp(dt: datetime) -> float:
    """Convert datetime to timestamp.
    
    Args:
        dt: Datetime object
        
    Returns:
        Unix timestamp
    """
    return dt.timestamp()