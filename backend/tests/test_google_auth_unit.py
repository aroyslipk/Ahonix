"""Unit tests for Google OAuth User Authentication Flow.

Tests:
1. Configuration resolution and fallbacks (GOOGLE_CLIENT_ID, GOOGLE_ADS_CLIENT_ID).
2. /api/auth/google/login: CSRF state generation, redirect URL construction, and missing config handling.
3. /api/auth/google/callback: State validation, token exchange, user creation/login, cookie assignment, and redirection.
4. /api/auth/session: Internal user_sessions lookup and fallback.
"""
import sys
from pathlib import Path
import os
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from starlette.requests import Request

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import auth
from auth import (
    get_google_auth_config,
    google_login,
    google_callback,
    google_session,
    init_auth,
)


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

    async def insert_one(self, doc):
        d = dict(doc)
        self.docs.append(d)
        return MagicMock(inserted_id=d.get("_id", "mock_id"))

    async def replace_one(self, filter_query, doc, upsert=False):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                self.docs[idx] = dict(doc)
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            self.docs.append(dict(doc))
            return MagicMock(matched_count=0, modified_count=0, upserted_id="mock_upsert")
        return MagicMock(matched_count=0, modified_count=0)

    async def update_one(self, filter_query, update, upsert=False):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    self.docs[idx].update(update["$set"])
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            new_doc = dict(filter_query)
            if "$set" in update:
                new_doc.update(update["$set"])
            self.docs.append(new_doc)
            return MagicMock(matched_count=0, modified_count=0, upserted_id="mock_upsert")
        return MagicMock(matched_count=0, modified_count=0)

    async def delete_one(self, filter_query):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                self.docs.pop(idx)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)


class MockDatabase:
    def __init__(self):
        self.users = MockCollection("users")
        self.user_sessions = MockCollection("user_sessions")
        self.google_auth_states = MockCollection("google_auth_states")


@pytest.fixture
def mock_db():
    db = MockDatabase()
    init_auth(db)
    return db


def make_mock_request(query_params=None, headers=None, json_body=None):
    scope = {
        "type": "http",
        "method": "GET" if json_body is None else "POST",
        "query_string": "&".join(f"{k}={v}" for k, v in (query_params or {}).items()).encode("utf-8"),
        "headers": [(k.lower().encode("utf-8"), v.encode("utf-8")) for k, v in (headers or {}).items()],
    }
    req = Request(scope)
    if json_body is not None:
        async def mock_json():
            return json_body
        req.json = mock_json
    return req


class TestGoogleAuthConfig:
    def test_config_explicit_google_client(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "explicit-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "explicit-secret")
        monkeypatch.setenv("FRONTEND_URL", "https://ahonix-staging-frontend.onrender.com")
        monkeypatch.setenv("APP_URL", "https://ahonix-staging-backend.onrender.com")
        monkeypatch.setenv("GOOGLE_AUTH_REDIRECT_URI", "https://ahonix-staging-backend.onrender.com/api/auth/google/callback")

        cfg = get_google_auth_config()
        assert cfg["client_id"] == "explicit-client-id"
        assert cfg["client_secret"] == "explicit-secret"
        assert cfg["redirect_uri"] == "https://ahonix-staging-backend.onrender.com/api/auth/google/callback"
        assert cfg["frontend_url"] == "https://ahonix-staging-frontend.onrender.com"

    def test_config_fallback_to_google_ads_client(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "ads-client-id")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "ads-secret")

        cfg = get_google_auth_config()
        assert cfg["client_id"] == "ads-client-id"
        assert cfg["client_secret"] == "ads-secret"


class TestGoogleLoginEndpoint:
    def test_login_missing_client_id_raises_503(self, mock_db, monkeypatch):
        async def _run():
            monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
            monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)

            req = make_mock_request()
            with pytest.raises(HTTPException) as exc:
                await google_login(req)
            assert exc.value.status_code == 503

        asyncio.run(_run())

    def test_login_generates_state_and_redirects(self, mock_db, monkeypatch):
        async def _run():
            monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
            monkeypatch.setenv("GOOGLE_AUTH_REDIRECT_URI", "https://ahonix-staging-backend.onrender.com/api/auth/google/callback")

            req = make_mock_request()
            resp = await google_login(req, redirect="/app/overview")

            assert isinstance(resp, RedirectResponse)
            assert resp.status_code == 302
            assert "accounts.google.com/o/oauth2/v2/auth" in resp.headers["location"]
            assert "client_id=test-client-id.apps.googleusercontent.com" in resp.headers["location"]
            assert "redirect_uri=https%3A%2F%2Fahonix-staging-backend.onrender.com%2Fapi%2Fauth%2Fgoogle%2Fcallback" in resp.headers["location"]

            # Verify state in DB
            assert len(mock_db.google_auth_states.docs) == 1
            state_doc = mock_db.google_auth_states.docs[0]
            assert state_doc["redirect"] == "/app/overview"

        asyncio.run(_run())


