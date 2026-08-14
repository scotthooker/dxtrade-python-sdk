# Velotrade Integration Test Results

Live results from testing `dxtrade-python-sdk` against **Velotrade's DXtrade
platform** (`dx.velotrade.com`). Test date: **2026-08-14**.

**Summary: 60/60 tests pass** — 52 offline (mocked) + 8 live (real Velotrade
account). All live tests were read-only and left the account flat.

---

## 1. Test suite layout

| File | Tests | Kind |
|---|---|---|
| `tests/test_auth.py` | 29 | Offline unit — auth handlers incl. new `get_auth_headers()` |
| `tests/test_transport.py` | 25 | Offline unit — REST methods, order placement/cancel, subscription shapes, ping/pong, `send_message` |
| `tests/test_utils.py` | 19 | Offline unit — high-level utils: streaming, open/close position, flatten, symbol/account resolution |
| `tests/test_velotrade_live.py` | 4 | Live — login, authenticated REST, full users→instruments flow, ping/logout |
| `tests/test_velotrade_ws_live.py` | 4 | Live — Push API: quotes stream, portfolio snapshot, legacy-payload rejection, ping stats |
| **Total** | **81** | |

Run everything (offline + live, requires broker `.env`):

```bash
venv/Scripts/python.exe -m pytest tests/ -q --no-cov
```

Live tests are skipped automatically when `.env` with `DXTRADE_USERNAME` is
absent, so CI stays hermetic.

---

## 2. Live test results (Velotrade)

### 2.1 REST — `tests/test_velotrade_live.py` ✅ 4/4

| Test | Result | Evidence |
|---|---|---|
| `test_authenticate_returns_session_token` | ✅ PASS | `POST /dxsca-web/login` → `sessionToken` returned |
| `test_authenticated_request_uses_token` | ✅ PASS | `GET /dxsca-web/users` → 200 with `Authorization: DXAPI <token>` |
| `test_full_flow_users_and_instruments` | ✅ PASS | login → `/users` → account `default:130000606` → account-scoped instruments query |
| `test_ping_and_logout` | ✅ PASS | `POST /ping` OK; `POST /logout` OK; local token cleared |

### 2.2 Push API (WebSocket) — `tests/test_velotrade_ws_live.py` ✅ 4/4

| Test | Result | Evidence |
|---|---|---|
| `test_market_data_subscription_streams_quotes` | ✅ PASS | Real-time `MarketData` events with `bid`/`ask` for requested symbols |
| `test_portfolio_subscription_receives_snapshot` | ✅ PASS | `AccountPortfolios` snapshot received with `payload.portfolios` |
| `test_portfolio_legacy_payload_rejected` | ✅ PASS | Old SDK payload shape → server **rejects** (see §3.2) |
| `test_ping_stats_tracked_on_active_channels` | ✅ PASS | Stats structures present; session health 1.0 |

---

## 3. Real message bodies captured from Velotrade

Captured with `tests/_diag_push.py` (diagnostic; not a pytest test).

### 3.1 Login & discovery

```
POST /dxsca-web/login  {username, password, domain:"default"}  ->  {sessionToken: "<redacted>"}
GET  /dxsca-web/users  ->  account code: default:130000606
GET  /dxsca-web/accounts/default%3A130000606/instruments/query?limit=100
     ->  symbols: ['AAOI', 'AAPL', 'AAVEUSD', 'ADAUSD', 'ADBE', 'AEROUSD', 'ALGOUSD', 'AMAT', ...]
```

### 3.2 Portfolio subscription — before/after the payload fix (gap G5)

Legacy SDK payload (rejected):

```json
{"type":"AccountPortfoliosSubscriptionRequest","requestId":"diag-legacy","session":"…",
 "payload":{"account":"default:130000606","eventTypes":[{"type":"Position","format":"COMPACT"}]}}
```

Server reply:

```json
{"type":"Reject","inReplyTo":"diag-legacy","session":"…",
 "payload":{"errorCode":"32","description":"Incorrect request parameters: <accounts>"}}
```

Spec payload (accepted — what the SDK sends now):

```json
{"type":"AccountPortfoliosSubscriptionRequest","requestId":"…","timestamp":"…","session":"…",
 "payload":{"requestType":"LIST","accounts":["default:130000606"]}}
```

Server reply:

```json
{"type":"AccountPortfolios","inReplyTo":"…","session":"…","timestamp":"…",
 "payload":{"portfolios":[{"account":"default:130000606","version":18,
   "balances":[{"account":"default:130000606","version":18,"value":5000.0,"currency":"USD"}],
   "positions":[],"orders":[],"owner":{"login":"3807193346…"}}]}}
```

### 3.3 Market data stream

```json
{"type":"MarketData","inReplyTo":"…","session":"…","timestamp":"2026-08-14T19:30:35.300Z",
 "payload":{"events":[
   {"symbol":"AAVEUSD","type":"Quote","ask":85.91,"bid":85.89,"time":"2026-08-14T19:30:35Z"},
   {"symbol":"ADBE","type":"Quote","ask":265.59,"bid":264.67,"time":"2026-08-14T19:30:35Z"},
   {"symbol":"ADAUSD","type":"Quote","ask":0.17897,"bid":0.17896,"time":"2026-08-14T19:30:35Z"}]}}
```

### 3.4 Ping/pong & session health (observed over a longer session)

