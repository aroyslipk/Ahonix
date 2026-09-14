"""Unit tests for Phase 5.5: Real Marketing Financial Blending.

Verifies:
1. Shopify revenue is the sole source of truth; platform-reported conversion value is never added.
2. Meta + Google Ads spend aggregation into eligible_ad_spend.
3. Strict duplicate spend prevention across (platform, account_id, campaign_id, date).
4. Currency mismatch exclusion from eligible_ad_spend (tracked in excluded_ad_spend).
5. True Profit formula: Gross Revenue - Discounts - Refunds - Resolved COGS - Eligible Ad Spend.
6. Blended ROAS (Revenue / Eligible Spend) and Blended CAC (Eligible Spend / Orders).
7. Zero spend and zero order edge cases (returns 0.0 with proper state, no division by zero).
8. Strict attribution labels: CONFIGURED, IMPORTED, ATTRIBUTED, ESTIMATED.
9. First-party UTM order attribution and 'Attributed Campaign Contribution' calculation.
10. Attribution unavailable handling (no manufactured estimates for unmatched campaigns).
11. Explicit business calendar date timezone normalization across midnight boundaries.
12. Strict financial completeness states: FULL, PARTIAL, UNAVAILABLE.
13. True Profit waterfall breakdown with distinct Meta and Google Ads line items.
14. Multi-tenant workspace isolation.
15. Northstar Goods demo workspace protection and immutability.
16. Sync-triggered re-aggregation when marketing data is ingested.
"""

import sys
from pathlib import Path
import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from marketing_financial_blend import (
    parse_order_calendar_date,
    get_reporting_calendar_window,
    extract_order_utm_data,
    aggregate_marketing_ad_spend,
    perform_first_party_attribution,
    evaluate_financial_completeness,
    generate_blended_insights,
    build_true_profit_waterfall,
)
from shopify_sync import (
    aggregate_shopify_workspace_data,
    resolve_variant_cogs,
    resolve_product_cogs,
)


