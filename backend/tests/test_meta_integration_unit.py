"""Unit and Security Tests for Phase 5.1: Meta Ads OAuth & Ad Account Connection.

Coverage:
1. Configurable Meta API Version:
   - Verification that version is configurable via META_API_VERSION env variable (not hardcoded).
   - Version cleaning and normalization ('21.0' -> 'v21.0', empty -> 'v21.0').
2. App Secret Proof Calculation:
   - Cryptographic HMAC-SHA256 digest calculation.
3. OAuth 2.0 Connect Flow:
   - State CSRF generation and persistence with 900s TTL.
   - Correct dialog URL generation with client_id, scopes, redirect_uri, and state.
4. Callback & Token Security:
   - Invalid state rejection.
   - Expired state rejection.
   - Consuming state nonce (single-use).
   - Short-lived token exchange & 60-day long-lived token exchange.
   - AES-256-GCM token encryption at rest.
5. Zero Secret Exposure:
   - Status responses never leak access tokens, ciphertexts, or app secrets.
6. Ad Account Discovery:
   - Calling /me/adaccounts with token and appsecret_proof.
   - Handling expired/revoked tokens (OAuthException) with status="reauth_required" and HTTP 401.
7. Ad Account Selection & Currency Mismatch:
   - Normalizing account ID (ensuring 'act_' prefix).
   - Detecting currency mismatch (e.g. EUR ad account vs USD store).
   - Never allowing incompatible currencies to be blindly blended.
8. Safe Disconnection:
   - Cleaning up stored connection.
9. Workspace Isolation:
   - Workspace A cannot view or mutate Workspace B's Meta connection.
10. Demo Workspace Protection:
   - Northstar Goods mutations blocked with HTTP 400.
"""
import sys
from pathlib import Path
import os
import hmac
import hashlib
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import meta_integration
from meta_integration import (
    clean_meta_api_version,
    get_meta_config,
    generate_appsecret_proof,
    connect_meta,
    meta_callback,
    get_meta_status,
    list_meta_ad_accounts,
    select_meta_ad_account,
    disconnect_meta,
    SelectMetaAccountBody,
    DEFAULT_META_API_VERSION,
    init_meta,
)
from shopify_integration import encrypt_token, decrypt_token


# --- Mock Async DB Engine ---------------------------------------------------
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
                matched.append(d)
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
        self.docs = [
            d for d in self.docs
            if not all(d.get(k) == v for k, v in filter_query.items())
        ]


class MockDatabase:
    def __init__(self):
        self.marketing_connections = MockCollection("marketing_connections")
        self.meta_oauth_states = MockCollection("meta_oauth_states")
        self.workspaces = MockCollection("workspaces")


# --- Test Suite --------------------------------------------------------------
class TestMetaApiVersionAndSecurity:
    def test_version_normalization(self):
        assert clean_meta_api_version("21.0") == "v21.0"
        assert clean_meta_api_version("v21.0") == "v21.0"
        assert clean_meta_api_version("V20.0") == "v20.0"
        assert clean_meta_api_version("") == DEFAULT_META_API_VERSION
        assert clean_meta_api_version(None) == DEFAULT_META_API_VERSION

    def test_version_configurable_via_env(self):
        with patch.dict(os.environ, {"META_API_VERSION": "v22.0"}):
            cfg = get_meta_config()
            assert cfg["api_version"] == "v22.0"

        with patch.dict(os.environ, {"META_API_VERSION": "23.0"}):
            cfg2 = get_meta_config()
            assert cfg2["api_version"] == "v23.0"

    def test_appsecret_proof_calculation(self):
        token = "EAABtest_token_12345"
        secret = "app_secret_test_xyz"
        expected = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()

        proof = generate_appsecret_proof(token, secret)
        assert proof == expected
        assert generate_appsecret_proof("", secret) == ""
        assert generate_appsecret_proof(token, "") == ""


