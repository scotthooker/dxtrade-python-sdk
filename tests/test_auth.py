"""Tests for authentication handlers."""

import hashlib
import hmac
import time
from base64 import b64encode
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import httpx
import pytest

from dxtrade.auth import AuthFactory
from dxtrade.auth import BearerTokenHandler
from dxtrade.auth import HMACHandler
from dxtrade.auth import SessionHandler
from dxtrade.errors import DXtradeAuthenticationError
from dxtrade.errors import DXtradeConfigurationError
from dxtrade.models import AuthType
from dxtrade.models import BearerTokenCredentials
from dxtrade.models import HMACCredentials
from dxtrade.models import SessionCredentials


class TestBearerTokenHandler:
    """Test bearer token authentication handler."""
    
    def test_init_with_valid_credentials(self, bearer_token_credentials):
        """Test initialization with valid credentials."""
        handler = BearerTokenHandler(bearer_token_credentials)
        assert handler.credentials == bearer_token_credentials
        assert handler.get_auth_type() == AuthType.BEARER_TOKEN
    
    def test_init_with_invalid_credentials(self, hmac_credentials):
        """Test initialization with invalid credentials type."""
        with pytest.raises(DXtradeConfigurationError):
            BearerTokenHandler(hmac_credentials)
    
    @pytest.mark.asyncio
    async def test_authenticate_request(self, bearer_token_credentials):
        """Test request authentication."""
        handler = BearerTokenHandler(bearer_token_credentials)
        
        # Create mock request
        request = MagicMock(spec=httpx.Request)
        request.headers = {}
        client = AsyncMock(spec=httpx.AsyncClient)
        
        # Authenticate request
        authenticated_request = await handler.authenticate(request, client)
        
        # Verify authentication header was added
        assert authenticated_request.headers["Authorization"] == "Bearer test_bearer_token"
        assert authenticated_request == request  # Same request object should be returned


