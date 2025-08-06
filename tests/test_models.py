"""Tests for pydantic models."""

from datetime import datetime
from datetime import timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from dxtrade.models import Account
from dxtrade.models import AuthType
from dxtrade.models import Balance
from dxtrade.models import BearerTokenCredentials
from dxtrade.models import BracketOrderRequest
from dxtrade.models import Candle
from dxtrade.models import EventType
from dxtrade.models import HMACCredentials
from dxtrade.models import HTTPConfig
from dxtrade.models import Instrument
from dxtrade.models import InstrumentType
from dxtrade.models import MarketStatus
from dxtrade.models import OCOOrderRequest
from dxtrade.models import Order
from dxtrade.models import OrderRequest
from dxtrade.models import OrderSide
from dxtrade.models import OrderStatus
from dxtrade.models import OrderType
from dxtrade.models import Position
from dxtrade.models import PositionSide
from dxtrade.models import Price
from dxtrade.models import PriceEvent
from dxtrade.models import SessionCredentials
from dxtrade.models import Tick
from dxtrade.models import TimeInForce
from dxtrade.models import Trade
from dxtrade.models import WebSocketConfig


class TestCredentialsModels:
    """Test authentication credential models."""
    
    def test_bearer_token_credentials(self):
        """Test BearerTokenCredentials model."""
        creds = BearerTokenCredentials(token="test_token_123")
        assert creds.token == "test_token_123"
        assert "test_token_123" not in repr(creds)  # Token should not be in repr
    
    def test_hmac_credentials(self):
        """Test HMACCredentials model."""
        creds = HMACCredentials(
            api_key="test_key",
            secret_key="test_secret",
            passphrase="test_pass"
        )
        assert creds.api_key == "test_key"
        assert creds.secret_key == "test_secret"
        assert creds.passphrase == "test_pass"
        
        # Secrets should not be in repr
        repr_str = repr(creds)
        assert "test_secret" not in repr_str
        assert "test_pass" not in repr_str
    
    def test_hmac_credentials_optional_passphrase(self):
        """Test HMACCredentials with optional passphrase."""
        creds = HMACCredentials(
            api_key="test_key",
            secret_key="test_secret"
        )
        assert creds.passphrase is None
    
    def test_session_credentials(self):
        """Test SessionCredentials model."""
        creds = SessionCredentials(
            username="test_user",
            password="test_pass"
        )
        assert creds.username == "test_user"
        assert creds.password == "test_pass"
        assert creds.session_token is None
        
        # Password should not be in repr
        repr_str = repr(creds)
        assert "test_pass" not in repr_str


class TestAccountModels:
    """Test account-related models."""
    
    def test_balance_model(self):
        """Test Balance model."""
        balance = Balance(
            currency="USD",
            balance=Decimal("1000.00"),
            available=Decimal("800.00"),
            used=Decimal("200.00"),
            reserved=Decimal("0.00")
        )
        
        assert balance.currency == "USD"
        assert balance.balance == Decimal("1000.00")
        assert balance.available == Decimal("800.00")
        assert balance.used == Decimal("200.00")
        assert balance.reserved == Decimal("0.00")
    
    def test_account_model(self, sample_account):
        """Test Account model."""
        account = sample_account
        
        assert account.account_id == "acc_123456"
        assert account.account_name == "Test Account"
        assert account.currency == "USD"
        assert account.balance == Decimal("10000.00")
        assert isinstance(account.created_at, datetime)
        assert len(account.balances) == 1
    
    def test_account_validation_errors(self):
        """Test Account model validation errors."""
        with pytest.raises(ValidationError):
            Account(
                account_id="",  # Empty string should fail
                account_name="Test",
                account_type="demo",
                currency="USD",
                balance=Decimal("1000"),
                equity=Decimal("1000"),
                margin=Decimal("0"),
                free_margin=Decimal("1000"),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )


class TestInstrumentModels:
    """Test instrument-related models."""
    
    def test_instrument_model(self, sample_instrument):
        """Test Instrument model."""
        instrument = sample_instrument
        
        assert instrument.symbol == "EURUSD"
        assert instrument.name == "Euro vs US Dollar"
        assert instrument.type == InstrumentType.FOREX
        assert instrument.base_currency == "EUR"
        assert instrument.quote_currency == "USD"
        assert instrument.digits == 5
        assert instrument.enabled is True
    
    def test_price_model(self, sample_price):
        """Test Price model."""
        price = sample_price
        
        assert price.symbol == "EURUSD"
        assert price.bid == Decimal("1.08745")
        assert price.ask == Decimal("1.08755")
        assert price.spread == Decimal("0.0001")
        assert isinstance(price.timestamp, datetime)
    
    def test_tick_model(self):
        """Test Tick model."""
        tick = Tick(
            symbol="EURUSD",
            bid=Decimal("1.08745"),
            ask=Decimal("1.08755"),
            volume=Decimal("100000"),
            timestamp=datetime.now(timezone.utc)
        )
        
        assert tick.symbol == "EURUSD"
        assert tick.volume == Decimal("100000")
    
    def test_candle_model(self):
        """Test Candle model."""
        candle = Candle(
            symbol="EURUSD",
            timestamp=datetime.now(timezone.utc),
            open=Decimal("1.08500"),
            high=Decimal("1.08800"),
            low=Decimal("1.08400"),
            close=Decimal("1.08750"),
            volume=Decimal("1000000")
        )
        
        assert candle.symbol == "EURUSD"
        assert candle.open == Decimal("1.08500")
        assert candle.high == Decimal("1.08800")
        assert candle.low == Decimal("1.08400")
        assert candle.close == Decimal("1.08750")


