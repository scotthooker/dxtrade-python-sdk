"""Tests for the main DXtrade client."""

from decimal import Decimal
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from dxtrade.client import DXtradeClient
from dxtrade.errors import DXtradeConfigurationError
from dxtrade.models import AuthType
from dxtrade.models import BearerTokenCredentials
from dxtrade.models import ClientConfig
from dxtrade.models import HMACCredentials
from dxtrade.models import HTTPConfig
from dxtrade.models import OrderRequest
from dxtrade.models import OrderSide
from dxtrade.models import OrderType
from dxtrade.models import SessionCredentials
from dxtrade.models import WebSocketConfig
from dxtrade.rest import AccountsAPI
from dxtrade.rest import InstrumentsAPI
from dxtrade.rest import OrdersAPI
from dxtrade.rest import PositionsAPI


class TestDXtradeClientInitialization:
    """Test DXtrade client initialization."""
    
    def test_init_with_config_object(self, http_config, bearer_token_credentials):
        """Test initialization with complete config object."""
        config = ClientConfig(
            http=http_config,
            websocket=None,
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials,
            clock_drift_threshold=30.0,
            enable_idempotency=True
        )
        
        client = DXtradeClient(config=config)
        
        assert client.config == config
        assert isinstance(client.accounts, AccountsAPI)
        assert isinstance(client.instruments, InstrumentsAPI)
        assert isinstance(client.orders, OrdersAPI)
        assert isinstance(client.positions, PositionsAPI)
    
    def test_init_with_individual_parameters(self, bearer_token_credentials):
        """Test initialization with individual parameters."""
        client = DXtradeClient(
            base_url="https://api.dxtrade.com",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials,
            timeout=60.0,
            max_retries=5,
            rate_limit=50
        )
        
        assert client.config.http.base_url == "https://api.dxtrade.com"
        assert client.config.http.timeout == 60.0
        assert client.config.http.max_retries == 5
        assert client.config.http.rate_limit == 50
        assert client.config.auth_type == AuthType.BEARER_TOKEN
    
    def test_init_with_websocket_config(self, bearer_token_credentials):
        """Test initialization with WebSocket configuration."""
        client = DXtradeClient(
            base_url="https://api.dxtrade.com",
            websocket_url="wss://push.dxtrade.com/stream",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials,
            heartbeat_interval=15.0
        )
        
        assert client.config.websocket is not None
        assert client.config.websocket.url == "wss://push.dxtrade.com/stream"
        assert client.config.websocket.heartbeat_interval == 15.0
    
    def test_init_missing_base_url(self, bearer_token_credentials):
        """Test initialization without base URL."""
        with pytest.raises(DXtradeConfigurationError, match="base_url is required"):
            DXtradeClient(
                auth_type=AuthType.BEARER_TOKEN,
                credentials=bearer_token_credentials
            )
    
    def test_init_missing_auth(self):
        """Test initialization without authentication."""
        with pytest.raises(DXtradeConfigurationError, match="auth_type and credentials are required"):
            DXtradeClient(base_url="https://api.dxtrade.com")
    
    def test_push_property_with_websocket_config(self, bearer_token_credentials):
        """Test push property when WebSocket is configured."""
        client = DXtradeClient(
            base_url="https://api.dxtrade.com",
            websocket_url="wss://push.dxtrade.com/stream",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials
        )
        
        push_client = client.push
        assert push_client is not None
        assert push_client.config.url == "wss://push.dxtrade.com/stream"
    
    def test_push_property_without_websocket_config(self, bearer_token_credentials):
        """Test push property when WebSocket is not configured."""
        client = DXtradeClient(
            base_url="https://api.dxtrade.com",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials
        )
        
        with pytest.raises(DXtradeConfigurationError, match="WebSocket URL not configured"):
            client.push


class TestDXtradeClientFactoryMethods:
    """Test client factory methods."""
    
    def test_create_with_bearer_token(self):
        """Test factory method for bearer token authentication."""
        client = DXtradeClient.create_with_bearer_token(
            base_url="https://api.dxtrade.com",
            token="test_token_123",
            websocket_url="wss://push.dxtrade.com/stream",
            timeout=45.0
        )
        
        assert client.config.auth_type == AuthType.BEARER_TOKEN
        assert isinstance(client.config.credentials, BearerTokenCredentials)
        assert client.config.credentials.token == "test_token_123"
        assert client.config.http.base_url == "https://api.dxtrade.com"
        assert client.config.http.timeout == 45.0
        assert client.config.websocket.url == "wss://push.dxtrade.com/stream"
    
    def test_create_with_hmac(self):
        """Test factory method for HMAC authentication."""
        client = DXtradeClient.create_with_hmac(
            base_url="https://api.dxtrade.com",
            api_key="test_api_key",
            secret_key="test_secret_key",
            passphrase="test_passphrase",
            rate_limit=100
        )
        
        assert client.config.auth_type == AuthType.HMAC
        assert isinstance(client.config.credentials, HMACCredentials)
        assert client.config.credentials.api_key == "test_api_key"
        assert client.config.credentials.secret_key == "test_secret_key"
        assert client.config.credentials.passphrase == "test_passphrase"
        assert client.config.http.rate_limit == 100
    
    def test_create_with_session(self):
        """Test factory method for session authentication."""
        client = DXtradeClient.create_with_session(
            base_url="https://api.dxtrade.com",
            username="test_user",
            password="test_password",
            max_retries=5
        )
        
        assert client.config.auth_type == AuthType.SESSION
        assert isinstance(client.config.credentials, SessionCredentials)
        assert client.config.credentials.username == "test_user"
        assert client.config.credentials.password == "test_password"
        assert client.config.http.max_retries == 5


