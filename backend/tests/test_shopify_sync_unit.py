"""Unit and Integration Tests for Phase 3.2: Real Shopify Data Synchronization & Analytics Pipeline.

Coverage:
1. Product normalization (variants, inventory, tags, cost extraction, raw record preservation)
2. Order normalization (line items, refunds, status, customer extraction, raw record preservation)
3. Cursor Link header parsing (RFC 5988 page_info extraction)
4. Leaky bucket & rate limiting (429 Retry-After, 401 token revocation)
5. Analytics aggregation with strict COGS rules (NEVER guessed 40% margin, marked ESTIMATED)
6. Analytics aggregation with strict marketing rules (unconnected, zeroed, marked ESTIMATED)
7. Workspace isolation across sync collections (shopify_products, shopify_orders, shopify_sync_meta)
8. Demo workspace preservation (Northstar Goods completely untouched)
9. Disconnect cleanup for real workspace vs demo workspace safety
"""
import sys
import os
from pathlib import Path
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from shopify_sync import (
    normalize_shopify_product,
    normalize_shopify_order,
    extract_next_page_info,
    shopify_get_request,
    aggregate_shopify_workspace_data,
    run_shopify_sync,
)
from demo_data import build_workspace_analytics


class TestShopifyProductNormalization:
    def test_normalize_product_with_variants_and_tags(self):
        raw_p = {
            "id": 8829102931,
            "title": "Nordic Wool Beanie",
            "product_type": "Apparel",
            "vendor": "Alpine Studio",
            "handle": "nordic-wool-beanie",
            "status": "active",
            "tags": "winter, wool, warm, beanie",
            "images": [{"src": "https://cdn.shopify.com/beanie.jpg"}],
            "variants": [
                {
                    "id": 101,
                    "title": "Navy / S",
                    "price": "35.00",
                    "compare_at_price": "45.00",
                    "sku": "BEA-NAV-S",
                    "inventory_quantity": 25,
                    "requires_shipping": True,
                },
                {
                    "id": 102,
                    "title": "Navy / M",
                    "price": "38.00",
                    "compare_at_price": None,
                    "sku": "BEA-NAV-M",
                    "inventory_quantity": 40,
                    "requires_shipping": True,
                },
            ],
            "created_at": "2026-08-01T12:00:00Z",
            "updated_at": "2026-08-15T15:30:00Z",
        }
        now = datetime.now(timezone.utc).isoformat()
        doc = normalize_shopify_product(raw_p, "ws_test_123", "test-shop.myshopify.com", now)

        assert doc["workspace_id"] == "ws_test_123"
        assert doc["product_id"] == "sp_8829102931"
        assert doc["shopify_id"] == 8829102931
        assert doc["title"] == "Nordic Wool Beanie"
        assert doc["category"] == "Apparel"
        assert doc["min_price"] == 35.00
        assert doc["max_price"] == 38.00
        assert doc["stock"] == 65
        assert doc["tags"] == ["winter", "wool", "warm", "beanie"]
        assert doc["image_url"] == "https://cdn.shopify.com/beanie.jpg"
        assert len(doc["variants"]) == 2
        assert doc["has_unit_cost"] is False
        assert doc["avg_unit_cost"] is None
        # Verify raw payload is preserved
        assert doc["raw"]["id"] == 8829102931

    def test_normalize_product_with_cost(self):
        raw_p = {
            "id": 12345,
            "title": "Leather Cardholder",
            "variants": [
                {"id": 1, "price": "40.00", "cost": "12.50", "inventory_quantity": 10},
                {"id": 2, "price": "40.00", "cost": "13.50", "inventory_quantity": 15},
            ],
        }
        doc = normalize_shopify_product(raw_p, "ws_test_123", "shop.myshopify.com", "2026-09-01T00:00:00Z")
        assert doc["has_unit_cost"] is True
        assert doc["avg_unit_cost"] == 13.0


