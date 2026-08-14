# AGENTS.md

Guidance for AI coding agents working in this repository. Read this before making changes.

## Project Overview

`dxtrade-sdk` is a Python SDK for the **DXTrade** trading platform (a white-label multi-asset broker platform used by many brokers). It is an unofficial SDK with two layers:

- **Transport layer** — `dxtrade.transport.DXTradeTransport` (factory: `create_transport()`). A minimal, raw-data-passthrough client designed for building bridges and middleware (RabbitMQ, Kafka, Redis). It handles session-token authentication, raw REST requests with auth headers, multi-channel WebSocket subscriptions with raw message forwarding, and automatic application-level ping/pong session extension. No data modeling — returns raw JSON.
- **High-level SDK layer** — `dxtrade.client.DXTradeClient` (factories: `create_client`, `create_demo_client`, `create_live_client`), typed REST modules (`dxtrade.rest`), WebSocket stream managers (`dxtrade.websocket`), and Pydantic type models (`dxtrade.types`, `dxtrade.models`). This layer mirrors the structure of the official TypeScript SDK.

The project is **platform-agnostic**: it works with any DXTrade broker purely through environment configuration (`DXTRADE_*` variables), with no broker-specific code hardcoded.

- Python `>=3.10`, fully async (`asyncio`), MIT licensed.
- Version `1.0.0` (matches `__version__` in `src/dxtrade/__init__.py` and `pyproject.toml`).
- Package name on PyPI: `dxtrade-sdk`. Public entry points are `dxtrade.create_transport`, `dxtrade.DXTradeTransport`, and `dxtrade.__version__` (see `src/dxtrade/__init__.py`).

## Repository Layout

```
pyproject.toml            # Build (hatchling), lint, type-check, test config
setup.py                  # Backwards-compat shim; real config lives in pyproject.toml
README.md                 # Primary documentation (usage, config, publishing)
CHANGELOG.md              # Keep a Changelog + SemVer
LICENSE                   # MIT
MANIFEST.in               # sdist include rules
.env.example              # Template for broker credentials / config (.env is gitignored)
.github/workflows/ci.yml  # CI: test matrix, lint, mypy, security, docs

src/dxtrade/
  __init__.py             # Public API surface (transport only)
  transport.py            # DXTradeTransport — raw REST + WebSocket passthrough (primary layer)
  auth.py                 # Auth handlers: BearerTokenHandler, HMACHandler, SessionHandler, AuthFactory
  utils.py                # High-level helpers on the transport: stream_quotes, open/close_position, flatten
  models.py               # Pydantic models (credentials, accounts, orders, positions, events)
  errors.py               # DXtrade* exception hierarchy
  config.py               # Dataclass-based SDKConfig + sub-configs (Endpoints, WebSocketConfig, ...)
  env_config.py           # Load SDKConfig from DXTRADE_* environment variables
  client.py               # DXTradeClient + factory functions
  core/http_client.py     # aiohttp-based HTTPClient (rate limiting, retries)
  rest/                   # AccountsAPI, OrdersAPI, PositionsAPI, InstrumentsAPI
  websocket/              # DXTradeStreamManager, UnifiedWebSocketStream (dual-connection)
  types/                  # Pydantic type models mirroring the TypeScript SDK
    common.py             # Environment, auth configs, SDKConfig, ApiResponse, ...
    trading.py            # Account, Instrument, Order, Position, Quote, ...
    websocket.py          # Generic WS message models and callbacks
    dxtrade_messages.py   # DXTrade-specific WS messages (Ping, MarketData, ...)

examples/
  stream_market_data.py   # Authenticate + stream quotes via transport layer
  stream_quotes.py        # Stream quotes via dxtrade.utils.stream_quotes (--symbols/--duration)
  trade_smoke.py          # Open/close a small position via utils (--stop-loss, --dry-run)
  bridge_example.py       # Bridge pattern: forward WS data to a message queue
  README.md               # Example docs

tests/
  conftest.py             # Fixtures (credentials, models, httpx mocks)
  test_auth.py            # Auth handler unit tests (bearer, HMAC, session, factory)
```

There is no `docs/` directory yet, although `pyproject.toml`, `MANIFEST.in`, and CI reference one (`docs/` sdist include, `mkdocs build` step, `docs/MIGRATION.md` in `CHANGELOG.md`). Do not assume it exists.

