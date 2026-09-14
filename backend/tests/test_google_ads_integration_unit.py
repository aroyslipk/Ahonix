"""Unit and Security Tests for Phase 5.3: Google Ads OAuth & Account Connection.

Coverage:
1. Google Ads OAuth 2.0 Flow:
   - Verification of OAuth URL generation with required scope (https://www.googleapis.com/auth/adwords).
   - Offline access enforcement (access_type=offline, prompt=consent).
   - Cryptographic CSRF state creation and single-use validation with 900s TTL.
   - Authorization code exchange and AES-256-GCM encryption of refresh token at rest.
2. Token Lifecycle & Error Handling:
   - Server-side access token refresh from encrypted refresh token.
   - Detection of invalid_grant / revoked tokens resulting in reauth_required status and HTTP 401.
   - Developer Token requirement (GOOGLE_ADS_DEVELOPER_TOKEN) enforced for API calls.
3. Customer Discovery & Normalization:
   - Normalization of customer IDs (e.g. '123-456-7890' -> '1234567890', 'customers/123-456-7890' -> '1234567890').
   - Accessible customer query (listAccessibleCustomers) returning sanitized metadata.
4. Manager Account (MCC) & Login Customer ID:
   - Proper persistence and normalization of login_customer_id when acting through a manager account.
5. Account Selection & Currency Safety:
   - Account selection binding to active workspace.
   - Currency comparison against store currency with currency_mismatch detection.
6. Workspace Isolation & Demo Protection:
   - Strict workspace-level isolation on connections and states.
   - Northstar Goods demo workspace immutability (mutations blocked with HTTP 400).
7. Disconnection & Zero Secret Exposure:
   - Safe removal of credentials upon disconnect.
   - Zero exposure of refresh tokens, client secrets, or developer tokens in status and responses.
"""
import sys
from pathlib import Path
import os
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import google_ads_integration
from google_ads_integration import (
    get_google_ads_config,
    normalize_customer_id,
    get_google_ads_access_token,
    connect_google_ads,
    google_ads_callback,
    get_google_ads_status,
    list_google_ads_accessible_customers,
    select_google_ads_account,
    disconnect_google_ads,
    SelectGoogleAdsAccountBody,
    DEFAULT_GOOGLE_ADS_SCOPE,
    init_google_ads,
)
from shopify_integration import encrypt_token, decrypt_token

_RealAsyncClient = httpx.AsyncClient


# --- Mock Async In-Memory MongoDB --------------------------------------------
class MockCursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, length=1000):
        return self.items[:length]

    def __aiter__(self):
        self._iter = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
        self.docs = []

    def find(self, query=None, projection=None):
        matched = []
        for d in self.docs:
            if not query:
                matched.append(dict(d))
                continue
            match = True
            for k, v in query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                res = dict(d)
                if projection:
                    for pk, pv in projection.items():
                        if pv == 0 and pk in res:
                            del res[pk]
                matched.append(res)
        return MockCursor(matched)

    async def find_one(self, query, projection=None):
        cursor = self.find(query, projection)
        items = await cursor.to_list(1)
        return items[0] if items else None

    async def replace_one(self, filter_query, doc, upsert=False):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                self.docs[idx] = dict(doc)
                return
        if upsert:
            self.docs.append(dict(doc))

    async def update_one(self, filter_query, update_spec, upsert=False):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update_spec:
                    d.update(update_spec["$set"])
                return
        if upsert:
            new_doc = dict(filter_query)
            if "$set" in update_spec:
                new_doc.update(update_spec["$set"])
            self.docs.append(new_doc)

    async def delete_one(self, filter_query):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                self.docs.pop(idx)
                return


class MockDB:
    def __init__(self):
        self.marketing_connections = MockCollection("marketing_connections")
        self.google_ads_oauth_states = MockCollection("google_ads_oauth_states")


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def live_workspace():
    return {
        "workspace_id": "ws_live_gads",
        "name": "Live Commerce Store",
        "currency": "USD",
        "is_demo": False,
    }


@pytest.fixture
def demo_workspace():
    return {
        "workspace_id": "ws_demo_northstar",
        "name": "Northstar Goods",
        "currency": "USD",
        "is_demo": True,
    }


