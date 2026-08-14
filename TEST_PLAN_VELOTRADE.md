# Velotrade Integration Test Plan — `dxtrade-python-sdk`

Scope: validating `dxtrade-sdk` (transport layer primarily) against Velotrade's DXtrade
platform deployment. Discovery performed live on **2026-08-14** via browser session
(sources listed in §10). All live probes were **unauthenticated** and read-only; every
test that needs credentials is marked with a credential requirement.

---

## 1. Purpose and Objectives

1. Prove the SDK can authenticate against Velotrade (`POST /dxsca-web/login`) and obtain a `sessionToken`.
2. Prove REST read-only access works (account discovery, metrics, instruments, positions, orders, market data) using Velotrade's auth scheme.
3. Prove the Push (WebSocket) API works: market-data stream, business/portfolio stream, application-level ping/pong session extension.
4. Prove the order lifecycle safely (demo/sandbox only): open, modify, close, error handling.
5. Identify and document every place the SDK's assumptions differ from Velotrade's live API (see §8 "Known gaps").
6. Prove the SDK never leaks credentials and handles rate limits/backpressure without blind retries.

**Non-goals:** FIX API (not provisioned by Velotrade), the broken high-level SDK layer
(`dxtrade.client`, `dxtrade.rest`, `dxtrade.websocket`, `dxtrade.core` — known import
failures, tracked separately), HMAC/Bearer auth (Velotrade trading accounts use session
token auth only).

---

## 2. Live-Verified Velotrade Environment (Discovery Output)

| Item | Value | Verification |
|---|---|---|
| REST base URL | `https://dx.velotrade.com/dxsca-web` | Login probe returned DXTrade JSON errors; Swagger served at `/dxsca-web/api/swagger.html` |
| REST login path | `POST /dxsca-web/login` | Empty body → `500 errorCode 110`; bad creds → `401 errorCode 3 "Authorization failed"` |
| REST login body | `{"username","password","domain"}` | Matches `LoginRequest` schema in OpenAPI |
| REST login domain | `default` | **Not** `vendor=velotrade` (website SSO param ≠ REST domain) |
| REST auth header | `Authorization: DXAPI <sessionToken>` | OpenAPI `securitySchemes.Authorization`; Velotrade docs |
| REST extra requirement | Non-empty `User-Agent` header (else 403 per spec) | REST spec "Authentication" |
| Business Push (WS) | `wss://dx.velotrade.com/dxsca-web/?format=JSON` — **trailing slash required** | Live open; `/dxsca-web/ws` and no-slash variants fail |
| Market-data Push (WS) | `wss://dx.velotrade.com/dxsca-web/md?format=JSON` | Live open (format param optional) |
| Account code format | `default:<number>` e.g. `default:130000505`, URL-encoded `default%3A...` in paths | Velotrade blog §2 |
| Account discovery | `GET /dxsca-web/users` → account records | OpenAPI `/users`; Velotrade blog |
| Push ping protocol | Server `{"type":"PingRequest","session","timestamp"}` → client `{"type":"Ping","session","timestamp"}` | Push API spec §Ping — **identical to SDK `_handle_ping_pong`** |
| Order endpoint | `POST /dxsca-web/accounts/{encodedAccountCode}/orders` | OpenAPI `SingleOrderRequest` |
| Not standalone (404) | `/dxsca-web/instruments`, `/dxsca-web/accounts`, `/dxsca-web/orders`, `/dxsca-web/positions`, `/dxsca-web/quotes`, `/dxsca-web/time` | Live probes |

### 2.1 REST endpoints present (OpenAPI `openapi.json`, live at `/dxsca-web/swagger/openapi.json`)

```
POST /login                 POST /loginByToken          POST /logout            POST /ping
GET  /users                 GET  /users/{username}
GET  /accounts/{account}/events          GET  /accounts/events
GET  /accounts/{account}/metrics         GET  /accounts/metrics
GET  /accounts/{account}/portfolio       GET  /accounts/portfolio
POST /accounts/{account}/close
POST /accounts/{account}/transfers       GET  /accounts/transfers
GET  /accounts/{account}/orders/history  GET  /accounts/orders/history
GET  /accounts/{account}/instruments/{symbol}
POST /accounts/{account}/instruments/query
GET  /accounts/{account}/instruments/type/{type}
GET  /instruments/{symbol}  POST /instruments/query     GET /instruments/type/{type}
POST /marketdata
POST /accounts/{account}/orders          POST /accounts/orders
GET  /accounts/{account}/orders/{order}
POST /accounts/{account}/orders/group
GET  /accounts/{account}/positions       GET  /accounts/positions
GET  /accounts/{account}/tvLoginInfo     GET  /accounts/tvLoginInfo
GET  /accounts/eodmetrics/{date}         GET  /conversionRates
```