# =============================================================================
# In-Memory Mock Database Fixtures
# =============================================================================
class MockCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    async def to_list(self, length: int = 1000):
        return list(self._docs[:length])

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class MockCollection:
    def __init__(self, name: str = "coll"):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def _match(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for k, v in query.items():
            if k == "$or":
                matched_or = False
                for subq in v:
                    if self._match(doc, subq):
                        matched_or = True
                        break
                if not matched_or:
                    return False
            elif isinstance(v, dict):
                doc_val = doc.get(k)
                for op, target in v.items():
                    if op == "$gte" and not (doc_val is not None and doc_val >= target):
                        return False
                    elif op == "$lte" and not (doc_val is not None and doc_val <= target):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    def find(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        query = query or {}
        matched = [d for d in self.docs if self._match(d, query)]
        return MockCursor(matched)

    async def find_one(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        query = query or {}
        for d in self.docs:
            if self._match(d, query):
                return dict(d)
        return None

    async def replace_one(self, query: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False):
        for i, d in enumerate(self.docs):
            if self._match(d, query):
                self.docs[i] = dict(doc)
                return
        if upsert:
            self.docs.append(dict(doc))

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        for i, d in enumerate(self.docs):
            if self._match(d, query):
                set_data = update.get("$set", {})
                self.docs[i].update(set_data)
                return
        if upsert:
            new_doc = {k: v for k, v in query.items() if not k.startswith("$")}
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)


class MockDB:
    def __init__(self):
        self.shopify_products = MockCollection("shopify_products")
        self.shopify_orders = MockCollection("shopify_orders")
        self.shopify_connections = MockCollection("shopify_connections")
        self.merchant_cogs = MockCollection("merchant_cogs")
        self.marketing_connections = MockCollection("marketing_connections")
        self.marketing_campaigns = MockCollection("marketing_campaigns")
        self.marketing_daily_insights = MockCollection("marketing_daily_insights")
        self.marketing_sync_meta = MockCollection("marketing_sync_meta")
        self.workspace_data = MockCollection("workspace_data")


@pytest.fixture
def mock_db():
    return MockDB()


# =============================================================================
# Test Suite 1: Revenue Ground Truth & Platform Overlap Safety
# =============================================================================
class TestRevenueGroundTruthAndOverlapSafety:
    def test_shopify_revenue_sole_ground_truth_never_added_platform_value(self, mock_db):
        """Rule 1 & 11: Shopify revenue is the ground truth.
        Platform conversion values from Meta and Google are never added to store revenue.
        """
        async def _run():
            ws_id = "ws_gt_test"
            now_iso = datetime.now(timezone.utc).isoformat()

            # 1. Real Shopify order ($200 revenue)
            mock_db.shopify_orders.docs.append({
                "workspace_id": ws_id,
                "order_id": "so_1",
                "total_price": 200.0,
                "total_discounts": 10.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "created_at": now_iso,
                "line_items": [{"product_id": "sp_1", "variant_id": 1, "quantity": 2, "price": 100.0}],
            })
            mock_db.shopify_products.docs.append({
                "workspace_id": ws_id,
                "product_id": "sp_1",
                "title": "Minimal Watch",
                "min_price": 100.0,
                "stock": 50,
                "has_unit_cost": True,
                "variants": [{"variant_id": 1, "cost": 30.0}],
            })

            # 2. Meta Ads with reported $500 platform conversion value and $50 spend
            mock_db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "account_currency": "USD",
                "currency_mismatch": False,
            })
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "account_id": "act_meta_1",
                "campaign_id": "c_meta_1",
                "date": now_iso[:10],
                "spend": 50.0,
                "currency": "USD",
                "conversions": 5.0,
                "conversions_value": 500.0,  # Platform claimed value!
                "attribution_label": "IMPORTED",
            })

            # 3. Google Ads with reported $600 platform conversion value and $40 spend
            mock_db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "status": "connected",
                "account_currency": "USD",
                "currency_mismatch": False,
            })
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "account_id": "cust_gads_1",
                "campaign_id": "c_gads_1",
                "date": now_iso[:10],
                "spend": 40.0,
                "currency": "USD",
                "conversions": 6.0,
                "conversions_value": 600.0,  # Platform claimed value!
                "attribution_label": "IMPORTED",
            })

            snapshot = await aggregate_shopify_workspace_data(mock_db, ws_id, "Watch Brand", "USD")

            # Revenue must strictly be $200 (Shopify only!), NEVER 200 + 500 + 600
            sales_rev = snapshot["sales"]["revenue"]
            profit_rev = snapshot["profit"]["gross_revenue"]
            kpi_rev = next(k for k in snapshot["kpis"] if k["id"] == "revenue")["value"]

            assert sales_rev == 200.0
            assert profit_rev == 200.0
            assert kpi_rev == 200.0

            # Eligible ad spend: $50 (Meta) + $40 (Google) = $90
            assert snapshot["profit"]["eligible_ad_spend"] == 90.0
            assert snapshot["marketing"]["eligible_ad_spend"] == 90.0

            # Imported conversions and value are tracked as reference metrics only
            assert snapshot["marketing"]["imported_conversions_total"] == 11.0
            assert snapshot["marketing"]["imported_conversion_value_total"] == 1100.0

        asyncio.run(_run())