class TestOrderModels:
    """Test order-related models."""
    
    def test_order_request_model(self):
        """Test OrderRequest model."""
        order = OrderRequest(
            symbol="EURUSD",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            volume=Decimal("0.1"),
            price=Decimal("1.08500"),
            time_in_force=TimeInForce.GTC,
            stop_loss=Decimal("1.08000"),
            take_profit=Decimal("1.09000")
        )
        
        assert order.symbol == "EURUSD"
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.LIMIT
        assert order.volume == Decimal("0.1")
        assert order.price == Decimal("1.08500")
        assert order.stop_loss == Decimal("1.08000")
        assert order.take_profit == Decimal("1.09000")
    
    def test_oco_order_request_model(self):
        """Test OCOOrderRequest model."""
        order = OCOOrderRequest(
            symbol="EURUSD",
            side=OrderSide.BUY,
            volume=Decimal("0.1"),
            price=Decimal("1.09000"),
            stop_price=Decimal("1.08000"),
            time_in_force=TimeInForce.GTC
        )
        
        assert order.symbol == "EURUSD"
        assert order.price == Decimal("1.09000")
        assert order.stop_price == Decimal("1.08000")
    
    def test_bracket_order_request_model(self):
        """Test BracketOrderRequest model."""
        order = BracketOrderRequest(
            symbol="EURUSD",
            side=OrderSide.BUY,
            volume=Decimal("0.1"),
            price=Decimal("1.08500"),
            stop_loss=Decimal("1.08000"),
            take_profit=Decimal("1.09000")
        )
        
        assert order.stop_loss == Decimal("1.08000")
        assert order.take_profit == Decimal("1.09000")
    
    def test_order_model(self, sample_order):
        """Test Order model."""
        order = sample_order
        
        assert order.order_id == "ord_123456"
        assert order.symbol == "EURUSD"
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.LIMIT
        assert order.status == OrderStatus.OPEN
        assert order.volume == Decimal("0.1")
        assert order.filled_volume == Decimal("0.0")
        assert order.remaining_volume == Decimal("0.1")
    
    def test_trade_model(self, sample_trade):
        """Test Trade model."""
        trade = sample_trade
        
        assert trade.trade_id == "trade_123456"
        assert trade.order_id == "ord_123456"
        assert trade.symbol == "EURUSD"
        assert trade.side == OrderSide.BUY
        assert trade.volume == Decimal("0.1")
        assert trade.price == Decimal("1.08500")


class TestPositionModels:
    """Test position-related models."""
    
    def test_position_model(self, sample_position):
        """Test Position model."""
        position = sample_position
        
        assert position.position_id == "pos_123456"
        assert position.account_id == "acc_123456"
        assert position.symbol == "EURUSD"
        assert position.side == PositionSide.LONG
        assert position.volume == Decimal("0.1")
        assert position.entry_price == Decimal("1.08500")
        assert position.unrealized_pnl == Decimal("25.0")


class TestEventModels:
    """Test push API event models."""
    
    def test_price_event_model(self):
        """Test PriceEvent model."""
        price_data = Price(
            symbol="EURUSD",
            bid=Decimal("1.08745"),
            ask=Decimal("1.08755"),
            spread=Decimal("0.0001"),
            timestamp=datetime.now(timezone.utc)
        )
        
        event = PriceEvent(
            type=EventType.PRICE,
            timestamp=datetime.now(timezone.utc),
            data=price_data
        )
        
        assert event.type == EventType.PRICE
        assert event.data.symbol == "EURUSD"
        assert event.data.bid == Decimal("1.08745")


