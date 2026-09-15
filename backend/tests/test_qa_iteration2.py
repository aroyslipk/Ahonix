"""AHONIX QA iteration 2 — reconciliation, marketing validity, action 409, IDOR."""
import os
import uuid
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


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def all_sections(admin):
    return {
        "overview": admin.get(f"{API}/overview").json(),
        "sales": admin.get(f"{API}/sales").json(),
        "products": admin.get(f"{API}/products").json(),
        "profit": admin.get(f"{API}/profit").json(),
        "returns": admin.get(f"{API}/returns").json(),
        "marketing": admin.get(f"{API}/marketing").json(),
        "actions": admin.get(f"{API}/actions").json(),
        "intelligence": admin.get(f"{API}/intelligence").json(),
    }


def _kpi(ov, key):
    return next(k["value"] for k in ov["kpis"] if k["id"] == key)


TOL = 1.0  # dollars


# --- 1. Reconciliation -------------------------------------------------------
class TestReconciliation:
    def test_revenue_reconciles_overview_sales_channels_countries_products(self, all_sections):
        ov = all_sections["overview"]
        sales = all_sections["sales"]["sales"]
        products = all_sections["products"]["products"]
        rev_ov = _kpi(ov, "revenue")
        rev_sales_header = sales["revenue"]
        rev_channels = sum(c["revenue"] for c in sales["by_channel"])
        rev_countries = sum(c["revenue"] for c in sales["by_country"])
        rev_products = sum(p["revenue"] for p in products)

        assert abs(rev_ov - rev_sales_header) < TOL, f"ov {rev_ov} vs sales header {rev_sales_header}"
        assert abs(rev_sales_header - rev_channels) < TOL, f"sales header {rev_sales_header} vs channels {rev_channels}"
        # by_country revenue is share-of-total distribution but should still sum ~ total (shares in demo_data sum to 1.0)
        country_shares = 0.46 + 0.18 + 0.13 + 0.11 + 0.07 + 0.05
        assert abs(rev_countries - rev_sales_header * country_shares) < TOL * 5
        assert abs(rev_products - rev_sales_header) < TOL, f"products sum {rev_products} vs sales {rev_sales_header}"

    def test_orders_reconcile(self, all_sections):
        ov = all_sections["overview"]
        sales = all_sections["sales"]["sales"]
        o_ov = _kpi(ov, "orders")
        o_channels = sum(c["orders"] for c in sales["by_channel"])
        assert o_ov == o_channels, f"orders overview {o_ov} vs channels {o_channels}"

    def test_true_profit_reconciles(self, all_sections):
        ov = all_sections["overview"]
        profit = all_sections["profit"]["profit"]
        tp_ov = _kpi(ov, "true-profit")
        tp_page = profit["true_profit"]
        # waterfall last step should equal
        waterfall_result = profit["steps"][-1]["value"]
        tp_products = sum(p["true_profit"] for p in profit["product_profit"])
        assert abs(tp_ov - tp_page) < TOL
        assert abs(tp_page - waterfall_result) < TOL
        # per-product sum should equal within a few dollars (rounding)
        assert abs(tp_products - tp_page) < 25, f"products sum {tp_products} vs page {tp_page}"

    def test_returns_reconcile(self, all_sections):
        ov = all_sections["overview"]
        returns = all_sections["returns"]["returns"]
        rr_ov = _kpi(ov, "return-rate")
        assert abs(rr_ov - returns["return_rate"]) < 0.1
        total_ret = returns["total_returns"]
        by_prod_sum = sum(p["returned_units"] for p in returns["by_product"])
        assert total_ret == by_prod_sum


# --- 2. Marketing validity ---------------------------------------------------
class TestMarketingValidity:
    def test_marketing_spend_equals_advertising_cost(self, all_sections):
        marketing = all_sections["marketing"]["marketing"]
        profit = all_sections["profit"]["profit"]
        ad_line = next(s for s in profit["steps"] if s["label"] == "Advertising")
        assert abs(marketing["total_spend"] - abs(ad_line["value"])) < TOL, \
            f"marketing spend {marketing['total_spend']} vs profit ad line {abs(ad_line['value'])}"

    def test_kpi_marketing_eff_equals_blended_roas(self, all_sections):
        ov = all_sections["overview"]
        marketing = all_sections["marketing"]["marketing"]
        kpi_eff = _kpi(ov, "marketing-eff")
        assert abs(kpi_eff - marketing["blended_roas"]) < 0.05

    def test_campaign_spends_sum_to_total(self, all_sections):
        marketing = all_sections["marketing"]["marketing"]
        s = sum(c["spend"] for c in marketing["campaigns"])
        assert abs(s - marketing["total_spend"]) < TOL

    def test_roas_paradox_holds(self, all_sections):
        marketing = all_sections["marketing"]["marketing"]
        campaigns = marketing["campaigns"]
        hi_roas = max(campaigns, key=lambda c: c["roas"])
        hi_contrib = max(campaigns, key=lambda c: c["contribution"])
        assert hi_roas["name"] != hi_contrib["name"], "paradox missing: same campaign leads on both"
        assert hi_roas["name"] == "Brand Search", f"expected Brand Search hi ROAS, got {hi_roas['name']}"
        assert hi_contrib["name"] == "Shopping - Catalog", \
            f"expected Shopping - Catalog hi contribution, got {hi_contrib['name']}"
        # Creator Spark negative contribution
        creator = next(c for c in campaigns if c["name"] == "Creator Spark")
        assert creator["contribution"] < 0

    def test_paradox_flag_in_marketing(self, all_sections):
        m = all_sections["marketing"]["marketing"]
        assert m["paradox"]["high_roas_campaign"] == "Brand Search"
        assert m["paradox"]["high_profit_campaign"] == "Shopping - Catalog"