class TestDXtradeClientConvenienceMethods:
    """Test client convenience methods."""
    
    @pytest.fixture
    def mock_client(self, bearer_token_credentials):
        """Create a mock client for testing."""
        client = DXtradeClient(
            base_url="https://api.dxtrade.com",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials
        )
        
        # Mock the API endpoints
        client.instruments = AsyncMock()
        client.accounts = AsyncMock()
        client.orders = AsyncMock()
        client.positions = AsyncMock()
        
        return client
    
    @pytest.mark.asyncio
    async def test_get_server_time(self, mock_client):
        """Test get_server_time convenience method."""
        expected_result = MagicMock()
        mock_client.instruments.get_server_time.return_value = expected_result
        
        result = await mock_client.get_server_time()
        
        mock_client.instruments.get_server_time.assert_called_once()
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_get_account_summary(self, mock_client):
        """Test get_account_summary convenience method."""
        expected_result = MagicMock()
        mock_client.accounts.get_account_summary.return_value = expected_result
        
        result = await mock_client.get_account_summary("acc_123")
        
        mock_client.accounts.get_account_summary.assert_called_once_with("acc_123")
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_get_current_prices(self, mock_client):
        """Test get_current_prices convenience method."""
        expected_result = MagicMock()
        mock_client.instruments.get_prices.return_value = expected_result
        
        result = await mock_client.get_current_prices(["EURUSD", "GBPUSD"])
        
        mock_client.instruments.get_prices.assert_called_once_with(["EURUSD", "GBPUSD"])
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_create_market_order(self, mock_client):
        """Test create_market_order convenience method."""
        expected_result = MagicMock()
        mock_client.orders.create_order.return_value = expected_result
        
        result = await mock_client.create_market_order(
            symbol="EURUSD",
            side="buy",
            volume=0.1,
            stop_loss=1.08000,
            take_profit=1.09000
        )
        
        # Verify the order request was created correctly
        call_args = mock_client.orders.create_order.call_args[0][0]
        assert isinstance(call_args, OrderRequest)
        assert call_args.symbol == "EURUSD"
        assert call_args.side == OrderSide.BUY
        assert call_args.type == OrderType.MARKET
        assert call_args.volume == Decimal("0.1")
        assert call_args.stop_loss == Decimal("1.08000")
        assert call_args.take_profit == Decimal("1.09000")
        
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_create_limit_order(self, mock_client):
        """Test create_limit_order convenience method."""
        expected_result = MagicMock()
        mock_client.orders.create_order.return_value = expected_result
        
        result = await mock_client.create_limit_order(
            symbol="EURUSD",
            side="sell",
            volume=0.2,
            price=1.09000,
            client_order_id="my_order_123"
        )
        
        # Verify the order request was created correctly
        call_args = mock_client.orders.create_order.call_args[0][0]
        assert isinstance(call_args, OrderRequest)
        assert call_args.symbol == "EURUSD"
        assert call_args.side == OrderSide.SELL
        assert call_args.type == OrderType.LIMIT
        assert call_args.volume == Decimal("0.2")
        assert call_args.price == Decimal("1.09000")
        assert call_args.client_order_id == "my_order_123"
        
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_get_open_orders(self, mock_client):
        """Test get_open_orders convenience method."""
        from dxtrade.models import OrderStatus
        
        expected_result = MagicMock()
        mock_client.orders.get_orders.return_value = expected_result
        
        result = await mock_client.get_open_orders("acc_123")
        
        mock_client.orders.get_orders.assert_called_once_with(
            account_id="acc_123",
            status=OrderStatus.OPEN
        )
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_get_open_positions(self, mock_client):
        """Test get_open_positions convenience method."""
        expected_result = MagicMock()
        mock_client.positions.get_positions.return_value = expected_result
        
        result = await mock_client.get_open_positions("acc_123")
        
        mock_client.positions.get_positions.assert_called_once_with(account_id="acc_123")
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_close_all_positions(self, mock_client):
        """Test close_all_positions convenience method."""
        expected_result = MagicMock()
        mock_client.positions.close_all_positions.return_value = expected_result
        
        result = await mock_client.close_all_positions("acc_123")
        
        mock_client.positions.close_all_positions.assert_called_once_with("acc_123")
        assert result == expected_result