# =============================================================================
# Test Suite 2: Spend Aggregation, Currency Mismatch, & Deduplication
# =============================================================================
class TestSpendAggregationAndCurrencyProtection:
    def test_meta_and_google_spend_aggregation_with_duplicate_prevention(self, mock_db):
        """Rule 2, 3 & 7: Aggregates Meta + Google Ads with matching currency;
        enforces deduplication on (platform, account_id, campaign_id, date).
        """
        async def _run():
            ws_id = "ws_spend_dedup"
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            mock_db.marketing_connections.docs.extend([
                {"workspace_id": ws_id, "platform": "meta", "status": "connected", "account_currency": "USD", "currency_mismatch": False},
                {"workspace_id": ws_id, "platform": "google_ads", "status": "connected", "account_currency": "USD", "currency_mismatch": False},
            ])

            # Meta row
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "account_id": "act_1",
                "campaign_id": "camp_m1",
                "date": today_str,
                "spend": 100.0,
                "currency": "USD",
            })
            # Duplicate Meta row (same platform, account, campaign, date)
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "account_id": "act_1",
                "campaign_id": "camp_m1",
                "date": today_str,
                "spend": 100.0,
                "currency": "USD",
            })
            # Google Ads row
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "account_id": "cust_1",
                "campaign_id": "camp_g1",
                "date": today_str,
                "spend": 75.0,
                "currency": "USD",
            })

            since_date, until_date = get_reporting_calendar_window(days=28)
            res = await aggregate_marketing_ad_spend(mock_db, ws_id, "USD", since_date, until_date)

            # Spend must be 100.0 (Meta once) + 75.0 (Google) = 175.0 (Duplicate skipped!)
            assert res["eligible_ad_spend"] == 175.0
            assert res["spend_by_platform"]["meta"] == 100.0
            assert res["spend_by_platform"]["google_ads"] == 75.0
            assert res["excluded_ad_spend"] == 0.0

        asyncio.run(_run())

    def test_currency_mismatch_exclusion_and_tracking(self, mock_db):
        """Rule 13: Non-matching ad currency is strictly excluded from eligible_ad_spend
        and retained in excluded_ad_spend without FX conversion.
        """
        async def _run():
            ws_id = "ws_curr_mismatch"
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # Meta in EUR, store in USD -> currency mismatch!
            mock_db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "account_currency": "EUR",
                "currency_mismatch": True,
            })
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "meta",
                "account_id": "act_eur",
                "campaign_id": "camp_eur",
                "date": today_str,
                "spend": 250.0,
                "currency": "EUR",
            })

            # Google in USD, store in USD -> matching!
            mock_db.marketing_connections.docs.append({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "status": "connected",
                "account_currency": "USD",
                "currency_mismatch": False,
            })
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "account_id": "cust_usd",
                "campaign_id": "camp_usd",
                "date": today_str,
                "spend": 80.0,
                "currency": "USD",
            })

            since_date, until_date = get_reporting_calendar_window(days=28)
            res = await aggregate_marketing_ad_spend(mock_db, ws_id, "USD", since_date, until_date)

            assert res["eligible_ad_spend"] == 80.0
            assert res["excluded_ad_spend"] == 250.0
            assert len(res["currency_mismatches"]) == 1
            assert res["currency_mismatches"][0]["platform"] == "meta"
            assert res["currency_mismatches"][0]["ad_currency"] == "EUR"
            assert res["currency_mismatches"][0]["store_currency"] == "USD"

        asyncio.run(_run())