### 2.2 Push API message shapes (from Velotrade Push API spec)

- **Envelope:** `type` (required), `requestId` (≤64 chars), `inReplyTo`, `refRequestId`,
  `timestamp` (required, ISO-8601 UTC), `session`, `principal`/`hash` (HMAC only), `payload`.
- **Market data sub:** `MarketDataSubscriptionRequest` → payload `{account, symbols,
  eventTypes:[{type:"Quote",format:"COMPACT"}]}` → server `MarketData` with
  `payload.events[]` (`{symbol,type,bid,ask,time}`). **Matches SDK exactly** (SDK omits `timestamp`).
- **Portfolio sub:** `AccountPortfoliosSubscriptionRequest` → payload
  `{requestType:"LIST", accounts:["default:..."]}` → server `AccountPortfolios` with
  `payload.portfolios[]`. **SDK payload differs** — SDK sends `{account, eventTypes:[{type:"Position",format:"COMPACT"}]}`.
- **Close sub:** `AccountPortfoliosCloseSubscriptionRequest` with `refRequestId` → server
  `AccountPortfoliosSubscriptionClosed`. SDK has no explicit close message.
- **Errors:** code `1` auth required (missing/expired session), `2` entity not found,
  `32` incorrect request parameters, `34` no market-data permission, `429` too many
  requests (default 1/min for `RequestType=ALL` subscriptions). WS close `1013` = backpressure.

### 2.3 REST error table (Velotrade blog "Common Errors")

| HTTP / code | Meaning | Safe action |
|---|---|---|
| 401 / 3 | Bad credentials, wrong domain, or account lock | Use domain `default`; stop retrying |
| 404 (HTML) | Wrong path shape | Use full encoded account code |
| 400 / 32 | Incorrect parameters | Validate fields/enums/account/symbol |
| 400 / 33 | Malformed/incompatible order | Validate order schema locally |
| 409 / 100 | Duplicate client identifier | Reconcile; do not blindly retry |
| 429 | Rate limit | Back off; never blind-retry a trade |

### 2.4 Order placement (OpenAPI `SingleOrderRequest`)

Fields: `account`, `orderCode` (client-generated, unique per account), `metadata`,
`type` (`MARKET|LIMIT|STOP`), `instrument`, `quantity` (base-currency units — forex lots
×100,000), `positionEffect` (`OPEN|CLOSE`), `positionCode`, `side` (`BUY|SELL`),
`limitPrice`, `stopPrice`, `priceOffset`, `priceLink`, `tif` (`DAY|GTC|IOC|FOK|GTD`),
`marginRate`, `expireDate`. A `200` response with an order id is an **acknowledgement,
not execution proof** — confirm via `/accounts/{code}/orders/history` or Push.

---

## 3. Prerequisites and Test Environment

- **Credentialed account:** one Velotrade challenge/eval account (username/password are
  the API credentials). Recommended: a fresh small 1-step or 2-step account with no open
  positions for phases A–D; a **demo/sandbox** account for phase E. Never run phase E on a
  funded account.
- **Python:** 3.10+; `pip install -e ".[dev]"` in the repo venv.
- **Network access:** `dx.velotrade.com` (REST + WSS). Corporate proxies break WS — verify first.
- **Clock sync:** REST HMAC not used, but Push timestamps should be near server time.
- **Secrets:** credentials only in `.env` (gitignored) or env vars; never in code/logs/CI.
- **Test data conventions:** every order uses a unique `orderCode` (e.g. `vt-<uuid>`);
  every subscription a unique `requestId`.

### 3.1 Recommended `.env` (place under `tests/velotrade/.env` or env vars — never commit)

