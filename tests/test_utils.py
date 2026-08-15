"""Unit tests for the high-level transport utilities."""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from dxtrade.utils import account_is_flat
from dxtrade.utils import close_position
from dxtrade.utils import find_account_code
from dxtrade.utils import flatten
from dxtrade.utils import open_position
from dxtrade.utils import resolve_account
from dxtrade.utils import resolve_symbol
from dxtrade.utils import stream_quotes


@pytest.fixture
def transport():
    """AsyncMock transport with a valid session and one account."""
    mock = AsyncMock()
    mock.auth_handler = MagicMock()
    mock.auth_handler.get_session_token.return_value = "token"
    mock.get_users.return_value = {"users": [{"accountCode": "default:12345"}]}
    return mock


class TestFindAccountCode:
    """Test account code extraction from /users responses."""

    def test_list_shape(self):
        users = [{"accountCode": "default:12345"}]
        assert find_account_code(users) == "default:12345"

    def test_nested_accounts(self):
        users = {"users": [{"accounts": [{"accountCode": "default:12345"}]}]}
        assert find_account_code(users) == "default:12345"

    def test_no_account(self):
        with pytest.raises(ValueError):
            find_account_code({"users": []})


class TestResolveAccount:
    """Test account discovery through the transport."""

    async def test_uses_existing_token(self, transport):
        account = await resolve_account(transport)
        assert account == "default:12345"
        transport.authenticate.assert_not_called()

    async def test_logs_in_when_no_token(self, transport):
        transport.auth_handler.get_session_token.return_value = None
        account = await resolve_account(transport)
        assert account == "default:12345"
        transport.authenticate.assert_awaited_once()


class TestResolveSymbol:
    """Test symbol hint resolution."""

    async def test_exact_match(self, transport):
        transport.query_instruments.return_value = {
            "instrumentDetails": [{"symbol": "BTCUSD", "minOrderSize": 0.001}]
        }
        symbol = await resolve_symbol(transport, "default:12345", "BTCUSD")
        assert symbol == "BTCUSD"

    async def test_usdt_hint_matches_usd_symbol(self, transport):
        # The server matches exactly: BTCUSDT returns nothing, BTCUSD returns
        # the instrument record.
        def query_side_effect(symbols=None, account=None, limit=None):
            if symbols == ["BTCUSD"]:
                return {
                    "instrumentDetails": [{"symbol": "BTCUSD", "minOrderSize": 0.001}]
                }
            return {"instrumentDetails": []}

        transport.query_instruments.side_effect = query_side_effect
        symbol = await resolve_symbol(transport, "default:12345", "BTCUSDT")
        assert symbol == "BTCUSD"
        # BTCUSDT (no match) and BTCUSD (match) were both queried
        queried = [
            call.kwargs["symbols"]
            for call in transport.query_instruments.call_args_list
        ]
        assert ["BTCUSDT"] in queried
        assert ["BTCUSD"] in queried

    async def test_unresolvable_raises(self, transport):
        transport.query_instruments.return_value = {"instrumentDetails": []}
        with pytest.raises(ValueError):
            await resolve_symbol(transport, "default:12345", "NOPE")


class TestOpenPosition:
    """Test opening a position with optional protective stop."""

    def _transport(self, transport):
        transport.query_instruments.return_value = {
            "instrumentDetails": [{"symbol": "BTCUSD", "minOrderSize": 0.001}]
        }
        transport.get_market_data.return_value = {
            "events": [{"type": "Quote", "bid": 60000.0, "ask": 60001.0}]
        }
        transport.get_account_positions.return_value = {
            "positions": [
                {
                    "positionCode": "P1",
                    "symbol": "BTCUSD",
                    "quantity": 0.001,
                    "side": "BUY",
                    "openPrice": 60001.0,
                }
            ]
        }
        transport.place_order.return_value = {"orderId": 100}
        return transport

    async def test_open_without_stop(self, transport):
        self._transport(transport)
        result = await open_position(transport, "BTCUSD")

        assert result["position"]["positionCode"] == "P1"
        assert result["stop_order"] is None
        assert transport.place_order.await_count == 1

    async def test_open_with_usd_stop_loss(self, transport):
        self._transport(transport)
        result = await open_position(transport, "BTCUSD", stop_loss=10.0)

        assert transport.place_order.await_count == 2
        # stop price = entry (ask) - loss/qty = 60001 - 10/0.001 = 50001
        stop_payload = transport.place_order.await_args_list[1].args[1]
        assert stop_payload["type"] == "STOP"
        assert stop_payload["positionEffect"] == "CLOSE"
        assert stop_payload["stopPrice"] == 50001.0
        assert stop_payload["side"] == "SELL"
        # closing STOP orders must not carry a quantity
        assert "quantity" not in stop_payload
        assert result["stop_order"] == {"orderId": 100}

    async def test_open_with_absolute_stop_price(self, transport):
        self._transport(transport)
        await open_position(transport, "BTCUSD", stop_loss_price=55000.0)

        stop_payload = transport.place_order.await_args_list[1].args[1]
        assert stop_payload["stopPrice"] == 55000.0

    async def test_bad_side(self, transport):
        with pytest.raises(ValueError):
            await open_position(transport, "BTCUSD", side="SIDEWAYS")

    async def test_no_fill_raises(self, transport):
        self._transport(transport)
        transport.get_account_positions.return_value = {"positions": []}
        with pytest.raises(RuntimeError):
            await open_position(transport, "BTCUSD", fill_timeout=0.2)


