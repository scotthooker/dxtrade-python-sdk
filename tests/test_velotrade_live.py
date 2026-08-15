"""Live smoke tests: authenticate against a real broker via the SDK transport.

These tests require a broker ``.env`` in the repository root with ``DXTRADE_*``
variables set (e.g. Velotrade). They are skipped otherwise and never run in CI.
"""

import os
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from dxtrade import create_transport

load_dotenv()

pytestmark = pytest.mark.skipif(
    not Path(".env").exists() or not os.getenv("DXTRADE_USERNAME"),
    reason="requires a broker .env with DXTRADE_USERNAME",
)


def _extract_account_code(users: Any) -> str:
    """Best-effort extraction of the first account code from a /users response.

    DXTrade account codes look like ``default:12345``. The exact /users
    response shape varies between brokers, so several shapes are handled.

    Args:
        users: Raw /users response (dict or list)

    Returns:
        First account code found

    Raises:
        ValueError: No account code could be located
    """

    def find_in(item: Any) -> str:
        if isinstance(item, dict):
            for key in ("accountCode", "account", "id"):
                value = item.get(key)
                if isinstance(value, str) and value.startswith("default:"):
                    return value
            for key in ("accounts", "users", "userDetails", "accountList"):
                value = item.get(key)
                if isinstance(value, list):
                    for entry in value:
                        found = find_in(entry)
                        if found:
                            return found
        elif isinstance(item, list):
            for entry in item:
                found = find_in(entry)
                if found:
                    return found
        return ""

    code = find_in(users)
    if not code:
        raise ValueError("Could not find an account code in /users response")
    return code


class TestLiveLogin:
    """Live login smoke tests against the configured broker."""

    async def test_authenticate_returns_session_token(self):
        """Login with SDK credentials and obtain a session token."""
        transport = create_transport()
        try:
            token = await transport.authenticate()

            assert token, "authenticate() returned an empty token"
            assert isinstance(token, str)
            assert len(token) >= 10, "session token suspiciously short"
        finally:
            await transport.close()

    async def test_authenticated_request_uses_token(self):
        """After login, a REST request carries the session token."""
        transport = create_transport()
        try:
            token = await transport.authenticate()
            assert token

            # /users is the account-discovery endpoint on DXTrade brokers.
            result = await transport.get_users()
            assert result is not None
        finally:
            await transport.close()

    async def test_full_flow_users_and_instruments(self):
        """Mirror the reference direct-API flow entirely through the SDK.

        login -> /users (account discovery) -> account-scoped instruments.
        """
        transport = create_transport()
        try:
            await transport.authenticate()

            users = await transport.get_users()
            account_code = _extract_account_code(users)
            assert account_code.startswith("default:")

            instruments = await transport.query_instruments(
                account=account_code, limit=5
            )
            assert instruments is not None
        finally:
            await transport.close()

    async def test_ping_and_logout(self):
        """Session validation via /ping and clean logout."""
        transport = create_transport()
        try:
            await transport.authenticate()

            ping_result = await transport.ping()
            assert ping_result is not None

            await transport.logout()
            assert transport.auth_handler.get_session_token() is None
        finally:
            await transport.close()
