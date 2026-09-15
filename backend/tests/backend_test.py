"""AHONIX backend API test suite."""
import os
import time
import uuid
import json
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ahonix-staging-backend.onrender.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "alex@northstargoods.com"
ADMIN_PASSWORD = "Ahonix2026!"


def is_live_server_reachable():
    try:
        r = requests.get(f"{API}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_live_server_reachable(),
    reason=f"Live backend server at {API} is not reachable. Set REACT_APP_BACKEND_URL to run live integration tests.",
)


# --- shared fixtures ---------------------------------------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def new_user():
    """Register a fresh user (no workspace)."""
    s = requests.Session()
    email = f"TEST_{uuid.uuid4().hex[:8]}@ahonix-test.com"
    password = "TestPass123!"
    r = s.post(f"{API}/auth/register", json={"name": "Test User", "email": email, "password": password})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {"session": s, "email": email, "password": password, "user": data}


# --- Auth --------------------------------------------------------------------
class TestAuth:
    def test_me_without_cookies_returns_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_register_returns_user_and_sets_cookies(self):
        s = requests.Session()
        email = f"TEST_{uuid.uuid4().hex[:8]}@ahonix-test.com"
        r = s.post(f"{API}/auth/register", json={"name": "Reg User", "email": email, "password": "abc123!"})
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == email.lower()
        assert data["onboarding_completed"] is False
        assert data["active_workspace_id"] is None
        assert "access_token" in s.cookies
        # /auth/me works with cookies
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == email.lower()

    def test_register_duplicate_rejected(self, new_user):
        r = requests.post(f"{API}/auth/register",
                          json={"name": "x", "email": new_user["email"], "password": "abc123!"})
        assert r.status_code == 400

    def test_login_admin_success(self, admin_session):
        me = admin_session.get(f"{API}/auth/me")
        assert me.status_code == 200
        u = me.json()
        assert u["email"] == ADMIN_EMAIL

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        # clone cookies for a second session to logout
        r2 = s.post(f"{API}/auth/logout")
        assert r2.status_code == 200
        # after logout, /auth/me on same session should be 401 (cookies deleted server-side)
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 401