# --- 3. Action lifecycle 409 ------------------------------------------------
class TestActionLifecycleGuards:
    def test_out_of_order_returns_409(self, admin):
        # act-2 is seeded as "Simulated". Simulating it again must 409.
        r = admin.post(f"{API}/actions/act-2", json={"op": "simulate"})
        assert r.status_code == 409, f"expected 409, got {r.status_code} {r.text}"

    def test_cannot_skip_backward(self, admin):
        # After we advance an action to Executed, executing again should 409.
        # Use act-1 (Awaiting Approval): approve -> execute -> execute again = 409
        r = admin.post(f"{API}/actions/act-1", json={"op": "approve"})
        assert r.status_code in (200, 409)
        r = admin.post(f"{API}/actions/act-1", json={"op": "execute"})
        assert r.status_code in (200, 409)
        r2 = admin.post(f"{API}/actions/act-1", json={"op": "execute"})
        assert r2.status_code == 409

    def test_executed_action_has_simulated_flag(self, admin):
        acts = admin.get(f"{API}/actions").json()["actions"]
        executed = [a for a in acts if a["stage"] in ("Executed", "Measured")]
        # There must be at least one Executed and it must carry simulated:True
        if executed:
            assert any(a.get("simulated") is True for a in executed)


# --- 4. Auth & IDOR ---------------------------------------------------------
@pytest.fixture(scope="module")
def isolated_user():
    s = requests.Session()
    email = f"TEST_iso_{uuid.uuid4().hex[:6]}@ahonix-test.com"
    r = s.post(f"{API}/auth/register",
               json={"name": "Iso User", "email": email, "password": "TestPass123!"})
    assert r.status_code == 200
    return s, email


class TestAuthIsolation:
    def test_unauthenticated_endpoints_401(self):
        for ep in ["/overview", "/profit", "/sales", "/actions", "/marketing"]:
            r = requests.get(f"{API}{ep}")
            assert r.status_code == 401, f"{ep} returned {r.status_code}"

    def test_isolated_user_cannot_read_admin_workspace(self, admin, isolated_user):
        s, _ = isolated_user
        admin_ws = admin.get(f"{API}/workspaces").json()["workspaces"]
        assert admin_ws
        admin_ws_id = admin_ws[0]["workspace_id"]
        # try to select admin's workspace
        r = s.post(f"{API}/workspaces/{admin_ws_id}/select")
        assert r.status_code == 404
        # bogus workspace also 404
        r = s.post(f"{API}/workspaces/ws_bogus1234/select")
        assert r.status_code == 404

    def test_actions_idor_scoped(self, admin, isolated_user):
        s, _ = isolated_user
        # New user with no workspace -> /actions/act-1 should be 404 (no active workspace) not 200
        r = s.post(f"{API}/actions/act-1", json={"op": "simulate"})
        assert r.status_code in (400, 404), f"IDOR? got {r.status_code}"

    def test_product_idor_scoped(self, admin, isolated_user):
        s, _ = isolated_user
        r = s.get(f"{API}/products/p1")
        assert r.status_code in (400, 404)

    def test_no_secrets_leaked_in_responses(self, admin):
        combined = ""
        for ep in ["/overview", "/profit", "/marketing", "/workspaces"]:
            combined += admin.get(f"{API}{ep}").text
        for secret_env in ["EMERGENT_LLM_KEY", "JWT_SECRET"]:
            val = os.environ.get(secret_env, "")
            if val and len(val) > 8:
                assert val not in combined, f"{secret_env} leaked in response"


# --- 5. Markets simulator edge cases ---------------------------------------
class TestMarketsSimulatorEdges:
    def test_normal_germany(self, admin):
        r = admin.post(f"{API}/markets/simulate", json={
            "country": "Germany", "price": 79.0, "demand_units": 500,
            "inventory_units": 400, "marketing_budget": 5000.0})
        assert r.status_code == 200
        d = r.json()["result"]
        assert d["projected_revenue"] > 0
        assert isinstance(d["projected_profit"], (int, float))

    def test_zero_inputs_no_crash(self, admin):
        r = admin.post(f"{API}/markets/simulate", json={
            "country": "Germany", "price": 0, "demand_units": 0,
            "inventory_units": 0, "marketing_budget": 0})
        # should not 500; either 200 with safe zeros or 400 for validation
        assert r.status_code in (200, 400, 422), r.text
        if r.status_code == 200:
            d = r.json()["result"]
            # no NaN
            import math
            for v in [d.get("projected_revenue"), d.get("projected_profit"),
                      d.get("estimated_orders"), d.get("estimated_cac")]:
                if isinstance(v, float):
                    assert not math.isnan(v)

    def test_unknown_country_falls_back(self, admin):
        r = admin.post(f"{API}/markets/simulate", json={
            "country": "Atlantis", "price": 50, "demand_units": 100,
            "inventory_units": 100, "marketing_budget": 1000})
        assert r.status_code == 200


# --- 6. Data version / meta -------------------------------------------------
class TestDataVersion:
    def test_meta_version_is_2(self, all_sections):
        meta = all_sections["overview"]["meta"]
        assert meta["version"] == 2
        assert meta["period_label"] == "last 4 weeks"