```bash
DXTRADE_BASE_URL=https://dx.velotrade.com/dxsca-web
DXTRADE_USERNAME=<trading-account-username>
DXTRADE_PASSWORD=<trading-account-password>
DXTRADE_DOMAIN=default
DXTRADE_ACCOUNT=default:<account-number>   # from GET /users — NOT the portal account id
DXTRADE_USER_AGENT=dxtrade-sdk-velotrade-tests/1.0
DXTRADE_LOG_LEVEL=INFO
DXTRADE_TIMEOUT=30
# NOTE: these two are documented by the SDK but NOT currently read by env_config.py
# (see §8 gap G2). Pass ws_url explicitly to subscribe() or patch env_config first.
DXTRADE_WS_MARKET_DATA_URL=wss://dx.velotrade.com/dxsca-web/md?format=JSON
DXTRADE_WS_PORTFOLIO_URL=wss://dx.velotrade.com/dxsca-web/?format=JSON
```

---

## 4. Test Architecture

- **Framework:** pytest + pytest-asyncio (`asyncio_mode=auto`), same conventions as `tests/test_auth.py`.
- **Three layers of tests:**
  1. **Mocked/offline** (default `pytest`, no credentials): config loading, auth-header
     construction, message-shape builders, ping/pong handling, URL fallback logic — all
     against recorded fixtures.
  2. **Contract tests** (no credentials, live): endpoint existence / auth rejection
     probes (`401`/`404` shape checks) — safe to run in CI.
  3. **Live integration** (credentials required, `-m live`, opt-in): real login, REST
     reads, Push subscriptions, order lifecycle.
- Markers: reuse `unit`; add `live` and `slow`. Keep live tests gated behind a
  `--live`/env flag so the suite never hits the network by default.
- Fixtures in `tests/velotrade/conftest.py`: `live_env` (env-file loader), `transport`
  (factory + clean shutdown), `session_token` (one login per module, reused), `account_code`
  (from `/users`), `instrument` (smallest tradable discovered).

---

## 5. Test Phases and Cases

### Phase A — Configuration and URL Contract (no credentials, offline + live probes)

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| A1 | High | `.env` loads for Velotrade values | Load `DXTRADE_BASE_URL`, auth, account from env via `load_config_from_env()` | `base_url == https://dx.velotrade.com/dxsca-web`; `auth.type == CREDENTIALS`; `domain == default` |
| A2 | High | Login URL construction | `transport.authenticate()` path resolution | URL = `https://dx.velotrade.com/dxsca-web/login` (no double slash, no `/dxsca-web/login` duplication) |
| A3 | High | MD WS URL precedence | `subscribe("quotes", cb, ws_url=…)` and config fallback | Explicit `ws_url` wins; config `market_data_url` used when set; otherwise `ValueError` (never silent wrong URL) |
| A4 | High | Portfolio WS URL for Velotrade | `subscribe("portfolio", cb, ws_url="wss://dx.velotrade.com/dxsca-web/?format=JSON")` | Connects (see D1). Assert trailing-slash URL, not `/ws` |
| A5 | Med | Endpoint existence probes (unauthenticated) | GET `/dxsca-web/ping`? (POST), `/users`, `/accounts/{code}/metrics` with no/bad auth | `401 errorCode 1` (auth required), **not** 404 — proves path exists |
| A6 | Med | Non-existent SDK defaults | GET `/dxsca-web/orders`, `/positions`, `/quotes`, `/time`, `/instruments` | 404 HTML — documents that SDK convenience methods hit dead paths (gap G6) |
| A7 | Med | Swagger/spec reachability | GET `/dxsca-web/swagger/openapi.json` | 200 JSON, paths superset of §2.1 |

### Phase B — Authentication and Session Lifecycle (credentials)

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| B1 | High | Successful login | `transport.authenticate()` | Returns non-empty `sessionToken`; stored in handler; expiry ≈ +1 h |
| B2 | High | Wrong password | Login with bad password | `DXtradeAuthenticationError`; HTTP 401 `errorCode 3`; no retry storm |
| B3 | High | Wrong domain | Login with `domain=velotrade` | Fails (401/3); retry with `default` succeeds — proves domain quirk |
| B4 | High | Login rate limit | 5 rapid logins | No hard 429; if 429, backoff honored (spec: 1 login/s default) |
| B5 | High | Token refresh on 401 | Call `request()` with expired token | One re-authenticate, one retry, success; exactly one extra login |
| B6 | High | **Auth header used for REST** | Inspect request headers on a real call | `Authorization: DXAPI <token>` present (see gap G1 — SDK sends `X-Auth-Token` only) |
| B7 | Med | User-Agent present | Inspect headers | Non-empty `User-Agent` on every request (spec requirement) |
| B8 | Med | `POST /ping` session validation | Send ping with valid token | Returns `200` and/or `sessionToken` (can refresh token) |
| B9 | Med | Logout | `SessionHandler.logout()` | `POST /logout`; local token cleared; subsequent calls re-auth |

