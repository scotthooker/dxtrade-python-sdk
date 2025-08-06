"""Test configuration and fixtures."""

from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Dict
from typing import List
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from dxtrade.models import Account
from dxtrade.models import AuthType
from dxtrade.models import Balance
from dxtrade.models import BearerTokenCredentials
from dxtrade.models import HMACCredentials
from dxtrade.models import HTTPConfig
from dxtrade.models import Instrument
from dxtrade.models import InstrumentType
from dxtrade.models import MarketStatus
from dxtrade.models import Order
from dxtrade.models import OrderSide
from dxtrade.models import OrderStatus
from dxtrade.models import OrderType
from dxtrade.models import Position
from dxtrade.models import PositionSide
from dxtrade.models import Price
from dxtrade.models import SessionCredentials
from dxtrade.models import TimeInForce
from dxtrade.models import Trade


@pytest.fixture
def bearer_token_credentials():
    """Bearer token credentials fixture."""
    return BearerTokenCredentials(token="test_bearer_token")


@pytest.fixture
def hmac_credentials():
    """HMAC credentials fixture."""
    return HMACCredentials(
        api_key="test_api_key",
        secret_key="test_secret_key",
        passphrase="test_passphrase"
    )


@pytest.fixture
def session_credentials():
    """Session credentials fixture."""
    return SessionCredentials(
        username="test_user",
        password="test_password",
        domain="default"
    )


@pytest.fixture
def http_config():
    """HTTP configuration fixture."""
    return HTTPConfig(
        base_url="https://api.dxtrade.com",
        timeout=30.0,
        max_retries=3,
        retry_backoff_factor=0.3,
        rate_limit=10,
        user_agent="test-agent/1.0.0"
    )


@pytest.fixture
def mock_httpx_response():
    """Mock httpx response fixture."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.headers = {}
    response.json.return_value = {"success": True, "data": {}}
    response.text = '{"success": true, "data": {}}'
    response.content = b'{"success": true, "data": {}}'
    return response


@pytest.fixture
def mock_httpx_client(mock_httpx_response):
    """Mock httpx client fixture."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = mock_httpx_response
    client.get.return_value = mock_httpx_response
    client.post.return_value = mock_httpx_response
    client.put.return_value = mock_httpx_response
    client.patch.return_value = mock_httpx_response
    client.delete.return_value = mock_httpx_response
    client.send.return_value = mock_httpx_response
    client.build_request.return_value = MagicMock(spec=httpx.Request)
    return client