class TestMetaOAuthLifecycle:
    def test_connect_generates_valid_url_and_persists_state(self):
        async def _run():
            db = MockDatabase()
            ws_id = "ws_meta_test_1"
            ws = {"workspace_id": ws_id, "name": "Live Store", "is_demo": False}
            user = {"user_id": "usr_meta_1", "email": "merchant@test.com"}

            async def _get_ws(u):
                return ws

            init_meta(db, _get_ws)

            with patch.dict(os.environ, {
                "META_APP_ID": "1234567890",
                "META_APP_SECRET": "meta_sec_999",
                "META_API_VERSION": "v21.0",
                "APP_URL": "https://ahonix.example.com",
            }):
                res = await connect_meta(user)
                assert res["ok"] is True
                auth_url = res["auth_url"]
                assert "client_id=1234567890" in auth_url
                assert "scope=ads_read,read_insights" in auth_url
                assert "state=" in auth_url
                assert "facebook.com/v21.0/dialog/oauth" in auth_url

                # Check state persisted
                saved_state = await db.meta_oauth_states.find_one({"state": res["state"]})
                assert saved_state is not None
                assert saved_state["workspace_id"] == ws_id
                assert saved_state["user_id"] == user["user_id"]

        asyncio.run(_run())

    def test_callback_rejects_invalid_or_expired_state(self):
        async def _run():
            db = MockDatabase()
            init_meta(db, AsyncMock())

            # 1. Invalid state
            req_invalid = MagicMock()
            req_invalid.query_params = {"code": "test_code", "state": "unknown_state_nonce"}
            res_invalid = await meta_callback(req_invalid)
            assert isinstance(res_invalid, RedirectResponse)
            assert "meta_error=invalid_state" in res_invalid.headers["location"]

            # 2. Expired state
            expired_state = "expired_nonce_123"
            now_utc = datetime.now(timezone.utc)
            db.meta_oauth_states.docs.append({
                "state": expired_state,
                "workspace_id": "ws_1",
                "user_id": "u_1",
                "expires_at": (now_utc - timedelta(seconds=10)).isoformat(),
            })
            req_expired = MagicMock()
            req_expired.query_params = {"code": "test_code", "state": expired_state}
            res_expired = await meta_callback(req_expired)
            assert isinstance(res_expired, RedirectResponse)
            assert "meta_error=expired_state" in res_expired.headers["location"]

        asyncio.run(_run())

    def test_callback_exchanges_tokens_and_encrypts_at_rest(self):
        async def _run():
            db = MockDatabase()
            ws_id = "ws_meta_cb"
            user_id = "usr_cb"
            init_meta(db, AsyncMock())

            state = "valid_meta_state_nonce"
            now_utc = datetime.now(timezone.utc)
            db.meta_oauth_states.docs.append({
                "state": state,
                "workspace_id": ws_id,
                "user_id": user_id,
                "expires_at": (now_utc + timedelta(seconds=600)).isoformat(),
            })

            req = MagicMock()
            req.query_params = {"code": "auth_code_from_fb", "state": state}

            # Mock short-lived and long-lived token responses
            short_lived_res = MagicMock()
            short_lived_res.status_code = 200
            short_lived_res.json.return_value = {
                "access_token": "EAA_short_lived_12345",
                "token_type": "bearer",
            }

            long_lived_res = MagicMock()
            long_lived_res.status_code = 200
            long_lived_res.json.return_value = {
                "access_token": "EAA_long_lived_60_days_67890",
                "token_type": "bearer",
                "expires_in": 5184000,  # 60 days
            }

            with patch.dict(os.environ, {
                "META_APP_ID": "111222333",
                "META_APP_SECRET": "fb_secret_abc",
                "META_API_VERSION": "v21.0",
            }):
                with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                    mock_get.side_effect = [short_lived_res, long_lived_res]
                    res = await meta_callback(req)

            assert isinstance(res, RedirectResponse)
            assert "meta=connected" in res.headers["location"]

            # Verify single-use state nonce was consumed
            consumed = await db.meta_oauth_states.find_one({"state": state})
            assert consumed is None

            # Verify connection stored in db.marketing_connections
            conn = await db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
            assert conn is not None
            assert conn["status"] == "connected"
            assert conn["api_version"] == "v21.0"
            # Access token must be encrypted (never plaintext)
            assert "EAA_long_lived" not in conn["encrypted_access_token"]
            decrypted = decrypt_token(conn["encrypted_access_token"])
            assert decrypted == "EAA_long_lived_60_days_67890"

        asyncio.run(_run())


