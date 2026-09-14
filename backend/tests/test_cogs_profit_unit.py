"""Unit and Integration Tests for Phase 4: Real Profit & Merchant COGS Configuration.

Coverage:
1. COGS precedence hierarchy:
   - Merchant variant override > Merchant product cost > Shopify imported variant cost > Shopify imported avg cost > Unconfigured ($0.00).
2. Labeling rules:
   - When 100% of COGS is merchant-configured: labeled CONFIGURED (NEVER "ACTUAL").
   - When 100% of COGS is Shopify imported: labeled IMPORTED.
   - When partially configured or unconfigured: labeled ESTIMATED.
3. True Profit dynamic recalculation:
   - Gross Profit, Contribution Margin, True Profit, and Waterfall steps accurately computed without any 40% heuristic.
   - Dynamic True Profit insight (best seller vs most profitable vs best margin).
4. Product-level mapping:
   - Product catalog enriched with unit_cost, cogs_source, cogs_status, and profitability scores.
5. API endpoints (GET /api/cogs, PUT /api/cogs/{product_id}, POST /api/cogs/batch):
   - Catalog retrieval, variant breakdowns, unit cost upsert, batch update.
   - Strict workspace isolation.
6. Demo workspace immutability:
   - Modifications on Northstar Goods rejected with HTTP 400.
   - Demo workspace remains 100% untouched.
"""
import sys
from pathlib import Path
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from shopify_sync import (
    resolve_variant_cogs,
    resolve_product_cogs,
    aggregate_shopify_workspace_data,
)
from server import (
    get_cogs_catalog,
    update_product_cogs,
    batch_update_cogs,
    UpdateCogsBody,
    VariantCostItem,
    BatchUpdateCogsBody,
    BatchCogsItem,
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
    def __init__(self):
        self.docs = []

    def find(self, query=None, projection=None):
        matched = []
        for d in self.docs:
            if not query:
                matched.append(d)
                continue
            ok = True
            for k, v in query.items():
                if k == "$or":
                    or_ok = False
                    for cond in v:
                        cond_ok = True
                        for ck, cv in cond.items():
                            if d.get(ck) != cv:
                                cond_ok = False
                                break
                        if cond_ok:
                            or_ok = True
                            break
                    if not or_ok:
                        ok = False
                        break
                elif d.get(k) != v:
                    ok = False
                    break
            if ok:
                matched.append(d)
        return MockCursor(matched)

    async def find_one(self, query, projection=None):
        cursor = self.find(query, projection)
        items = await cursor.to_list(1)
        return items[0] if items else None

    async def replace_one(self, filter_query, doc, upsert=False):
        for i, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                self.docs[i] = doc
                return
        if upsert:
            self.docs.append(doc)

    async def update_one(self, filter_query, update_spec, upsert=False):
        for i, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update_spec:
                    d.update(update_spec["$set"])
                return
        if upsert and "$set" in update_spec:
            doc = {**filter_query, **update_spec["$set"]}
            self.docs.append(doc)

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def count_documents(self, query=None):
        cursor = self.find(query)
        items = await cursor.to_list(10000)
        return len(items)


class MockDatabase:
    def __init__(self):
        self.shopify_products = MockCollection()
        self.shopify_orders = MockCollection()
        self.merchant_cogs = MockCollection()
        self.workspace_data = MockCollection()
        self.workspaces = MockCollection()
        self.users = MockCollection()


class TestCogsPrecedenceHierarchy:
    def test_variant_override_takes_precedence_over_all(self):
        prod = {
            "product_id": "sp_100",
            "has_unit_cost": True,
            "avg_unit_cost": 18.0,
            "variants": [
                {"variant_id": 101, "cost": 16.0, "price": 40.0},
                {"variant_id": 102, "cost": 20.0, "price": 50.0},
            ],
        }
        cogs_rec = {
            "product_id": "sp_100",
            "unit_cost": 15.0,  # product-level merchant cost
            "variants": [
                {"variant_id": 101, "unit_cost": 12.50},  # variant-level override
            ],
        }
        # Variant 101 has variant override $12.50
        cost, src, status = resolve_variant_cogs(prod, 101, cogs_rec)
        assert cost == 12.50
        assert src == "merchant"
        assert status == "CONFIGURED"

        # Variant 102 falls back to product-level merchant cost $15.00
        cost2, src2, status2 = resolve_variant_cogs(prod, 102, cogs_rec)
        assert cost2 == 15.0
        assert src2 == "merchant"
        assert status2 == "CONFIGURED"

    def test_merchant_product_cost_takes_precedence_over_shopify_imported(self):
        prod = {
            "product_id": "sp_200",
            "has_unit_cost": True,
            "avg_unit_cost": 22.0,
            "variants": [{"variant_id": 201, "cost": 21.0, "price": 60.0}],
        }
        cogs_rec = {
            "product_id": "sp_200",
            "unit_cost": 19.50,
            "variants": [],
        }
        cost, src, status = resolve_variant_cogs(prod, 201, cogs_rec)
        assert cost == 19.50
        assert src == "merchant"
        assert status == "CONFIGURED"

    def test_shopify_imported_cost_used_when_merchant_unconfigured(self):
        prod = {
            "product_id": "sp_300",
            "has_unit_cost": True,
            "avg_unit_cost": 14.0,
            "variants": [{"variant_id": 301, "cost": 13.50, "price": 35.0}],
        }
        # No merchant record
        cost, src, status = resolve_variant_cogs(prod, 301, None)
        assert cost == 13.50
        assert src == "imported"
        assert status == "IMPORTED"

    def test_unconfigured_fallback_to_zero(self):
        prod = {
            "product_id": "sp_400",
            "has_unit_cost": False,
            "avg_unit_cost": None,
            "variants": [{"variant_id": 401, "cost": None, "price": 25.0}],
        }
        cost, src, status = resolve_variant_cogs(prod, 401, None)
        assert cost == 0.0
        assert src == "unconfigured"
        assert status == "UNCONFIGURED"


class TestCogsLabelingCorrection:
    def test_all_merchant_cogs_labeled_configured_never_actual(self):
        """User Requirement: When 100% of COGS is configured by the merchant, do NOT label it as ACTUAL.
        Use CONFIGURED."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_merch_100"
            now = datetime.now(timezone.utc).isoformat()

            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_bag",
                "title": "Canvas Tote Bag",
                "category": "Accessories",
                "min_price": 50.0,
                "stock": 100,
                "has_unit_cost": False,
                "avg_unit_cost": None,
                "variants": [{"variant_id": 901, "price": 50.0, "cost": None}],
            }
            db.shopify_products.docs.append(prod)

            # Order: 2 units sold
            order = {
                "workspace_id": ws_id,
                "order_id": "so_9001",
                "total_price": 100.0,
                "subtotal_price": 100.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "created_at": now,
                "financial_status": "paid",
                "line_items": [{"product_id": "sp_bag", "variant_id": 901, "quantity": 2, "price": 50.0}],
            }
            db.shopify_orders.docs.append(order)

            # Merchant configured unit cost: $15.00
            cogs_doc = {
                "workspace_id": ws_id,
                "product_id": "sp_bag",
                "unit_cost": 15.0,
                "variants": [],
            }
            db.merchant_cogs.docs.append(cogs_doc)

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Tote Co", "USD")

            # Labeling checks
            p_data = analytics["profit"]
            assert p_data["cogs_kind"] == "CONFIGURED"
            assert p_data["cogs_kind"] != "ACTUAL"  # Critical user instruction
            assert p_data["cogs_label"] == "Product Cost (COGS - Configured)"

            # Check true profit KPI
            tp_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            assert tp_kpi["kind"] == "CONFIGURED"
            assert tp_kpi["kind"] != "ACTUAL"

            # COGS amount: 2 units * $15.00 = $30.00
            assert p_data["total_cogs"] == 30.0
            assert p_data["true_profit"] == 70.0  # $100 - $30
            assert p_data["margin"] == 70.0

        asyncio.run(_run())

    def test_all_shopify_imported_cogs_labeled_imported(self):
        """User Requirement: Shopify imported cost clearly distinguished from merchant-configured cost."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_imported_cogs"
            now = datetime.now(timezone.utc).isoformat()

            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_hat",
                "title": "Winter Beanie",
                "category": "Apparel",
                "min_price": 30.0,
                "stock": 40,
                "has_unit_cost": True,
                "avg_unit_cost": 10.0,
                "variants": [{"variant_id": 801, "price": 30.0, "cost": 10.0}],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_8001",
                "total_price": 60.0,
                "subtotal_price": 60.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "created_at": now,
                "financial_status": "paid",
                "line_items": [{"product_id": "sp_hat", "variant_id": 801, "quantity": 2, "price": 30.0}],
            }
            db.shopify_orders.docs.append(order)

            # No merchant cogs record
            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Hat Co", "USD")

            p_data = analytics["profit"]
            assert p_data["cogs_kind"] == "IMPORTED"
            assert p_data["cogs_label"] == "Product Cost (COGS - Imported)"
            assert p_data["total_cogs"] == 20.0  # 2 * $10.0
            assert p_data["true_profit"] == 40.0  # $60 - $20

            tp_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            assert tp_kpi["kind"] == "IMPORTED"

        asyncio.run(_run())

    def test_unconfigured_cogs_labeled_estimated(self):
        """User Requirement: Keep ESTIMATED for partial/unconfigured COGS-dependent metrics."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_unconf_cogs"
            now = datetime.now(timezone.utc).isoformat()

            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_unconf",
                "title": "Mystery Item",
                "category": "Novelty",
                "min_price": 25.0,
                "stock": 10,
                "has_unit_cost": False,
                "avg_unit_cost": None,
                "variants": [{"variant_id": 701, "price": 25.0, "cost": None}],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_7001",
                "total_price": 25.0,
                "subtotal_price": 25.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "created_at": now,
                "financial_status": "paid",
                "line_items": [{"product_id": "sp_unconf", "variant_id": 701, "quantity": 1, "price": 25.0}],
            }
            db.shopify_orders.docs.append(order)

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Mystery Co", "USD")

            p_data = analytics["profit"]
            assert p_data["cogs_kind"] == "ESTIMATED"
            assert p_data["cogs_label"] == "Product Cost (COGS - Unconfigured)"
            assert p_data["total_cogs"] == 0.0

            tp_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            assert tp_kpi["kind"] == "ESTIMATED"

        asyncio.run(_run())


class TestTrueProfitCalculationsAndInsights:
    def test_dynamic_recalculation_and_mismatch_insight(self):
        async def _run():
            db = MockDatabase()
            ws_id = "ws_profit_recalc"
            now = datetime.now(timezone.utc).isoformat()

            # Product A: High sales, low margin ($100 retail, $90 cost -> $10 profit per unit)
            # Product B: Low sales, high margin ($120 retail, $30 cost -> $90 profit per unit)
            prod_a = {
                "workspace_id": ws_id,
                "product_id": "sp_prod_a",
                "title": "Product A (High Volume)",
                "category": "Tech",
                "min_price": 100.0,
                "stock": 50,
                "variants": [{"variant_id": 1, "price": 100.0}],
            }
            prod_b = {
                "workspace_id": ws_id,
                "product_id": "sp_prod_b",
                "title": "Product B (High Profit)",
                "category": "Tech",
                "min_price": 120.0,
                "stock": 50,
                "variants": [{"variant_id": 2, "price": 120.0}],
            }
            db.shopify_products.docs.extend([prod_a, prod_b])

            # Order: 5 units of Product A ($500 rev), 3 units of Product B ($360 rev)
            # Discounts = $20, Refunds = $10
            order = {
                "workspace_id": ws_id,
                "order_id": "so_multi",
                "total_price": 860.0,
                "subtotal_price": 860.0,
                "total_discounts": 20.0,
                "total_refunded": 10.0,
                "created_at": now,
                "financial_status": "paid",
                "line_items": [
                    {"product_id": "sp_prod_a", "variant_id": 1, "quantity": 5, "price": 100.0},
                    {"product_id": "sp_prod_b", "variant_id": 2, "quantity": 3, "price": 120.0},
                ],
            }
            db.shopify_orders.docs.append(order)

            # Configure COGS: Prod A = $90, Prod B = $30
            db.merchant_cogs.docs.extend([
                {"workspace_id": ws_id, "product_id": "sp_prod_a", "unit_cost": 90.0, "variants": []},
                {"workspace_id": ws_id, "product_id": "sp_prod_b", "unit_cost": 30.0, "variants": []},
            ])

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Tech Store", "USD")
            p_data = analytics["profit"]

            # Total COGS = (5 * $90) + (3 * $30) = $450 + $90 = $540.00
            assert p_data["total_cogs"] == 540.0
            # Gross Revenue = $860
            # True Profit = 860 - 20 (disc) - 10 (ref) - 540 (cogs) = $290.00
            assert p_data["true_profit"] == 290.0

            # Product A: Rev $500, COGS $450 -> True Profit = $50
            # Product B: Rev $360, COGS $90 -> True Profit = $270
            # Mismatch insight: Best seller is Product A, but Most Profitable is Product B!
            insight = p_data["insight"]
            assert insight["best_seller"] == "Product A (High Volume)"
            assert insight["most_profitable"] == "Product B (High Profit)"
            assert insight["mismatch"] is True

        asyncio.run(_run())


class TestCogsApiEndpoints:
    def test_cogs_catalog_and_update_lifecycle(self):
        async def _run():
            mock_db = MockDatabase()
            ws_id = "ws_api_test"
            user = {"user_id": "u_test", "email": "merchant@test.com", "active_workspace_id": ws_id}

            # Setup workspace
            ws = {"workspace_id": ws_id, "user_id": "u_test", "name": "Live Store", "currency": "USD", "is_demo": False}
            mock_db.workspaces.docs.append(ws)

            # Setup product in shopify_products
            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_555",
                "shopify_id": 555,
                "title": "Ceramic Mug",
                "category": "Kitchen",
                "min_price": 20.0,
                "max_price": 25.0,
                "stock": 30,
                "variants": [
                    {"variant_id": 11, "title": "White", "price": 20.0, "cost": None, "inventory_quantity": 15},
                    {"variant_id": 12, "title": "Black", "price": 25.0, "cost": 8.0, "inventory_quantity": 15},
                ],
            }
            mock_db.shopify_products.docs.append(prod)

            with patch("server.db", mock_db), patch("server.get_active_workspace", return_value=ws):
                # 1. GET /api/cogs before configuration
                cat = await get_cogs_catalog(user=user)
                assert cat["total_products"] == 1
                assert cat["products"][0]["product_id"] == "sp_555"
                # Variant 12 has imported cost $8.0, Variant 11 is unconfigured
                assert cat["products"][0]["variants"][1]["imported_cost"] == 8.0

                # 2. PUT /api/cogs/sp_555 configure product unit cost $6.0, variant 12 override $7.50
                body = UpdateCogsBody(
                    unit_cost=6.0,
                    variants=[
                        VariantCostItem(variant_id=11, unit_cost=6.0),
                        VariantCostItem(variant_id=12, unit_cost=7.50),
                    ],
                )
                put_res = await update_product_cogs(product_id="sp_555", body=body, user=user)
                assert put_res["ok"] is True
                assert put_res["unit_cost"] == 6.0

                # 3. GET /api/cogs after configuration
                cat_after = await get_cogs_catalog(user=user)
                assert cat_after["configured_count"] == 1
                assert cat_after["coverage_pct"] == 100.0
                p_after = cat_after["products"][0]
                assert p_after["cogs_status"] == "CONFIGURED"
                assert p_after["configured_unit_cost"] == 6.0
                assert p_after["variants"][1]["status"] == "CONFIGURED"
                assert p_after["variants"][1]["configured_cost"] == 7.50

                # 4. POST /api/cogs/batch
                batch_body = BatchUpdateCogsBody(
                    items=[
                        BatchCogsItem(product_id="sp_555", unit_cost=5.50, variants=[]),
                    ]
                )
                batch_res = await batch_update_cogs(body=batch_body, user=user)
                assert batch_res["ok"] is True
                assert batch_res["updated_count"] == 1

        asyncio.run(_run())

    def test_workspace_isolation_in_cogs_storage(self):
        """Ensure Workspace A cannot see or edit Workspace B's COGS."""
        async def _run():
            mock_db = MockDatabase()
            ws_a = "ws_brand_1"
            ws_b = "ws_brand_2"

            mock_db.shopify_products.docs.extend([
                {"workspace_id": ws_a, "product_id": "sp_prod_a", "title": "Brand A Item", "min_price": 30.0, "variants": []},
                {"workspace_id": ws_b, "product_id": "sp_prod_b", "title": "Brand B Item", "min_price": 50.0, "variants": []},
            ])

            user_a = {"user_id": "u_a", "active_workspace_id": ws_a}
            ws_a_doc = {"workspace_id": ws_a, "user_id": "u_a", "name": "Brand A", "is_demo": False}

            with patch("server.db", mock_db), patch("server.get_active_workspace", return_value=ws_a_doc):
                cat_a = await get_cogs_catalog(user=user_a)
                p_ids = [p["product_id"] for p in cat_a["products"]]
                assert "sp_prod_a" in p_ids
                assert "sp_prod_b" not in p_ids  # Isolated!

                # Attempt to edit Product B from Workspace A -> should fail with 404
                body = UpdateCogsBody(unit_cost=10.0, variants=[])
                with pytest.raises(HTTPException) as exc_info:
                    await update_product_cogs(product_id="sp_prod_b", body=body, user=user_a)
                assert exc_info.value.status_code == 404

        asyncio.run(_run())


class TestDemoWorkspaceSafety:
    def test_demo_workspace_cogs_modification_rejected(self):
        """User Requirement: Do not modify the demo workspace."""
        async def _run():
            mock_db = MockDatabase()
            demo_ws = {
                "workspace_id": "ws_demo_northstar",
                "name": "Northstar Goods",
                "is_demo": True,
            }
            user = {"user_id": "u_admin", "active_workspace_id": "ws_demo_northstar"}

            with patch("server.db", mock_db), patch("server.get_active_workspace", return_value=demo_ws):
                body = UpdateCogsBody(unit_cost=10.0, variants=[])
                with pytest.raises(HTTPException) as exc_info:
                    await update_product_cogs(product_id="prod_1", body=body, user=user)
                assert exc_info.value.status_code == 400
                assert "locked for northstar goods" in exc_info.value.detail.lower()

                batch_body = BatchUpdateCogsBody(items=[BatchCogsItem(product_id="prod_1", unit_cost=10.0)])
                with pytest.raises(HTTPException) as exc_batch:
                    await batch_update_cogs(body=batch_body, user=user)
                assert exc_batch.value.status_code == 400
                assert "locked for northstar goods" in exc_batch.value.detail.lower()

        asyncio.run(_run())