## Two Configuration Systems

The codebase contains **two parallel, incompatible config systems** — keep this in mind before touching either:

1. **Dataclass-based** (`config.py` + `env_config.py`) — `SDKConfig` (alias `DXTradeConfig`) with `AuthConfig`, `Features`, `Endpoints`, `WebSocketConfig`, `RateLimitConfig`, `RetryConfig`. Loaded from environment via `load_config_from_env()`. **This is what the transport layer uses.**
2. **Pydantic-based** (`types/common.py`) — pydantic `SDKConfig` with `AuthConfig` as a Union of `SessionAuth` / `BearerAuth` / `HmacAuth` / `CredentialsAuth`, plus `RateLimitConfig`, `FeaturesConfig`, `URLsConfig`, `EndpointsConfig`, `WebSocketConfig`. **This is what the high-level SDK layer (`client.py`, `core/`, `rest/`, `websocket/`) uses.**

The two `AuthConfig`, `SDKConfig`, and `WebSocketConfig` names are different classes with different shapes — do not assume you can pass one where the other is expected. The high-level layer also expects auth as a Pydantic model with a `type` field (`"session"`, `"bearer"`, `"hmac"`, `"credentials"`), while the dataclass layer uses the `AuthType` enum defined in `config.py` (a third, separate `AuthType` enum also exists in `models.py` with values `bearer_token`/`hmac`/`session`).

## Environment Configuration

Configuration comes from a `.env` file (loaded via `python-dotenv` by the transport) or environment variables. All variables use the `DXTRADE_` prefix. See `.env.example` for the full annotated template.

Key variables:

