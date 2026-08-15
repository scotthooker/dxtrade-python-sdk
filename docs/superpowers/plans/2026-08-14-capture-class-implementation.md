# Capture Class Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single, easy-to-use `Capture` class that wraps the DXTrade transport layer for streaming quotes, placing orders, and storing data to CSV + Polars DataFrame.

**Architecture:** The `Capture` class internally manages a `DXTradeTransport` instance and a `QuoteStore` for data persistence. It delegates trading operations to `dxtrade.utils` helpers and provides a clean object-oriented API for users.

**Tech Stack:** Python 3.10+, aiohttp, websockets, polars (optional), pytest for testing.

## Global Constraints

- Python `>=3.10`, fully async (`asyncio`)
- Polars is optional: lazy import only when data methods are called; show helpful error if not installed
- Reuse existing `dxtrade.utils` helpers (`open_position`, `close_position`, `flatten`, `resolve_account`, `resolve_symbol`)
- Follow existing code style: black-formatted, ruff-linted, mypy strict
- TDD: write failing tests first, then minimal implementation
- Frequent commits: one commit per task

---

### Task 1: Create `src/dxtrade/capture.py` with `QuoteStore` class

**Files:**
- Create: `src/dxtrade/capture.py`

**Interfaces:**
- Consumes: `datetime`, `pathlib`, `csv`, `polars` (lazy import)
- Produces: `QuoteStore` class with methods: `__init__`, `append`, `flush`, `close`, `polars_df` property, `last_prices`, `to_parquet`, `to_csv`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture.py
from dxtrade.capture import QuoteStore
from pathlib import Path
import tempfile

def test_quote_store_append_and_flush():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = QuoteStore(tmpdir)
        store.append({"symbol": "CL", "bid": 75.5, "ask": 75.6, "type": "Quote", "time": "2026-08-14T12:00:00.000Z"})
        store.flush()
        assert store.polars_df.height == 1
        assert store.polars_df["symbol"][0] == "CL"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_capture.py::test_quote_store_append_and_flush -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'dxtrade.capture'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/dxtrade/capture.py