class TestDXtradeClientContextManager:
    """Test client as async context manager."""
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, bearer_token_credentials):
        """Test using client as async context manager."""
        with patch('dxtrade.http.DXtradeHTTPClient') as mock_http:
            mock_http_instance = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            async with DXtradeClient(
                base_url="https://api.dxtrade.com",
                auth_type=AuthType.BEARER_TOKEN,
                credentials=bearer_token_credentials
            ) as client:
                assert client is not None
                assert isinstance(client, DXtradeClient)
            
            # Verify close was called
            mock_http_instance.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_manual_close(self, bearer_token_credentials):
        """Test manual client close."""
        with patch('dxtrade.http.DXtradeHTTPClient') as mock_http:
            mock_http_instance = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            client = DXtradeClient(
                base_url="https://api.dxtrade.com",
                auth_type=AuthType.BEARER_TOKEN,
                credentials=bearer_token_credentials
            )
            
            await client.close()
            
            # Verify close was called
            mock_http_instance.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_with_push_client(self, bearer_token_credentials):
        """Test closing client with initialized push client."""
        with patch('dxtrade.http.DXtradeHTTPClient') as mock_http, \
             patch('dxtrade.push.DXtradePushClient') as mock_push:
            
            mock_http_instance = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            mock_push_instance = AsyncMock()
            mock_push.return_value = mock_push_instance
            
            client = DXtradeClient(
                base_url="https://api.dxtrade.com",
                websocket_url="wss://push.dxtrade.com/stream",
                auth_type=AuthType.BEARER_TOKEN,
                credentials=bearer_token_credentials
            )
            
            # Initialize push client
            _ = client.push
            
            await client.close()
            
            # Verify both clients were closed
            mock_http_instance.close.assert_called_once()
            mock_push_instance.disconnect.assert_called_once()


class TestDXtradeClientIntegration:
    """Test client integration scenarios."""
    
    def test_auth_handler_property(self, bearer_token_credentials):
        """Test accessing auth handler."""
        client = DXtradeClient(
            base_url="https://api.dxtrade.com",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials
        )
        
        auth_handler = client.auth_handler
        assert auth_handler is not None
        assert auth_handler.get_auth_type() == AuthType.BEARER_TOKEN
    
    def test_client_alias(self, bearer_token_credentials):
        """Test DXClient alias."""
        from dxtrade.client import DXClient
        
        client = DXClient(
            base_url="https://api.dxtrade.com",
            auth_type=AuthType.BEARER_TOKEN,
            credentials=bearer_token_credentials
        )
        
        assert isinstance(client, DXtradeClient)
    
    @pytest.mark.asyncio
    async def test_comprehensive_workflow(self, bearer_token_credentials):
        """Test a comprehensive client workflow."""
        with patch('dxtrade.http.DXtradeHTTPClient') as mock_http:
            mock_http_instance = AsyncMock()
            mock_http.return_value = mock_http_instance
            
            # Mock API responses
            mock_server_time = MagicMock()
            mock_account_summary = {"balance": 10000.0, "equity": 10500.0}
            mock_prices = [MagicMock()]
            mock_order = MagicMock()
            
            client = DXtradeClient(
                base_url="https://api.dxtrade.com",
                auth_type=AuthType.BEARER_TOKEN,
                credentials=bearer_token_credentials
            )
            
            # Mock the API methods
            client.instruments.get_server_time = AsyncMock(return_value=mock_server_time)
            client.accounts.get_account_summary = AsyncMock(return_value=mock_account_summary)
            client.instruments.get_prices = AsyncMock(return_value=mock_prices)
            client.orders.create_order = AsyncMock(return_value=mock_order)
            
            # Test workflow
            server_time = await client.get_server_time()
            account = await client.get_account_summary("acc_123")
            prices = await client.get_current_prices(["EURUSD"])
            order = await client.create_market_order("EURUSD", "buy", 0.1)
            
            # Verify all calls were made
            assert server_time == mock_server_time
            assert account == mock_account_summary
            assert prices == mock_prices
            assert order == mock_order
            
            client.instruments.get_server_time.assert_called_once()
            client.accounts.get_account_summary.assert_called_once_with("acc_123")
            client.instruments.get_prices.assert_called_once_with(["EURUSD"])
            client.orders.create_order.assert_called_once()