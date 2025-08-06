"""Authentication handlers for DXtrade API."""

from __future__ import annotations

import hashlib
import hmac
import time
from abc import ABC
from abc import abstractmethod
from base64 import b64encode
from typing import Any
from typing import Dict
from typing import Optional
from urllib.parse import urlencode

import httpx

from dxtrade.errors import DXtradeAuthenticationError
from dxtrade.errors import DXtradeConfigurationError
from dxtrade.models import AnyCredentials
from dxtrade.models import AuthType
from dxtrade.models import BearerTokenCredentials
from dxtrade.models import HMACCredentials
from dxtrade.models import SessionCredentials


class AuthHandler(ABC):
    """Base class for authentication handlers."""
    
    def __init__(self, credentials: AnyCredentials) -> None:
        """Initialize auth handler.
        
        Args:
            credentials: Authentication credentials
        """
        self.credentials = credentials

    @abstractmethod
    async def authenticate(
        self,
        request: httpx.Request,
        client: httpx.AsyncClient,
    ) -> httpx.Request:
        """Authenticate a request.
        
        Args:
            request: HTTP request to authenticate
            client: HTTP client for making additional requests
            
        Returns:
            Authenticated request
            
        Raises:
            DXtradeAuthenticationError: Authentication failed
        """

    @abstractmethod
    def get_auth_type(self) -> AuthType:
        """Get the authentication type.
        
        Returns:
            Authentication type
        """


class BearerTokenHandler(AuthHandler):
    """Bearer token authentication handler."""
    
    def __init__(self, credentials: BearerTokenCredentials) -> None:
        """Initialize bearer token handler.
        
        Args:
            credentials: Bearer token credentials
        """
        if not isinstance(credentials, BearerTokenCredentials):
            raise DXtradeConfigurationError(
                "Bearer token handler requires BearerTokenCredentials"
            )
        super().__init__(credentials)
        self.credentials: BearerTokenCredentials = credentials

    async def authenticate(
        self,
        request: httpx.Request,
        client: httpx.AsyncClient,
    ) -> httpx.Request:
        """Authenticate request with bearer token.
        
        Args:
            request: HTTP request to authenticate
            client: HTTP client (unused for bearer token)
            
        Returns:
            Authenticated request
        """
        request.headers["Authorization"] = f"Bearer {self.credentials.token}"
        return request

    def get_auth_type(self) -> AuthType:
        """Get the authentication type.
        
        Returns:
            Bearer token auth type
        """
        return AuthType.BEARER_TOKEN