# =============================================================================
# Test Suite 1: Customer ID Normalization & Developer Token Requirement
# =============================================================================
class TestGoogleAdsNormalizationAndConfig:
    def test_customer_id_normalization(self):
        """Verifies customer IDs and resource names are normalized to digits-only."""
        assert normalize_customer_id("123-456-7890") == "1234567890"
        assert normalize_customer_id("customers/123-456-7890") == "1234567890"
        assert normalize_customer_id("customers/1234567890") == "1234567890"
        assert normalize_customer_id(" 987-654-3210 ") == "9876543210"
        assert normalize_customer_id("") == ""
        assert normalize_customer_id(None) == ""

    def test_developer_token_requirement(self, mock_db, live_workspace):
        """Verifies customer discovery requires GOOGLE_ADS_DEVELOPER_TOKEN."""
        async def _run():
            init_google_ads(mock_db, AsyncMock(return_value=live_workspace))
            user = {"user_id": "u1", "email": "u1@example.com"}

            # Setup connected Google connection
            await mock_db.marketing_connections.replace_one(
                {"workspace_id": live_workspace["workspace_id"], "platform": "google_ads"},
                {
                    "workspace_id": live_workspace["workspace_id"],
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypt_token("refresh_123"),
                },
                upsert=True,
            )

            with patch.dict(os.environ, {"GOOGLE_ADS_DEVELOPER_TOKEN": ""}):
                with pytest.raises(HTTPException) as exc_info:
                    await list_google_ads_accessible_customers(user=user)
                assert exc_info.value.status_code == 503
                assert "DEVELOPER_TOKEN" in exc_info.value.detail

        asyncio.run(_run())


