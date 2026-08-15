# Capture Class Design

**Date:** 2026-08-14  
**Author:** AI Agent  
**Status:** Approved

## Overview

A single, easy-to-use class that wraps the DXTrade transport layer and provides high-level methods for:
- Subscribing/unsubscribing to quotes
- Placing orders, closing positions, flattening
- Storing streaming data to long-term storage (CSV) and a queryable structure (Polars DataFrame)
- Easy query methods on the captured data

**Goal:** Make it stupidly simple to manage positions and get data. Users should be able to instantiate one class and call methods without juggling transport + store + helpers separately.

## Architecture

### Class Structure

```
src/dxtrade/capture.py
└── class Capture
    ├── Internal: DXTradeTransport (created internally)
    ├── Internal: QuoteStore (refactored from stream_quotes_store.py)
    └── Public methods (below)
```

### Dependencies

- Reuses `dxtrade.transport.DXTradeTransport` for connectivity
- Reuses `dxtrade.utils` helpers (`open_position`, `close_position`, `flatten`, `resolve_account`, `resolve_symbol`)
- Lazy Polars import (only when data methods are called)
- Optional dependency: `polars>=1.0` (installed via `pip install -e ".[capture]"`)

## Public API

### Constructor

```python
def __init__(
    self,
    symbols: list[str] | None = None,
    data_dir: str = "data/quotes",
    write_parquet: bool = False,
    config: Any | None = None,
)
```

- `symbols`: Symbol hints to stream (e.g. `["CL", "NATGAS", "XAU"]`). Resolved to platform symbols on `subscribe()`.
- `data_dir`: Directory for CSV files (created if missing).
- `write_parquet`: Also write a parquet snapshot on `close()`.
- `config`: Optional SDK config (loads from env if None).

### Lifecycle Methods

```python
async def connect(self) -> None
async def close(self) -> None
async def __aenter__(self) -> "Capture"
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

- `connect()`: Authenticate and prepare transport.
- `close()`: Unsubscribe, flush data, close transport.
- Context manager support: `async with Capture(...) as cap:`

### Streaming Methods

```python
async def subscribe(self, symbols: list[str] | None = None) -> None
async def unsubscribe(self) -> None
```

- `subscribe()`: Start streaming quotes for symbols (constructor symbols if None). Resolves symbol hints, subscribes to transport, starts capture loop.
- `unsubscribe()`: Stop streaming.

### Trading Methods

```python
async def place_order(
    self,
    symbol: str,
    side: str = "BUY",
    quantity: float | None = None,
    stop_loss: float | None = None,
    stop_loss_price: float | None = None,
) -> dict[str, Any]

async def close_position(
    self,
    symbol: str | None = None,
    position_code: str | None = None,
) -> dict[str, Any]

async def flatten(self) -> dict[str, Any]

async def get_positions(self) -> list[dict[str, Any]]

async def get_orders(self) -> list[dict[str, Any]]
```

- All delegate to `dxtrade.utils` helpers with the internal transport.
- `place_order()`: Open a market position with optional protective stop.
- `close_position()`: Close a specific position.
- `flatten()`: Close all positions and cancel working orders.
- `get_positions()` / `get_orders()`: Fetch current state.

### Data Access Methods

```python
def get_dataframe(self) -> pl.DataFrame
def last_prices(self) -> pl.DataFrame
def to_parquet(self, path: Path | str) -> None
def to_csv(self, path: Path | str) -> None
def append(self, event: dict[str, Any]) -> None  # manual capture
```

- `get_dataframe()`: Return the full captured DataFrame (lazy Polars import).
- `last_prices()`: Last bid/ask per symbol.
- `to_parquet()` / `to_csv()`: Write to a specific path.
- `append()`: Manually record a quote event (for custom callbacks).

## Data Flow

1. **On `subscribe()`:**
   - Resolve symbol hints to platform symbols via `utils.resolve_symbol()`
   - Call `transport.subscribe("quotes", callback)`
   - Callback captures events → internal `QuoteStore`

2. **During streaming:**
   - Events appended to pending list
   - Flush every 2 seconds to CSV + Polars DataFrame

3. **On `close()` / `unsubscribe()`:**
   - Final flush
   - Optionally write parquet snapshot
   - Close transport

## Error Handling

- Transport errors (auth failure, connection loss): raise as-is; user handles reconnection.
- Polars not installed: `ImportError` with helpful message ("install with `pip install -e '.[capture]'`").
- Symbol resolution failure: `ValueError` with the unresolved hint.
- Trading errors: delegate to `utils` helpers (they raise `RuntimeError` / `ValueError`).

## Testing

Unit tests (mock transport):
- Subscribe/unsubscribe lifecycle
- Data ingestion → CSV + Polars frame
- `last_prices()` aggregation
- Order placement delegation

Integration tests (live Velotrade):
- Stream 9 symbols for 30s → verify CSV + parquet
- Open/close small position → verify journal

## Usage Example

```python
from dxtrade import Capture

async with Capture(
    symbols=["CL", "NATGAS", "XAU", "XAG", "AAPL", "BABA", "AXTI", "AMD", "AMZN"],
    data_dir="data/quotes",
    write_parquet=True,
) as cap:
    await cap.subscribe()
    
    # Stream for 60 seconds
    await asyncio.sleep(60)
    
    # Query data
    print(cap.last_prices())
    cap.to_parquet("snapshot.parquet")
    
    # Trade
    order = await cap.place_order("BTCUSD", "BUY", quantity=0.01, stop_loss=10.0)
    await cap.close_position(position_code=order["position"]["positionCode"])
    
    await cap.unsubscribe()
```

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `src/dxtrade/capture.py` | Create | Main `Capture` class + internal `QuoteStore` |
| `src/dxtrade/__init__.py` | Edit | Export `Capture` |
| `examples/capture_example.py` | Create | Demo script |
| `pyproject.toml` | No change | `capture` extra already exists |
| `AGENTS.md` | Edit | Document the `Capture` class |
| `CHANGELOG.md` | Edit | Note the new class |
| `tests/test_capture.py` | Create | Unit tests |

## Out of Scope

- Multi-account management (single account per instance)
- Advanced order types (limit, stop-limit — use transport directly)
- Real-time analytics (DataFrame is for post-hoc queries)
- Database storage (CSV + parquet only; user can load into DB later)