class HMACHandler(AuthHandler):
    """HMAC authentication handler."""
    
    def __init__(self, credentials: HMACCredentials) -> None:
        """Initialize HMAC handler.
        
        Args:
            credentials: HMAC credentials
        """
        if not isinstance(credentials, HMACCredentials):
            raise DXtradeConfigurationError(
                "HMAC handler requires HMACCredentials"
            )
        super().__init__(credentials)
        self.credentials: HMACCredentials = credentials

    async def authenticate(
        self,
        request: httpx.Request,
        client: httpx.AsyncClient,
    ) -> httpx.Request:
        """Authenticate request with HMAC signature.
        
        Args:
            request: HTTP request to authenticate
            client: HTTP client (unused for HMAC)
            
        Returns:
            Authenticated request
        """
        timestamp = str(int(time.time() * 1000))
        
        # Prepare signature components
        method = request.method.upper()
        path = str(request.url.path)
        if request.url.query:
            path += f"?{request.url.query}"
        
        body = ""
        if request.content:
            body = request.content.decode("utf-8")
        
        # Create signature string
        signature_string = f"{timestamp}{method}{path}{body}"
        if self.credentials.passphrase:
            signature_string += self.credentials.passphrase
        
        # Generate HMAC signature
        signature = hmac.new(
            self.credentials.secret_key.encode("utf-8"),
            signature_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = b64encode(signature).decode("utf-8")
        
        # Add authentication headers
        request.headers["DX-API-KEY"] = self.credentials.api_key
        request.headers["DX-API-TIMESTAMP"] = timestamp
        request.headers["DX-API-SIGNATURE"] = signature_b64
        
        if self.credentials.passphrase:
            request.headers["DX-API-PASSPHRASE"] = self.credentials.passphrase
        
        return request

    def get_auth_type(self) -> AuthType:
        """Get the authentication type.
        
        Returns:
            HMAC auth type
        """
        return AuthType.HMAC


class SessionHandler(AuthHandler):
    """Session-based authentication handler."""
    
    def __init__(self, credentials: SessionCredentials) -> None:
        """Initialize session handler.
        
        Args:
            credentials: Session credentials
        """
        if not isinstance(credentials, SessionCredentials):
            raise DXtradeConfigurationError(
                "Session handler requires SessionCredentials"
            )
        super().__init__(credentials)
        self.credentials: SessionCredentials = credentials
        self._session_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        self._last_login: Optional[float] = None

    async def authenticate(
        self,
        request: httpx.Request,
        client: httpx.AsyncClient,
    ) -> httpx.Request:
        """Authenticate request with session token.
        
        Args:
            request: HTTP request to authenticate
            client: HTTP client for session management
            
        Returns:
            Authenticated request
            
        Raises:
            DXtradeAuthenticationError: Authentication failed
        """
        # Check if we need to get/refresh session token
        if not self._session_token or self._is_token_expired():
            await self._refresh_session_token(client)
        
        if not self._session_token:
            raise DXtradeAuthenticationError("Failed to obtain session token")
        
        # Add both X-Auth-Token and Authorization headers as shown in the example
        request.headers["X-Auth-Token"] = self._session_token
        request.headers["Authorization"] = f"DXAPI {self._session_token}"
        return request

    async def _refresh_session_token(self, client: httpx.AsyncClient) -> None:
        """Refresh the session token.
        
        Args:
            client: HTTP client for authentication request
            
        Raises:
            DXtradeAuthenticationError: Authentication failed
        """
        try:
            login_data = {
                "username": self.credentials.username,
                "password": self.credentials.password,
                "domain": self.credentials.domain or "default",
            }
            
            response = await client.post("/login", json=login_data)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract session token directly from response
            self._session_token = data.get("sessionToken")
            
            if not self._session_token:
                raise DXtradeAuthenticationError(
                    data.get("message", "No session token in response")
                )
            
            # Set token expiration (default to 1 hour as per example)
            self._token_expires_at = time.time() + 3600 - 300  # 1 hour with 5 min buffer
            self._last_login = time.time()
                
        except httpx.HTTPError as e:
            raise DXtradeAuthenticationError(f"Login request failed: {e}") from e

    def _is_token_expired(self) -> bool:
        """Check if the current token is expired.
        
        Returns:
            True if token is expired or expiring soon
        """
        if not self._token_expires_at or not self._last_login:
            return True
        
        # Re-login if session is older than 1 hour (as per example)
        if (time.time() - self._last_login) > 3600:
            return True
            
        return time.time() >= self._token_expires_at

    def get_auth_type(self) -> AuthType:
        """Get the authentication type.
        
        Returns:
            Session auth type
        """
        return AuthType.SESSION

    async def logout(self, client: httpx.AsyncClient) -> None:
        """Log out and invalidate the session token.
        
        Args:
            client: HTTP client for logout request
        """
        if not self._session_token:
            return
        
        try:
            # Try to invalidate token on server
            headers = {
                "X-Auth-Token": self._session_token,
                "Authorization": f"DXAPI {self._session_token}"
            }
            await client.post("/logout", headers=headers)
        except httpx.HTTPError:
            # Ignore logout errors - we'll clear the token anyway
            pass
        finally:
            self._session_token = None
            self._token_expires_at = None
            self._last_login = None


class AuthFactory:
    """Factory for creating authentication handlers."""
    
    _handlers: Dict[AuthType, type[AuthHandler]] = {
        AuthType.BEARER_TOKEN: BearerTokenHandler,
        AuthType.HMAC: HMACHandler,
        AuthType.SESSION: SessionHandler,
    }

    @classmethod
    def create_handler(
        self,
        auth_type: AuthType,
        credentials: AnyCredentials,
    ) -> AuthHandler:
        """Create an authentication handler.
        
        Args:
            auth_type: Authentication type
            credentials: Authentication credentials
            
        Returns:
            Authentication handler
            
        Raises:
            DXtradeConfigurationError: Invalid auth type or credentials
        """
        handler_class = self._handlers.get(auth_type)
        if not handler_class:
            raise DXtradeConfigurationError(f"Unsupported auth type: {auth_type}")
        
        return handler_class(credentials)

    @classmethod
    def register_handler(
        cls,
        auth_type: AuthType,
        handler_class: type[AuthHandler],
    ) -> None:
        """Register a custom authentication handler.
        
        Args:
            auth_type: Authentication type
            handler_class: Handler class
        """
        cls._handlers[auth_type] = handler_class

    @classmethod
    def get_supported_types(cls) -> list[AuthType]:
        """Get supported authentication types.
        
        Returns:
            List of supported auth types
        """
        return list(cls._handlers.keys())