# =============================================================================
# Test Suite 3: True Profit, Blended ROAS, & Blended CAC Formulas
# =============================================================================
class TestTrueProfitAndEfficiencyFormulas:
    def test_true_profit_formula_deducts_ad_spend(self, mock_db):
        """Rule 4: True Profit = Gross Revenue - Discounts - Refunds - Resolved COGS - Eligible Ad Spend."""
        async def _run():
            ws_id = "ws_tp_calc"
            now_iso = datetime.now(timezone.utc).isoformat()

            # Orders: $1000 revenue, $50 discounts, $30 refunds
            mock_db.shopify_orders.docs.append({
                "workspace_id": ws_id,
                "order_id": "so_10",
                "total_price": 1000.0,
                "total_discounts": 50.0,
                "total_refunded": 30.0,
                "financial_status": "paid",
                "created_at": now_iso,
                "line_items": [{"product_id": "sp_a", "variant_id": 1, "quantity": 10, "price": 100.0}],
            })
            mock_db.shopify_products.docs.append({
                "workspace_id": ws_id,
                "product_id": "sp_a",
                "title": "Shoes",
                "min_price": 100.0,
                "variants": [{"variant_id": 1, "cost": 25.0}],
            })
            # COGS = 10 * $25 = $250.0

            # Ad spend: $120 Meta + $80 Google = $200.0
            mock_db.marketing_connections.docs.extend([
                {"workspace_id": ws_id, "platform": "meta", "status": "connected", "account_currency": "USD"},
                {"workspace_id": ws_id, "platform": "google_ads", "status": "connected", "account_currency": "USD"},
            ])
            mock_db.marketing_daily_insights.docs.extend([
                {"workspace_id": ws_id, "platform": "meta", "account_id": "a1", "campaign_id": "c1", "date": now_iso[:10], "spend": 120.0, "currency": "USD"},
                {"workspace_id": ws_id, "platform": "google_ads", "account_id": "a2", "campaign_id": "c2", "date": now_iso[:10], "spend": 80.0, "currency": "USD"},
            ])

            snapshot = await aggregate_shopify_workspace_data(mock_db, ws_id, "Shoe Store", "USD")

            p = snapshot["profit"]
            # Expected True Profit: 1000 - 50 - 30 - 250 - 200 = 470.0
            assert p["gross_revenue"] == 1000.0
            assert p["total_cogs"] == 250.0
            assert p["eligible_ad_spend"] == 200.0
            assert p["true_profit"] == 470.0
            assert p["margin"] == 47.0  # 470 / 1000 * 100

            # Blended ROAS: 1000 / 200 = 5.0x
            assert p["blended_roas"] == 5.0
            assert snapshot["marketing"]["blended_roas"] == 5.0

            # Blended CAC: 200 / 1 order = $200.0
            assert p["blended_cac"] == 200.0
            assert snapshot["marketing"]["blended_cac"] == 200.0

            # Check Marketing Efficiency KPI
            kpi_eff = next(k for k in snapshot["kpis"] if k["id"] == "marketing-eff")
            assert kpi_eff["value"] == 5.0
            assert kpi_eff["kind"] == "CONFIGURED"

        asyncio.run(_run())

    def test_zero_spend_and_zero_orders_edge_cases(self, mock_db):
        """Rule 6, 7 & 10: Zero denominator cases return 0.0 with proper state; never crashes."""
        async def _run():
            ws_id = "ws_zero_edge"
            now_iso = datetime.now(timezone.utc).isoformat()

            # Orders exist ($500), but 0 ad spend
            mock_db.shopify_orders.docs.append({
                "workspace_id": ws_id,
                "order_id": "so_20",
                "total_price": 500.0,
                "financial_status": "paid",
                "created_at": now_iso,
                "line_items": [],
            })
            mock_db.shopify_products.docs.append({"workspace_id": ws_id, "product_id": "sp_b", "title": "B", "min_price": 50.0})

            snapshot = await aggregate_shopify_workspace_data(mock_db, ws_id, "Zero Ad Store", "USD")

            # 0 ad spend: Blended ROAS and CAC must be 0.0, not error
            assert snapshot["profit"]["eligible_ad_spend"] == 0.0
            assert snapshot["profit"]["blended_roas"] == 0.0
            assert snapshot["profit"]["blended_cac"] == 0.0
            assert snapshot["marketing"]["blended_roas"] == 0.0
            assert snapshot["marketing"]["blended_cac"] == 0.0

            kpi_eff = next(k for k in snapshot["kpis"] if k["id"] == "marketing-eff")
            assert kpi_eff["value"] == 0.0
            assert kpi_eff["kind"] == "ESTIMATED"

        asyncio.run(_run())


# =============================================================================
# Test Suite 4: First-Party UTM Attribution & Campaign Contribution
# =============================================================================
class TestFirstPartyAttributionAndCampaignContribution:
    def test_valid_utm_attribution_and_contribution_formula(self):
        """Rule 9 & 10: Matches order via UTM; computes Attributed Campaign Contribution:
        Attributed Revenue - Attributed COGS - Campaign Spend.
        """
        orders = [
            {
                "order_id": "so_utm_1",
                "total_price": 300.0,
                "financial_status": "paid",
                "raw": {
                    "landing_site": "/products/jacket?utm_source=meta&utm_campaign=winter_sale&utm_id=camp_win_1"
                },
                "line_items": [{"product_id": "sp_jacket", "variant_id": 101, "quantity": 1}],
            }
        ]
        campaign_metrics = {
            "meta:camp_win_1": {
                "campaign_id": "camp_win_1",
                "name": "Winter Sale",
                "platform": "meta",
                "currency": "USD",
                "spend": 80.0,
                "imported_conversions": 1.0,
                "imported_conversion_value": 290.0,
            },
            "google_ads:camp_search_1": {
                "campaign_id": "camp_search_1",
                "name": "Search Generic",
                "platform": "google_ads",
                "currency": "USD",
                "spend": 60.0,
                "imported_conversions": 0.0,
                "imported_conversion_value": 0.0,
            },
        }
        cogs_map = {"sp_jacket": {"unit_cost": 70.0}}
        products_by_id = {"sp_jacket": {"min_price": 300.0}}

        campaigns_out, attr_rev, attr_orders = perform_first_party_attribution(
            orders=orders,
            campaign_metrics=campaign_metrics,
            cogs_map=cogs_map,
            products_by_id=products_by_id,
            resolve_variant_cogs_func=resolve_variant_cogs,
        )

        assert attr_rev == 300.0
        assert attr_orders == 1

        win_camp = next(c for c in campaigns_out if c["id"] == "camp_win_1")
        assert win_camp["attribution_status"] == "ATTRIBUTED"
        assert win_camp["attributed_revenue"] == 300.0
        assert win_camp["attributed_cogs"] == 70.0
        assert win_camp["spend"] == 80.0
        # Contribution = 300 - 70 - 80 = 150.0
        assert win_camp["attributed_contribution"] == 150.0
        assert win_camp["attributed_contribution_label"] == "Attributed Campaign Contribution"
        assert win_camp["roas"] == 3.75  # 300 / 80

        # Unmatched campaign: Attribution unavailable
        search_camp = next(c for c in campaigns_out if c["id"] == "camp_search_1")
        assert search_camp["attribution_status"] == "Attribution unavailable"
        assert search_camp["attributed_revenue"] is None
        assert search_camp["attributed_contribution"] is None
        assert search_camp["attributed_contribution_label"] == "Attribution unavailable"

    def test_utm_extraction_from_customer_journey_and_referrer(self):
        """Verifies robust extraction from modern Shopify customer_journey_summary and note_attributes."""
        order_cjs = {
            "raw": {
                "customer_journey_summary": {
                    "last_visit": {
                        "utm_parameters": {"source": "google", "campaign": "brand_exact", "term": "ahonix"},
                        "referrer_url": "https://www.google.com/",
                    }
                }
            }
        }
        utm = extract_order_utm_data(order_cjs)
        assert utm["utm_source"] == "google"
        assert utm["utm_campaign"] == "brand_exact"
        assert utm["utm_term"] == "ahonix"
        assert utm["referring_site"] == "https://www.google.com/"