### Phase C — REST Read-Only API (credentials)

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| C1 | High | Account discovery | `GET /users` via `request("GET","/users")` | JSON with account record containing full code `default:<n>`; matches `DXTRADE_ACCOUNT` |
| C2 | High | Metrics | `GET /accounts/{enc}/metrics` | `account`, `equity`, `balance`, `margin`, `openPL`, counts; keys match `AccountMetrics` |
| C3 | High | Positions | `GET /accounts/{enc}/positions` | Empty list (fresh account) with 200 |
| C4 | High | Orders | `GET /accounts/{enc}/orders` and `/orders/history` | 200 (possibly empty); history contains any prior fills |
| C5 | High | Instrument discovery | `GET /accounts/{enc}/instruments/query?symbols=BTC` and no-arg variant | Symbols with `tradingStatus`, min/max order size, `marginRate`, `assetClass`; multi-asset across crypto/forex/equities/indices |
| C6 | Med | Instrument quantity units | Compare `minOrderSize` for EURUSD | Confirm lots vs base units; record conversion (blog: lots ×100,000 for forex) |
| C7 | Med | Market data snapshot | `POST /marketdata` `{symbols:[…], eventTypes:[{type:"Quote",format:"COMPACT"}]}` | Quote events for subscribed symbols |
| C8 | Med | Bad path shape | `GET /accounts/{code}/orders/` (trailing slash) or unencoded colon | Correctly reports 404/400; test verifies URL-encoding of `:` as `%3A` |
| C9 | Low | Rate limit surface | Burst 20 instrument queries | No 429; if 429, `Retry-After` honored, no blind retry |

### Phase D — Push API / WebSocket (credentials)

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| D1 | High | Market-data socket connects | `subscribe("quotes", cb, md_url)` | Handshake OK with `additional_headers` strategy; connection healthy |
| D2 | High | Quote subscription streams | `send_market_data_subscription(["EUR/USD","BTCUSD"], account)` | Within N s, callback receives `{"type":"MarketData",…,"payload":{"events":[…bid/ask…]}}`; `inReplyTo` matches `requestId` |
| D3 | High | **Subscription without `timestamp` accepted?** | Send SDK-shaped message (no `timestamp` field) | Record result: if `Reject`/error 32 arrives, document required field (gap G4) and add test for corrected message |
| D4 | High | Ping/pong auto-extension | Stay connected; observe `PingRequest` | SDK replies `{"type":"Ping","session","timestamp"}`; `get_ping_stats()["quotes"]["ping_responses_sent"]` increments; `get_session_health()` ≥ 1.0 |
| D5 | High | Portfolio socket connects | `subscribe("portfolio", cb, biz_url)` | Connects at `wss://…/dxsca-web/?format=JSON` |
| D6 | High | Portfolio subscription streams | `send_portfolio_subscription(account)` with SDK payload | **Expected mismatch** — server Rejects (error 32) because payload shape differs (gap G5). Fix payload to `{requestType:"LIST",accounts:[…]}` (+timestamp), then assert `{"type":"AccountPortfolios","payload":{"portfolios":[…]}}` snapshot arrives |
| D7 | High | Portfolio updates on order | Place small order (Phase E), watch portfolio | Full portfolio snapshot (no diffs) with new position/working order; `version` increments |
| D8 | Med | Explicit close subscription | Send `AccountPortfoliosCloseSubscriptionRequest` with `refRequestId` | `AccountPortfoliosSubscriptionClosed`; no further portfolio messages |
| D9 | Med | Multiple sessions one channel | Subscribe with two account codes on one socket | Independent streams, no message interleaving |
| D10 | Med | `RequestType=ALL` rate limit | Issue `RequestType=ALL` subscriptions >1/min | `Reject` 429; verify backoff behavior |
| D11 | Low | Compression param | Connect with `compression=gzip` | Either works transparently or server ignores; record actual behavior |
| D12 | Low | Backpressure (1013) | Slow consumer under heavy quotes | Connection closes 1013; transport surfaces error; no auto-flood of reconnects |