class TestConfigModels:
    """Test configuration models."""
    
    def test_http_config_model(self):
        """Test HTTPConfig model."""
        config = HTTPConfig(
            base_url="https://api.dxtrade.com",
            timeout=30.0,
            max_retries=3,
            retry_backoff_factor=0.3,
            rate_limit=100,
            user_agent="test-sdk/1.0.0"
        )
        
        assert config.base_url == "https://api.dxtrade.com"
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.rate_limit == 100
    
    def test_websocket_config_model(self):
        """Test WebSocketConfig model."""
        config = WebSocketConfig(
            url="wss://push.dxtrade.com/v1/stream",
            max_retries=5,
            retry_backoff_factor=0.5,
            heartbeat_interval=30.0,
            max_message_size=1024*1024,
            ping_interval=20.0,
            ping_timeout=10.0
        )
        
        assert config.url == "wss://push.dxtrade.com/v1/stream"
        assert config.max_retries == 5
        assert config.heartbeat_interval == 30.0


class TestEnums:
    """Test enum values."""
    
    def test_auth_type_enum(self):
        """Test AuthType enum."""
        assert AuthType.BEARER_TOKEN == "bearer_token"
        assert AuthType.HMAC == "hmac"
        assert AuthType.SESSION == "session"
    
    def test_order_enums(self):
        """Test order-related enums."""
        assert OrderSide.BUY == "buy"
        assert OrderSide.SELL == "sell"
        
        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
        assert OrderType.STOP == "stop"
        
        assert OrderStatus.OPEN == "open"
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.CANCELLED == "cancelled"
        
        assert TimeInForce.GTC == "gtc"
        assert TimeInForce.IOC == "ioc"
        assert TimeInForce.FOK == "fok"
    
    def test_instrument_enums(self):
        """Test instrument-related enums."""
        assert InstrumentType.FOREX == "forex"
        assert InstrumentType.CFD == "cfd"
        assert InstrumentType.CRYPTO == "crypto"
        
        assert MarketStatus.OPEN == "open"
        assert MarketStatus.CLOSED == "closed"
    
    def test_position_enums(self):
        """Test position-related enums."""
        assert PositionSide.LONG == "long"
        assert PositionSide.SHORT == "short"
    
    def test_event_enums(self):
        """Test event-related enums."""
        assert EventType.PRICE == "price"
        assert EventType.ORDER == "order"
        assert EventType.POSITION == "position"
        assert EventType.ACCOUNT == "account"
        assert EventType.HEARTBEAT == "heartbeat"


class TestModelValidation:
    """Test model validation edge cases."""
    
    def test_decimal_conversion(self):
        """Test automatic decimal conversion."""
        balance = Balance(
            currency="USD",
            balance="1000.50",  # String should be converted to Decimal
            available=1000.25,   # Float should be converted to Decimal
            used=200,           # Int should be converted to Decimal
            reserved=Decimal("0.25")  # Decimal should remain Decimal
        )
        
        assert isinstance(balance.balance, Decimal)
        assert isinstance(balance.available, Decimal)
        assert isinstance(balance.used, Decimal)
        assert isinstance(balance.reserved, Decimal)
        
        assert balance.balance == Decimal("1000.50")
        assert balance.available == Decimal("1000.25")
        assert balance.used == Decimal("200")
        assert balance.reserved == Decimal("0.25")
    
    def test_datetime_validation(self):
        """Test datetime validation."""
        # Should accept datetime objects
        now = datetime.now(timezone.utc)
        price = Price(
            symbol="EURUSD",
            bid=Decimal("1.08745"),
            ask=Decimal("1.08755"),
            spread=Decimal("0.0001"),
            timestamp=now
        )
        assert price.timestamp == now
        
        # Should parse ISO format strings
        price2 = Price(
            symbol="EURUSD",
            bid=Decimal("1.08745"),
            ask=Decimal("1.08755"),
            spread=Decimal("0.0001"),
            timestamp="2024-01-01T12:00:00Z"
        )
        assert isinstance(price2.timestamp, datetime)
    
    def test_enum_validation(self):
        """Test enum validation."""
        # Valid enum values
        order = OrderRequest(
            symbol="EURUSD",
            side="buy",  # String should be converted to enum
            type=OrderType.LIMIT,  # Enum should be accepted
            volume=Decimal("0.1")
        )
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.LIMIT
        
        # Invalid enum values should raise ValidationError
        with pytest.raises(ValidationError):
            OrderRequest(
                symbol="EURUSD",
                side="invalid_side",  # Invalid enum value
                type=OrderType.LIMIT,
                volume=Decimal("0.1")
            )
    
    def test_required_fields(self):
        """Test required field validation."""
        # Missing required field should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            Price(
                symbol="EURUSD",
                bid=Decimal("1.08745"),
                # ask is required but missing
                spread=Decimal("0.0001"),
                timestamp=datetime.now(timezone.utc)
            )
        
        assert "ask" in str(exc_info.value)
    
    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            Price(
                symbol="EURUSD",
                bid=Decimal("1.08745"),
                ask=Decimal("1.08755"),
                spread=Decimal("0.0001"),
                timestamp=datetime.now(timezone.utc),
                extra_field="not_allowed"  # Should be forbidden
            )