@pytest.fixture
def sample_account():
    """Sample account fixture."""
    return Account(
        account_id="acc_123456",
        account_name="Test Account",
        account_type="demo",
        currency="USD",
        balance=Decimal("10000.00"),
        equity=Decimal("10500.00"),
        margin=Decimal("500.00"),
        free_margin=Decimal("9500.00"),
        margin_level=Decimal("2100.0"),
        balances=[
            Balance(
                currency="USD",
                balance=Decimal("10000.00"),
                available=Decimal("9500.00"),
                used=Decimal("500.00"),
                reserved=Decimal("0.00")
            )
        ],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_instrument():
    """Sample instrument fixture."""
    return Instrument(
        symbol="EURUSD",
        name="Euro vs US Dollar",
        type=InstrumentType.FOREX,
        base_currency="EUR",
        quote_currency="USD",
        tick_size=Decimal("0.00001"),
        tick_value=Decimal("1.0"),
        contract_size=Decimal("100000"),
        min_volume=Decimal("0.01"),
        max_volume=Decimal("100.0"),
        volume_step=Decimal("0.01"),
        margin_rate=Decimal("0.02"),
        swap_long=Decimal("-0.5"),
        swap_short=Decimal("0.3"),
        market_status=MarketStatus.OPEN,
        digits=5,
        enabled=True
    )


@pytest.fixture
def sample_price():
    """Sample price fixture."""
    return Price(
        symbol="EURUSD",
        bid=Decimal("1.08745"),
        ask=Decimal("1.08755"),
        spread=Decimal("0.0001"),
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_order():
    """Sample order fixture."""
    return Order(
        order_id="ord_123456",
        client_order_id="client_123",
        account_id="acc_123456",
        symbol="EURUSD",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        status=OrderStatus.OPEN,
        volume=Decimal("0.1"),
        filled_volume=Decimal("0.0"),
        remaining_volume=Decimal("0.1"),
        price=Decimal("1.08500"),
        time_in_force=TimeInForce.GTC,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_position():
    """Sample position fixture."""
    return Position(
        position_id="pos_123456",
        account_id="acc_123456",
        symbol="EURUSD",
        side=PositionSide.LONG,
        volume=Decimal("0.1"),
        entry_price=Decimal("1.08500"),
        current_price=Decimal("1.08750"),
        unrealized_pnl=Decimal("25.0"),
        realized_pnl=Decimal("0.0"),
        margin=Decimal("217.5"),
        opened_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_trade():
    """Sample trade fixture."""
    return Trade(
        trade_id="trade_123456",
        order_id="ord_123456",
        account_id="acc_123456",
        symbol="EURUSD",
        side=OrderSide.BUY,
        volume=Decimal("0.1"),
        price=Decimal("1.08500"),
        commission=Decimal("0.0"),
        swap=Decimal("0.0"),
        executed_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def api_response_data():
    """Sample API response data fixture."""
    return {
        "success": True,
        "data": {
            "id": "test_123",
            "value": "test_value",
            "timestamp": "2024-01-01T12:00:00Z"
        },
        "timestamp": "2024-01-01T12:00:00Z"
    }


@pytest.fixture
def api_error_response():
    """Sample API error response fixture."""
    return {
        "success": False,
        "error_code": "INVALID_REQUEST",
        "error_message": "Invalid request parameters",
        "details": {"field": "symbol", "message": "Required field missing"},
        "timestamp": "2024-01-01T12:00:00Z"
    }


@pytest.fixture
def paginated_response_data():
    """Sample paginated response data fixture."""
    return {
        "success": True,
        "data": [
            {"id": "1", "value": "first"},
            {"id": "2", "value": "second"},
            {"id": "3", "value": "third"}
        ],
        "pagination": {
            "offset": 0,
            "limit": 100,
            "total": 3,
            "has_more": False
        },
        "timestamp": "2024-01-01T12:00:00Z"
    }


# Mock server responses
@pytest.fixture
def mock_server_responses():
    """Mock server responses for different endpoints."""
    return {
        "/accounts": {
            "success": True,
            "data": [
                {
                    "account_id": "acc_123456",
                    "account_name": "Test Account",
                    "account_type": "demo",
                    "currency": "USD",
                    "balance": "10000.00",
                    "equity": "10500.00",
                    "margin": "500.00",
                    "free_margin": "9500.00",
                    "margin_level": "2100.0",
                    "balances": [],
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T12:00:00Z"
                }
            ]
        },
        "/instruments": {
            "success": True,
            "data": [
                {
                    "symbol": "EURUSD",
                    "name": "Euro vs US Dollar",
                    "type": "forex",
                    "base_currency": "EUR",
                    "quote_currency": "USD",
                    "tick_size": "0.00001",
                    "tick_value": "1.0",
                    "contract_size": "100000",
                    "min_volume": "0.01",
                    "max_volume": "100.0",
                    "volume_step": "0.01",
                    "margin_rate": "0.02",
                    "market_status": "open",
                    "digits": 5,
                    "enabled": True
                }
            ]
        },
        "/market/prices": {
            "success": True,
            "data": [
                {
                    "symbol": "EURUSD",
                    "bid": "1.08745",
                    "ask": "1.08755",
                    "spread": "0.0001",
                    "timestamp": "2024-01-01T12:00:00Z"
                }
            ]
        },
        "/orders": {
            "success": True,
            "data": [
                {
                    "order_id": "ord_123456",
                    "account_id": "acc_123456",
                    "symbol": "EURUSD",
                    "side": "buy",
                    "type": "limit",
                    "status": "open",
                    "volume": "0.1",
                    "filled_volume": "0.0",
                    "remaining_volume": "0.1",
                    "price": "1.08500",
                    "time_in_force": "gtc",
                    "created_at": "2024-01-01T12:00:00Z",
                    "updated_at": "2024-01-01T12:00:00Z"
                }
            ],
            "pagination": {
                "offset": 0,
                "limit": 100,
                "total": 1,
                "has_more": False
            }
        },
        "/positions": {
            "success": True,
            "data": [
                {
                    "position_id": "pos_123456",
                    "account_id": "acc_123456",
                    "symbol": "EURUSD",
                    "side": "long",
                    "volume": "0.1",
                    "entry_price": "1.08500",
                    "current_price": "1.08750",
                    "unrealized_pnl": "25.0",
                    "realized_pnl": "0.0",
                    "margin": "217.5",
                    "opened_at": "2024-01-01T12:00:00Z",
                    "updated_at": "2024-01-01T12:00:00Z"
                }
            ],
            "pagination": {
                "offset": 0,
                "limit": 100,
                "total": 1,
                "has_more": False
            }
        }
    }


# Rate limiting test helpers
@pytest.fixture
def rate_limit_headers():
    """Rate limit headers fixture."""
    return {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "50",
        "X-RateLimit-Reset": str(int(datetime.now(timezone.utc).timestamp()) + 3600),
        "Retry-After": "60"
    }


# WebSocket test helpers
@pytest.fixture
def websocket_message():
    """Sample WebSocket message fixture."""
    return {
        "type": "price",
        "timestamp": "2024-01-01T12:00:00Z",
        "data": {
            "symbol": "EURUSD",
            "bid": "1.08745",
            "ask": "1.08755",
            "spread": "0.0001",
            "timestamp": "2024-01-01T12:00:00Z"
        }
    }


@pytest.fixture
def mock_websocket():
    """Mock WebSocket fixture."""
    ws = AsyncMock()
    ws.send.return_value = None
    ws.recv.return_value = '{"type": "heartbeat", "data": {}}'
    ws.close.return_value = None
    return ws


# Error simulation helpers
@pytest.fixture
def http_timeout_error():
    """HTTP timeout error fixture."""
    return httpx.TimeoutException("Request timed out")


@pytest.fixture
def http_connection_error():
    """HTTP connection error fixture."""
    return httpx.ConnectError("Connection failed")


@pytest.fixture
def validation_error():
    """Pydantic validation error fixture."""
    try:
        # Trigger a validation error
        Account(account_id="", account_name="", account_type="", currency="")
    except ValidationError as e:
        return e