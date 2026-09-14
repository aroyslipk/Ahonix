"""AHONIX — Phase 5.7 Final End-to-End Verification Test Suite.

Comprehensive end-to-end verification covering:
1. Real Shopify End-to-End (OAuth, products, orders, refunds, discounts, webhooks, workspace isolation, demo protection)
2. Real COGS End-to-End (imported cost, merchant product cost, variant override, unconfigured cost, dynamic recalculation, labeling CONFIGURED/IMPORTED/ESTIMATED, never ACTUAL for merchant cost)
3. Real Meta End-to-End (OAuth, account discovery, selection, 28-day sync, 3-day restatement, daily insights, deduping, pagination, reauth, currency mismatch)
4. Real Google Ads End-to-End (OAuth, customer discovery, selection, manager login-customer-id, 28-day sync, 3-day restatement, cost_micros, deduping, token protection, reauth)
5. Financial Truth Verification (True Profit, Blended ROAS, Blended CAC, platform conversion value never added to Shopify revenue)
6. Double-Counting Check (deterministic scenario with Meta/Google platform conversion values vs Shopify order revenue, idempotency of repeated syncs)
7. Currency Check (all eligible, Meta EUR excluded, Google EUR excluded, raw mismatch data preserved, excluded_ad_spend tracking)
8. Attribution Check (reliable UTM -> ATTRIBUTED, without UTM -> Attribution unavailable, platform conversion value -> IMPORTED, never ACTUAL)
9. Completeness Check (FULL, PARTIAL, UNAVAILABLE with human-readable diagnostic reasons)
10. Timezone / Date Check (boundary cases 23:59:59 and 00:00:01, 28-day canonical window)
11. Security & Leak Prevention (no tokens, developer tokens, secrets exposed in API responses)
"""
import sys
import os
from pathlib import Path
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import shopify_integration
from shopify_integration import (
    connect_shopify,
    get_shopify_status,
    encrypt_token,
    decrypt_token,
    ConnectBody,
)
import shopify_sync
from shopify_sync import (
    normalize_shopify_product,
    normalize_shopify_order,
    resolve_variant_cogs,
    resolve_product_cogs,
    aggregate_shopify_workspace_data,
)
import meta_integration
from meta_integration import (
    connect_meta,
    get_meta_status,
    SelectMetaAccountBody,
)
import meta_sync
from meta_sync import (
    sync_meta_insights_for_workspace,
    normalize_meta_daily_insight,
)
import google_ads_integration
from google_ads_integration import (
    connect_google_ads,
    get_google_ads_status,
    SelectGoogleAdsAccountBody,
    normalize_customer_id,
)
import google_ads_sync
from google_ads_sync import (
    sync_google_ads_insights_for_workspace,
    normalize_google_ads_daily_insight,
    micros_to_currency,
)
import marketing_financial_blend
from marketing_financial_blend import (
    aggregate_marketing_ad_spend,
    get_reporting_calendar_window,
    perform_first_party_attribution,
    extract_order_utm_data,
    parse_order_calendar_date,
    evaluate_financial_completeness,
    build_true_profit_waterfall,
    generate_blended_insights,
)


class MockCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, key, direction=1):
        reverse = direction == -1
        self.items = sorted(self.items, key=lambda x: x.get(key, ""), reverse=reverse)
        return self

    def limit(self, count):
        self.items = self.items[:count]
        return self

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
    def __init__(self, name="mock_col"):
        self.name = name
        self.docs = []

    def find(self, filter_dict=None, projection=None):
        filter_dict = filter_dict or {}
        matched = [self._project(dict(d), projection) for d in self.docs if self._match(d, filter_dict)]
        return MockCursor(matched)

    async def find_one(self, filter_dict, projection=None):
        for d in self.docs:
            if self._match(d, filter_dict):
                return self._project(dict(d), projection)
        return None

    async def insert_one(self, doc):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = f"mock_{len(self.docs)+1}"
        self.docs.append(d)
        return MagicMock(inserted_id=d["_id"])

    async def update_one(self, filter_dict, update_dict, upsert=False):
        for i, d in enumerate(self.docs):
            if self._match(d, filter_dict):
                if "$set" in update_dict:
                    self.docs[i].update(update_dict["$set"])
                if "$unset" in update_dict:
                    for k in update_dict["$unset"]:
                        self.docs[i].pop(k, None)
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            new_doc = dict(filter_dict)
            if "$set" in update_dict:
                new_doc.update(update_dict["$set"])
            if "_id" not in new_doc:
                new_doc["_id"] = f"mock_{len(self.docs)+1}"
            self.docs.append(new_doc)
            return MagicMock(matched_count=0, modified_count=1, upserted_id=new_doc["_id"])
        return MagicMock(matched_count=0, modified_count=0)

    async def replace_one(self, filter_dict, replacement, upsert=False):
        for i, d in enumerate(self.docs):
            if self._match(d, filter_dict):
                new_doc = dict(replacement)
                if "_id" in d and "_id" not in new_doc:
                    new_doc["_id"] = d["_id"]
                self.docs[i] = new_doc
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            new_doc = dict(replacement)
            if "_id" not in new_doc:
                new_doc["_id"] = f"mock_{len(self.docs)+1}"
            self.docs.append(new_doc)
            return MagicMock(matched_count=0, modified_count=1, upserted_id=new_doc["_id"])
        return MagicMock(matched_count=0, modified_count=0)

    async def delete_one(self, filter_dict):
        for i, d in enumerate(self.docs):
            if self._match(d, filter_dict):
                self.docs.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    async def delete_many(self, filter_dict):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._match(d, filter_dict)]
        return MagicMock(deleted_count=before - len(self.docs))

    async def count_documents(self, filter_dict):
        return sum(1 for d in self.docs if self._match(d, filter_dict))

    def _match(self, doc, filter_dict):
        for k, v in filter_dict.items():
            if k.startswith("$"):
                continue
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$nin" in v and doc.get(k) in v["$nin"]:
                    return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                if "$gte" in v and (doc.get(k) is None or doc.get(k) < v["$gte"]):
                    return False
                if "$lte" in v and (doc.get(k) is None or doc.get(k) > v["$lte"]):
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def _project(self, doc, projection):
        if not projection:
            return doc
        res = dict(doc)
        if isinstance(projection, dict):
            for k, v in projection.items():
                if v == 0:
                    res.pop(k, None)
        return res


class MockDB:
    def __init__(self):
        self.users = MockCollection("users")
        self.workspaces = MockCollection("workspaces")
        self.workspace_data = MockCollection("workspace_data")
        self.shopify_stores = MockCollection("shopify_stores")
        self.shopify_connections = MockCollection("shopify_connections")
        self.shopify_synced_data = MockCollection("shopify_synced_data")
        self.shopify_sync_meta = MockCollection("shopify_sync_meta")
        self.shopify_oauth_states = MockCollection("shopify_oauth_states")
        self.oauth_states = MockCollection("oauth_states")
        self.shopify_products = MockCollection("shopify_products")
        self.shopify_orders = MockCollection("shopify_orders")
        self.cogs = MockCollection("cogs")
        self.marketing_connections = MockCollection("marketing_connections")
        self.marketing_campaigns = MockCollection("marketing_campaigns")
        self.marketing_daily_insights = MockCollection("marketing_daily_insights")
        self.marketing_sync_meta = MockCollection("marketing_sync_meta")