# --- Onboarding + Workspace + Data isolation ---------------------------------
class TestWorkspaceAndIsolation:
    def test_new_user_has_no_workspace(self, new_user):
        r = new_user["session"].get(f"{API}/overview")
        # Expect 404 (no active workspace) OR empty:true depending on flow
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json().get("empty") is True

    def test_create_demo_workspace(self, new_user):
        r = new_user["session"].post(f"{API}/workspaces", json={
            "name": "Northstar Goods", "business_type": "DTC Brand",
            "channels": ["Shopify"], "size": "1-10", "country": "US",
            "currency": "USD", "mode": "demo"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_demo"] is True
        assert d["workspace_id"].startswith("ws_")

    def test_overview_populated_after_onboarding(self, new_user):
        r = new_user["session"].get(f"{API}/overview")
        assert r.status_code == 200
        d = r.json()
        assert d.get("empty") is False
        assert "kpis" in d and len(d["kpis"]) >= 4
        # KPI structure
        ids = {k["id"] for k in d["kpis"]}
        assert {"revenue", "true-profit", "orders", "aov"}.issubset(ids)
        assert "priorities" in d
        assert "briefing" in d

    def test_data_isolation_admin_vs_new(self, admin_session, new_user):
        r_admin = admin_session.get(f"{API}/overview").json()
        r_new = new_user["session"].get(f"{API}/overview").json()
        # both should have workspaces but different workspace names/ids should not leak.
        # Ensure list workspaces returns only user-owned
        ws_admin = admin_session.get(f"{API}/workspaces").json()["workspaces"]
        ws_new = new_user["session"].get(f"{API}/workspaces").json()["workspaces"]
        admin_ids = {w["workspace_id"] for w in ws_admin}
        new_ids = {w["workspace_id"] for w in ws_new}
        assert admin_ids.isdisjoint(new_ids)
        # try selecting admin's workspace from new user -> should 404
        if ws_admin:
            r = new_user["session"].post(f"{API}/workspaces/{list(admin_ids)[0]}/select")
            assert r.status_code == 404


# --- Analytics section endpoints ---------------------------------------------
SECTIONS = ["overview", "intelligence", "profit", "sales", "products",
            "inventory", "returns", "marketing", "customers", "operations",
            "markets", "actions"]


class TestAnalyticsSections:
    @pytest.mark.parametrize("section", SECTIONS)
    def test_section_returns_200_and_data(self, admin_session, section):
        r = admin_session.get(f"{API}/{section}")
        assert r.status_code == 200, f"{section}: {r.status_code} {r.text[:200]}"
        d = r.json()
        # for admin (has workspace), should not be empty
        assert d.get("empty") is False, f"{section} returned empty"
        assert "workspace" in d

    def test_product_detail(self, admin_session):
        products = admin_session.get(f"{API}/products").json()["products"]
        assert len(products) > 0
        pid = products[0]["id"]
        r = admin_session.get(f"{API}/products/{pid}")
        assert r.status_code == 200
        assert r.json()["product"]["id"] == pid

    def test_product_detail_not_found(self, admin_session):
        r = admin_session.get(f"{API}/products/nonexistent-xyz")
        assert r.status_code == 404


# --- Metric consistency ------------------------------------------------------
class TestMetricConsistency:
    def test_overview_profit_matches_profit_endpoint(self, admin_session):
        ov = admin_session.get(f"{API}/overview").json()
        pf = admin_session.get(f"{API}/profit").json()
        overview_profit = next(k["value"] for k in ov["kpis"] if k["id"] == "true-profit")
        profit_value = pf["profit"]["true_profit"] if "true_profit" in pf["profit"] else pf["profit"].get("steps", [{}])[-1].get("value")
        # allow small numeric difference (within 5% or 10 units)
        diff = abs(float(overview_profit) - float(profit_value))
        assert diff / max(abs(float(profit_value)), 1) < 0.05 or diff < 10, \
            f"true profit mismatch overview={overview_profit} profit={profit_value}"

    def test_overview_revenue_matches_sales(self, admin_session):
        ov = admin_session.get(f"{API}/overview").json()
        sl = admin_session.get(f"{API}/sales").json()
        rev_overview = next(k["value"] for k in ov["kpis"] if k["id"] == "revenue")
        sales_data = sl["sales"]
        rev_sales = sales_data.get("revenue") or sales_data.get("total_revenue") or \
                    sales_data.get("summary", {}).get("revenue")
        assert rev_sales is not None, f"no revenue in sales: {list(sales_data.keys())}"
        diff = abs(float(rev_overview) - float(rev_sales))
        assert diff / max(abs(float(rev_sales)), 1) < 0.05 or diff < 10


# --- Market simulate ---------------------------------------------------------
class TestMarketSimulate:
    def test_simulate(self, admin_session):
        r = admin_session.post(f"{API}/markets/simulate", json={
            "country": "Germany", "price": 79.0, "demand_units": 500,
            "inventory_units": 400, "marketing_budget": 5000.0
        })
        assert r.status_code == 200, r.text
        assert "result" in r.json()


# --- Action lifecycle --------------------------------------------------------
class TestActionLifecycle:
    def test_action_transitions(self, new_user):
        # Create fresh demo workspace so we always have Detected actions available
        s = new_user["session"]
        # ensure workspace exists
        ws = s.get(f"{API}/workspaces").json()["workspaces"]
        if not ws:
            r = s.post(f"{API}/workspaces", json={"name": "TEST_wsA", "mode": "demo",
                                                  "currency": "USD"})
            assert r.status_code == 200
        actions = s.get(f"{API}/actions").json()["actions"]
        assert len(actions) > 0
        detected = next((a for a in actions if a["stage"] == "Detected"), None)
        assert detected, f"no Detected action available; stages: {[a['stage'] for a in actions]}"
        aid = detected["action_id"]
        for op, expected in [("simulate", "Simulated"), ("approve", "Approved"),
                              ("execute", "Executed"), ("measure", "Measured")]:
            r = s.post(f"{API}/actions/{aid}", json={"op": op})
            assert r.status_code == 200, f"{op}: {r.text}"
            assert r.json()["action"]["stage"] == expected
        # after execute, ensure simulated flag
        final = s.get(f"{API}/actions").json()["actions"]
        act = next(a for a in final if a["action_id"] == aid)
        assert act.get("simulated") is True

    def test_invalid_op(self, admin_session):
        actions = admin_session.get(f"{API}/actions").json()["actions"]
        aid = actions[0]["action_id"]
        r = admin_session.post(f"{API}/actions/{aid}", json={"op": "bogus"})
        assert r.status_code == 400


# --- Ask AHONIX (SSE streaming) ---------------------------------------------
class TestAskAhonix:
    def test_ask_streams_answer(self, admin_session):
        with admin_session.post(f"{API}/ask",
                                json={"question": "What is my best selling product?"},
                                stream=True, timeout=60) as r:
            assert r.status_code == 200
            got_delta = False
            got_done = False
            content = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                if "delta" in payload:
                    got_delta = True
                    content += payload["delta"]
                if "error" in payload:
                    pytest.fail(f"stream error: {payload['error']}")
                if payload.get("done"):
                    got_done = True
                    break
            assert got_delta, "no text deltas received"
            assert got_done, "no done event"
            assert "###" in content or len(content) > 50, "response too short / not markdown"

    def test_ask_empty_question_rejected(self, admin_session):
        """Empty or whitespace-only question should be rejected (422)."""
        r = admin_session.post(f"{API}/ask", json={"question": "   "})
        assert r.status_code == 422, f"Expected 422 for empty question, got {r.status_code}"

    def test_ask_oversized_question_rejected(self, admin_session):
        """Question exceeding max length should be rejected (422)."""
        r = admin_session.post(f"{API}/ask", json={"question": "x" * 5001})
        assert r.status_code == 422, f"Expected 422 for oversized question, got {r.status_code}"


# --- Production Hardening: Input Validation ----------------------------------
class TestInputValidation:
    def test_action_invalid_op_returns_422(self, admin_session):
        """Invalid action op (not in Literal set) should return 422 from Pydantic."""
        actions = admin_session.get(f"{API}/actions").json()["actions"]
        aid = actions[0]["action_id"]
        r = admin_session.post(f"{API}/actions/{aid}", json={"op": "invalid_op"})
        assert r.status_code == 422, f"Expected 422, got {r.status_code}"

    def test_simulate_negative_price_rejected(self, admin_session):
        """Negative price in market simulation should be rejected (422)."""
        r = admin_session.post(f"{API}/markets/simulate", json={
            "country": "Germany", "price": -10.0, "demand_units": 500,
            "inventory_units": 400, "marketing_budget": 5000.0
        })
        assert r.status_code == 422

    def test_workspace_invalid_mode_rejected(self, admin_session):
        """Workspace mode not in Literal['demo','real'] should be rejected (422)."""
        r = admin_session.post(f"{API}/workspaces", json={
            "name": "Test", "mode": "invalid_mode"
        })
        assert r.status_code == 422

    def test_register_password_too_short(self):
        """Password under 6 chars should be rejected."""
        r = requests.post(f"{API}/auth/register", json={
            "name": "Short PW", "email": f"TEST_{uuid.uuid4().hex[:8]}@ahonix-test.com",
            "password": "abc"
        })
        assert r.status_code in (400, 422)

    def test_register_name_too_long(self):
        """Name exceeding max length should be rejected (422)."""
        r = requests.post(f"{API}/auth/register", json={
            "name": "x" * 200, "email": f"TEST_{uuid.uuid4().hex[:8]}@ahonix-test.com",
            "password": "abc123!"
        })
        assert r.status_code == 422

    def test_reset_password_invalid_token_format(self):
        """Reset token with invalid characters should be rejected."""
        r = requests.post(f"{API}/auth/reset-password", json={
            "token": "<script>alert(1)</script>",
            "password": "newpass123"
        })
        assert r.status_code == 400 or r.status_code == 422


# --- Production Hardening: Health & Headers ----------------------------------
class TestHealthAndSecurity:
    def test_health_endpoint(self, admin_session):
        """Health endpoint should return 200 with status."""
        r = admin_session.get(f"{API}/health")
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert "db" in d

    def test_security_headers_present(self, admin_session):
        """Security headers should be set on responses."""
        r = admin_session.get(f"{API}/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert "strict-origin" in r.headers.get("Referrer-Policy", "").lower()

    def test_action_backward_transition_blocked(self, admin_session):
        """Attempting a backward stage transition should return 409."""
        actions = admin_session.get(f"{API}/actions").json()["actions"]
        # Find an action that's past Detected (e.g., Simulated or later)
        advanced = next((a for a in actions if a["stage"] not in ("Detected", "Explained")), None)
        if advanced:
            r = admin_session.post(f"{API}/actions/{advanced['action_id']}", json={"op": "simulate"})
            assert r.status_code == 409, f"Expected 409 for backward transition, got {r.status_code}"

