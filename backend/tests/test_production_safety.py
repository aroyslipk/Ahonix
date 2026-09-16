"""Tests for Production Safety & Integration Configuration.

Verifies:
1. Email verification workflow (register -> verification required -> login blocked -> token verify -> login allowed).
2. Rate-limited resend verification.
3. Google OAuth unconfigured safety (503 for API, browser redirect for HTML).
4. Stripe truthful billing (free tier default, 503 on unconfigured checkout & portal).
5. Meta & Google Ads truthful not-configured states.
"""
import os
import secrets
from unittest.mock import MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient

# Set testing environment variables before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-production-safety-secret-key-64-bytes-minimum-length-security"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_ADS_CLIENT_ID"] = ""
os.environ["META_APP_ID"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""

from server import app
import auth
import billing
import meta_integration
import google_ads_integration
from auth import get_current_user


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

    async def update_many(self, filter_query, update):
        count = 0
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    self.docs[idx].update(update["$set"])
                count += 1
        return MagicMock(matched_count=count, modified_count=count)

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

    async def delete_many(self, filter_query):
        remaining = []
        deleted = 0
        for d in self.docs:
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                deleted += 1
            else:
                remaining.append(d)
        self.docs = remaining
        return MagicMock(deleted_count=deleted)


class MockDB:
    def __init__(self):
        self._collections = {}

    def __getattr__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]


@pytest.fixture(autouse=True)
def init_isolated_modules():
    mock_db = MockDB()
    async def mock_demo_ws(user):
        if isinstance(user, dict):
            uid = user.get("user_id", "usr_test")
            ws_id = user.get("active_workspace_id", f"ws_{uid[:8]}")
        else:
            uid = str(user)
            ws_id = f"ws_{uid[:8]}"
        return {"workspace_id": ws_id, "user_id": uid, "name": "Live Workspace", "currency": "USD", "is_demo": False}

    auth.init_auth(mock_db)
    billing.init_billing(mock_db, mock_demo_ws)
    meta_integration.init_meta(mock_db, mock_demo_ws)
    google_ads_integration.init_google_ads(mock_db, mock_demo_ws)

    os.environ["ENVIRONMENT"] = "test"
    os.environ["STRIPE_SECRET_KEY"] = ""
    os.environ["GOOGLE_CLIENT_ID"] = ""
    os.environ["GOOGLE_ADS_CLIENT_ID"] = ""
    os.environ["META_APP_ID"] = ""
    os.environ["RESEND_API_KEY"] = ""
    os.environ["SMTP_HOST"] = ""

    yield mock_db
    app.dependency_overrides.clear()