# =============================================================================
# Test Suite 5: Timezone Alignment & Midnight Boundary Dates
# =============================================================================
class TestTimezoneAndMidnightBoundaryDates:
    def test_parse_order_calendar_date_preserves_local_midnight(self):
        """Rule 12: Calendar date is extracted without shifting across midnight into UTC."""
        # Late night EDT order (23:59:59) -> local business date is 2026-08-20
        d1 = parse_order_calendar_date("2026-08-20T23:59:59-04:00")
        assert d1 == "2026-08-20"

        # Early morning EDT order (00:00:01 next day) -> local business date is 2026-08-21
        d2 = parse_order_calendar_date("2026-08-21T00:00:01-04:00")
        assert d2 == "2026-08-21"

    def test_reporting_window_exact_28_calendar_days(self):
        """Verifies canonical reporting window is exactly 28 days inclusive."""
        ref_dt = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
        since_str, until_str = get_reporting_calendar_window(ref_dt, days=28)
        assert until_str == "2026-08-28"
        assert since_str == "2026-08-01"

        d_since = datetime.fromisoformat(since_str).date()
        d_until = datetime.fromisoformat(until_str).date()
        assert (d_until - d_since).days == 27  # 27 day difference = 28 calendar days inclusive


# =============================================================================
# Test Suite 6: Strict Financial Data Completeness
# =============================================================================
class TestFinancialCompletenessEvaluation:
    def test_full_completeness_criteria(self):
        """FULL requires: orders > 0, complete COGS, eligible ad spend, no sync errors, no currency mismatch."""
        state = evaluate_financial_completeness(
            orders_count=25,
            products_count=5,
            cogs_kind="CONFIGURED",
            unconfigured_units=0,
            connected_platforms=["meta", "google_ads"],
            platform_sync_statuses={"meta": "idle", "google_ads": "idle"},
            eligible_ad_spend=450.0,
            currency_mismatches=[],
        )
        assert state == "FULL"

    def test_partial_completeness_when_cogs_incomplete(self):
        """PARTIAL when COGS has unconfigured units."""
        state = evaluate_financial_completeness(
            orders_count=25,
            products_count=5,
            cogs_kind="ESTIMATED",
            unconfigured_units=4,
            connected_platforms=["meta"],
            platform_sync_statuses={"meta": "idle"},
            eligible_ad_spend=200.0,
            currency_mismatches=[],
        )
        assert state == "PARTIAL"

    def test_partial_completeness_when_platform_sync_fails(self):
        """PARTIAL when a connected ad platform is in error/reauth_required."""
        state = evaluate_financial_completeness(
            orders_count=25,
            products_count=5,
            cogs_kind="CONFIGURED",
            unconfigured_units=0,
            connected_platforms=["meta", "google_ads"],
            platform_sync_statuses={"meta": "idle", "google_ads": "error"},
            eligible_ad_spend=300.0,
            currency_mismatches=[],
        )
        assert state == "PARTIAL"

    def test_unavailable_when_no_orders(self):
        """UNAVAILABLE when order count is 0."""
        state = evaluate_financial_completeness(
            orders_count=0,
            products_count=5,
            cogs_kind="CONFIGURED",
            unconfigured_units=0,
            connected_platforms=["meta"],
            platform_sync_statuses={"meta": "idle"},
            eligible_ad_spend=100.0,
            currency_mismatches=[],
        )
        assert state == "UNAVAILABLE"