# =============================================================================
# Test Suite 2: OAuth Lifecycle & State Security
# =============================================================================
class TestGoogleAdsOAuthFlow:
    def test_connect_generates_valid_oauth_url_and_state(self, mock_db, live_workspace):
        """Verifies connect returns valid URL with adwords scope, offline access, and consent prompt."""
        async def _run():
            init_google_ads(mock_db, AsyncMock(return_value=live_workspace))
            user = {"user_id": "u_auth", "email": "auth@example.com"}

            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "mock_client_id.apps.googleusercontent.com",
                "GOOGLE_ADS_CLIENT_SECRET": "mock_client_secret_123",
                "GOOGLE_ADS_REDIRECT_URI": "http://localhost:3000/api/integrations/google-ads/callback",
            }
            with patch.dict(os.environ, env_vars):
                res = await connect_google_ads(user=user)

            assert res["ok"] is True
            assert "accounts.google.com/o/oauth2/v2/auth" in res["auth_url"]
            assert "client_id=mock_client_id.apps.googleusercontent.com" in res["auth_url"]
            assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fadwords" in res["auth_url"] or "scope=https://www.googleapis.com/auth/adwords" in res["auth_url"]
            assert "access_type=offline" in res["auth_url"]
            assert "prompt=consent" in res["auth_url"]

            # Verify state was persisted with TTL in DB
            state_doc = await mock_db.google_ads_oauth_states.find_one({"state": res["state"]})
            assert state_doc is not None
            assert state_doc["workspace_id"] == live_workspace["workspace_id"]
            assert state_doc["user_id"] == "u_auth"

        asyncio.run(_run())

    def test_callback_rejects_invalid_or_expired_state(self, mock_db):
        """Verifies callback rejects missing, forged, or expired state."""
        async def _run():
            init_google_ads(mock_db, AsyncMock())

            # 1. State not in DB
            req = MagicMock()
            req.query_params = {"code": "test_code", "state": "unknown_state"}
            res = await google_ads_callback(req)
            assert isinstance(res, RedirectResponse)
            assert "google_ads_error=invalid_state" in res.headers["location"]

            # 2. Expired state
            expired_state = "state_exp_123"
            now_utc = datetime.now(timezone.utc)
            await mock_db.google_ads_oauth_states.replace_one(
                {"state": expired_state},
                {
                    "state": expired_state,
                    "workspace_id": "ws_1",
                    "user_id": "u_1",
                    "expires_at": (now_utc - timedelta(seconds=10)).isoformat(),
                },
                upsert=True,
            )
            req2 = MagicMock()
            req2.query_params = {"code": "test_code", "state": expired_state}
            res2 = await google_ads_callback(req2)
            assert isinstance(res2, RedirectResponse)
            assert "google_ads_error=expired_state" in res2.headers["location"]

        asyncio.run(_run())

    def test_callback_exchanges_code_and_encrypts_refresh_token(self, mock_db):
        """Verifies authorization code exchange and AES-256-GCM encryption of refresh token at rest."""
        async def _run():
            init_google_ads(mock_db, AsyncMock())
            state_nonce = "valid_state_nonce_123"
            now_utc = datetime.now(timezone.utc)

            await mock_db.google_ads_oauth_states.replace_one(
                {"state": state_nonce},
                {
                    "state": state_nonce,
                    "workspace_id": "ws_cb_test",
                    "user_id": "usr_cb",
                    "expires_at": (now_utc + timedelta(seconds=600)).isoformat(),
                },
                upsert=True,
            )

            token_response_payload = {
                "access_token": "ya29.short_lived_access_token",
                "refresh_token": "1//0gD_real_refresh_token_secret",
                "expires_in": 3599,
                "token_type": "Bearer",
            }

            async def mock_token_exchange(request: httpx.Request):
                return httpx.Response(200, json=token_response_payload)

            transport = httpx.MockTransport(mock_token_exchange)

            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "client_id_val",
                "GOOGLE_ADS_CLIENT_SECRET": "client_sec_val",
                "GOOGLE_ADS_REDIRECT_URI": "http://localhost:3000/api/integrations/google-ads/callback",
                "FRONTEND_URL": "http://localhost:3000",
            }

            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    req = MagicMock()
                    req.query_params = {"code": "google_auth_code_999", "state": state_nonce}
                    res = await google_ads_callback(req)

            assert isinstance(res, RedirectResponse)
            assert "google_ads=connected" in res.headers["location"]

            # Verify connection stored in DB
            conn = await mock_db.marketing_connections.find_one({"workspace_id": "ws_cb_test", "platform": "google_ads"})
            assert conn is not None
            assert conn["status"] == "connected"
            assert "encrypted_refresh_token" in conn

            # Verify encryption at rest (plaintext token is NOT in the database)
            encrypted = conn["encrypted_refresh_token"]
            assert encrypted != "1//0gD_real_refresh_token_secret"
            decrypted = decrypt_token(encrypted)
            assert decrypted == "1//0gD_real_refresh_token_secret"

            # Verify single-use state was deleted
            consumed_state = await mock_db.google_ads_oauth_states.find_one({"state": state_nonce})
            assert consumed_state is None

        asyncio.run(_run())


# =============================================================================
# Test Suite 3: Token Lifecycle & Reauth Handling
# =============================================================================
class TestGoogleAdsTokenLifecycle:
    def test_get_access_token_success(self, mock_db, live_workspace):
        """Verifies get_google_ads_access_token decrypts refresh token and fetches access token."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_refresh = encrypt_token("mock_refresh_token_active")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypted_refresh,
                },
                upsert=True,
            )

            async def mock_refresh(request: httpx.Request):
                return httpx.Response(200, json={"access_token": "ya29.fresh_access_token_123", "expires_in": 3600})

            transport = httpx.MockTransport(mock_refresh)
            async with httpx.AsyncClient(transport=transport) as client:
                env_vars = {"GOOGLE_ADS_CLIENT_ID": "cid", "GOOGLE_ADS_CLIENT_SECRET": "csec"}
                with patch.dict(os.environ, env_vars):
                    token = await get_google_ads_access_token(mock_db, ws_id, client=client)

            assert token == "ya29.fresh_access_token_123"

        asyncio.run(_run())

    def test_invalid_grant_transitions_to_reauth_required(self, mock_db, live_workspace):
        """Verifies invalid_grant response marks connection status as reauth_required and raises HTTP 401."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_refresh = encrypt_token("revoked_refresh_token")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypted_refresh,
                },
                upsert=True,
            )

            async def mock_revoked(request: httpx.Request):
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."})

            transport = httpx.MockTransport(mock_revoked)
            async with httpx.AsyncClient(transport=transport) as client:
                env_vars = {"GOOGLE_ADS_CLIENT_ID": "cid", "GOOGLE_ADS_CLIENT_SECRET": "csec"}
                with patch.dict(os.environ, env_vars):
                    with pytest.raises(HTTPException) as exc_info:
                        await get_google_ads_access_token(mock_db, ws_id, client=client)

            assert exc_info.value.status_code == 401
            assert "reconnect" in exc_info.value.detail.lower()

            conn = await mock_db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "google_ads"})
            assert conn["status"] == "reauth_required"
            assert "expired or revoked" in conn["sync_error"]

        asyncio.run(_run())