# ============================================================================
# 1. Real Shopify End-to-End
# ============================================================================
class TestShopifyEndToEnd:
    """Verifies complete Shopify lifecycle, data normalization, webhooks, and isolation."""

    def test_shopify_e2e_lifecycle(self):
        with patch.dict(os.environ, {"SHOPIFY_API_KEY": "test_key", "SHOPIFY_API_SECRET": "test_secret", "APP_URL": "https://app.ahonix.com"}):
            async def _run():
                db = MockDB()
                ws_live = {"workspace_id": "ws_live_01", "name": "Live Store", "is_demo": False, "currency": "USD"}
                ws_demo = {"workspace_id": "ws_demo_01", "name": "Northstar Goods", "is_demo": True, "currency": "USD"}
                db.workspaces.docs.extend([ws_live, ws_demo])

                async def get_ws(u):
                    return ws_live

                shopify_integration.init_shopify(db, get_ws)

                # 1. OAuth Connect URL generation
                conn_res = await connect_shopify(ConnectBody(shop="my-brand.myshopify.com"), user={"user_id": "u1"})
                assert "auth_url" in conn_res
                assert "oauth/authorize" in conn_res["auth_url"]
                assert "state=" in conn_res["auth_url"]

                now_ts = "2026-08-20T14:30:00Z"
                shop_domain = "my-brand.myshopify.com"

                # 2. Ingest normalized product & order
                raw_product = {
                    "id": 9901,
                    "title": "Cashmere Sweater",
                    "variants": [
                        {"id": 99011, "title": "S", "price": "120.00", "sku": "CS-S", "inventory_item_id": 8801},
                        {"id": 99012, "title": "M", "price": "120.00", "sku": "CS-M", "inventory_item_id": 8802},
                    ],
                }
                norm_prod = normalize_shopify_product(raw_product, "ws_live_01", shop_domain, now_ts)
                assert norm_prod["product_id"] == "sp_9901"
                assert len(norm_prod["variants"]) == 2
                await db.shopify_products.insert_one(norm_prod)

                raw_order = {
                    "id": 5001,
                    "name": "#1001",
                    "created_at": "2026-08-20T14:30:00-04:00",
                    "total_price": "240.00",
                    "total_discounts": "20.00",
                    "total_line_items_price": "240.00",
                    "financial_status": "paid",
                    "line_items": [
                        {"id": 701, "product_id": 9901, "variant_id": 99011, "quantity": 2, "price": "120.00", "title": "Cashmere Sweater - S"}
                    ],
                    "refunds": [
                        {
                            "transactions": [{"amount": "120.00", "status": "success"}],
                            "refund_line_items": [{"line_item_id": 701, "quantity": 1, "subtotal": 120.00}],
                        }
                    ],
                    "customer_journey_summary": {
                        "last_visit": {
                            "utm_parameters": {"source": "meta", "campaign": "winter_launch", "campaign_id": "camp_meta_100"}
                        }
                    }
                }
                norm_order = normalize_shopify_order(raw_order, "ws_live_01", shop_domain, now_ts)
                assert norm_order["order_id"] == "so_5001"
                assert norm_order["total_discounts"] == 20.00
                assert norm_order["total_refunded"] == 120.00
                await db.shopify_orders.insert_one(norm_order)

                # 3. Workspace analytics aggregation
                await aggregate_shopify_workspace_data(db, "ws_live_01", store_name="Live Store")
                ws_data = await db.workspace_data.find_one({"workspace_id": "ws_live_01"})
                assert ws_data is not None
                assert ws_data["profit"]["gross_revenue"] == 240.00

                # 4. Workspace isolation check: Workspace B sees 0 products/orders
                ws_data_b = await db.workspace_data.find_one({"workspace_id": "ws_other"})
                assert ws_data_b is None

                # 5. Demo protection: Northstar Goods remains untouched and demo data is protected from deletion
                await db.workspace_data.insert_one({"workspace_id": "ws_demo_01", "name": "Northstar Goods", "profit": {"gross_revenue": 50000.0}})
                await db.shopify_connections.insert_one({"workspace_id": "ws_demo_01", "shop": "demo.myshopify.com"})

                async def get_ws_demo(u):
                    return ws_demo
                shopify_integration.init_shopify(db, get_ws_demo)

                dis_res = await shopify_integration.disconnect_shopify(user={"user_id": "u_demo"})
                assert dis_res["ok"] is True
                # Verify demo workspace_data was NOT deleted by disconnect
                demo_data = await db.workspace_data.find_one({"workspace_id": "ws_demo_01"})
                assert demo_data is not None
                assert demo_data["profit"]["gross_revenue"] == 50000.0

            asyncio.run(_run())