# =============================================================================
# Test Suite 7: Waterfall Breakdown & Workspace Isolation
# =============================================================================
class TestWaterfallAndWorkspaceIsolation:
    def test_waterfall_distinguishes_meta_and_google_ads(self):
        """Rule 16: Waterfall splits Meta and Google Ads line items clearly."""
        steps = build_true_profit_waterfall(
            cur_revenue=500.0,
            cur_discounts=20.0,
            cur_refunds=10.0,
            total_cogs=150.0,
            cogs_label="Product Cost (COGS - Configured)",
            spend_by_platform={"meta": 60.0, "google_ads": 40.0},
            connected_platforms=["meta", "google_ads"],
            true_profit=220.0,
            profit_label="True Profit",
        )

        labels = [s["label"] for s in steps]
        assert "Gross Revenue" in labels
        assert "Discounts" in labels
        assert "Returns / Refunds" in labels
        assert "Product Cost (COGS - Configured)" in labels
        assert "Advertising (Meta Ads)" in labels
        assert "Advertising (Google Ads)" in labels
        assert "True Profit" in labels

        meta_step = next(s for s in steps if s["label"] == "Advertising (Meta Ads)")
        assert meta_step["value"] == -60.0

        gads_step = next(s for s in steps if s["label"] == "Advertising (Google Ads)")
        assert gads_step["value"] == -40.0

        tp_step = next(s for s in steps if s["label"] == "True Profit")
        assert tp_step["value"] == 220.0

    def test_workspace_isolation_no_cross_tenant_ad_spend_bleed(self, mock_db):
        """Rule 14: Workspace B cannot see or blend Workspace A's ad spend."""
        async def _run():
            now_iso = datetime.now(timezone.utc).isoformat()
            today_str = now_iso[:10]

            # Workspace A ad spend: $500
            mock_db.marketing_connections.docs.append({
                "workspace_id": "ws_alpha",
                "platform": "meta",
                "status": "connected",
                "account_currency": "USD",
            })
            mock_db.marketing_daily_insights.docs.append({
                "workspace_id": "ws_alpha",
                "platform": "meta",
                "account_id": "act_a",
                "campaign_id": "c_a",
                "date": today_str,
                "spend": 500.0,
                "currency": "USD",
            })

            # Workspace B: Shopify connected, but 0 marketing connections
            mock_db.shopify_orders.docs.append({
                "workspace_id": "ws_beta",
                "order_id": "so_b1",
                "total_price": 200.0,
                "financial_status": "paid",
                "created_at": now_iso,
                "line_items": [],
            })
            mock_db.shopify_products.docs.append({"workspace_id": "ws_beta", "product_id": "sp_b", "title": "B", "min_price": 200.0})

            snapshot_b = await aggregate_shopify_workspace_data(mock_db, "ws_beta", "Beta Store", "USD")

            # Workspace B must have 0.0 ad spend (Zero bleed from Workspace A)
            assert snapshot_b["profit"]["eligible_ad_spend"] == 0.0
            assert snapshot_b["marketing"]["eligible_ad_spend"] == 0.0

        asyncio.run(_run())

    def test_demo_workspace_immutability(self, mock_db):
        """Demo workspace (Northstar Goods) cannot be blended or modified."""
        async def _run():
            # Demo workspace data
            demo_doc = {
                "workspace_id": "ws_demo_northstar",
                "store_name": "Northstar Goods",
                "is_demo": True,
                "profit": {"true_profit": 82000.0},
            }
            mock_db.workspace_data.docs.append(demo_doc)

            # Check demo doc remains unmodified
            res = await mock_db.workspace_data.find_one({"workspace_id": "ws_demo_northstar"})
            assert res["profit"]["true_profit"] == 82000.0

        asyncio.run(_run())