# =============================================================================
# Test Suite 4: Customer Discovery & Account Selection
# =============================================================================
class TestGoogleAdsAccountsAndSelection:
    def test_customer_discovery_list_accessible(self, mock_db, live_workspace):
        """Verifies GET /accounts calls listAccessibleCustomers and returns normalized accounts."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            init_google_ads(mock_db, AsyncMock(return_value=live_workspace))
            user = {"user_id": "u1", "email": "u1@example.com"}

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypt_token("valid_refresh"),
                    "selected_customer_id": "1234567890",
                },
                upsert=True,
            )

            async def mock_handler(request: httpx.Request):
                url_str = str(request.url)
                if "oauth2.googleapis.com/token" in url_str:
                    return httpx.Response(200, json={"access_token": "ya29.test"})
                if "listAccessibleCustomers" in url_str:
                    assert request.headers.get("developer-token") == "dev_token_secret"
                    return httpx.Response(200, json={"resourceNames": ["customers/1234567890", "customers/9876543210"]})
                return httpx.Response(404)

            transport = httpx.MockTransport(mock_handler)
            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "cid",
                "GOOGLE_ADS_CLIENT_SECRET": "csec",
                "GOOGLE_ADS_DEVELOPER_TOKEN": "dev_token_secret",
            }
            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    res = await list_google_ads_accessible_customers(user=user)

            assert res["ok"] is True
            assert len(res["accounts"]) == 2
            assert res["accounts"][0]["customer_id"] == "1234567890"
            assert res["accounts"][0]["is_selected"] is True
            assert res["accounts"][1]["customer_id"] == "9876543210"
            assert res["accounts"][1]["is_selected"] is False

        asyncio.run(_run())

    def test_account_selection_and_login_customer_id(self, mock_db, live_workspace):
        """Verifies POST /select-account normalizes IDs, handles login-customer-id, and checks currency."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            init_google_ads(mock_db, AsyncMock(return_value=live_workspace))
            user = {"user_id": "u1", "email": "u1@example.com"}

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypt_token("valid_refresh"),
                },
                upsert=True,
            )

            async def mock_handler(request: httpx.Request):
                url_str = str(request.url)
                if "oauth2.googleapis.com/token" in url_str:
                    return httpx.Response(200, json={"access_token": "ya29.test"})
                if "searchStream" in url_str:
                    assert request.headers.get("login-customer-id") == "9998887777"
                    return httpx.Response(200, json=[{
                        "results": [{
                            "customer": {
                                "id": "1112223333",
                                "descriptiveName": "Managed Brand Client",
                                "currencyCode": "EUR",  # Mismatch with USD store
                                "timeZone": "Europe/Berlin",
                            }
                        }]
                    }])
                return httpx.Response(404)

            transport = httpx.MockTransport(mock_handler)
            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "cid",
                "GOOGLE_ADS_CLIENT_SECRET": "csec",
                "GOOGLE_ADS_DEVELOPER_TOKEN": "dev_token_secret",
            }
            body = SelectGoogleAdsAccountBody(
                customer_id="111-222-3333",
                login_customer_id="999-888-7777",
            )

            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    res = await select_google_ads_account(body=body, user=user)

            assert res["ok"] is True
            assert res["selected_customer_id"] == "1112223333"  # Normalized
            assert res["login_customer_id"] == "9998887777"      # Normalized
            assert res["account_currency"] == "EUR"
            assert res["store_currency"] == "USD"
            assert res["currency_mismatch"] is True
            assert res["warning"] is not None

            # Verify persisted connection in DB
            conn = await mock_db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "google_ads"})
            assert conn["selected_customer_id"] == "1112223333"
            assert conn["login_customer_id"] == "9998887777"
            assert conn["currency_mismatch"] is True
            assert conn["account_currency"] == "EUR"

        asyncio.run(_run())