"""Capture class for streaming quotes and managing positions."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CSV_COLUMNS = ["symbol", "type", "bid", "ask", "spread", "time", "received_at"]


class QuoteStore:
    """Collect quote events into an append-only CSV store and a Polars frame."""

    def __init__(self, data_dir: str, write_parquet: bool = False) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.write_parquet = write_parquet
        self._pending: list[dict[str, Any]] = []
        self._df: Any | None = None
        self._csv_path: Path | None = None

    def append(self, event: dict[str, Any]) -> None:
        """Record one quote event."""
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
            import polars as pl
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
        import polars as pl
        pl_path = Path(path)
        self._df.write_parquet(pl_path)

    def to_csv(self, path: str | Path) -> None:
        """Write the DataFrame to a CSV file."""
        if self._df is None or self._df.height == 0:
            return
        import polars as pl
        pl_path = Path(path)
        self._df.write_csv(pl_path)


def _import_polars() -> None:
    """Lazy import polars with helpful error message."""
    try:
        import polars  # noqa: F401
    except ImportError:
        raise ImportError(
            "Polars is required for data operations. "
            "Install with: pip install -e '.[capture]'"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_capture.py::test_quote_store_append_and_flush -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dxtrade/capture.py tests/test_capture.py
git commit -m "feat: add QuoteStore class for quote capture"
```

---

### Task 2: Add `Capture` class with lifecycle methods

**Files:**
- Modify: `src/dxtrade/capture.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Consumes: `QuoteStore` (from Task 1), `DXTradeTransport`
- Produces: `Capture` class with methods: `__init__`, `connect`, `close`, `__aenter__`, `__aexit__`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture.py
import pytest
from dxtrade.capture import Capture

@pytest.mark.asyncio
async def test_capture_context_manager():
    async with Capture(symbols=["CL"], data_dir="data/quotes") as cap:
        assert cap.transport is not None
        assert cap.store is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_capture.py::test_capture_context_manager -v
```
Expected: FAIL with "ImportError: cannot import name 'Capture' from 'dxtrade.capture'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/dxtrade/capture.py (add to existing file)

from typing import Any

from .transport import DXTradeTransport


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
        self.transport = create_transport(self.config)
        self.store = QuoteStore(self.data_dir, self.write_parquet)
        self._account = await resolve_account(self.transport)

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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_capture.py::test_capture_context_manager -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dxtrade/capture.py tests/test_capture.py
git commit -m "feat: add Capture class with lifecycle methods"
```

---

### Task 3: Add streaming methods to `Capture`

**Files:**
- Modify: `src/dxtrade/capture.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Consumes: `Capture` class (from Task 2), `transport.subscribe()`, `transport.send_market_data_subscription()`
- Produces: `Capture.subscribe()`, `Capture.unsubscribe()` methods

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture.py
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_capture_subscribe():
    with patch("dxtrade.capture.create_transport") as mock_factory:
        mock_transport = AsyncMock()
        mock_transport.get_users = AsyncMock(return_value={"accounts": [{"accountCode": "default:123"}]})
        mock_transport.wait_for_channel = AsyncMock(return_value=True)
        mock_factory.return_value = mock_transport

        cap = Capture(symbols=["CL"])
        await cap.connect()
        await cap.subscribe()
        
        mock_transport.subscribe.assert_called_once()
        assert cap._subscribed is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_capture.py::test_capture_subscribe -v
```
Expected: FAIL with "AttributeError: 'Capture' object has no attribute 'subscribe'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/dxtrade/capture.py (add to Capture class)

from .utils import resolve_account, resolve_symbol

async def subscribe(self, symbols: list[str] | None = None) -> None:
    """Start streaming quotes for symbols."""
    if not self.transport or not self.store:
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
                if isinstance(event, dict):
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_capture.py::test_capture_subscribe -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dxtrade/capture.py tests/test_capture.py
git commit -m "feat: add subscribe/unsubscribe methods to Capture"
```

---

### Task 4: Add trading methods to `Capture`

**Files:**
- Modify: `src/dxtrade/capture.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Consumes: `dxtrade.utils.open_position`, `close_position`, `flatten`
- Produces: `Capture.place_order()`, `close_position()`, `flatten()`, `get_positions()`, `get_orders()`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture.py
@pytest.mark.asyncio
async def test_capture_place_order():
    with patch("dxtrade.capture.open_position") as mock_open:
        mock_open.return_value = {"order": {"orderId": "123"}, "position": {"positionCode": "pos1"}}
        
        cap = Capture()
        cap.transport = AsyncMock()
        cap._account = "default:123"
        
        result = await cap.place_order("CL", "BUY", quantity=1.0)
        assert result["order"]["orderId"] == "123"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_capture.py::test_capture_place_order -v
```
Expected: FAIL with "AttributeError: 'Capture' object has no attribute 'place_order'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/dxtrade/capture.py (add to Capture class)

from .utils import open_position, close_position, flatten

async def place_order(
    self,
    symbol: str,
    side: str = "BUY",
    quantity: float | None = None,
    stop_loss: float | None = None,
    stop_loss_price: float | None = None,
) -> dict[str, Any]:
    """Open a market position with optional protective stop."""
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
    """Close a specific position."""
    if not self.transport or not self._account:
        raise RuntimeError("Call connect() first")
    
    return await close_position(
        self.transport,
        account=self._account,
        symbol=symbol,
        position_code=position_code,
    )

async def flatten(self) -> dict[str, Any]:
    """Close all positions and cancel working orders."""
    if not self.transport or not self._account:
        raise RuntimeError("Call connect() first")
    
    return await flatten(self.transport, account=self._account)

async def get_positions(self) -> list[dict[str, Any]]:
    """Get current open positions."""
    if not self.transport or not self._account:
        raise RuntimeError("Call connect() first")
    
    from .utils import as_list
    payload = await self.transport.get_account_positions(self._account)
    return as_list(payload, "positions")

async def get_orders(self) -> list[dict[str, Any]]:
    """Get current working orders."""
    if not self.transport or not self._account:
        raise RuntimeError("Call connect() first")
    
    from .utils import as_list
    payload = await self.transport.get_account_orders(self._account)
    return as_list(payload, "orders")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_capture.py -k "place_order or close_position or flatten" -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dxtrade/capture.py tests/test_capture.py
git commit -m "feat: add trading methods to Capture"
```

---

### Task 5: Add data access methods to `Capture`

**Files:**
- Modify: `src/dxtrade/capture.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Consumes: `QuoteStore` methods (from Task 1)
- Produces: `Capture.get_dataframe()`, `last_prices()`, `to_parquet()`, `to_csv()`, `append()`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture.py
def test_capture_data_access():
    import tempfile
    cap = Capture(data_dir=tempfile.gettempdir())
    cap.store = QuoteStore(tempfile.gettempdir())
    cap.store.append({"symbol": "CL", "bid": 75.5, "ask": 75.6, "type": "Quote", "time": "2026-08-14T12:00:00.000Z"})
    cap.store.flush()
    
    df = cap.get_dataframe()
    assert df.height == 1
    last = cap.last_prices()
    assert last.height == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_capture.py::test_capture_data_access -v
```
Expected: FAIL with "AttributeError: 'Capture' object has no attribute 'get_dataframe'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/dxtrade/capture.py (add to Capture class)

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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_capture.py::test_capture_data_access -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dxtrade/capture.py tests/test_capture.py
git commit -m "feat: add data access methods to Capture"
```

---

### Task 6: Export `Capture` from `src/dxtrade/__init__.py`

**Files:**
- Modify: `src/dxtrade/__init__.py`

**Interfaces:**
- Consumes: `Capture` class from `capture.py`
- Produces: Public API `from dxtrade import Capture`

- [ ] **Step 1: Read current `__init__.py`**

```bash
cat src/dxtrade/__init__.py
```

- [ ] **Step 2: Add `Capture` export**

```python
# src/dxtrade/__init__.py (add to existing exports)

from .capture import Capture, QuoteStore

__all__ = [
    "DXTradeTransport",
    "create_transport",
    "Capture",
    "QuoteStore",
    "__version__",
]
```

- [ ] **Step 3: Verify import works**

```bash
PYTHONPATH=src venv/Scripts/python.exe -c "from dxtrade import Capture; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/dxtrade/__init__.py
git commit -m "feat: export Capture from dxtrade package"
```

---

### Task 7: Create example script

**Files:**
- Create: `examples/capture_example.py`

**Interfaces:**
- Consumes: `Capture` class from `dxtrade`

- [ ] **Step 1: Write example script**

```python
#!/usr/bin/env python3
"""
Example: Using the Capture class for streaming and trading.