```
ping stats (quotes):  {"ping_requests_received": 2, "ping_responses_sent": 2,
                       "session_extensions": 2, ...}
session health:       {"active_channels": 2, "healthy_channels": 2, "session_health": 1.0,
                       "ping_response_success_rate": 1.0,
                       "connection_strategies": {"portfolio": "additional_headers",
                                                 "quotes": "additional_headers"},
                       "websockets_version": "17.0.1"}
```

The SDK's automatic `Ping` reply to the server's `PingRequest` works live, and
both sockets connected via the `additional_headers` strategy.

### 3.5 Explicit subscription close (Push spec)

```json
{"type":"AccountPortfoliosCloseSubscriptionRequest","requestId":"diag-close",
 "refRequestId":"<original requestId>","session":"…","timestamp":"…"}
```

Server reply:

```json
{"type":"AccountPortfoliosSubscriptionClosed","inReplyTo":"diag-close","session":"…","timestamp":"…"}
```

---

## 4. SDK changes made to pass these tests

All changes are broker-agnostic — they follow the official DXTrade API
specifications (REST OpenAPI + Push API), which any DXTrade broker shares.

| Change | File(s) | Why |
|---|---|---|
| `get_auth_headers()` on all auth handlers; transport builds headers through the handler | `auth.py`, `transport.py` | Velotrade requires `Authorization: DXAPI <token>`; SDK only sent `X-Auth-Token` → 401 on `/users` |
| New REST methods: `get_users`, `get_account_metrics/portfolio/positions/orders/orders_history`, `query_instruments`, `get_market_data`, `ping`, `logout`, `_encode_account` | `transport.py` | SDK's old convenience methods hit non-existent paths (`/orders`, `/positions`, `/time`…) → 404 |
| Portfolio subscription payload → `{requestType:"LIST", accounts:[…]}` | `transport.py` | Old payload rejected by server: `errorCode 32 <accounts>` |
| `timestamp` added to all Push subscription messages | `transport.py` | Required by the Push API message envelope |
| `send_message()` no longer calls `recv()` | `transport.py` | `recv` collided with the background handler → `websockets.ConcurrencyError` |
| Ping stats stored via `setdefault` | `transport.py` | Counters were dropped before the channel's stats dict existed |
| `env_config.py` reads `DXTRADE_WS_MARKET_DATA_URL` / `DXTRADE_WS_PORTFOLIO_URL` | `env_config.py` | Documented vars were never loaded; `subscribe()` without explicit URL failed |
| `httpx` declared in `pyproject.toml` | `pyproject.toml` | Imported by `auth.py` but undeclared |

---

## 5. Live trade execution (2026-08-14, account `default:130000606`)

### 6.1 Intended trade — BTCUSD buy + $10 stop loss, closed after 30 s

| Step | Order | Details |
|---|---|---|
| Open | 2980544 MARKET BUY | 0.001 BTCUSD @ 62,956.7 (platform min, ~$63 notional) |
| Stop | 2980550 STOP SELL | protective stop @ 52,956.7 (= entry − 10,000 pts = $10 loss on 0.001 BTC) |
| Hold | — | 30 seconds |
| Close | 2980555 MARKET SELL | full close; position gone, `openOrdersCount=0` |

Net result: **flat**, equity $4,999.77, session PnL −$0.03 (spread only).

### 6.2 Findings from the trade run

- **Symbol naming**: Velotrade uses `BTCUSD` (crypto/FOREX type, min order
  0.001, margin rate 0.1667); `BTCUSDT` is not a valid symbol. The utils'
  `resolve_symbol()` handles `BTCUSDT` → `BTCUSD` automatically.
- **Closing STOP/LIMIT orders must NOT carry a quantity** — the server rejects
  them with `errorCode 33 "Incorrect request. Closing STOP/LIMIT orders should
  not have specified quantity"`. The protective stop is placed without
  `quantity` (full close).
- **Protective stops auto-cancel** when their parent position closes — no
  orphaned working orders remain (confirmed via `/orders` + `openOrdersCount`).
- **Working-order detection**: the orders list does not reliably echo the stop's
  `orderCode`; `metrics.openOrdersCount` is the reliable signal (the utils'
  `account_is_flat()` uses it).
- **Order/position codes** on this deployment are numeric strings (e.g.
  `2980544`); `positionCode` from `/positions` is used directly in closing and
  stop orders.
- **`/orders` history** uses `orderCode` prefixed with
  `dxsca-integration-session-code:` — client codes remain unique per account.

### 6.3 Diagnostic scripts

- `tests/_diag_trade.py` — the full open/stop/hold/close/verify flow with
  `--dry-run` support and guaranteed flatten in a `finally` block.
- `tests/_diag_push.py` — captures real Push message bodies (quotes, portfolio,
  ping, close-subscription).

## 6. Known limitations / next steps

- **Ping interval observation**: the server pinged ~2× over a ~1 min session;
  a dedicated long-run ping test would confirm the cadence.
- **Explicit subscription close** is verified at the protocol level (unit test +
  diag capture) but there is no SDK helper yet — `send_message()` is used with
  the raw `*CloseSubscriptionRequest` payload. A `close_subscription()` helper
  is a candidate addition.
- **Order lifecycle (Phase E of `TEST_PLAN_VELOTRADE.md`) is not yet tested** —
  that requires a demo/sandbox account. The plan's E1–E12 cases are the next step.
- **`get_session_health()`** returns `last_activity` as a `datetime` (not
  JSON-serializable); harmless, but noted.
- Offline quality gates: `ruff` clean on new files; `black` clean on new files;
  `mypy` still red tree-wide (pre-existing 272 errors; the new code's errors
  were fixed — count dropped to 90 for the two touched modules).