### Phase E — Order Lifecycle (demo/sandbox ONLY)

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| E1 | High | Market order open | `POST /accounts/{enc}/orders` with `orderCode`, `type=MARKET`, `side=BUY`, `instrument`, `quantity`, `tif=GTC` | 200 ack with order id; then order reaches `COMPLETED` and a position appears (confirm via C3 + Push) |
| E2 | High | Unique orderCode enforced | Repeat same `orderCode` | `409 errorCode 100`; original order untouched |
| E3 | High | Duplicate idempotency | Retry E1 with new `orderCode` after timeout | At most one fill (no double execution) — reconcile via history |
| E4 | High | Close position | `positionEffect=CLOSE`, `positionCode`, opposite `side`, same instrument, new `orderCode`, `tif=GTC`, omit `quantity` for full close | Position gone; no residual working/protective orders; verify via C3/C4 |
| E5 | High | Malformed order | `type=MARKET` with `limitPrice` set, or missing `quantity` | `400 errorCode 33`; no state change |
| E6 | High | Invalid instrument/symbol | Order on unlisted symbol | `400 errorCode 32`; clear error |
| E7 | Med | LIMIT order | `type=LIMIT` with realistic `limitPrice` | `WORKING` state; cancelable |
| E8 | Med | Cancel working order | `DELETE/PUT /accounts/{enc}/orders/{order}` per spec | Order `CANCELED`; position never opens |
| E9 | Med | STOP order + TP/SL | STOP order with `stopPrice`; attach TP/SL | Triggers per rules; protective orders visible in portfolio |
| E10 | Low | Bracket/group order | `POST /accounts/{enc}/orders/group` | Accepted or documented unsupported; record |
| E11 | High | Rules compliance | Compare API state after E1–E9 against Velotrade eval rules (daily loss, max drawdown) | No rule breach; note that eval rules bind API trades identically to manual |
| E12 | High | Flat-state smoke | Isolated connectivity smoke: open+close, assert flat | Total positions and working orders == 0 at end |

### Phase F — Resilience and Shutdown

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| F1 | High | Clean shutdown sequence | Stop new actions → reconcile → confirm flat → explicit close subscriptions → close sockets → REST logout | No orphan orders; `logout` returns; no exception on teardown |
| F2 | Med | WS drop + reconnect | Kill socket mid-subscription | Reconnect with backoff; **fresh REST snapshot before trusting local state** (blog guidance) |
| F3 | Med | Session expiry mid-run | Force token expiry (shorten `_token_expires_at`) | Next request re-authenticates; Push subscriptions resubscribed with new session |
| F4 | Med | Process interruption | SIGINT during connected stream | Socket/task cleanup; no zombie tasks; no partial subscriptions left |
| F5 | Low | Backoff + jitter | 3 failed connects | Delays grow (base_delay, exponential, jitter) — assert monotonic-ish |

### Phase G — Security and Hygiene

| ID | Pri | Test | Steps | Expected result |
|---|---|---|---|---|
| G-S1 | High | No secret leakage | Run A–F with `LOG_LEVEL=DEBUG` | No username/password/`sessionToken`/`Authorization` value in logs |
| G-S2 | High | Credentials `repr=False` | `repr(SessionCredentials(...))` | No password/token visible |
| G-S3 | High | `.env` gitignored | `git check-ignore .env` | Ignored; only `.env.example` committed |
| G-S4 | Med | `Authorization` header not logged | HTTP-level debug capture | Header values redacted |
| G-S5 | Med | No blind trade retries | Force 429/409 on order | Client surfaces error; does not auto-resubmit (409/100, 429 semantics) |

---

## 6. Known SDK Gaps vs Velotrade (adaptation work — fixes needed before Phase C/D pass)