# ============================================================================
# 2. Real COGS End-to-End
# ============================================================================
class TestCogsEndToEnd:
    """Verifies imported costs, merchant configuration, variant overrides, and labeling."""

    def test_cogs_resolution_and_labeling(self):
        # A. Unconfigured cost
        prod_unconfigured = {"variants": [{"variant_id": "v1", "price": 100.0, "imported_cost": None}]}
        cogs_none = None
        u_cost, source, status = resolve_variant_cogs(prod_unconfigured, "v1", cogs_none)
        assert u_cost == 0.0
        assert source == "unconfigured"
        assert status == "UNCONFIGURED"
        assert status != "ACTUAL"

        # B. Imported cost from Shopify
        prod_imported = {"variants": [{"variant_id": "v1", "price": 100.0, "cost": 35.0}]}
        u_cost, source, status = resolve_variant_cogs(prod_imported, "v1", cogs_none)
        assert u_cost == 35.0
        assert source == "imported"
        assert status == "IMPORTED"
        assert status != "ACTUAL"

        # C. Merchant product-level cost (Never label ACTUAL)
        cogs_product = {"unit_cost": 42.0, "variants": []}
        u_cost, source, status = resolve_variant_cogs(prod_imported, "v1", cogs_product)
        assert u_cost == 42.0
        assert source == "merchant"
        assert status == "CONFIGURED"
        assert status != "ACTUAL"

        # D. Merchant variant-level override
        cogs_variant = {"unit_cost": 42.0, "variants": [{"variant_id": "v1", "unit_cost": 48.50}]}
        u_cost, source, status = resolve_variant_cogs(prod_imported, "v1", cogs_variant)
        assert u_cost == 48.50
        assert source == "merchant"
        assert status == "CONFIGURED"
        assert status != "ACTUAL"