class TestGoogleCallbackEndpoint:
    def test_callback_handles_google_error(self, mock_db, monkeypatch):
        async def _run():
            monkeypatch.setenv("FRONTEND_URL", "https://ahonix-staging-frontend.onrender.com")
            req = make_mock_request(query_params={"error": "access_denied"})
            resp = await google_callback(req)

            assert isinstance(resp, RedirectResponse)
            assert resp.headers["location"] == "https://ahonix-staging-frontend.onrender.com/login?error=access_denied"

        asyncio.run(_run())

    def test_callback_handles_invalid_state(self, mock_db, monkeypatch):
        async def _run():
            monkeypatch.setenv("FRONTEND_URL", "https://ahonix-staging-frontend.onrender.com")
            req = make_mock_request(query_params={"code": "test_code", "state": "unknown_state"})
            resp = await google_callback(req)

            assert isinstance(resp, RedirectResponse)
            assert resp.headers["location"] == "https://ahonix-staging-frontend.onrender.com/login?error=invalid_state"

        asyncio.run(_run())

    def test_callback_success_creates_user_and_session(self, mock_db, monkeypatch):
        async def _run():
            monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
            monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
            monkeypatch.setenv("FRONTEND_URL", "https://ahonix-staging-frontend.onrender.com")
            monkeypatch.setenv("APP_URL", "https://ahonix-staging-backend.onrender.com")

            # Insert valid state
            test_state = "valid-csrf-token"
            await mock_db.google_auth_states.insert_one({
                "state": test_state,
                "redirect": "/app/overview",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            })

            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {"access_token": "mock-google-token"}

            mock_userinfo_resp = MagicMock()
            mock_userinfo_resp.status_code = 200
            mock_userinfo_resp.json.return_value = {
                "email": "testmerchant@example.com",
                "name": "Alex Merchant",
                "picture": "https://example.com/avatar.jpg",
            }

            with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_token_resp)), \
                 patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_userinfo_resp)):
                req = make_mock_request(query_params={"code": "valid_code", "state": test_state})
                resp = await google_callback(req)

            assert isinstance(resp, RedirectResponse)
            assert resp.status_code == 302
            assert resp.headers["location"].startswith("https://ahonix-staging-frontend.onrender.com/app/overview#session_id=")

            # User in DB
            user = await mock_db.users.find_one({"email": "testmerchant@example.com"})
            assert user is not None
            assert user["name"] == "Alex Merchant"
            assert user["auth_provider"] == "google"

            # Session in DB
            sess = await mock_db.user_sessions.find_one({"user_id": user["user_id"]})
            assert sess is not None
            assert sess["email"] == "testmerchant@example.com"

            # Cookie in response
            cookie_headers = [v for k, v in resp.raw_headers if k.decode().lower() == "set-cookie"]
            cookie_str = " ".join(c.decode() for c in cookie_headers)
            assert "access_token=" in cookie_str
            assert "session_token=" in cookie_str

        asyncio.run(_run())


class TestSessionEndpoint:
    def test_session_resolves_from_user_sessions(self, mock_db):
        async def _run():
            user_id = "user_test123"
            await mock_db.users.insert_one({
                "user_id": user_id,
                "email": "stored@example.com",
                "name": "Stored User",
                "auth_provider": "google",
                "onboarding_completed": True,
                "active_workspace_id": "ws_123",
            })
            session_token = "sess_abc123xyz"
            await mock_db.user_sessions.insert_one({
                "session_token": session_token,
                "user_id": user_id,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            })

            req = make_mock_request(json_body={"session_id": session_token})
            resp = MagicMock()
            resp.set_cookie = MagicMock()

            user_data = await google_session(req, resp)
            assert user_data["email"] == "stored@example.com"
            assert user_data["user_id"] == user_id
            assert resp.set_cookie.called

        asyncio.run(_run())