class TestHMACHandler:
    """Test HMAC authentication handler."""
    
    def test_init_with_valid_credentials(self, hmac_credentials):
        """Test initialization with valid credentials."""
        handler = HMACHandler(hmac_credentials)
        assert handler.credentials == hmac_credentials
        assert handler.get_auth_type() == AuthType.HMAC
    
    def test_init_with_invalid_credentials(self, bearer_token_credentials):
        """Test initialization with invalid credentials type."""
        with pytest.raises(DXtradeConfigurationError):
            HMACHandler(bearer_token_credentials)
    
    @pytest.mark.asyncio
    async def test_authenticate_request_get(self, hmac_credentials):
        """Test GET request authentication."""
        handler = HMACHandler(hmac_credentials)
        
        # Create mock GET request
        request = MagicMock(spec=httpx.Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/accounts"
        request.url.query = b""
        request.content = b""
        request.headers = {}
        
        client = AsyncMock(spec=httpx.AsyncClient)
        
        # Authenticate request
        authenticated_request = await handler.authenticate(request, client)
        
        # Verify HMAC headers were added
        assert "DX-API-KEY" in authenticated_request.headers
        assert "DX-API-TIMESTAMP" in authenticated_request.headers
        assert "DX-API-SIGNATURE" in authenticated_request.headers
        assert "DX-API-PASSPHRASE" in authenticated_request.headers
        
        assert authenticated_request.headers["DX-API-KEY"] == "test_api_key"
        assert authenticated_request.headers["DX-API-PASSPHRASE"] == "test_passphrase"
    
    @pytest.mark.asyncio
    async def test_authenticate_request_post_with_body(self, hmac_credentials):
        """Test POST request authentication with body."""
        handler = HMACHandler(hmac_credentials)
        
        # Create mock POST request with JSON body
        request = MagicMock(spec=httpx.Request)
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/orders"
        request.url.query = b""
        request.content = b'{"symbol": "EURUSD", "side": "buy"}'
        request.headers = {}
        
        client = AsyncMock(spec=httpx.AsyncClient)
        
        # Authenticate request
        authenticated_request = await handler.authenticate(request, client)
        
        # Verify signature includes body
        timestamp = authenticated_request.headers["DX-API-TIMESTAMP"]
        expected_signature_string = (
            f'{timestamp}POST/api/orders{{"symbol": "EURUSD", "side": "buy"}}test_passphrase'
        )
        
        expected_signature = hmac.new(
            "test_secret_key".encode("utf-8"),
            expected_signature_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_signature_b64 = b64encode(expected_signature).decode("utf-8")
        
        assert authenticated_request.headers["DX-API-SIGNATURE"] == expected_signature_b64
    
    @pytest.mark.asyncio
    async def test_authenticate_request_without_passphrase(self):
        """Test authentication without passphrase."""
        credentials = HMACCredentials(
            api_key="test_api_key",
            secret_key="test_secret_key"
            # No passphrase
        )
        handler = HMACHandler(credentials)
        
        request = MagicMock(spec=httpx.Request)
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/accounts"
        request.url.query = b""
        request.content = b""
        request.headers = {}
        
        client = AsyncMock(spec=httpx.AsyncClient)
        
        authenticated_request = await handler.authenticate(request, client)
        
        # Should not include passphrase header
        assert "DX-API-PASSPHRASE" not in authenticated_request.headers
        
        # Signature should not include passphrase
        timestamp = authenticated_request.headers["DX-API-TIMESTAMP"]
        expected_signature_string = f'{timestamp}GET/api/accounts'
        
        expected_signature = hmac.new(
            "test_secret_key".encode("utf-8"),
            expected_signature_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_signature_b64 = b64encode(expected_signature).decode("utf-8")
        
        assert authenticated_request.headers["DX-API-SIGNATURE"] == expected_signature_b64


class TestSessionHandler:
    """Test session authentication handler."""
    
    def test_init_with_valid_credentials(self, session_credentials):
        """Test initialization with valid credentials."""
        handler = SessionHandler(session_credentials)
        assert handler.credentials == session_credentials
        assert handler.get_auth_type() == AuthType.SESSION
    
    def test_init_with_invalid_credentials(self, bearer_token_credentials):
        """Test initialization with invalid credentials type."""
        with pytest.raises(DXtradeConfigurationError):
            SessionHandler(bearer_token_credentials)
    
    def test_init_with_existing_token(self):
        """Test initialization with existing session token."""
        credentials = SessionCredentials(
            username="test_user",
            password="test_password",
            session_token="existing_token"
        )
        handler = SessionHandler(credentials)
        assert handler._session_token == "existing_token"
    
    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self, session_credentials):
        """Test authentication with valid session token."""
        handler = SessionHandler(session_credentials)
        handler._session_token = "valid_token"
        handler._token_expires_at = time.time() + 3600  # 1 hour from now
        
        request = MagicMock(spec=httpx.Request)
        request.headers = {}
        client = AsyncMock(spec=httpx.AsyncClient)
        
        authenticated_request = await handler.authenticate(request, client)
        
        assert authenticated_request.headers["Authorization"] == "Bearer valid_token"
    
    @pytest.mark.asyncio
    async def test_authenticate_requires_login(self, session_credentials):
        """Test authentication that requires login."""
        handler = SessionHandler(session_credentials)
        # No existing token
        
        # Mock successful login response
        login_response = MagicMock(spec=httpx.Response)
        login_response.raise_for_status.return_value = None
        login_response.json.return_value = {
            "success": True,
            "data": {
                "token": "new_session_token",
                "expires_in": 3600
            }
        }
        
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = login_response
        
        request = MagicMock(spec=httpx.Request)
        request.headers = {}
        
        authenticated_request = await handler.authenticate(request, client)
        
        # Verify login was called
        client.post.assert_called_once_with(
            "/auth/login",
            json={"username": "test_user", "password": "test_password"}
        )
        
        # Verify token was set
        assert handler._session_token == "new_session_token"
        assert authenticated_request.headers["Authorization"] == "Bearer new_session_token"
    
    @pytest.mark.asyncio
    async def test_authenticate_login_failure(self, session_credentials):
        """Test authentication with login failure."""
        handler = SessionHandler(session_credentials)
        
        # Mock failed login response
        login_response = MagicMock(spec=httpx.Response)
        login_response.raise_for_status.return_value = None
        login_response.json.return_value = {
            "success": False,
            "message": "Invalid credentials"
        }
        
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = login_response
        
        request = MagicMock(spec=httpx.Request)
        request.headers = {}
        
        with pytest.raises(DXtradeAuthenticationError, match="Invalid credentials"):
            await handler.authenticate(request, client)
    
    @pytest.mark.asyncio
    async def test_authenticate_login_network_error(self, session_credentials):
        """Test authentication with network error during login."""
        handler = SessionHandler(session_credentials)
        
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("Connection failed")
        
        request = MagicMock(spec=httpx.Request)
        request.headers = {}
        
        with pytest.raises(DXtradeAuthenticationError, match="Login request failed"):
            await handler.authenticate(request, client)
    
    def test_token_expiration_check(self, session_credentials):
        """Test token expiration detection."""
        handler = SessionHandler(session_credentials)
        
        # No expiration time set
        assert handler._is_token_expired() is True
        
        # Expired token
        handler._token_expires_at = time.time() - 3600  # 1 hour ago
        assert handler._is_token_expired() is True
        
        # Valid token
        handler._token_expires_at = time.time() + 3600  # 1 hour from now
        assert handler._is_token_expired() is False
    
    @pytest.mark.asyncio
    async def test_logout(self, session_credentials):
        """Test logout functionality."""
        handler = SessionHandler(session_credentials)
        handler._session_token = "test_token"
        
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = MagicMock(spec=httpx.Response)
        
        await handler.logout(client)
        
        # Verify logout request was made
        client.post.assert_called_once_with(
            "/auth/logout",
            headers={"Authorization": "Bearer test_token"}
        )
        
        # Verify token was cleared
        assert handler._session_token is None
        assert handler._token_expires_at is None
    
    @pytest.mark.asyncio
    async def test_logout_network_error(self, session_credentials):
        """Test logout with network error (should not raise)."""
        handler = SessionHandler(session_credentials)
        handler._session_token = "test_token"
        
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("Connection failed")
        
        # Should not raise exception
        await handler.logout(client)
        
        # Token should still be cleared
        assert handler._session_token is None


class TestAuthFactory:
    """Test authentication factory."""
    
    def test_create_bearer_token_handler(self, bearer_token_credentials):
        """Test creating bearer token handler."""
        handler = AuthFactory.create_handler(
            AuthType.BEARER_TOKEN,
            bearer_token_credentials
        )
        assert isinstance(handler, BearerTokenHandler)
        assert handler.credentials == bearer_token_credentials
    
    def test_create_hmac_handler(self, hmac_credentials):
        """Test creating HMAC handler."""
        handler = AuthFactory.create_handler(
            AuthType.HMAC,
            hmac_credentials
        )
        assert isinstance(handler, HMACHandler)
        assert handler.credentials == hmac_credentials
    
    def test_create_session_handler(self, session_credentials):
        """Test creating session handler."""
        handler = AuthFactory.create_handler(
            AuthType.SESSION,
            session_credentials
        )
        assert isinstance(handler, SessionHandler)
        assert handler.credentials == session_credentials
    
    def test_create_unsupported_handler(self, bearer_token_credentials):
        """Test creating handler with unsupported auth type."""
        with pytest.raises(DXtradeConfigurationError, match="Unsupported auth type"):
            AuthFactory.create_handler("unsupported", bearer_token_credentials)
    
    def test_register_custom_handler(self, bearer_token_credentials):
        """Test registering custom authentication handler."""
        class CustomAuthHandler(BearerTokenHandler):
            pass
        
        # Register custom handler
        AuthFactory.register_handler("custom", CustomAuthHandler)
        
        # Should be able to create it
        handler = AuthFactory.create_handler("custom", bearer_token_credentials)
        assert isinstance(handler, CustomAuthHandler)
        
        # Should appear in supported types
        supported = AuthFactory.get_supported_types()
        assert "custom" in supported
    
    def test_get_supported_types(self):
        """Test getting supported authentication types."""
        supported = AuthFactory.get_supported_types()
        
        assert AuthType.BEARER_TOKEN in supported
        assert AuthType.HMAC in supported
        assert AuthType.SESSION in supported