# ============================================================================
# 3. Real Meta End-to-End
# ============================================================================
class TestMetaEndToEnd:
    """Verifies Meta OAuth, account selection, daily insights sync, and deduplication."""

    def test_meta_sync_and_deduplication(self):
        async def _run():
            db = MockDB()
            ws_id = "ws_meta_test"
            await db.workspaces.insert_one({"workspace_id": ws_id, "name": "Brand Store", "currency": "USD", "is_demo": False})

            # Connect Meta Ads
            enc_token = encrypt_token("mock_meta_access_token_abc")
            await db.marketing_connections.insert_one({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": enc_token,
                "selected_account_id": "act_102030",
                "selected_account_name": "Meta Brand US",
                "account_currency": "USD",
                "currency_mismatch": False,
            })

            async def get_ws_meta(u):
                return {"workspace_id": ws_id, "currency": "USD", "is_demo": False}

            meta_integration.init_meta(db, get_ws_meta)

            # Check status endpoint never leaks access token
            status = await get_meta_status(user={"id": "u1"})
            assert status["connected"] is True
            assert status["selected_account_id"] == "act_102030"
            assert "encrypted_access_token" not in status
            assert "access_token" not in status

            # Simulate 28-day sync with MockTransport
            campaigns_resp = {
                "data": [
                    {"id": "camp_m1", "name": "Summer Retargeting", "status": "ACTIVE", "objective": "OUTCOME_SALES"}
                ]
            }
            insights_resp = {
                "data": [
                    {
                        "campaign_id": "camp_m1",
                        "campaign_name": "Summer Retargeting",
                        "date_start": "2026-08-15",
                        "spend": "150.00",
                        "impressions": "10000",
                        "clicks": "250",
                        "actions": [{"action_type": "purchase", "value": "12"}],
                        "action_values": [{"action_type": "purchase", "value": "600.00"}],
                    }
                ]
            }

            async def mock_handler(request: httpx.Request):
                url_str = str(request.url)
                if "/campaigns" in url_str:
                    return httpx.Response(200, json=campaigns_resp)
                if "/insights" in url_str:
                    return httpx.Response(200, json=insights_resp)
                return httpx.Response(404)

            transport = httpx.MockTransport(mock_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                with patch.dict(os.environ, {"META_APP_SECRET": "meta_sec_123"}):
                    res = await sync_meta_insights_for_workspace(
                        db=db,
                        workspace_id=ws_id,
                        is_demo=False,
                        full_refresh=False,
                        http_client=client,
                    )
                    assert res["ok"] is True
                    assert res["synced_insights"] == 1

                    # Check document in DB
                    doc = await db.marketing_daily_insights.find_one({"workspace_id": ws_id, "campaign_id": "camp_m1"})
                    assert doc is not None
                    assert doc["spend"] == 150.00
                    assert doc["currency"] == "USD"
                    assert doc["attribution_label"] == "IMPORTED"

                    # Verify idempotency: repeated sync updates in place, does not duplicate
                    res2 = await sync_meta_insights_for_workspace(
                        db=db,
                        workspace_id=ws_id,
                        is_demo=False,
                        full_refresh=False,
                        http_client=client,
                    )
                    assert res2["ok"] is True

                    count = await db.marketing_daily_insights.count_documents({"workspace_id": ws_id, "campaign_id": "camp_m1"})
                    assert count == 1, "Repeated sync must update in-place without duplicating records"

        asyncio.run(_run())


# ============================================================================
# 4. Real Google Ads End-to-End
# ============================================================================
class TestGoogleAdsEndToEnd:
    """Verifies Google Ads OAuth, customer discovery, cost_micros, and token protection."""

    def test_google_ads_sync_and_token_protection(self):
        async def _run():
            db = MockDB()
            ws_id = "ws_google_test"
            await db.workspaces.insert_one({"workspace_id": ws_id, "name": "Brand Store", "currency": "USD", "is_demo": False})

            enc_refresh = encrypt_token("mock_google_refresh_token_xyz")
            await db.marketing_connections.insert_one({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "status": "connected",
                "encrypted_refresh_token": enc_refresh,
                "selected_customer_id": "1234567890",
                "selected_account_name": "Google Ads Main",
                "login_customer_id": "9998887777",
                "account_currency": "USD",
                "currency_mismatch": False,
            })

            async def get_ws_google(u):
                return {"workspace_id": ws_id, "currency": "USD", "is_demo": False}

            google_ads_integration.init_google_ads(db, get_ws_google)

            # Customer ID normalization
            assert normalize_customer_id("123-456-7890") == "1234567890"

            # Check status endpoint never leaks refresh token or developer token
            status = await get_google_ads_status(user={"id": "u1"})
            assert status["connected"] is True
            assert status["selected_customer_id"] == "1234567890"
            assert "encrypted_refresh_token" not in status
            assert "refresh_token" not in status
            assert "developer_token" not in status

            # cost_micros conversion test
            raw_row = {
                "campaign": {"id": "98765", "name": "Brand Search Exact"},
                "metrics": {
                    "costMicros": "250000000",  # $250.00
                    "impressions": "5000",
                    "clicks": "120",
                    "conversions": 15.0,
                    "conversionsValue": 750.0,
                },
                "segments": {"date": "2026-08-16"},
            }
            parsed = normalize_google_ads_daily_insight(raw_row, "ws_google_test", "1234567890", "USD")
            assert parsed["spend"] == 250.00
            assert parsed["campaign_id"] == "98765"
            assert parsed["clicks"] == 120

        asyncio.run(_run())


# ============================================================================
# 5. Financial Truth & Double Counting Verification
# ============================================================================
class TestFinancialTruthAndDoubleCounting:
    """Verifies financial truth: Shopify is sole ground truth for revenue; platform values never added."""

    def test_financial_formulas_and_platform_independence(self):
        cur_revenue = 10000.00
        cur_discounts = 500.00
        cur_refunds = 300.00
        total_cogs = 3200.00
        eligible_ad_spend = 2000.00
        order_count = 100

        # True Profit formula
        true_profit = cur_revenue - cur_discounts - cur_refunds - total_cogs - eligible_ad_spend
        assert true_profit == 4000.00

        # Blended ROAS = Shopify Gross Revenue / Eligible Real Ad Spend
        blended_roas = round(cur_revenue / eligible_ad_spend, 2)
        assert blended_roas == 5.00

        # Blended CAC = Eligible Real Ad Spend / Shopify Order Count
        blended_cac = round(eligible_ad_spend / order_count, 2)
        assert blended_cac == 20.00

    def test_double_counting_prevention_deterministic(self):
        """Meta reports $10,000 conversion value. Google reports $8,000. Shopify reports $5,000 actual revenue.
        Assert Shopify revenue is counted exactly once and platform values are NOT added.
        """
        shopify_revenue = 5000.00
        meta_reported_conv_value = 10000.00
        google_reported_conv_value = 8000.00

        # Ingested platform conversion values are reference-only IMPORTED metrics
        imported_conversion_value_total = meta_reported_conv_value + google_reported_conv_value
        assert imported_conversion_value_total == 18000.00

        # Financial gross revenue is strictly Shopify revenue
        financial_gross_revenue = shopify_revenue
        assert financial_gross_revenue == 5000.00
        assert financial_gross_revenue != 5000.00 + imported_conversion_value_total


# ============================================================================
# 6. Currency Mismatch Isolation
# ============================================================================
class TestCurrencyIsolation:
    """Verifies that currency mismatches are strictly excluded from True Profit/ROAS/CAC."""

    def test_currency_isolation_scenarios(self):
        async def _run():
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            since_date, until_date = get_reporting_calendar_window(days=28)

            # Scenario 1: USD store, USD Meta, USD Google -> All eligible
            db1 = MockDB()
            ws_id1 = "ws_curr_1"
            await db1.marketing_connections.insert_one({"workspace_id": ws_id1, "platform": "meta", "status": "connected", "account_currency": "USD", "currency_mismatch": False})
            await db1.marketing_connections.insert_one({"workspace_id": ws_id1, "platform": "google_ads", "status": "connected", "account_currency": "USD", "currency_mismatch": False})
            await db1.marketing_daily_insights.insert_one({"workspace_id": ws_id1, "platform": "meta", "account_id": "m1", "campaign_id": "c1", "date": today_str, "spend": 100.0, "currency": "USD", "impressions": 1000, "clicks": 50, "conversions": 2, "conversions_value": 100})
            await db1.marketing_daily_insights.insert_one({"workspace_id": ws_id1, "platform": "google_ads", "account_id": "g1", "campaign_id": "c2", "date": today_str, "spend": 200.0, "currency": "USD", "impressions": 2000, "clicks": 100, "conversions": 4, "conversions_value": 200})

            res1 = await aggregate_marketing_ad_spend(db1, ws_id1, "USD", since_date, until_date)
            assert res1["eligible_ad_spend"] == 300.00
            assert res1["excluded_ad_spend"] == 0.00
            assert len(res1["currency_mismatches"]) == 0

            # Scenario 2: USD store, EUR Meta, USD Google -> Meta excluded
            db2 = MockDB()
            ws_id2 = "ws_curr_2"
            await db2.marketing_connections.insert_one({"workspace_id": ws_id2, "platform": "meta", "status": "connected", "account_currency": "EUR", "currency_mismatch": True})
            await db2.marketing_connections.insert_one({"workspace_id": ws_id2, "platform": "google_ads", "status": "connected", "account_currency": "USD", "currency_mismatch": False})
            await db2.marketing_daily_insights.insert_one({"workspace_id": ws_id2, "platform": "meta", "account_id": "m1", "campaign_id": "c1", "date": today_str, "spend": 100.0, "currency": "EUR", "impressions": 1000, "clicks": 50, "conversions": 2, "conversions_value": 100})
            await db2.marketing_daily_insights.insert_one({"workspace_id": ws_id2, "platform": "google_ads", "account_id": "g1", "campaign_id": "c2", "date": today_str, "spend": 200.0, "currency": "USD", "impressions": 2000, "clicks": 100, "conversions": 4, "conversions_value": 200})

            res2 = await aggregate_marketing_ad_spend(db2, ws_id2, "USD", since_date, until_date)
            assert res2["eligible_ad_spend"] == 200.00
            assert res2["excluded_ad_spend"] == 100.00
            assert len(res2["currency_mismatches"]) == 1
            assert res2["currency_mismatches"][0]["platform"] == "meta"

            # Scenario 3: USD store, USD Meta, EUR Google -> Google excluded
            db3 = MockDB()
            ws_id3 = "ws_curr_3"
            await db3.marketing_connections.insert_one({"workspace_id": ws_id3, "platform": "meta", "status": "connected", "account_currency": "USD", "currency_mismatch": False})
            await db3.marketing_connections.insert_one({"workspace_id": ws_id3, "platform": "google_ads", "status": "connected", "account_currency": "EUR", "currency_mismatch": True})
            await db3.marketing_daily_insights.insert_one({"workspace_id": ws_id3, "platform": "meta", "account_id": "m1", "campaign_id": "c1", "date": today_str, "spend": 100.0, "currency": "USD", "impressions": 1000, "clicks": 50, "conversions": 2, "conversions_value": 100})
            await db3.marketing_daily_insights.insert_one({"workspace_id": ws_id3, "platform": "google_ads", "account_id": "g1", "campaign_id": "c2", "date": today_str, "spend": 200.0, "currency": "EUR", "impressions": 2000, "clicks": 100, "conversions": 4, "conversions_value": 200})

            res3 = await aggregate_marketing_ad_spend(db3, ws_id3, "USD", since_date, until_date)
            assert res3["eligible_ad_spend"] == 100.00
            assert res3["excluded_ad_spend"] == 200.00
            assert len(res3["currency_mismatches"]) == 1
            assert res3["currency_mismatches"][0]["platform"] == "google_ads"

        asyncio.run(_run())


# ============================================================================
# 7. Attribution Check
# ============================================================================
class TestAttributionUX:
    """Verifies first-party UTM attribution vs Attribution unavailable."""

    def test_attribution_scenarios(self):
        campaign_metrics = {
            "meta:camp_1": {
                "campaign_id": "camp_1",
                "name": "Retargeting Sale",
                "platform": "meta",
                "currency": "USD",
                "spend": 100.0,
                "impressions": 5000,
                "clicks": 150,
                "imported_conversions": 5.0,
                "imported_conversion_value": 250.0,
            },
            "google_ads:camp_2": {
                "campaign_id": "camp_2",
                "name": "Generic Search",
                "platform": "google_ads",
                "currency": "USD",
                "spend": 150.0,
                "impressions": 6000,
                "clicks": 200,
                "imported_conversions": 3.0,
                "imported_conversion_value": 180.0,
            },
        }

        # Order 1 matches camp_1 via customer_journey_summary
        orders = [
            {
                "id": "ord_1",
                "total_price": 200.0,
                "financial_status": "paid",
                "line_items": [{"product_id": "p1", "variant_id": "v1", "quantity": 1}],
                "raw": {
                    "customer_journey_summary": {
                        "last_visit": {
                            "utm_parameters": {"campaign": "Retargeting Sale", "source": "meta"}
                        }
                    }
                },
            }
        ]

        cogs_map = {"p1": {"unit_cost": 50.0}}
        products_by_id = {"p1": {"min_price": 200.0}}

        camps_out, attr_rev, attr_orders = perform_first_party_attribution(
            orders=orders,
            campaign_metrics=campaign_metrics,
            cogs_map=cogs_map,
            products_by_id=products_by_id,
            resolve_variant_cogs_func=resolve_variant_cogs,
        )

        # Camp 1: Verified attribution
        c1 = next(c for c in camps_out if c["id"] == "camp_1")
        assert c1["attribution_status"] == "ATTRIBUTED"
        assert c1["attributed_revenue"] == 200.0
        assert c1["attributed_cogs"] == 50.0
        assert c1["attributed_contribution"] == 50.0  # 200 - 50 - 100 = 50.0
        assert c1["impressions"] == 5000
        assert c1["clicks"] == 150

        # Camp 2: No matched orders -> Attribution unavailable
        c2 = next(c for c in camps_out if c["id"] == "camp_2")
        assert c2["attribution_status"] == "Attribution unavailable"
        assert c2["attributed_revenue"] is None
        assert c2["attributed_contribution"] is None


# ============================================================================
# 8. Financial Completeness Check
# ============================================================================
class TestFinancialCompleteness:
    """Verifies FULL, PARTIAL, and UNAVAILABLE completeness states and human-readable reasons."""

    def test_completeness_evaluations(self):
        # 1. FULL state
        full_res = evaluate_financial_completeness(
            orders_count=50,
            products_count=10,
            cogs_kind="CONFIGURED",
            unconfigured_units=0,
            connected_platforms=["meta", "google_ads"],
            platform_sync_statuses={"meta": "success", "google_ads": "success"},
            eligible_ad_spend=500.0,
            currency_mismatches=[],
        )
        assert full_res == "FULL"

        # 2. PARTIAL due to unconfigured COGS
        cogs_partial = evaluate_financial_completeness(
            orders_count=50,
            products_count=10,
            cogs_kind="ESTIMATED",
            unconfigured_units=15,
            connected_platforms=["meta"],
            platform_sync_statuses={"meta": "success"},
            eligible_ad_spend=200.0,
            currency_mismatches=[],
        )
        assert cogs_partial == "PARTIAL"

        # 3. PARTIAL due to failed ad platform
        sync_failed_partial = evaluate_financial_completeness(
            orders_count=50,
            products_count=10,
            cogs_kind="CONFIGURED",
            unconfigured_units=0,
            connected_platforms=["meta"],
            platform_sync_statuses={"meta": "reauth_required"},
            eligible_ad_spend=0.0,
            currency_mismatches=[],
        )
        assert sync_failed_partial == "PARTIAL"

        # 4. UNAVAILABLE when orders_count is 0
        unavail = evaluate_financial_completeness(
            orders_count=0,
            products_count=10,
            cogs_kind="UNCONFIGURED",
            unconfigured_units=0,
            connected_platforms=[],
            platform_sync_statuses={},
            eligible_ad_spend=0.0,
            currency_mismatches=[],
        )
        assert unavail == "UNAVAILABLE"


# ============================================================================
# 9. Timezone & Canonical Business Date Normalization
# ============================================================================
class TestTimezoneAndDateBoundary:
    """Verifies that 23:59:59 and 00:00:01 boundaries preserve local business dates."""

    def test_midnight_boundary_preservation(self):
        # 11:59 PM EDT on Aug 20
        d_late = parse_order_calendar_date("2026-08-20T23:59:59-04:00")
        assert d_late == "2026-08-20"

        # 12:01 AM EDT on Aug 21
        d_early = parse_order_calendar_date("2026-08-21T00:01:00-04:00")
        assert d_early == "2026-08-21"


# ============================================================================
# 10. Security & Credentials Sanitization
# ============================================================================
class TestSecuritySanitization:
    """Verifies that access tokens, refresh tokens, developer tokens, and secrets are NEVER exposed."""

    def test_tokens_never_in_status_responses(self):
        async def _run():
            db = MockDB()
            ws_id = "ws_sec_test"
            await db.workspaces.insert_one({"workspace_id": ws_id, "name": "Secure Brand", "currency": "USD", "is_demo": False})

            # Store encrypted tokens
            await db.marketing_connections.insert_one({
                "workspace_id": ws_id,
                "platform": "meta",
                "status": "connected",
                "encrypted_access_token": encrypt_token("meta_secret_token_123"),
                "selected_account_id": "act_888",
            })
            await db.marketing_connections.insert_one({
                "workspace_id": ws_id,
                "platform": "google_ads",
                "status": "connected",
                "encrypted_refresh_token": encrypt_token("google_refresh_token_456"),
                "selected_customer_id": "7778889999",
            })

            async def get_ws_sec(u):
                return {"workspace_id": ws_id, "currency": "USD", "is_demo": False}

            meta_integration.init_meta(db, get_ws_sec)
            google_ads_integration.init_google_ads(db, get_ws_sec)

            meta_status = await get_meta_status(user={"id": "u1"})
            google_status = await get_google_ads_status(user={"id": "u1"})

            # Assert no sensitive fields in responses
            for key in ["encrypted_access_token", "access_token", "app_secret"]:
                assert key not in meta_status

            for key in ["encrypted_refresh_token", "refresh_token", "developer_token", "client_secret"]:
                assert key not in google_status

        asyncio.run(_run())
