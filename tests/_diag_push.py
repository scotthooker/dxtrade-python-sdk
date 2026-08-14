"""Diagnostic: capture real Velotrade Push message bodies for tests.md.

Run: PYTHONPATH=src venv/Scripts/python.exe tests/_diag_push.py
"""

import asyncio
import json
import sys

sys.path.insert(0, "src")

from dxtrade import create_transport

MD_URL = "wss://dx.velotrade.com/dxsca-web/md?format=JSON"
PF_URL = "wss://dx.velotrade.com/dxsca-web/?format=JSON"


def extract_account_code(users):
    def find_in(item):
        if isinstance(item, dict):
            for key in ("accountCode", "account", "id"):
                v = item.get(key)
                if isinstance(v, str) and v.startswith("default:"):
                    return v
            for key in ("accounts", "users", "userDetails", "accountList"):
                v = item.get(key)
                if isinstance(v, list):
                    for e in v:
                        f = find_in(e)
                        if f:
                            return f
        elif isinstance(item, list):
            for e in item:
                f = find_in(e)
                if f:
                    return f
        return ""

    code = find_in(users)
    if not code:
        raise ValueError("no account code")
    return code


def extract_symbols(instruments):
    if isinstance(instruments, dict):
        for key in ("instrumentDetails", "instruments", "symbols"):
            v = instruments.get(key)
            if (
                isinstance(v, list)
                and v
                and isinstance(v[0], dict)
                and "symbol" in v[0]
            ):
                return [i["symbol"] for i in v]
        for _key, v in instruments.items():
            if (
                isinstance(v, list)
                and v
                and isinstance(v[0], dict)
                and "symbol" in v[0]
            ):
                return [i["symbol"] for i in v]
    return []


async def main():
    transport = create_transport()
    try:
        token = await transport.authenticate()
        print("1. LOGIN -> sessionToken:", token[:12], "...")

        users = await transport.get_users()
        account = extract_account_code(users)
        print("2. /users -> account code:", account)

        instruments = await transport.query_instruments(account=account, limit=100)
        symbols = extract_symbols(instruments)
        print("3. instruments -> symbols:", symbols[:8], "...")
        assert symbols

        # ---- Portfolio: legacy payload then spec payload ----
        pf_msgs = []
        pf_ready = asyncio.Event()

        def pf_cb(msg):
            pf_msgs.append(msg)
            pf_ready.set()

        await transport.subscribe("portfolio", pf_cb, ws_url=PF_URL)
        for _ in range(180):
            if "portfolio" in transport._websockets:
                break
            await asyncio.sleep(0.25)

        legacy = {
            "type": "AccountPortfoliosSubscriptionRequest",
            "requestId": "diag-legacy",
            "session": token,
            "payload": {
                "account": account,
                "eventTypes": [{"type": "Position", "format": "COMPACT"}],
            },
        }
        print("4. sending LEGACY portfolio payload:", json.dumps(legacy["payload"]))
        await transport.send_message("portfolio", legacy)
        await asyncio.sleep(6)
        legacy_reply = next(
            (
                m
                for m in pf_msgs
                if isinstance(m, dict) and m.get("inReplyTo") == "diag-legacy"
            ),
            None,
        )
        print(
            "   legacy reply:", json.dumps(legacy_reply) if legacy_reply else "(none)"
        )

        pf_msgs.clear()
        await transport.send_portfolio_subscription(account)
        await asyncio.sleep(6)
        snap = next(
            (
                m
                for m in pf_msgs
                if isinstance(m, dict) and m.get("type") == "AccountPortfolios"
            ),
            None,
        )
        print("5. spec portfolio reply:", json.dumps(snap)[:400] if snap else "(none)")
        print(
            "   portfolio count:",
            len(snap.get("payload", {}).get("portfolios", [])) if snap else "n/a",
        )

        # ---- Market data ----
        md_msgs = []
        md_ready = asyncio.Event()

        def md_cb(msg):
            md_msgs.append(msg)
            md_ready.set()

        await transport.subscribe("quotes", md_cb, ws_url=MD_URL)
        for _ in range(180):
            if "quotes" in transport._websockets:
                break
            await asyncio.sleep(0.25)

        await transport.send_market_data_subscription(symbols[:5], account)
        try:
            await asyncio.wait_for(md_ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            print("6. no MarketData within 30s")
            return
        market = next(
            m for m in md_msgs if isinstance(m, dict) and m.get("type") == "MarketData"
        )
        print("6. MarketData sample:", json.dumps(market)[:500])

        # ---- Ping stats ----
        print("7. ping stats (quotes):", json.dumps(transport.get_ping_stats("quotes")))
        print(
            "   session health:",
            json.dumps(transport.get_session_health(), default=str),
        )

        # ---- Close subscription explicitly (spec close request) ----
        close_req = {
            "type": "AccountPortfoliosCloseSubscriptionRequest",
            "requestId": "diag-close",
            "refRequestId": snap.get("inReplyTo") if snap else "unknown",
            "session": token,
            "timestamp": "2026-08-14T00:00:00.000Z",
        }
        pf_msgs.clear()
        await transport.send_message("portfolio", close_req)
        await asyncio.sleep(3)
        close_reply = next(
            (
                m
                for m in pf_msgs
                if isinstance(m, dict) and m.get("inReplyTo") == "diag-close"
            ),
            None,
        )
        print(
            "8. close subscription reply:",
            json.dumps(close_reply)[:300] if close_reply else "(none)",
        )
    finally:
        await transport.close()
        print("9. transport closed cleanly")


if __name__ == "__main__":
    asyncio.run(main())
