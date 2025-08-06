"""Exception classes for DXtrade SDK."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Optional


class DXtradeError(Exception):
    """Base exception for all DXtrade SDK errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize DXtrade error.
        
        Args:
            message: Error message
            error_code: Optional error code
            details: Optional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        """Detailed representation of the error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"details={self.details!r})"
        )


class DXtradeHTTPError(DXtradeError):
    """HTTP-related error from DXtrade API."""
    
    def __init__(
        self,
        message: str,
        status_code: int,
        response_text: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize HTTP error.
        
        Args:
            message: Error message
            status_code: HTTP status code
            response_text: Raw response text
            error_code: Optional error code
            details: Optional error details
        """
        super().__init__(message, error_code, details)
        self.status_code = status_code
        self.response_text = response_text

    def __str__(self) -> str:
        """String representation of the HTTP error."""
        base = super().__str__()
        return f"HTTP {self.status_code}: {base}"


class DXtradeRateLimitError(DXtradeHTTPError):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        remaining: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retry
            limit: Rate limit
            remaining: Remaining requests
            details: Optional error details
        """
        super().__init__(message, 429, error_code="RATE_LIMIT_EXCEEDED", details=details)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining

    def __str__(self) -> str:
        """String representation of the rate limit error."""
        base = super().__str__()
        if self.retry_after:
            return f"{base} (retry after {self.retry_after}s)"
        return base


class DXtradeTimeoutError(DXtradeError):
    """Request timeout error."""
    
    def __init__(
        self,
        message: str = "Request timed out",
        timeout: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize timeout error.
        
        Args:
            message: Error message
            timeout: Timeout value in seconds
            details: Optional error details
        """
        super().__init__(message, "TIMEOUT", details)
        self.timeout = timeout

    def __str__(self) -> str:
        """String representation of the timeout error."""
        base = super().__str__()
        if self.timeout:
            return f"{base} (timeout: {self.timeout}s)"
        return base


class DXtradeAuthenticationError(DXtradeHTTPError):
    """Authentication failed error."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize authentication error.
        
        Args:
            message: Error message
            details: Optional error details
        """
        super().__init__(message, 401, error_code="AUTHENTICATION_FAILED", details=details)


class DXtradeAuthorizationError(DXtradeHTTPError):
    """Authorization failed error."""
    
    def __init__(
        self,
        message: str = "Authorization failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize authorization error.
        
        Args:
            message: Error message
            details: Optional error details
        """
        super().__init__(message, 403, error_code="AUTHORIZATION_FAILED", details=details)


class DXtradeValidationError(DXtradeHTTPError):
    """Request validation error."""
    
    def __init__(
        self,
        message: str = "Request validation failed",
        field_errors: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize validation error.
        
        Args:
            message: Error message
            field_errors: Field-specific validation errors
            details: Optional error details
        """
        super().__init__(message, 400, error_code="VALIDATION_ERROR", details=details)
        self.field_errors = field_errors or {}

    def __str__(self) -> str:
        """String representation of the validation error."""
        base = super().__str__()
        if self.field_errors:
            errors = ", ".join(f"{field}: {error}" for field, error in self.field_errors.items())
            return f"{base} ({errors})"
        return base


class DXtradeWebSocketError(DXtradeError):
    """WebSocket connection or communication error."""
    
    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize WebSocket error.
        
        Args:
            message: Error message
            code: WebSocket close code
            reason: Close reason
            details: Optional error details
        """
        super().__init__(message, "WEBSOCKET_ERROR", details)
        self.code = code
        self.reason = reason

    def __str__(self) -> str:
        """String representation of the WebSocket error."""
        base = super().__str__()
        if self.code and self.reason:
            return f"{base} (code: {self.code}, reason: {self.reason})"
        elif self.code:
            return f"{base} (code: {self.code})"
        return base


class DXtradeConnectionError(DXtradeError):
    """Network connection error."""
    
    def __init__(
        self,
        message: str = "Connection failed",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize connection error.
        
        Args:
            message: Error message
            details: Optional error details
        """
        super().__init__(message, "CONNECTION_ERROR", details)


class DXtradeConfigurationError(DXtradeError):
    """Configuration error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize configuration error.
        
        Args:
            message: Error message
            details: Optional error details
        """
        super().__init__(message, "CONFIGURATION_ERROR", details)


class DXtradeClockDriftError(DXtradeError):
    """Clock drift error."""
    
    def __init__(
        self,
        message: str = "Clock drift detected",
        drift: Optional[float] = None,
        threshold: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize clock drift error.
        
        Args:
            message: Error message
            drift: Clock drift in seconds
            threshold: Threshold in seconds
            details: Optional error details
        """
        super().__init__(message, "CLOCK_DRIFT", details)
        self.drift = drift
        self.threshold = threshold

    def __str__(self) -> str:
        """String representation of the clock drift error."""
        base = super().__str__()
        if self.drift and self.threshold:
            return f"{base} (drift: {self.drift}s, threshold: {self.threshold}s)"
        return base


class DXtradeDataError(DXtradeError):
    """Data processing or validation error."""
    
    def __init__(
        self,
        message: str,
        data: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize data error.
        
        Args:
            message: Error message
            data: Invalid data that caused the error
            details: Optional error details
        """
        super().__init__(message, "DATA_ERROR", details)
        self.data = data