class TestClosePosition:
    """Test closing a position."""

    async def test_close_by_symbol(self, transport):
        transport.get_account_positions.return_value = {
            "positions": [
                {
                    "positionCode": "P1",
                    "symbol": "BTCUSD",
                    "quantity": 0.001,
                    "side": "BUY",
                }
            ]
        }
        transport.place_order.return_value = {"orderId": 200}

        result = await close_position(transport, symbol="BTCUSD")

        payload = transport.place_order.await_args.args[1]
        assert payload["positionEffect"] == "CLOSE"
        assert payload["positionCode"] == "P1"
        assert payload["side"] == "SELL"
        assert "quantity" not in payload
        assert result["position"]["positionCode"] == "P1"

    async def test_close_requires_exactly_one(self, transport):
        transport.get_account_positions.return_value = {"positions": []}
        with pytest.raises(ValueError):
            await close_position(transport, symbol="BTCUSD")


class TestFlatten:
    """Test flattening the account."""

    async def test_closes_and_cancels(self, transport):
        transport.get_account_positions.return_value = {
            "positions": [
                {"positionCode": "P1", "symbol": "BTCUSD", "side": "BUY"},
                {"positionCode": "P2", "symbol": "ETHUSD", "side": "SELL"},
            ]
        }
        transport.get_account_orders.return_value = {
            "orders": [
                {"orderCode": "o1", "status": "WORKING"},
                {"orderCode": "o2", "status": "COMPLETED"},
            ]
        }

        result = await flatten(transport)

        assert result["closed"] == ["P1", "P2"]
        assert result["cancelled"] == ["o1"]
        assert not result["errors"]


class TestAccountIsFlat:
    """Test the flat-state check."""

    async def test_flat(self, transport):
        transport.get_account_metrics.return_value = {
            "metrics": [{"openPositionsCount": 0, "openOrdersCount": 0}]
        }
        assert await account_is_flat(transport) is True

    async def test_not_flat(self, transport):
        transport.get_account_metrics.return_value = {
            "metrics": [{"openPositionsCount": 1, "openOrdersCount": 0}]
        }
        assert await account_is_flat(transport) is False


class TestStreamQuotes:
    """Test quote streaming."""

    async def test_streams_and_collects(self, transport):
        transport.query_instruments.return_value = {
            "instrumentDetails": [{"symbol": "BTCUSD", "minOrderSize": 0.001}]
        }
        transport.wait_for_channel.return_value = True

        captured = {}

        async def fake_subscribe(channel, callback, **kwargs):
            captured["callback"] = callback

        transport.subscribe.side_effect = fake_subscribe

        # A short real sleep is fine; no network involved.
        events = await stream_quotes(transport, symbols=["BTCUSD"], duration=0.01)

        assert events == []
        # Deliver a quote through the captured callback
        callback = captured["callback"]
        callback(
            {
                "type": "MarketData",
                "payload": {
                    "events": [
                        {"symbol": "BTCUSD", "bid": 1.0, "ask": 1.1, "time": "t"}
                    ]
                },
            }
        )
        transport.send_market_data_subscription.assert_awaited_once_with(
            ["BTCUSD"], "default:12345"
        )
        transport.unsubscribe.assert_awaited_once_with("quotes")