class TestMetaStatusAndAccountSelection:
    def test_status_never_exposes_secrets_or_tokens(self):
        async def _run():
            db = MockDatabase()
            ws_id = "ws_status_sec"
            user = {"user_id": "u_1", "active_workspace_id": ws_id}
            ws = {"workspace_id": ws_id, "name": "Store", "is_demo": False}

            async def _get_ws(u):
                return ws

            init_meta(db, _get_ws)

            # Insert connected record with encrypted token
            db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": encrypt_token("secret_token_12345"),
                "selected_account_id": "act_998877",
                "selected_account_name": "My Main Ads",
                "account_currency": "USD",
                "currency_mismatch": False,
                "last_sync_at": None,
            })

            status = await get_meta_status(user)
            assert status["connected"] is True
            assert status["platform"] == "meta"
            assert status["selected_account_id"] == "act_998877"
            assert status["selected_account_name"] == "My Main Ads"

            # ZERO SECRET EXPOSURE:
            assert "encrypted_access_token" not in status
            assert "access_token" not in status
            assert "app_secret" not in status

        asyncio.run(_run())

    def test_list_ad_accounts_and_reauth_on_expired_token(self):
        async def _run():
            db = MockDatabase()
            ws_id = "ws_act_list"
            user = {"user_id": "u_2", "active_workspace_id": ws_id}
            ws = {"workspace_id": ws_id, "currency": "USD", "is_demo": False}

            async def _get_ws(u):
                return ws

            init_meta(db, _get_ws)

            db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": encrypt_token("tok_abc"),
                "api_version": "v21.0",
            })

            # 1. Successful account listing with appsecret_proof
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": [
                    {"id": "act_101", "account_id": "101", "name": "US DTC", "currency": "USD", "timezone_name": "America/New_York", "account_status": 1},
                    {"id": "act_102", "account_id": "102", "name": "EU Brand", "currency": "EUR", "timezone_name": "Europe/Berlin", "account_status": 1},
                ]
            }

            with patch.dict(os.environ, {"META_APP_SECRET": "sec_123"}):
                with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                    mock_get.return_value = mock_resp
                    res = await list_meta_ad_accounts(user)

            assert res["ok"] is True
            assert len(res["accounts"]) == 2
            assert res["accounts"][0]["id"] == "act_101"
            assert res["accounts"][0]["currency_mismatch"] is False  # USD == USD
            assert res["accounts"][1]["currency_mismatch"] is True   # EUR != USD

            # 2. Token revoked / expired handling (OAuthException code 190)
            mock_revoked_resp = MagicMock()
            mock_revoked_resp.status_code = 400
            mock_revoked_resp.json.return_value = {
                "error": {
                    "message": "Error validating access token: Session has expired.",
                    "type": "OAuthException",
                    "code": 190,
                }
            }

            with patch.dict(os.environ, {"META_APP_SECRET": "sec_123"}):
                with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                    mock_get.return_value = mock_revoked_resp
                    with pytest.raises(HTTPException) as exc_info:
                        await list_meta_ad_accounts(user)

            assert exc_info.value.status_code == 401
            assert "expired or revoked" in exc_info.value.detail.lower()

            # Connection status in DB must transition to reauth_required
            conn_after = await db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
            assert conn_after["status"] == "reauth_required"

        asyncio.run(_run())

    def test_account_selection_currency_mismatch_protection(self):
        """User Requirement 6: If ad account currency != Shopify currency,
        clearly mark financial aggregation as currency-mismatch / unavailable;
        never add incompatible currencies directly."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_curr_test"
            user = {"user_id": "u_3", "active_workspace_id": ws_id}
            # Workspace store currency is USD
            ws = {"workspace_id": ws_id, "currency": "USD", "is_demo": False}

            async def _get_ws(u):
                return ws

            init_meta(db, _get_ws)

            db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": encrypt_token("tok_curr"),
                "api_version": "v21.0",
            })

            # Mock account validation returning EUR
            mock_act_eur = MagicMock()
            mock_act_eur.status_code = 200
            mock_act_eur.json.return_value = {
                "id": "act_888999",
                "name": "European Campaigns",
                "currency": "EUR",
                "timezone_name": "Europe/London",
            }

            with patch.dict(os.environ, {"META_APP_SECRET": "sec_123"}):
                with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                    mock_get.return_value = mock_act_eur
                    sel_res = await select_meta_ad_account(
                        body=SelectMetaAccountBody(account_id="888999", account_name="European Campaigns"),
                        user=user,
                    )

            assert sel_res["ok"] is True
            assert sel_res["selected_account_id"] == "act_888999"
            assert sel_res["account_currency"] == "EUR"
            assert sel_res["store_currency"] == "USD"
            assert sel_res["currency_mismatch"] is True
            assert sel_res["warning"] is not None
            assert "inaccurate financial calculations" in sel_res["warning"]

            # Check DB record has currency_mismatch: True
            conn_db = await db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
            assert conn_db["currency_mismatch"] is True
            assert conn_db["account_currency"] == "EUR"

        asyncio.run(_run())

    def test_disconnect_removes_connection(self):
        async def _run():
            db = MockDatabase()
            ws_id = "ws_dis_test"
            user = {"user_id": "u_dis", "active_workspace_id": ws_id}
            ws = {"workspace_id": ws_id, "is_demo": False}

            async def _get_ws(u):
                return ws

            init_meta(db, _get_ws)

            db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": encrypt_token("tok_dis"),
            })

            dis_res = await disconnect_meta(user)
            assert dis_res["ok"] is True
            assert dis_res["disconnected"] is True

            # Must be deleted from DB
            conn = await db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
            assert conn is None

        asyncio.run(_run())


class TestWorkspaceIsolationAndDemoProtection:
    def test_workspace_isolation_meta(self):
        async def _run():
            db = MockDatabase()
            ws_a = "ws_brand_alpha"
            ws_b = "ws_brand_beta"
            user_a = {"user_id": "u_a", "active_workspace_id": ws_a}
            ws_a_doc = {"workspace_id": ws_a, "currency": "USD", "is_demo": False}

            async def _get_ws(u):
                return ws_a_doc

            init_meta(db, _get_ws)

            # Store B has Meta connected
            db.marketing_connections.docs.append({
                "workspace_id": ws_b,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": encrypt_token("tok_beta"),
            })

            # User A checks status -> disconnected (cannot see B)
            status_a = await get_meta_status(user_a)
            assert status_a["connected"] is False

            # User A attempts to list accounts -> fails (400)
            with pytest.raises(HTTPException) as exc_info:
                await list_meta_ad_accounts(user_a)
            assert exc_info.value.status_code == 400

        asyncio.run(_run())

    def test_demo_workspace_mutations_blocked(self):
        async def _run():
            db = MockDatabase()
            demo_ws = {"workspace_id": "ws_demo_northstar", "name": "Northstar Goods", "is_demo": True}
            user_admin = {"user_id": "u_admin", "active_workspace_id": "ws_demo_northstar"}

            async def _get_ws(u):
                return demo_ws

            init_meta(db, _get_ws)

            # Connect blocked
            with pytest.raises(HTTPException) as exc_conn:
                await connect_meta(user_admin)
            assert exc_conn.value.status_code == 400
            assert "demo workspace northstar goods" in exc_conn.value.detail.lower()

            # Select account blocked
            with pytest.raises(HTTPException) as exc_sel:
                await select_meta_ad_account(SelectMetaAccountBody(account_id="act_123"), user_admin)
            assert exc_sel.value.status_code == 400

            # Status returns is_demo=True, connected=False
            st = await get_meta_status(user_admin)
            assert st["connected"] is False
            assert st["is_demo"] is True

        asyncio.run(_run())