| Variable | Purpose |
|---|---|
| `DXTRADE_USERNAME`, `DXTRADE_PASSWORD`, `DXTRADE_DOMAIN` | Credentials auth (domain defaults to `default`) |
| `DXTRADE_SESSION_TOKEN` | Session-token auth (alternative to credentials) |
| `DXTRADE_BEARER_TOKEN` / `DXTRADE_API_KEY` + `DXTRADE_API_SECRET` | Bearer / HMAC auth |
| `DXTRADE_BASE_URL` | REST base URL, e.g. `https://your-broker.com/dxsca-web` |
| `DXTRADE_WS_MARKET_DATA_URL` | Market data WS URL, e.g. `wss://.../dxsca-web/md?format=JSON` |
| `DXTRADE_WS_PORTFOLIO_URL` | Portfolio/account WS URL |
| `DXTRADE_ACCOUNT` | Account ID, e.g. `default:demo`; falls back to `default:<DXTRADE_ACCOUNT_NAME>` |
| `DXTRADE_TIMEOUT` | Request timeout (default 30 s) |
| `DXTRADE_WS_PING_INTERVAL`, `DXTRADE_WS_RECONNECT_ATTEMPTS`, `DXTRADE_WS_RECONNECT_DELAY` | WebSocket tuning |
| `DXTRADE_LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `DXTRADE_ENDPOINT_*`, `DXTRADE_WS_*`, `DXTRADE_RATE_LIMIT_*`, `DXTRADE_RETRY_*`, `DXTRADE_FEATURE_*` | Endpoint paths, WS paths/format, rate limiting, retry, feature flags |

`env_config.py` documents every supported variable in its `load_config_from_env()` docstring. Note a quirk: `DXTRADE_WS_MARKET_DATA_URL`/`DXTRADE_WS_PORTFOLIO_URL` are used by the transport layer, while `env_config.py` itself reads `DXTRADE_WS_URL` + `DXTRADE_WS_MARKET_DATA_PATH`/`DXTRADE_WS_PORTFOLIO_PATH` — the transport's `subscribe()` uses the explicit URL variables when present.

## Build and Test Commands

Development environment:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

Tests (pytest — config in `[tool.pytest.ini_options]`):

```bash
pytest                          # runs tests/, asyncio_mode=auto
pytest tests/test_auth.py       # single file
pytest --cov=dxtrade            # coverage report (term-missing)
```

`pyproject.toml` sets coverage enforcement: `--cov=dxtrade`, `--cov-fail-under=90` (branch coverage on `src`). **Warning:** in the current tree the 24 tests pass, but total coverage is only ~16%, so a bare `pytest` exits with code 1 (coverage gate fails). See "Known Issues" below.

Code quality (all configured in `pyproject.toml`, all run in CI):

```bash
ruff check src tests            # lint (E/W/F/I/B/C4/UP/RUF; E501, B008, C901 ignored)
black --check src tests         # formatting (line-length 88)
mypy src                        # strict typing
```

Fix formatting with `black src tests` and auto-fix lint with `ruff check src tests --fix`.

Build and publish (from README):

```bash
python -m build                 # build sdist + wheel
python -m twine upload --repository testpypi dist/*   # test first
python -m twine upload dist/*                         # then publish
```

Bump the version in **both** `pyproject.toml` and `src/dxtrade/__init__.py`, and add a `CHANGELOG.md` entry. Follow SemVer.

## Testing Strategy

- **Test framework:** pytest with `pytest-asyncio` in `asyncio_mode = "auto"` (async tests need no explicit marker). Markers registered: `unit`, `integration`, `slow` (there are currently no integration/slow tests).
- **Current coverage:** only `tests/test_auth.py` exists (auth handler unit tests). Tests mock `httpx.AsyncClient`/`httpx.Request` via `unittest.mock` fixtures in `tests/conftest.py` — they never touch the network. Verified state: **24 tests, all passing**, but ~16% total coverage, so the configured `--cov-fail-under=90` gate fails (pytest exit code 1). Raising coverage to ≥90% is open work, not done work.
- **Pattern to follow:** per-class test classes (`TestBearerTokenHandler`, `TestSessionHandler`, ...), fixtures in `conftest.py`, descriptive test names (`test_authenticate_login_failure`), and assertions on both behavior and call arguments (`client.post.assert_called_once_with(...)`).
- `tests/conftest.py` requires `httpx` at import time, and `tests/test_auth.py` imports `dxtrade.auth`, which imports `httpx` and `dxtrade.models` — the test suite depends on the `dxtrade` package being importable.

## Code Style Guidelines

- **Line length 88** (black default; ruff `E501` ignored because black handles it). Black-formatted, ruff-linted (see config above).
- **Strict typing:** mypy runs in `strict` mode on `src` (`disallow_untyped_defs`, `warn_return_any`, `no_implicit_optional`, `extra_checks`, ...). Tests are exempt from `disallow_untyped_defs`. All public functions are fully typed.
- **Type hints:** modern syntax (`Optional[str]`, `Dict[str, Any]` from `typing`; `str | None` is *not* used). Pydantic models use `Field(..., description=...)` everywhere.
- **Docstrings:** Google-style with `Args:` / `Returns:` / `Raises:` sections on every public class/method.
- **Logging:** use `logging.getLogger(__name__)` per module, and `logger.info/debug/warning/error` — not `print` (a few `print` calls remain in `websocket/stream_manager.py`; do not extend that pattern).
- **Emoji in log/print messages:** the codebase liberally uses emoji in user-facing log lines and example output (e.g. `✅`, `❌`, `🔌`, `📡`, `📤`, `🔄`, `📈`). Match this convention in new transport/example code.
- **Enum conventions:** `models.py` uses lowercase enum values (`"buy"`, `"market"`, `"open"`); `types/trading.py` uses uppercase (`"BUY"`, `"MARKET"`). `types/common.py` `Environment` uses lowercase (`"demo"`/`"live"`). Match the file you are editing.
- **Secrets hygiene:** credentials models use `repr=False` on secret fields (`HMACCredentials.secret_key`, `SessionCredentials.password`); `SDKConfig.to_dict()` deliberately omits sensitive auth fields. Do not log tokens or passwords.

## Architecture Notes

### Transport layer (`transport.py`) — the working, documented core

- `DXTradeTransport.authenticate()` POSTs `{"username", "password", "domain"}` to the login endpoint and stores `sessionToken` (expires after 1 hour, refreshed lazily on 401).
- REST: `request(method, endpoint, ...)` attaches the auth handler's headers (for session auth: both `X-Auth-Token` and `Authorization: DXAPI <token>`), parses JSON or text, and auto-refreshes the token once on 401. Spec-aligned helpers exist for the official DXTrade REST API: `get_users`, `get_account_metrics`, `get_account_portfolio`, `get_account_positions`, `get_account_orders`, `get_account_orders_history`, `query_instruments`, `get_market_data`, `ping`, `logout`.
- WebSocket: `subscribe(channel, callback, ws_url)` opens a connection per channel ("quotes"/"market_data" → market data URL, everything else → portfolio URL) and forwards raw parsed messages to the callback. `wait_for_channel(channel, timeout)` waits until the background connection is established. When `ws_url` is omitted the URL comes from the config (`DXTRADE_WS_MARKET_DATA_URL` / `DXTRADE_WS_PORTFOLIO_URL`, else constructed from the base URL as `/md` and `/` — no `/ws` segment).
- **4-tier connection fallback** for `websockets` library compatibility: `additional_headers` (v12+) → `extra_headers` (v9–10) → subprotocol auth → post-connection auth message. Tracked per channel in `get_connection_strategies()`.
- **Application-level ping/pong:** server sends `{"type": "PingRequest"}`; the transport replies `{"type": "Ping", "session": <token>, "timestamp": <ISO ms>}` and *does not* forward ping messages to user callbacks. Stats via `get_ping_stats()` / `get_session_health()`.
- Subscription messages (sent by `send_market_data_subscription` / `send_portfolio_subscription`) use DXTrade's protocol: `MarketDataSubscriptionRequest` (payload: `account`, `symbols`, `eventTypes: [{"type": "Quote", "format": "COMPACT"}]`) and `AccountPortfoliosSubscriptionRequest` (payload: `requestType: "LIST"`, `accounts: [...]`), each with a `requestId`, `timestamp`, and `session`.
- Incoming data shapes: `{"type": "MarketData", "payload": {"events": [{"symbol", "bid", "ask", "timestamp"}]}}` and `{"type": "AccountPortfolios", "payload": {...}}`.

### Authentication (`auth.py`)

- `AuthHandler` ABC with `authenticate(request, client)` and `get_auth_headers()` (transport-agnostic header builder); implementations: `BearerTokenHandler`, `HMACHandler` (signs `timestamp + method + path + body [+ passphrase]` with HMAC-SHA256, headers `DX-API-KEY`, `DX-API-TIMESTAMP`, `DX-API-SIGNATURE`, `DX-API-PASSPHRASE`), `SessionHandler` (sends **both** `X-Auth-Token` and `Authorization: DXAPI <token>` headers; token auto-refresh, 1 h expiry with 5 min buffer, `logout()`).
- The transport layer builds request/WS headers through `auth_handler.get_auth_headers()`, so each broker's auth scheme (header names, token formats) lives in its handler rather than being hardcoded in the transport.
- `AuthFactory.create_handler(auth_type, credentials)` with `register_handler` for custom handlers. `AuthType` enum lives in `models.py` (`bearer_token`/`hmac`/`session`).

### High-level utilities (`utils.py`)

Convenience wrappers over the transport for the common flows — account discovery,
symbol resolution, streaming, and order lifecycle. All helpers work with any
DXTrade broker:

- `resolve_account(transport)` / `find_account_code(users)` — authenticate on
  demand and extract the account code (`default:12345`) from `/users`.
- `resolve_symbol(transport, account, hint)` — resolve user hints to platform
  symbols (e.g. `BTCUSDT` → `BTCUSD`); `discover_symbols()` returns a few
  tradable symbols.
- `stream_quotes(transport, symbols, duration, on_quote)` — subscribe, collect
  quote events for a duration, unsubscribe; returns the events list.
- `open_position(transport, symbol, side, quantity, stop_loss, stop_loss_price,
  account)` — market order with optional protective stop. `stop_loss` is a max
  loss in account currency (converted to a price from the quote);
  `stop_loss_price` is an absolute price. The protective stop is placed as a
  closing STOP order **without a quantity** (the DXTrade API rejects closing
  STOP/LIMIT orders that carry one — `errorCode 33`).
- `close_position(transport, symbol, position_code, account)` — market close of
  exactly one matching position; `flatten(transport)` closes everything and
  cancels working orders; `account_is_flat(transport)` checks
  `openPositionsCount`/`openOrdersCount` via `/metrics`.
- `order_code(prefix)` — unique client order codes (required per account).

Note: closing orders and the utils' stop placement omit `quantity` (full close).
Protective stops auto-cancel on the platform when their position closes.

### High-level SDK layer (broken in the current tree — see Known Issues)

`client.py`, `core/`, `rest/`, `websocket/` implement the typed client: `DXTradeClient` exposes `accounts`/`orders`/`positions`/`instruments` REST modules and `create_stream` / `start_stream` / `create_unified_stream` WebSocket entry points. The WebSocket managers (`websocket/stream_manager.py`) implement the dual-connection (market data + portfolio) architecture from the TypeScript SDK, with auto-reconnect, ping/pong, and a `run_stability_test()`.

## Known Issues (as of the current tree)

Verified against a fresh venv with runtime deps installed (import checks, `pytest`, `ruff`, `black --check`, `mypy` all executed on this tree) — treat the high-level layer with caution:

- **The high-level SDK layer does not import cleanly.** Several modules reference names that do not exist, which raises `ImportError` at import time (confirmed):
  - `client.py` imports `ConfigError` from `dxtrade.errors` (only `DXtradeConfigurationError` exists) and references an undefined `HttpClient`.
  - `rest/*.py` and `core/http_client.py` fail at import: `core/http_client.py` imports `CredentialsAuth`, `HTTPMethod`, `ApiResponse` from `dxtrade.config` (those live in `types/common.py`, not `config.py`) and calls `config.rate_limit.window`, which the dataclass `RateLimitConfig` does not define.
  - `websocket/*.py` import `WebSocketError` from `dxtrade.errors` (exists only as `DXtradeWebSocketError`).
  - `core/__init__.py` imports `WebSocketClient` from `core/websocket_client.py`, which does not exist.
  - Consequence: `import dxtrade` works (transport layer only), but `import dxtrade.client` / `dxtrade.rest.*` / `dxtrade.websocket.*` / `dxtrade.core` all raise `ImportError`.
- **Undeclared dependency:** `auth.py` imports `httpx` — now declared in `pyproject.toml` dependencies (fixed in Unreleased).
- **All quality gates are currently red** (measured on this tree):
  - `pytest`: 24 tests pass, but coverage is 15.9% vs the required 90% → exit code 1.
  - `ruff check src tests`: 1591 errors (1329 auto-fixable) — most are formatting (the tree was not run through `black`).
  - `black --check src tests`: 25 files would be reformatted.
  - `mypy src`: 272 errors in 16 files (strict mode), e.g. untyped functions in `client.py` and `str` vs `Environment` mismatches.
  - Consequently CI (`.github/workflows/ci.yml` runs all four) would fail on the current tree.
- **Two `AuthConfig`/`SDKConfig`/`WebSocketConfig` definitions** (dataclass vs pydantic) — see "Two Configuration Systems" above.
- `docs/` is referenced by build/CI but absent.
- The public `__init__.py` deliberately exports only the transport layer — `DXTradeClient` is documented in README/CHANGELOG but not exported from `dxtrade` (the README Quick Start also uses `from dxtrade import create_transport`).

When fixing these: prefer the transport layer's working patterns, add `httpx` to `pyproject.toml` dependencies, and consolidate the two config systems rather than adding a third.

## Security Considerations

- **Never commit credentials.** `.env` is gitignored; only commit the `.env.example` template. Credentials go in environment variables, never hardcoded.
- Session tokens and passwords are marked `repr=False` in Pydantic models — keep it that way. Do not log tokens, headers, or request bodies containing credentials.
- The SDK sends session tokens in both `X-Auth-Token` and `Authorization` headers — both are required by the DXTrade API; do not "simplify" this.
- CI runs `bandit -r src/` and `safety check` (results uploaded as artifacts; failures are non-fatal via `|| true`).
- HMAC signing includes method, path, query, body, and optional passphrase; timestamps prevent replay.
- Trading involves real money — the transport forwards raw data untouched and never fabricates messages; keep it that way.

## Conventions Summary

- Follow the existing per-module conventions; match the style of the file you edit (black + ruff + mypy strict are enforced in CI).
- English (US) for all comments, docstrings, and docs.
- Keep the transport layer minimal and raw — that is its stated design goal ("~200 lines vs 2000+ for full SDK").
- When changing message formats or env vars, update `.env.example`, `README.md`, and `CHANGELOG.md` (SemVer + Keep a Changelog).
