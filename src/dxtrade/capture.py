"""Capture class for streaming quotes and managing positions."""

from __future__ import annotations

# mypy: disable-error-code="no-untyped-call"
import csv
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from .transport import DXTradeTransport
from .utils import as_list
from .utils import close_position
from .utils import flatten
from .utils import open_position
from .utils import resolve_account
from .utils import resolve_symbol

CSV_COLUMNS = ["symbol", "type", "bid", "ask", "spread", "time", "received_at"]


class QuoteStore:
    """Collect quote events into an append-only CSV store and a Polars frame.

    Long-term storage is one CSV file per day; the header is written once and
    rows are appended in batches on :meth:`flush`. The Polars frame is rebuilt
    incrementally as rows arrive and is available via :attr:`polars_df`.
    """

    def __init__(self, data_dir: str, write_parquet: bool = False) -> None:
        """Initialize the store.

        Args:
            data_dir: Directory for the CSV/parquet files (created if missing)
            write_parquet: Also write a parquet snapshot on :meth:`close`
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.write_parquet = write_parquet
        self._pending: list[dict[str, Any]] = []
        self._df: Any | None = None
        self._csv_path: Path | None = None

    def append(self, event: dict[str, Any]) -> None:
        """Record one quote event (e.g. from a MarketData payload event)."""
        bid = event.get("bid")
        ask = event.get("ask")
        spread = (
            round(float(ask) - float(bid), 8)
            if bid is not None and ask is not None
            else None
        )
        self._pending.append(
            {
                "symbol": event.get("symbol"),
                "type": event.get("type", "Quote"),
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "time": event.get("time"),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    @property
    def polars_df(self) -> Any:
        """In-memory Polars DataFrame of all quotes received so far."""
        if self._df is None:
            _import_polars()
            import polars as pl

            return pl.DataFrame(schema=dict.fromkeys(CSV_COLUMNS, pl.Utf8))
        return self._df

    def last_prices(self) -> Any:
        """Last bid/ask per symbol as a small DataFrame."""
        _import_polars()
        import polars as pl

        return self.polars_df.group_by("symbol").agg(
            pl.col("bid").last().alias("last_bid"),
            pl.col("ask").last().alias("last_ask"),
            pl.col("received_at").last().alias("last_received_at"),
        )

    def flush(self) -> None:
        """Write pending rows to today's CSV and update the Polars frame."""
        if not self._pending:
            return
        rows = self._pending
        self._pending = []
        self._write_csv(rows)
        self._extend_df(rows)

    def close(self) -> None:
        """Flush everything; optionally write a parquet snapshot."""
        self.flush()
        if self.write_parquet and self._df is not None and self._df.height:
            _import_polars()
            snapshot = (
                self.data_dir
                / f"quotes_snapshot_{datetime.now(timezone.utc):%Y-%m-%d}.parquet"
            )
            self._df.write_parquet(snapshot)

    def _write_csv(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.data_dir / f"quotes_{today}.csv"
        new_file = not path.exists() or path.stat().st_size == 0
        with open(path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            if new_file:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)
        self._csv_path = path

    def _extend_df(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        _import_polars()
        import polars as pl

        new = pl.DataFrame(rows)
        self._df = new if self._df is None else pl.concat([self._df, new])

    def to_parquet(self, path: str | Path) -> None:
        """Write the DataFrame to a parquet file."""
        _import_polars()
        if self._df is None or self._df.height == 0:
            return
        pl_path = Path(path)
        self._df.write_parquet(pl_path)

    def to_csv(self, path: str | Path) -> None:
        """Write the DataFrame to a CSV file."""
        if self._df is None or self._df.height == 0:
            return
        _import_polars()

        pl_path = Path(path)
        self._df.write_csv(pl_path)


def _import_polars() -> None:
    """Lazy import polars with helpful error message."""
    try:
        import polars  # noqa: F401
    except ImportError as err:
        raise ImportError(
            "Polars is required for data operations. "
            "Install with: pip install -e '.[capture]'"
        ) from err


class Capture:
    """High-level class for streaming quotes and managing positions.

    Provides a simple API for:
    - Subscribing to market data
    - Placing and closing orders
    - Storing quotes to CSV + Polars DataFrame
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        data_dir: str = "data/quotes",
        write_parquet: bool = False,
        config: Any | None = None,
    ) -> None:
        """Initialize Capture.

        Args:
            symbols: Symbol hints to stream (e.g. ["CL", "NATGAS"]). Resolved on subscribe().
            data_dir: Directory for CSV files (created if missing).
            write_parquet: Also write a parquet snapshot on close().
            config: Optional SDK config (loads from env if None).
        """
        self.symbols = symbols or []
        self.data_dir = data_dir
        self.write_parquet = write_parquet
        self.config = config
        self.transport: DXTradeTransport | None = None
        self.store: QuoteStore | None = None
        self._account: str | None = None
        self._subscribed = False

    async def connect(self) -> None:
        """Authenticate and prepare transport."""
        from .transport import create_transport

        self.transport = create_transport(self.config)
        self.store = QuoteStore(self.data_dir, self.write_parquet)
        self._account = await resolve_account(self.transport)  # str

    async def close(self) -> None:
        """Unsubscribe, flush data, and close transport."""
        if self._subscribed and self.transport:
            await self.transport.unsubscribe("quotes")
            self._subscribed = False
        if self.store:
            self.store.close()
        if self.transport:
            await self.transport.close()

    async def __aenter__(self) -> Capture:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def subscribe(self, symbols: list[str] | None = None) -> None:
        """Start streaming quotes for symbols.

        Args:
            symbols: Symbol hints to stream (uses constructor symbols if None).
        """
        if not self.transport or not self.store or not self._account:
            raise RuntimeError("Call connect() first")

        symbols_to_stream = symbols or self.symbols
        if not symbols_to_stream:
            raise ValueError("No symbols to stream")

        # Resolve symbol hints to platform symbols
        resolved = []
        for hint in symbols_to_stream:
            symbol = await resolve_symbol(self.transport, self._account, hint)
            resolved.append(symbol)

        def callback(message: Any) -> None:
            if isinstance(message, dict) and message.get("type") == "MarketData":
                for event in message.get("payload", {}).get("events", []):
                    if isinstance(event, dict) and self.store:
                        self.store.append(event)

        await self.transport.subscribe("quotes", callback)
        if not await self.transport.wait_for_channel("quotes", timeout=30.0):
            await self.transport.unsubscribe("quotes")
            raise TimeoutError("market data channel did not connect")

        await self.transport.send_market_data_subscription(resolved, self._account)
        self._subscribed = True

    async def unsubscribe(self) -> None:
        """Stop streaming quotes."""
        if self.transport and self._subscribed:
            await self.transport.unsubscribe("quotes")
            self._subscribed = False

    async def place_order(
        self,
        symbol: str,
        side: str = "BUY",
        quantity: float | None = None,
        stop_loss: float | None = None,
        stop_loss_price: float | None = None,
    ) -> dict[str, Any]:
        """Open a market position with optional protective stop.

        Args:
            symbol: Symbol hint (e.g. "BTCUSDT").
            side: "BUY" or "SELL".
            quantity: Position size in base units (defaults to instrument minimum).
            stop_loss: Optional max loss in account currency.
            stop_loss_price: Optional absolute stop price.

        Returns:
            Dict with order, position, and stop_order keys.
        """
        if not self.transport or not self._account:
            raise RuntimeError("Call connect() first")

        return await open_position(
            self.transport,
            symbol=symbol,
            side=side,
            quantity=quantity,
            stop_loss=stop_loss,
            stop_loss_price=stop_loss_price,
            account=self._account,
        )

    async def close_position(
        self,
        symbol: str | None = None,
        position_code: str | None = None,
    ) -> dict[str, Any]:
        """Close a specific position.

        Args:
            symbol: Optional symbol filter.
            position_code: Optional position code to close.

        Returns:
            Dict with order and position keys.
        """
        if not self.transport or not self._account:
            raise RuntimeError("Call connect() first")

        return await close_position(
            self.transport,
            account=self._account,
            symbol=symbol,
            position_code=position_code,
        )

    async def flatten(self) -> dict[str, Any]:
        """Close all positions and cancel working orders.

        Returns:
            Dict with closed, cancelled, and errors keys.
        """
        if not self.transport or not self._account:
            raise RuntimeError("Call connect() first")

        return await flatten(self.transport, account=self._account)

    async def get_positions(self) -> list[dict[str, Any]]:
        """Get current open positions."""
        if not self.transport or not self._account:
            raise RuntimeError("Call connect() first")

        payload = await self.transport.get_account_positions(self._account)
        return as_list(payload, "positions")

    async def get_orders(self) -> list[dict[str, Any]]:
        """Get current working orders."""
        if not self.transport or not self._account:
            raise RuntimeError("Call connect() first")

        payload = await self.transport.get_account_orders(self._account)
        return as_list(payload, "orders")

    def get_dataframe(self) -> Any:
        """Return the full captured DataFrame."""
        if not self.store:
            raise RuntimeError("Call connect() first")
        return self.store.polars_df

    def last_prices(self) -> Any:
        """Return last bid/ask per symbol."""
        if not self.store:
            raise RuntimeError("Call connect() first")
        return self.store.last_prices()

    def to_parquet(self, path: str | Path) -> None:
        """Write captured data to a parquet file."""
        if not self.store:
            raise RuntimeError("Call connect() first")
        self.store.to_parquet(path)

    def to_csv(self, path: str | Path) -> None:
        """Write captured data to a CSV file."""
        if not self.store:
            raise RuntimeError("Call connect() first")
        self.store.to_csv(path)

    def append(self, event: dict[str, Any]) -> None:
        """Manually record a quote event."""
        if not self.store:
            raise RuntimeError("Call connect() first")
        self.store.append(event)