Usage:
    PYTHONPATH=src venv/Scripts/python.exe examples/capture_example.py
"""

import asyncio
from dxtrade import Capture

async def main():
    async with Capture(
        symbols=["CL", "NATGAS", "XAU", "XAG", "AAPL", "BABA", "AXTI", "AMD", "AMZN"],
        data_dir="data/quotes",
        write_parquet=True,
    ) as cap:
        await cap.subscribe()
        print("📡 Streaming quotes...")

        # Stream for 30 seconds
        await asyncio.sleep(30)

        # Query captured data
        print("\n🟦 Last prices:")
        print(cap.last_prices())

        # Save snapshot
        cap.to_parquet("data/quotes/snapshot.parquet")
        print("📦 Saved parquet snapshot")

        await cap.unsubscribe()
        print("⏹️  Done")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
```

- [ ] **Step 2: Test the example**

```bash
PYTHONPATH=src venv/Scripts/python.exe examples/capture_example.py
```
Expected: Runs for 30s, prints prices, saves parquet

- [ ] **Step 3: Commit**

```bash
git add examples/capture_example.py
git commit -m "feat: add capture_example.py demo script"
```

---

### Task 8: Update `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add Capture class to architecture section**

```markdown
### High-level utilities (`utils.py`)

Convenience wrappers over the transport layer for common flows — account discovery,
symbol resolution, streaming, and order lifecycle.

### Capture class (`capture.py`)

High-level class for streaming quotes and managing positions. Provides:
- `subscribe()` / `unsubscribe()` — control quote streaming
- `place_order()` / `close_position()` / `flatten()` — trading operations
- `get_dataframe()` / `last_prices()` / `to_parquet()` — data access
- Context manager support: `async with Capture(...) as cap:`

Usage:
```python
from dxtrade import Capture

async with Capture(symbols=["CL", "NATGAS"], data_dir="data/quotes") as cap:
    await cap.subscribe()
    await asyncio.sleep(60)
    print(cap.last_prices())
    cap.to_parquet("snapshot.parquet")
```
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: document Capture class in AGENTS.md"
```

---

### Task 9: Update `CHANGELOG.md`

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add Unreleased entry**

```markdown
## [Unreleased]

### Added
- `dxtrade.capture.Capture` class for high-level quote streaming and position management
- `dxtrade.capture.QuoteStore` for append-only CSV + Polars DataFrame capture
- `examples/capture_example.py` demo script
- `capture` optional dependency (`pip install -e ".[capture]"`) for Polars support
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add Capture class to CHANGELOG.md"
```

---

### Task 10: Final verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/test_capture.py -v
```
Expected: All tests pass

- [ ] **Step 2: Run lint**

```bash
ruff check src/dxtrade/capture.py tests/test_capture.py
black --check src/dxtrade/capture.py tests/test_capture.py
mypy src/dxtrade/capture.py
```
Expected: All pass

- [ ] **Step 3: Verify import**

```bash
PYTHONPATH=src venv/Scripts/python.exe -c "from dxtrade import Capture; cap = Capture(); print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Final commit (if needed)**

```bash
git add .
git commit -m "chore: final cleanup for Capture class"
```

---

## Self-Review

**1. Spec coverage:** All requirements from the design doc are covered:
- ✅ `Capture` class with lifecycle methods
- ✅ Streaming methods (`subscribe`, `unsubscribe`)
- ✅ Trading methods (`place_order`, `close_position`, `flatten`, `get_positions`, `get_orders`)
- ✅ Data access methods (`get_dataframe`, `last_prices`, `to_parquet`, `to_csv`, `append`)
- ✅ Export from `__init__.py`
- ✅ Example script
- ✅ Documentation updates
- ✅ Unit tests

**2. Placeholder scan:** No TBD/TODO patterns found. All steps have complete code.

**3. Type consistency:** All method signatures match across tasks. `Capture` class methods use consistent naming.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-14-capture-class-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
