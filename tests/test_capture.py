"""Tests for the Capture class and QuoteStore."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest


def test_quote_store_append_and_flush():
    """Test that QuoteStore can append events and flush to DataFrame."""
    from dxtrade.capture import QuoteStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir)
        store.append(
            {
                "symbol": "CL",
                "bid": 75.5,
                "ask": 75.6,
                "type": "Quote",
                "time": "2026-08-14T12:00:00.000Z",
            }
        )
        store.flush()
        assert store.polars_df.height == 1
        assert store.polars_df["symbol"][0] == "CL"


@pytest.mark.asyncio
async def test_capture_context_manager():
    """Test that Capture works as a context manager."""
    from dxtrade.capture import Capture

    with patch("dxtrade.transport.create_transport") as mock_factory:
        mock_transport = AsyncMock()
        mock_transport.get_users = AsyncMock(
            return_value={"accounts": [{"accountCode": "default:123"}]}
        )
        mock_factory.return_value = mock_transport

        async with Capture(symbols=["CL"], data_dir="data/quotes") as cap:
            assert cap.transport is not None
            assert cap.store is not None


@pytest.mark.asyncio
async def test_capture_subscribe():
    """Test that Capture.subscribe() calls transport correctly."""
    from dxtrade.capture import Capture

    with patch("dxtrade.transport.create_transport") as mock_factory:
        mock_transport = AsyncMock()
        mock_transport.get_users = AsyncMock(
            return_value={"accounts": [{"accountCode": "default:123"}]}
        )
        mock_transport.wait_for_channel = AsyncMock(return_value=True)
        mock_transport.subscribe = AsyncMock()
        mock_transport.send_market_data_subscription = AsyncMock()
        mock_factory.return_value = mock_transport

        with patch("dxtrade.capture.resolve_symbol", return_value="CL"):
            cap = Capture(symbols=["CL"])
            await cap.connect()
            await cap.subscribe()

            mock_transport.subscribe.assert_called_once()
            assert cap._subscribed is True


@pytest.mark.asyncio
async def test_capture_place_order():
    """Test that Capture.place_order() delegates to utils."""
    from dxtrade.capture import Capture

    with patch("dxtrade.capture.open_position") as mock_open:
        mock_open.return_value = {
            "order": {"orderId": "123"},
            "position": {"positionCode": "pos1"},
        }

        cap = Capture()
        cap.transport = AsyncMock()
        cap._account = "default:123"
        cap.store = AsyncMock()

        result = await cap.place_order("CL", "BUY", quantity=1.0)
        assert result["order"]["orderId"] == "123"
        mock_open.assert_called_once()


@pytest.mark.asyncio
async def test_capture_close_position():
    """Test that Capture.close_position() delegates to utils."""
    from dxtrade.capture import Capture

    with patch("dxtrade.capture.close_position") as mock_close:
        mock_close.return_value = {
            "order": {"orderId": "123"},
            "position": {"positionCode": "pos1"},
        }

        cap = Capture()
        cap.transport = AsyncMock()
        cap._account = "default:123"
        cap.store = AsyncMock()

        result = await cap.close_position(position_code="pos1")
        assert result["order"]["orderId"] == "123"
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_capture_flatten():
    """Test that Capture.flatten() delegates to utils."""
    from dxtrade.capture import Capture

    with patch("dxtrade.capture.flatten") as mock_flatten:
        mock_flatten.return_value = {
            "closed": ["pos1"],
            "cancelled": ["ord1"],
            "errors": [],
        }

        cap = Capture()
        cap.transport = AsyncMock()
        cap._account = "default:123"
        cap.store = AsyncMock()

        result = await cap.flatten()
        assert "closed" in result
        mock_flatten.assert_called_once()


def test_capture_data_access():
    """Test that Capture data access methods work."""
    from dxtrade.capture import Capture
    from dxtrade.capture import QuoteStore

    cap = Capture(data_dir=tempfile.gettempdir())
    cap.store = QuoteStore(tempfile.gettempdir())
    cap.store.append(
        {
            "symbol": "CL",
            "bid": 75.5,
            "ask": 75.6,
            "type": "Quote",
            "time": "2026-08-14T12:00:00.000Z",
        }
    )
    cap.store.flush()

    df = cap.get_dataframe()
    assert df.height == 1

    last = cap.last_prices()
    assert last.height == 1


def test_capture_append():
    """Test that Capture.append() delegates to store."""
    from dxtrade.capture import Capture
    from dxtrade.capture import QuoteStore

    cap = Capture(data_dir=tempfile.gettempdir())
    cap.store = QuoteStore(tempfile.gettempdir())

    cap.append(
        {
            "symbol": "CL",
            "bid": 75.5,
            "ask": 75.6,
            "type": "Quote",
            "time": "2026-08-14T12:00:00.000Z",
        }
    )

    assert len(cap.store._pending) == 1


def test_quote_store_to_parquet():
    """Test that QuoteStore.to_parquet() works."""
    from dxtrade.capture import QuoteStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir, write_parquet=True)
        store.append(
            {
                "symbol": "CL",
                "bid": 75.5,
                "ask": 75.6,
                "type": "Quote",
                "time": "2026-08-14T12:00:00.000Z",
            }
        )
        store.flush()

        parquet_path = Path(tmpdir) / "test.parquet"
        store.to_parquet(parquet_path)
        assert parquet_path.exists()


def test_quote_store_to_csv():
    """Test that QuoteStore.to_csv() works."""
    from dxtrade.capture import QuoteStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir)
        store.append(
            {
                "symbol": "CL",
                "bid": 75.5,
                "ask": 75.6,
                "type": "Quote",
                "time": "2026-08-14T12:00:00.000Z",
            }
        )
        store.flush()

        csv_path = Path(tmpdir) / "test.csv"
        store.to_csv(csv_path)
        assert csv_path.exists()


def test_quote_store_ohlcv_conversion():
    """Test that QuoteStore.to_ohlcv() converts quotes to OHLCV bars."""
    from dxtrade.capture import QuoteStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir)

        # Add multiple quotes over a time range
        base_time = "2026-08-14T12:00:"
        for i in range(5):
            store.append(
                {
                    "symbol": "CL",
                    "bid": 75.0 + i * 0.1,
                    "ask": 75.1 + i * 0.1,
                    "type": "Quote",
                    "time": f"{base_time}{i:02d}.000Z",
                }
            )
        store.flush()

        ohlcv = store.to_ohlcv(timeframe="1m")
        assert ohlcv.height > 0
        assert "symbol" in ohlcv.columns
        assert "open" in ohlcv.columns
        assert "high" in ohlcv.columns
        assert "low" in ohlcv.columns
        assert "close" in ohlcv.columns
        assert "bar_count" in ohlcv.columns


def test_quote_store_ohlcv_empty():
    """Test that to_ohlcv() returns empty DataFrame when no data."""
    from dxtrade.capture import QuoteStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir)
        ohlcv = store.to_ohlcv(timeframe="1m")
        assert ohlcv.height == 0
        assert "symbol" in ohlcv.columns


def test_quote_store_ohlcv_timeframes():
    """Test OHLCV conversion with different timeframes."""
    from dxtrade.capture import QuoteStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir)

        # Add quotes over multiple minutes
        for minute in range(3):
            for sec in range(2):
                store.append(
                    {
                        "symbol": "CL",
                        "bid": 75.0 + minute * 0.1 + sec * 0.01,
                        "ask": 75.1 + minute * 0.1 + sec * 0.01,
                        "type": "Quote",
                        "time": f"2026-08-14T12:{minute:02d}:{sec:02d}.000Z",
                    }
                )
        store.flush()

        # Test 1-minute bars
        ohlcv_1m = store.to_ohlcv(timeframe="1m")
        assert ohlcv_1m.height >= 1

        # Test 5-minute bars
        ohlcv_5m = store.to_ohlcv(timeframe="5m")
        assert ohlcv_5m.height >= 1


def test_capture_get_ohlcv():
    """Test that Capture.get_ohlcv() delegates to store."""
    from dxtrade.capture import Capture
    from dxtrade.capture import QuoteStore

    cap = Capture(data_dir=tempfile.gettempdir())
    cap.store = QuoteStore(tempfile.gettempdir())
    cap.store.append(
        {
            "symbol": "CL",
            "bid": 75.5,
            "ask": 75.6,
            "type": "Quote",
            "time": "2026-08-14T12:00:00.000Z",
        }
    )
    cap.store.flush()

    ohlcv = cap.get_ohlcv(timeframe="1m")
    # With 1 quote, OHLCV creates 1 bar (open=high=low=close)
    assert ohlcv.height == 1
    assert ohlcv["open"][0] == 75.5
    assert ohlcv["close"][0] == 75.5


def test_parse_timeframe():
    """Test timeframe parsing."""
    from dxtrade.capture import _parse_timeframe

    assert _parse_timeframe("1m") == "1m"
    assert _parse_timeframe("5m") == "5m"
    assert _parse_timeframe("1h") == "1h"
    assert _parse_timeframe("4h") == "4h"
    assert _parse_timeframe("1d") == "1d"
    assert _parse_timeframe("60") == "60m"  # Numeric-only treated as minutes
    assert _parse_timeframe("") == "1m"  # Empty defaults to 1m
    assert _parse_timeframe(None) == "1m"  # None defaults to 1m