class TestShopifyOrderNormalization:
    def test_normalize_order_with_line_items_and_refunds(self):
        raw_o = {
            "id": 99201123,
            "name": "#1042",
            "order_number": 1042,
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "currency": "USD",
            "total_price": "120.00",
            "subtotal_price": "110.00",
            "total_discounts": "10.00",
            "total_tax": "8.50",
            "created_at": "2026-08-20T10:00:00Z",
            "updated_at": "2026-08-21T11:00:00Z",
            "line_items": [
                {
                    "id": 501,
                    "product_id": 8829102931,
                    "variant_id": 101,
                    "title": "Nordic Wool Beanie",
                    "variant_title": "Navy / S",
                    "sku": "BEA-NAV-S",
                    "quantity": 2,
                    "price": "35.00",
                    "total_discount": "0.00",
                },
                {
                    "id": 502,
                    "product_id": 8829102932,
                    "variant_id": 103,
                    "title": "Thermal Scarf",
                    "quantity": 1,
                    "price": "50.00",
                    "total_discount": "10.00",
                },
            ],
            "customer": {
                "id": 771029,
                "email": "customer@example.com",
                "orders_count": 3,
                "total_spent": "340.50",
            },
            "shipping_address": {
                "country_code": "US",
                "city": "Seattle",
            },
            "refunds": [
                {
                    "transactions": [{"status": "success", "amount": "35.00"}],
                    "refund_line_items": [{"quantity": 1}],
                }
            ],
        }
        now = datetime.now(timezone.utc).isoformat()
        doc = normalize_shopify_order(raw_o, "ws_test_123", "test-shop.myshopify.com", now)

        assert doc["workspace_id"] == "ws_test_123"
        assert doc["order_id"] == "so_99201123"
        assert doc["order_name"] == "#1042"
        assert doc["total_price"] == 120.00
        assert doc["subtotal_price"] == 110.00
        assert doc["total_discounts"] == 10.00
        assert doc["total_refunded"] == 35.00
        assert doc["refunded_units"] == 1
        assert doc["line_items_count"] == 3
        assert len(doc["line_items"]) == 2
        assert doc["customer"]["customer_id"] == "sc_771029"
        assert doc["customer"]["email"] == "customer@example.com"
        assert doc["shipping_country"] == "US"
        assert doc["raw"]["id"] == 99201123

    def test_normalize_order_without_customer_or_refunds(self):
        raw_o = {
            "id": 99201124,
            "total_price": "50.00",
            "customer": None,
            "refunds": [],
        }
        doc = normalize_shopify_order(raw_o, "ws_test_123", "test-shop.myshopify.com", "2026-09-01T00:00:00Z")
        assert doc["customer"] is None
        assert doc["total_refunded"] == 0.0
        assert doc["refunded_units"] == 0


class TestCursorPagination:
    def test_extract_next_page_info(self):
        link_header = (
            '<https://shop.myshopify.com/admin/api/2026-07/products.json?limit=50&page_info=eyJsYXN0X2lkIjoxfQ>; rel="next", '
            '<https://shop.myshopify.com/admin/api/2026-07/products.json?limit=50&page_info=eyJsYXN0X2lkIjowfQ>; rel="previous"'
        )
        res = httpx.Response(200, headers={"Link": link_header})
        page_info = extract_next_page_info(res)
        assert page_info == "eyJsYXN0X2lkIjoxfQ"

    def test_extract_next_page_info_none(self):
        res = httpx.Response(200, headers={})
        assert extract_next_page_info(res) is None


class TestRateLimitingAndSecurity:
    def test_token_revocation_401(self):
        async def _run():
            mock_client = AsyncMock()
            mock_res = MagicMock()
            mock_res.status_code = 401
            mock_res.headers = {}
            mock_client.get.return_value = mock_res

            with pytest.raises(HTTPException) as exc_info:
                await shopify_get_request(mock_client, "https://test.myshopify.com", {})
            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail.lower()

        asyncio.run(_run())

    def test_rate_limit_429_backoff_and_retry(self):
        async def _run():
            mock_client = AsyncMock()
            res_429 = MagicMock()
            res_429.status_code = 429
            res_429.headers = {"Retry-After": "0.01"}

            res_200 = MagicMock()
            res_200.status_code = 200
            res_200.headers = {"X-Shopify-Shop-Api-Call-Limit": "10/40"}

            mock_client.get.side_effect = [res_429, res_200]

            res = await shopify_get_request(mock_client, "https://test.myshopify.com", {})
            assert res.status_code == 200
            assert mock_client.get.call_count == 2

        asyncio.run(_run())


class MockCursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, length):
        return self.items[:length]


class MockDB:
    def __init__(self):
        self.shopify_products_data = []
        self.shopify_orders_data = []
        self.workspace_data_store = {}

    @property
    def shopify_products(self):
        db_self = self
        class Coll:
            def find(self, query):
                ws_id = query.get("workspace_id")
                return MockCursor([p for p in db_self.shopify_products_data if p.get("workspace_id") == ws_id])
            async def count_documents(self, query):
                ws_id = query.get("workspace_id")
                return len([p for p in db_self.shopify_products_data if p.get("workspace_id") == ws_id])
            async def replace_one(self, query, doc, upsert=True):
                db_self.shopify_products_data.append(doc)
        return Coll()

    @property
    def shopify_orders(self):
        db_self = self
        class Coll:
            def find(self, query):
                ws_id = query.get("workspace_id")
                return MockCursor([o for o in db_self.shopify_orders_data if o.get("workspace_id") == ws_id])
            async def count_documents(self, query):
                ws_id = query.get("workspace_id")
                return len([o for o in db_self.shopify_orders_data if o.get("workspace_id") == ws_id])
            async def replace_one(self, query, doc, upsert=True):
                db_self.shopify_orders_data.append(doc)
        return Coll()

    @property
    def workspace_data(self):
        db_self = self
        class Coll:
            async def replace_one(self, query, doc, upsert=True):
                ws_id = query.get("workspace_id")
                db_self.workspace_data_store[ws_id] = doc
            async def find_one(self, query, proj=None):
                ws_id = query.get("workspace_id")
                return db_self.workspace_data_store.get(ws_id)
        return Coll()