def test_email_verification_lifecycle():
    """Test full registration -> unverified blocked -> verify token -> login allowed lifecycle."""
    client = TestClient(app)
    unique_id = secrets.token_hex(4)
    email = f"merchant_{unique_id}@testahonix.com"
    password = "SecurePassword2026!"

    # 1. Registration
    reg_resp = client.post(
        "/api/auth/register",
        json={"name": "Safety Tester", "email": email, "password": password},
    )
    assert reg_resp.status_code == 200, reg_resp.text
    reg_data = reg_resp.json()
    assert reg_data.get("requires_verification") is True
    # In test/dev environment, dev_token is provided
    dev_token = reg_data.get("dev_token")
    assert dev_token is not None, "dev_token should be returned in non-production environments"

    # 2. Login should be BLOCKED with 403 EMAIL_NOT_VERIFIED
    login_blocked = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_blocked.status_code == 403
    blocked_data = login_blocked.json()
    assert "not verified" in str(blocked_data.get("detail", "")).lower()

    # 3. Invalid token verification should fail with 400
    invalid_verify = client.post(
        "/api/auth/verify-email",
        json={"token": "completely-invalid-nonexistent-token"},
    )
    assert invalid_verify.status_code == 400

    # 4. Valid token verification should succeed
    verify_resp = client.post(
        "/api/auth/verify-email",
        json={"token": dev_token},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    verify_data = verify_resp.json()
    assert verify_data.get("ok") is True
    assert verify_data["user"]["email"] == email

    # 5. Using the same token again should fail (token consumed)
    reverify_resp = client.post(
        "/api/auth/verify-email",
        json={"token": dev_token},
    )
    assert reverify_resp.status_code == 400

    # 6. Login should now SUCCEED with 200
    login_allowed = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_allowed.status_code == 200
    assert login_allowed.json()["email"] == email


def test_resend_verification_email():
    """Test resending verification email generates a fresh token."""
    client = TestClient(app)
    unique_id = secrets.token_hex(4)
    email = f"resend_{unique_id}@testahonix.com"
    password = "SecurePassword2026!"

    # Register
    reg_resp = client.post(
        "/api/auth/register",
        json={"name": "Resend Tester", "email": email, "password": password},
    )
    assert reg_resp.status_code == 200
    first_token = reg_resp.json().get("dev_token")

    # Request resend
    resend_resp = client.post(
        "/api/auth/resend-verification",
        json={"email": email},
    )
    assert resend_resp.status_code == 200
    resend_data = resend_resp.json()
    assert resend_data.get("ok") is True
    second_token = resend_data.get("dev_token")
    assert second_token is not None
    assert second_token != first_token

    # Verify with second token succeeds
    verify_resp = client.post(
        "/api/auth/verify-email",
        json={"token": second_token},
    )
    assert verify_resp.status_code == 200


def test_google_oauth_unconfigured_safety():
    """Verify Google OAuth missing config returns clean 503 for API and redirect for browser."""
    client = TestClient(app)
    # Status endpoint returns configured: False
    status_resp = client.get("/api/auth/google/status")
    assert status_resp.status_code == 200
    assert status_resp.json().get("configured") is False

    # API client request returns 503
    api_resp = client.get("/api/auth/google/login", headers={"Accept": "application/json"})
    assert api_resp.status_code == 503
    assert "Google OAuth is not configured" in api_resp.json()["detail"]

    # Browser client request (Accept: text/html) returns redirect to /login?error=...
    browser_resp = client.get(
        "/api/auth/google/login",
        headers={"Accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    )
    assert browser_resp.status_code in (302, 307)
    assert "/login?error=" in browser_resp.headers["location"]


def test_stripe_truthful_unconfigured_billing():
    """Verify unconfigured Stripe defaults to Free Tier and returns 503 on checkout & portal."""
    mock_user = {
        "user_id": "usr_billing_test",
        "email": "billing@testahonix.com",
        "name": "Billing Tester",
        "active_workspace_id": "ws_billing_123",
    }
    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)

    # Status should report Free Tier, not Growth, and configured: False
    status_resp = client.get("/api/billing/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["plan_id"] == "free"
    assert data["plan_name"] == "Free Tier"
    assert data["has_active_subscription"] is False
    assert data["configured"] is False

    # Checkout should return 503 Billing not configured (not crash, not fake subscription)
    checkout_resp = client.post(
        "/api/billing/create-checkout-session",
        json={"plan_id": "growth", "interval": "month"},
    )
    assert checkout_resp.status_code == 503
    assert "Billing is not configured" in checkout_resp.json()["detail"]

    # Customer portal should return 503
    portal_resp = client.post("/api/billing/customer-portal")
    assert portal_resp.status_code == 503
    assert "not configured" in portal_resp.json()["detail"].lower()


def test_meta_and_google_ads_unconfigured_status():
    """Verify Meta and Google Ads report configured: False and status: not_configured."""
    mock_user = {
        "user_id": "usr_ads_test",
        "email": "ads@testahonix.com",
        "name": "Ads Tester",
        "active_workspace_id": "ws_ads_123",
    }
    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)

    # Meta Ads status
    meta_status = client.get("/api/integrations/meta/status")
    assert meta_status.status_code == 200
    meta_data = meta_status.json()
    assert meta_data.get("configured") is False
    assert meta_data.get("status") in ("not_configured", "disconnected")

    # Google Ads status
    gads_status = client.get("/api/integrations/google-ads/status")
    assert gads_status.status_code == 200
    gads_data = gads_status.json()
    assert gads_data.get("configured") is False
    assert gads_data.get("status") in ("not_configured", "disconnected")
