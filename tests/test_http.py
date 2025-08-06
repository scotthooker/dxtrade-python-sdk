"""Tests for HTTP client."""

import asyncio
from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import httpx
import pytest

from dxtrade.errors import DXtradeHTTPError
from dxtrade.errors import DXtradeRateLimitError
from dxtrade.errors import DXtradeTimeoutError
from dxtrade.http import DXtradeHTTPClient
from dxtrade.models import HTTPConfig


class TestDXtradeHTTPClient:
    """Test HTTP client functionality."""
    
    @pytest.fixture
    def client_config(self):
        """HTTP client configuration fixture."""
        return HTTPConfig(
            base_url="https://api.dxtrade.com",
            timeout=30.0,
            max_retries=3,
            retry_backoff_factor=0.3,
            rate_limit=10,
            user_agent="test-sdk/1.0.0"
        )
    
    @pytest.fixture
    async def http_client(self, client_config):
        """HTTP client fixture."""
        async with DXtradeHTTPClient(client_config) as client:
            yield client
    
    def test_init(self, client_config):
        """Test HTTP client initialization."""
        client = DXtradeHTTPClient(client_config)
        
        assert client.config == client_config
        assert client._rate_limiter is not None
        assert client._idempotency_manager is not None
        assert client._clock_drift_detector is not None
    
    def test_init_without_rate_limit(self):
        """Test initialization without rate limiting."""
        config = HTTPConfig(
            base_url="https://api.dxtrade.com",
            timeout=30.0,
            max_retries=3,
            retry_backoff_factor=0.3,
            rate_limit=None,  # No rate limiting
            user_agent="test-sdk/1.0.0"
        )
        
        client = DXtradeHTTPClient(config)
        assert client._rate_limiter is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, client_config):
        """Test using client as context manager."""
        async with DXtradeHTTPClient(client_config) as client:
            assert client is not None
            assert isinstance(client, DXtradeHTTPClient)
    
    @pytest.mark.asyncio
    async def test_successful_request(self, client_config):
        """Test successful HTTP request."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Date": "Wed, 01 Jan 2024 12:00:00 GMT"}
        mock_response.json.return_value = {"success": True, "data": {}}
        mock_response.text = '{"success": true, "data": {}}'
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config) as client:
                response = await client.request("GET", "/test")
                
                assert response == mock_response
                mock_client.build_request.assert_called_once()
                mock_client.send.assert_called_once_with(mock_request)
    
    @pytest.mark.asyncio
    async def test_request_with_authentication(self, client_config, bearer_token_credentials):
        """Test request with authentication."""
        from dxtrade.auth import BearerTokenHandler
        
        auth_handler = BearerTokenHandler(bearer_token_credentials)
        
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_request.headers = {}
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config, auth_handler) as client:
                await client.request("GET", "/test")
                
                # Verify auth header was added
                assert mock_request.headers["Authorization"] == "Bearer test_bearer_token"
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, client_config):
        """Test rate limiting functionality."""
        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('dxtrade.utils.RateLimiter') as mock_rate_limiter_class:
            
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_rate_limiter = AsyncMock()
            mock_rate_limiter_class.return_value = mock_rate_limiter
            mock_rate_limiter.acquire.side_effect = DXtradeRateLimitError("Rate limit exceeded")
            
            async with DXtradeHTTPClient(client_config) as client:
                with pytest.raises(DXtradeRateLimitError):
                    await client.request("GET", "/test")
                
                mock_rate_limiter.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, client_config):
        """Test HTTP error response handling."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {
            "success": False,
            "error_code": "INVALID_REQUEST",
            "error_message": "Invalid parameters",
            "details": {"field": "symbol"}
        }
        mock_response.text = "Bad Request"
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config) as client:
                with pytest.raises(DXtradeHTTPError) as exc_info:
                    await client.request("GET", "/test")
                
                error = exc_info.value
                assert error.status_code == 400
                assert error.error_code == "INVALID_REQUEST"
                assert "Invalid parameters" in str(error)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, client_config, rate_limit_headers):
        """Test rate limit error handling."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = rate_limit_headers
        mock_response.json.return_value = {
            "success": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "error_message": "Too many requests"
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config) as client:
                with pytest.raises(DXtradeRateLimitError) as exc_info:
                    await client.request("GET", "/test")
                
                error = exc_info.value
                assert error.status_code == 429
                assert error.retry_after == 60
                assert error.limit == 100
                assert error.remaining == 50
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, client_config):
        """Test timeout error handling."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.side_effect = httpx.TimeoutException("Request timed out")
            
            async with DXtradeHTTPClient(client_config) as client:
                with pytest.raises(DXtradeTimeoutError) as exc_info:
                    await client.request("GET", "/test")
                
                error = exc_info.value
                assert "Request timeout after 4 attempts" in str(error)
                assert error.timeout == 30.0
    
    @pytest.mark.asyncio
    async def test_retry_logic(self, client_config):
        """Test retry logic for transient errors."""
        mock_responses = [
            # First two attempts fail
            httpx.TimeoutException("Timeout 1"),
            httpx.TimeoutException("Timeout 2"), 
            # Third attempt succeeds
            MagicMock(spec=httpx.Response)
        ]
        mock_responses[2].status_code = 200
        mock_responses[2].headers = {}
        
        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('asyncio.sleep') as mock_sleep:  # Speed up test
            
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.side_effect = mock_responses
            
            async with DXtradeHTTPClient(client_config) as client:
                response = await client.request("GET", "/test")
                
                assert response == mock_responses[2]
                assert mock_client.send.call_count == 3
                assert mock_sleep.call_count == 2  # Two retry delays
    
    @pytest.mark.asyncio
    async def test_idempotency_key_usage(self, client_config):
        """Test idempotency key functionality."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config) as client:
                await client.request(
                    "POST", "/test",
                    json={"test": "data"},
                    idempotency_key="test_key_123"
                )
                
                # Verify idempotency key was included in request headers
                build_call_kwargs = mock_client.build_request.call_args[1]
                headers = build_call_kwargs.get("headers", {})
                assert headers.get("Idempotency-Key") == "test_key_123"
    
    @pytest.mark.asyncio
    async def test_server_time_parsing(self, client_config):
        """Test server time parsing and clock drift detection."""
        server_date = datetime.now(timezone.utc)
        date_header = server_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Date": date_header}
        
        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('httpx._utils.parse_header_date') as mock_parse_date:
            
            mock_parse_date.return_value = server_date
            
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config) as client:
                await client.request("GET", "/test")
                
                mock_parse_date.assert_called_once_with(date_header)
                # Clock drift detector should have been updated
                assert client._clock_drift_detector._server_time_offset is not None
    
    @pytest.mark.asyncio
    async def test_convenience_methods(self, client_config):
        """Test HTTP convenience methods."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {}
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_request = MagicMock(spec=httpx.Request)
            mock_client.build_request.return_value = mock_request
            mock_client.send.return_value = mock_response
            
            async with DXtradeHTTPClient(client_config) as client:
                # Test GET
                await client.get("/test", params={"q": "search"})
                
                # Test POST
                await client.post("/test", json={"data": "value"})
                
                # Test PUT
                await client.put("/test", data="raw data")
                
                # Test PATCH
                await client.patch("/test", json={"update": "value"})
                
                # Test DELETE
                await client.delete("/test")
                
                # Verify all methods were called
                assert mock_client.build_request.call_count == 5
                assert mock_client.send.call_count == 5