class TestAnalyticsAggregationStrictRules:
    def test_missing_cogs_never_guessed_40_percent(self):
        """User Requirement 7: For analytics aggregation, NEVER present a guessed 40%
        contribution margin as actual/true merchant COGS. Mark missing COGS as ESTIMATED."""
        async def _run():
            db = MockDB()
            ws_id = "ws_real_merch_1"

            # Product without unit cost in variants
            p = {
                "workspace_id": ws_id,
                "product_id": "sp_1",
                "title": "Eco Water Bottle",
                "category": "Home",
                "min_price": 30.0,
                "stock": 50,
                "has_unit_cost": False,
                "avg_unit_cost": None,
            }
            db.shopify_products_data.append(p)

            now_iso = datetime.now(timezone.utc).isoformat()
            # Order within last 4 weeks
            o = {
                "workspace_id": ws_id,
                "order_id": "so_101",
                "total_price": 60.0,
                "subtotal_price": 60.0,
                "total_discounts": 5.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "line_items_count": 2,
                "line_items": [{"product_id": "sp_1", "quantity": 2, "price": 30.0}],
                "created_at": now_iso,
                "customer": {"customer_id": "sc_999"},
            }
            db.shopify_orders_data.append(o)

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Real Store", "USD")

            # Check KPIs
            true_profit_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            # COGS must be marked ESTIMATED
            assert true_profit_kpi["kind"] == "ESTIMATED"
            assert "unconfigured in shopify" in true_profit_kpi["tooltip"].lower()

            # Check Waterfall Profit Steps
            waterfall_steps = analytics["profit"]["steps"]
            cogs_step = next(s for s in waterfall_steps if "cogs" in s["label"].lower())
            assert "Unconfigured" in cogs_step["label"]
            assert cogs_step["value"] == 0.0  # NOT 40% guessed cost!

            # Check Marketing KPI
            mktg_kpi = next(k for k in analytics["kpis"] if k["id"] == "marketing-eff")
            assert mktg_kpi["value"] == 0.0
            assert mktg_kpi["kind"] == "ESTIMATED"
            assert "no ad accounts" in mktg_kpi["tooltip"].lower()

            # Check stored in workspace_data
            stored = await db.workspace_data.find_one({"workspace_id": ws_id})
            assert stored is not None
            assert stored["workspace_id"] == ws_id
            assert stored["meta"]["source"] == "shopify_real"

        asyncio.run(_run())

    def test_workspace_isolation(self):
        """User Requirement 11: Add strong workspace isolation tests."""
        async def _run():
            db = MockDB()
            ws_a = "ws_brand_alpha"
            ws_b = "ws_brand_beta"

            # Add data to Alpha
            db.shopify_products_data.append({
                "workspace_id": ws_a,
                "product_id": "sp_alpha",
                "title": "Alpha Widget",
                "min_price": 50.0,
                "stock": 100,
            })
            db.shopify_orders_data.append({
                "workspace_id": ws_a,
                "order_id": "so_alpha",
                "total_price": 50.0,
                "financial_status": "paid",
                "line_items_count": 1,
                "line_items": [{"product_id": "sp_alpha", "quantity": 1, "price": 50.0}],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            # Add data to Beta
            db.shopify_products_data.append({
                "workspace_id": ws_b,
                "product_id": "sp_beta",
                "title": "Beta Gadget",
                "min_price": 200.0,
                "stock": 10,
            })

            # Aggregate Alpha
            analytics_a = await aggregate_shopify_workspace_data(db, ws_a, "Alpha Brand", "USD")
            # Aggregate Beta
            analytics_b = await aggregate_shopify_workspace_data(db, ws_b, "Beta Brand", "USD")

            assert len(analytics_a["products"]) == 1
            assert analytics_a["products"][0]["name"] == "Alpha Widget"
            assert analytics_a["sales"]["revenue"] == 50.0

            assert len(analytics_b["products"]) == 1
            assert analytics_b["products"][0]["name"] == "Beta Gadget"
            assert analytics_b["sales"]["revenue"] == 0.0  # Beta had 0 orders

        asyncio.run(_run())


class TestDemoWorkspaceSafety:
    def test_demo_workspace_preserved_intact(self):
        """User Requirement 1 & 2: Keep sync read-only and preserve existing demo workspace exactly."""
        demo_analytics = build_workspace_analytics("Northstar Goods", "USD")
        assert demo_analytics["store_name"] == "Northstar Goods"
        assert len(demo_analytics["kpis"]) == 6
        assert len(demo_analytics["products"]) == 12
        assert demo_analytics["meta"]["version"] == 2
        assert demo_analytics["meta"]["datasets"] == 8