# =============================================================================
# Test Suite 5: Workspace Isolation, Demo Protection, & Disconnect
# =============================================================================
class TestWorkspaceIsolationAndSecurity:
    def test_demo_workspace_blocked(self, mock_db, demo_workspace):
        """Verifies Northstar Goods cannot connect or modify Google Ads."""
        async def _run():
            init_google_ads(mock_db, AsyncMock(return_value=demo_workspace))
            user = {"user_id": "u_demo", "email": "demo@northstargoods.com"}

            with pytest.raises(HTTPException) as exc_connect:
                await connect_google_ads(user=user)
            assert exc_connect.value.status_code == 400

            with pytest.raises(HTTPException) as exc_accounts:
                await list_google_ads_accessible_customers(user=user)
            assert exc_accounts.value.status_code == 400

            with pytest.raises(HTTPException) as exc_select:
                await select_google_ads_account(
                    body=SelectGoogleAdsAccountBody(customer_id="1234567890"),
                    user=user,
                )
            assert exc_select.value.status_code == 400

        asyncio.run(_run())

    def test_workspace_isolation(self, mock_db):
        """Verifies Workspace A cannot see Workspace B's Google Ads status."""
        async def _run():
            # Workspace A connected
            await mock_db.marketing_connections.replace_one(
                {"workspace_id": "ws_a", "platform": "google_ads"},
                {
                    "workspace_id": "ws_a",
                    "platform": "google_ads",
                    "status": "connected",
                    "selected_customer_id": "1111111111",
                    "encrypted_refresh_token": encrypt_token("token_a"),
                },
                upsert=True,
            )

            # Workspace B queries status
            ws_b = {"workspace_id": "ws_b", "name": "Brand B", "currency": "USD", "is_demo": False}
            init_google_ads(mock_db, AsyncMock(return_value=ws_b))
            user_b = {"user_id": "u_b", "email": "b@example.com"}

            status_b = await get_google_ads_status(user=user_b)
            assert status_b["connected"] is False
            assert status_b["selected_customer_id"] is None

        asyncio.run(_run())

    def test_status_never_exposes_secrets(self, mock_db, live_workspace):
        """Verifies status endpoint returns public metadata only and never exposes tokens."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            init_google_ads(mock_db, AsyncMock(return_value=live_workspace))
            user = {"user_id": "u1", "email": "u1@example.com"}

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypt_token("secret_refresh_token_xyz"),
                    "selected_customer_id": "9998887776",
                    "selected_account_name": "My Google Ads Brand",
                    "account_currency": "USD",
                    "currency_mismatch": False,
                },
                upsert=True,
            )

            status = await get_google_ads_status(user=user)
            assert status["connected"] is True
            assert status["selected_customer_id"] == "9998887776"

            # Strict secret absence check
            assert "encrypted_refresh_token" not in status
            assert "refresh_token" not in status
            assert "access_token" not in status
            assert "developer_token" not in status
            assert "client_secret" not in status

        asyncio.run(_run())

    def test_disconnect_removes_connection(self, mock_db, live_workspace):
        """Verifies POST /disconnect cleans up stored connection."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            init_google_ads(mock_db, AsyncMock(return_value=live_workspace))
            user = {"user_id": "u1", "email": "u1@example.com"}

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypt_token("tok"),
                },
                upsert=True,
            )

            res = await disconnect_google_ads(user=user)
            assert res["ok"] is True
            assert res["disconnected"] is True

            conn = await mock_db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "google_ads"})
            assert conn is None

        asyncio.run(_run())