| # | Gap | Evidence | Impact | Suggested fix |
|---|---|---|---|---|
| G1 | `transport.request()` sends only `X-Auth-Token`; Velotrade requires `Authorization: DXAPI <token>` | OpenAPI security scheme; Velotrade docs; `auth.py:228-229` sends both, `transport.py:195` sends one | All REST reads fail (401) | Add `Authorization: DXAPI` header in `transport.request()`; keep `X-Auth-Token` for legacy brokers (send both, like `SessionHandler`) |
| G2 | `DXTRADE_WS_MARKET_DATA_URL` / `DXTRADE_WS_PORTFOLIO_URL` documented but never read by `env_config.py` | `config.py:106-107` fields default None; no env read in `env_config.py`; `.env.example:17-20` documents them | `subscribe()` raises "No WebSocket URL configured" from env-only setup | Read the two vars in `_load_websocket_from_env()`; populate `market_data_url`/`portfolio_url` |
| G3 | `WebSocketConfig.get_market_data_url()/get_portfolio_url()` hardcode `{ws_base}/ws{path}` | `config.py:136,155` | Wrong URLs for Velotrade (`/md`, and `/` with trailing slash); never `/ws…` | Don't inject `/ws`; honor explicit URLs/paths verbatim |
| G4 | Push envelope `timestamp` omitted by SDK subscription builders | Push spec marks `timestamp` **required**; SDK `send_market_data_subscription`/`send_portfolio_subscription` omit it | Potential Reject (error 32) — must verify live (D3) | Add `timestamp` (ISO-8601 ms UTC) to all outbound Push messages |
| G5 | Portfolio subscription payload shape differs | Spec: `payload{requestType:"LIST", accounts:[…]}`; SDK: `payload{account, eventTypes:[{type:"Position",…}]}` | Portfolio subscription rejected; no portfolio stream | Build `{requestType, accounts}` payload; drop `eventTypes` for portfolio |
| G6 | Convenience methods hit dead paths | `transport.py:893-927` use `/accounts`, `/orders`, `/positions`, `/quotes`, `/time` → 404 | Those methods unusable on Velotrade | Point at `/users`, `/accounts/{code}/orders`, `/accounts/{code}/positions`, `/accounts/{code}/metrics`, `POST /marketdata`, `POST /ping` |
| G7 | No explicit Push close-subscription requests on shutdown | Spec requires `*CloseSubscriptionRequest` with `refRequestId`; SDK only closes the socket | Server keeps pushing / stale subs on reconnect | Send matching close requests in `unsubscribe()`/shutdown |
| G8 | Transport lacks reconnect with exponential backoff + jitter | `transport.py` `_websocket_handler` exits on failure; blog mandates backoff+jitter | Stream dies permanently on transient drop | Add bounded reconnect loop (reuse `RetryConfig`) |
| G9 | SDK default endpoints `/time`; Velotrade has no `/time` | OpenAPI: only `/ping` | `get_server_time()` 404 | Map to `POST /ping` |

---

## 7. Exit Criteria

1. A1–A7, B1, B2, B6, B7, B8, C1–C8, D1–D4, D6(fixed), D7, D8, E1–E6, E12, F1, G-S1–G-S3 all pass on the credentialed account.
2. Gaps G1–G9 confirmed resolved or explicitly waived with a tracked issue + workaround documented.
3. A run of the full suite leaves the account **flat** (zero positions, zero working orders) and logs out.
4. `pytest` (offline suite) stays green; live suite is opt-in via marker/flag.
5. No credentials in logs, artifacts, or committed files.

---

## 8. Tooling and CI Notes

- Offline tests must not touch the network; mock at the `aiohttp`/`websockets` boundary (conftest already mocks `httpx` — extend pattern to `aiohttp`).
- Record live exchanges once as VCR-style fixtures (request/response JSON, headers redacted) to keep CI hermetic and enable regression on message shapes (D2/D6).
- Add `pytest -m live` exclusion in CI; keep contract probes (A5–A7) in the default run.
- Timeouts: use generous WS waits (≥ server ping interval) — ping interval configurable via `DXTRADE_WS_PING_INTERVAL` (default 45 s); tests that need a fast ping should lower it.

---

## 9. References

- Velotrade API article: https://velotrade.com/blog/dxtrade-api-algo-trading
- Velotrade API access page: https://velotrade.com/api-access
- Velotrade developer portal (live): https://dx.velotrade.com/developers/ (REST API, Push API specs)
- Velotrade Swagger (live): https://dx.velotrade.com/dxsca-web/api/swagger.html — spec at `/dxsca-web/swagger/openapi.json`
- Velotrade DXtrade AI knowledge base: https://velotrade.com/downloads/velotrade-dxtrade-ai-kb.zip
- Trading terminal: https://dx.velotrade.com/ (login) | Portal: https://portal.velotrade.com/
- Repo AGENTS.md "Known Issues" for the broken high-level layer (out of scope here)

> Discovery date: 2026-08-14. Velotrade can change endpoints/behaviour — re-run Phase A probes and re-read the developer portal before a release; rules pages are controlling for trading rules.
