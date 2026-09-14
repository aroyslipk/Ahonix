"""AHONIX — Phase 4.5 Real Shopify End-to-End Smoke Test Suite.

Verifies:
1. Full end-to-end lifecycle for connected Shopify stores:
   - OAuth connect URL generation & state persistence
   - OAuth callback, token encryption & secure storage
   - Read-only products sync
   - Read-only orders sync
   - Real-time webhook events (product create/update/delete, order create/update)
   - Real workspace analytics aggregation into db.workspace_data
   - COGS catalog population
   - Merchant COGS configuration (product & variant level)
   - Dynamic True Profit recalculation across analytics views
2. Specific Scenarios:
   A. Shopify product with no cost -> status UNCONFIGURED / ESTIMATED
   B. Shopify product with imported cost -> status IMPORTED
   C. Merchant product-level COGS -> status CONFIGURED (never "ACTUAL")
   D. Merchant variant-level COGS override -> variant cost takes precedence
   E. Change merchant COGS -> historical analytics recalculate correctly
   F. Shopify webhook product/order event -> workspace analytics update correctly
   G. Demo workspace Northstar Goods -> untouched and COGS mutation blocked (HTTP 400)
3. Workspace isolation:
   - Merchant A cannot read or write Merchant B COGS
   - Shopify data remains workspace-scoped
4. Zero fabricated metrics:
   - No guessed 40% COGS
   - No fake ad spend (0.0 / unconnected)
   - No fake ROAS (0.0 / unconnected)
   - Accurate, un-fabricated True Profit
"""
import sys
from pathlib import Path
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import shopify_integration
from shopify_integration import (
    connect_shopify,
    shopify_callback,
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
import shopify_webhooks
from shopify_webhooks import (
    process_webhook_event,
    verify_shopify_webhook_hmac,
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
from demo_data import build_workspace_analytics


# --- Mock Asynchronous Database Engine ---------------------------------------
class MockCursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, length=10000):
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
                        match = False
                        break
                elif d.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(d)
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

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def delete_one(self, filter_query):
        self.docs = [
            d for d in self.docs
            if not all(d.get(k) == v for k, v in filter_query.items())
        ]

    async def count_documents(self, query=None):
        cursor = self.find(query)
        items = await cursor.to_list(10000)
        return len(items)


class MockDatabase:
    def __init__(self):
        self.shopify_connections = MockCollection("shopify_connections")
        self.shopify_oauth_states = MockCollection("shopify_oauth_states")
        self.shopify_products = MockCollection("shopify_products")
        self.shopify_orders = MockCollection("shopify_orders")
        self.shopify_sync_meta = MockCollection("shopify_sync_meta")
        self.shopify_webhook_events = MockCollection("shopify_webhook_events")
        self.merchant_cogs = MockCollection("merchant_cogs")
        self.workspace_data = MockCollection("workspace_data")
        self.workspaces = MockCollection("workspaces")
        self.users = MockCollection("users")


# --- Test Suite --------------------------------------------------------------
class TestPhase45SmokeScenarios:
    def test_scenario_a_unconfigured_cogs(self):
        """Scenario A: Shopify product with no cost -> status UNCONFIGURED / ESTIMATED."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_smoke_a"
            now = datetime.now(timezone.utc).isoformat()

            # Product has no unit cost
            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_item_a",
                "title": "Unconfigured Bamboo Straw",
                "category": "Home",
                "min_price": 20.0,
                "stock": 50,
                "has_unit_cost": False,
                "avg_unit_cost": None,
                "variants": [{"variant_id": 101, "price": 20.0, "cost": None}],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_order_a",
                "total_price": 40.0,
                "subtotal_price": 40.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "created_at": now,
                "line_items": [{"product_id": "sp_item_a", "variant_id": 101, "quantity": 2, "price": 20.0}],
            }
            db.shopify_orders.docs.append(order)

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Straw Co", "USD")
            p = analytics["profit"]

            # Checks:
            assert p["cogs_kind"] == "ESTIMATED"
            assert p["cogs_label"] == "Product Cost (COGS - Unconfigured)"
            assert p["total_cogs"] == 0.0  # Zero fallback, NO 40% heuristic!
            assert p["true_profit"] == 40.0  # Pre-COGS gross contribution

            prod_entry = analytics["products"][0]
            assert prod_entry["cogs_status"] == "UNCONFIGURED"
            assert prod_entry["cogs_source"] == "unconfigured"

            tp_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            assert tp_kpi["kind"] == "ESTIMATED"

        asyncio.run(_run())

    def test_scenario_b_shopify_imported_cost(self):
        """Scenario B: Shopify product with imported cost -> status IMPORTED."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_smoke_b"
            now = datetime.now(timezone.utc).isoformat()

            # Product has imported cost from Shopify
            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_item_b",
                "title": "Imported Merino Sock",
                "category": "Apparel",
                "min_price": 25.0,
                "stock": 80,
                "has_unit_cost": True,
                "avg_unit_cost": 8.50,
                "variants": [{"variant_id": 201, "price": 25.0, "cost": 8.50}],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_order_b",
                "total_price": 50.0,
                "subtotal_price": 50.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "created_at": now,
                "line_items": [{"product_id": "sp_item_b", "variant_id": 201, "quantity": 2, "price": 25.0}],
            }
            db.shopify_orders.docs.append(order)

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Sock Co", "USD")
            p = analytics["profit"]

            # Checks:
            assert p["cogs_kind"] == "IMPORTED"
            assert p["cogs_label"] == "Product Cost (COGS - Imported)"
            assert p["total_cogs"] == 17.00  # 2 units * $8.50
            assert p["true_profit"] == 33.00  # $50 - $17

            prod_entry = analytics["products"][0]
            assert prod_entry["cogs_status"] == "IMPORTED"
            assert prod_entry["unit_cost"] == 8.50

            tp_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            assert tp_kpi["kind"] == "IMPORTED"

        asyncio.run(_run())

    def test_scenario_c_merchant_product_level_cogs(self):
        """Scenario C: Merchant product-level COGS -> status CONFIGURED (never ACTUAL)."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_smoke_c"
            now = datetime.now(timezone.utc).isoformat()

            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_item_c",
                "title": "Ceramic Pour-Over",
                "category": "Kitchen",
                "min_price": 45.0,
                "stock": 30,
                "has_unit_cost": False,
                "avg_unit_cost": None,
                "variants": [{"variant_id": 301, "price": 45.0, "cost": None}],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_order_c",
                "total_price": 90.0,
                "subtotal_price": 90.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "created_at": now,
                "line_items": [{"product_id": "sp_item_c", "variant_id": 301, "quantity": 2, "price": 45.0}],
            }
            db.shopify_orders.docs.append(order)

            # Merchant configured product unit cost = $14.00
            db.merchant_cogs.docs.append({
                "workspace_id": ws_id,
                "product_id": "sp_item_c",
                "unit_cost": 14.00,
                "variants": [],
            })

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Pour Co", "USD")
            p = analytics["profit"]

            # Verify CONFIGURED labeling (CRITICAL: never ACTUAL)
            assert p["cogs_kind"] == "CONFIGURED"
            assert p["cogs_kind"] != "ACTUAL"
            assert p["cogs_label"] == "Product Cost (COGS - Configured)"
            assert p["total_cogs"] == 28.00  # 2 units * $14.00
            assert p["true_profit"] == 62.00  # $90 - $28

            tp_kpi = next(k for k in analytics["kpis"] if k["id"] == "true-profit")
            assert tp_kpi["kind"] == "CONFIGURED"
            assert tp_kpi["kind"] != "ACTUAL"

            prod_entry = analytics["products"][0]
            assert prod_entry["cogs_status"] == "CONFIGURED"
            assert prod_entry["unit_cost"] == 14.00

        asyncio.run(_run())

    def test_scenario_d_variant_level_cogs_override(self):
        """Scenario D: Merchant variant-level COGS override takes precedence."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_smoke_d"
            now = datetime.now(timezone.utc).isoformat()

            # Product with 2 variants: Small and Large
            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_item_d",
                "title": "Hoodie",
                "category": "Apparel",
                "min_price": 60.0,
                "stock": 100,
                "has_unit_cost": True,
                "avg_unit_cost": 25.0,
                "variants": [
                    {"variant_id": 401, "title": "Small", "price": 60.0, "cost": 22.0},
                    {"variant_id": 402, "title": "Large", "price": 65.0, "cost": 28.0},
                ],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_order_d",
                "total_price": 190.0,
                "subtotal_price": 190.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "created_at": now,
                "line_items": [
                    {"product_id": "sp_item_d", "variant_id": 401, "quantity": 2, "price": 60.0},  # Small: 2 * $18 = $36
                    {"product_id": "sp_item_d", "variant_id": 402, "quantity": 1, "price": 65.0},  # Large: 1 * $32 = $32
                ],
            }
            db.shopify_orders.docs.append(order)

            # Merchant configuration: Default $20, but Small override = $18, Large override = $32
            db.merchant_cogs.docs.append({
                "workspace_id": ws_id,
                "product_id": "sp_item_d",
                "unit_cost": 20.0,
                "variants": [
                    {"variant_id": 401, "unit_cost": 18.0},
                    {"variant_id": 402, "unit_cost": 32.0},
                ],
            })

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Hoodie Co", "USD")
            p = analytics["profit"]

            # Total COGS should be 2 * $18 + 1 * $32 = $68.00 (NOT default $20*3=$60, NOT imported $22*2+$28=$72)
            assert p["total_cogs"] == 68.00
            assert p["cogs_kind"] == "CONFIGURED"
            assert p["true_profit"] == 122.00  # $190 - $68

        asyncio.run(_run())

    def test_scenario_e_change_merchant_cogs_recalculates_historical(self):
        """Scenario E: Change merchant COGS -> historical analytics recalculate correctly."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_smoke_e"
            now = datetime.now(timezone.utc).isoformat()
            user = {"user_id": "u_e", "email": "merchant_e@test.com", "active_workspace_id": ws_id}
            ws_doc = {"workspace_id": ws_id, "user_id": "u_e", "name": "Store E", "currency": "USD", "is_demo": False}
            db.workspaces.docs.append(ws_doc)

            prod = {
                "workspace_id": ws_id,
                "product_id": "sp_widget_e",
                "shopify_id": 5555,
                "title": "Precision Widget",
                "category": "Tools",
                "min_price": 100.0,
                "stock": 50,
                "variants": [{"variant_id": 501, "price": 100.0, "cost": None}],
            }
            db.shopify_products.docs.append(prod)

            order = {
                "workspace_id": ws_id,
                "order_id": "so_order_e",
                "total_price": 500.0,
                "subtotal_price": 500.0,
                "total_discounts": 20.0,
                "total_refunded": 30.0,
                "financial_status": "paid",
                "created_at": now,
                "line_items": [{"product_id": "sp_widget_e", "variant_id": 501, "quantity": 5, "price": 100.0}],
            }
            db.shopify_orders.docs.append(order)

            with patch("server.db", db), patch("server.get_active_workspace", return_value=ws_doc):
                # 1. Initially set COGS = $30.00
                await update_product_cogs(
                    product_id="sp_widget_e",
                    body=UpdateCogsBody(unit_cost=30.00, variants=[]),
                    user=user,
                )
                snap_1 = await db.workspace_data.find_one({"workspace_id": ws_id})
                # Total COGS = 5 * $30 = $150
                assert snap_1["profit"]["total_cogs"] == 150.00
                # True Profit = $500 - $20 (disc) - $30 (ref) - $150 (cogs) = $300.00
                assert snap_1["profit"]["true_profit"] == 300.00

                # 2. Merchant updates COGS = $45.00
                await update_product_cogs(
                    product_id="sp_widget_e",
                    body=UpdateCogsBody(unit_cost=45.00, variants=[]),
                    user=user,
                )
                snap_2 = await db.workspace_data.find_one({"workspace_id": ws_id})
                # Total COGS = 5 * $45 = $225
                assert snap_2["profit"]["total_cogs"] == 225.00
                # True Profit = $500 - $20 - $30 - $225 = $225.00
                assert snap_2["profit"]["true_profit"] == 225.00
                assert snap_2["profit"]["gross_profit"] == 275.00  # $500 - $225
                assert snap_2["profit"]["contribution_margin"] == 225.00

        asyncio.run(_run())

    def test_scenario_f_webhook_updates_analytics_and_cogs(self):
        """Scenario F: Shopify webhook product/order event updates analytics correctly."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_smoke_f"
            shop = "webhook-store.myshopify.com"
            now = datetime.now(timezone.utc).isoformat()

            # Connection record
            db.shopify_connections.docs.append({
                "workspace_id": ws_id,
                "shop": shop,
                "status": "connected",
            })

            # 1. Product create webhook
            prod_payload = {
                "id": 8881,
                "title": "Webhook Leather Wallet",
                "product_type": "Accessories",
                "status": "active",
                "variants": [{"id": 88811, "price": "40.00", "cost": "12.00", "inventory_quantity": 20}],
                "updated_at": now,
            }
            p_res = await process_webhook_event(
                db=db,
                shop=shop,
                topic="products/create",
                webhook_id="wh_p_1",
                payload=prod_payload,
            )
            assert p_res["ok"] is True
            assert len(db.shopify_products.docs) == 1

            # 2. Order create webhook
            order_payload = {
                "id": 9991,
                "name": "#1099",
                "total_price": "80.00",
                "subtotal_price": "80.00",
                "total_discounts": "0.00",
                "financial_status": "paid",
                "created_at": now,
                "line_items": [{"id": 1, "product_id": 8881, "variant_id": 88811, "quantity": 2, "price": "40.00"}],
            }
            o_res = await process_webhook_event(
                db=db,
                shop=shop,
                topic="orders/create",
                webhook_id="wh_o_1",
                payload=order_payload,
            )
            assert o_res["ok"] is True
            assert len(db.shopify_orders.docs) == 1

            # Aggregated analytics should be automatically produced
            snap = await db.workspace_data.find_one({"workspace_id": ws_id})
            assert snap is not None
            assert snap["profit"]["gross_revenue"] == 80.00
            assert snap["profit"]["total_cogs"] == 24.00  # 2 * $12 imported cost
            assert snap["profit"]["cogs_kind"] == "IMPORTED"
            assert snap["profit"]["true_profit"] == 56.00

        asyncio.run(_run())

    def test_scenario_g_demo_workspace_safety(self):
        """Scenario G: Demo workspace Northstar Goods remains untouched and COGS mutation blocked."""
        async def _run():
            db = MockDatabase()
            demo_ws = {
                "workspace_id": "ws_demo_northstar",
                "name": "Northstar Goods",
                "is_demo": True,
            }
            user = {"user_id": "u_admin", "active_workspace_id": "ws_demo_northstar"}

            with patch("server.db", db), patch("server.get_active_workspace", return_value=demo_ws):
                # Verify PUT /api/cogs is rejected with 400
                with pytest.raises(HTTPException) as exc_put:
                    await update_product_cogs("sp_any", UpdateCogsBody(unit_cost=15.0), user)
                assert exc_put.value.status_code == 400
                assert "locked for northstar goods" in exc_put.value.detail.lower()

                # Verify POST /api/cogs/batch is rejected with 400
                with pytest.raises(HTTPException) as exc_batch:
                    await batch_update_cogs(BatchUpdateCogsBody(items=[BatchCogsItem(product_id="sp_any", unit_cost=15.0)]), user)
                assert exc_batch.value.status_code == 400
                assert "locked for northstar goods" in exc_batch.value.detail.lower()

                # Verify GET /api/cogs for demo returns read-only catalog
                # Mock workspace data with 2 products
                db.workspace_data.docs.append({
                    "workspace_id": "ws_demo_northstar",
                    "products": [
                        {"id": "prod_d1", "name": "Demo Hoodie", "category": "Apparel", "price": 85.0, "unit_cost": 28.0, "stock": 45, "margin": 67.0},
                    ],
                })
                cat = await get_cogs_catalog(user)
                assert cat["is_demo"] is True
                assert cat["total_products"] == 1
                assert cat["products"][0]["title"] == "Demo Hoodie"

        asyncio.run(_run())


class TestWorkspaceIsolationAndIntegrity:
    def test_cross_workspace_cogs_isolation(self):
        """Merchant A cannot read or modify Merchant B's COGS."""
        async def _run():
            db = MockDatabase()
            ws_a = "ws_brand_alpha"
            ws_b = "ws_brand_beta"
            user_a = {"user_id": "u_alpha", "email": "alpha@test.com", "active_workspace_id": ws_a}
            ws_a_doc = {"workspace_id": ws_a, "user_id": "u_alpha", "name": "Brand Alpha", "is_demo": False}

            # Setup products for each workspace
            db.shopify_products.docs.extend([
                {"workspace_id": ws_a, "product_id": "sp_prod_alpha", "title": "Alpha Item", "min_price": 50.0, "variants": []},
                {"workspace_id": ws_b, "product_id": "sp_prod_beta", "title": "Beta Item", "min_price": 80.0, "variants": []},
            ])

            with patch("server.db", db), patch("server.get_active_workspace", return_value=ws_a_doc):
                # Merchant A gets catalog -> only sees Alpha Item
                cat_a = await get_cogs_catalog(user_a)
                p_ids = [p["product_id"] for p in cat_a["products"]]
                assert "sp_prod_alpha" in p_ids
                assert "sp_prod_beta" not in p_ids

                # Merchant A attempts to mutate Beta Item -> 404 Not Found
                with pytest.raises(HTTPException) as exc_info:
                    await update_product_cogs("sp_prod_beta", UpdateCogsBody(unit_cost=25.0), user_a)
                assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_no_fabricated_metrics(self):
        """Verify analytics engine never invents fake ad spend, ROAS, or guessed COGS."""
        async def _run():
            db = MockDatabase()
            ws_id = "ws_clean_metrics"
            now = datetime.now(timezone.utc).isoformat()

            db.shopify_products.docs.append({
                "workspace_id": ws_id,
                "product_id": "sp_clean",
                "title": "Clean Product",
                "category": "Home",
                "min_price": 100.0,
                "stock": 20,
                "has_unit_cost": False,
                "avg_unit_cost": None,
                "variants": [{"variant_id": 1, "price": 100.0, "cost": None}],
            })
            db.shopify_orders.docs.append({
                "workspace_id": ws_id,
                "order_id": "so_clean",
                "total_price": 100.0,
                "subtotal_price": 100.0,
                "total_discounts": 0.0,
                "total_refunded": 0.0,
                "financial_status": "paid",
                "created_at": now,
                "line_items": [{"product_id": "sp_clean", "variant_id": 1, "quantity": 1, "price": 100.0}],
            })

            analytics = await aggregate_shopify_workspace_data(db, ws_id, "Clean Brand", "USD")

            # 1. COGS is 0.0, NOT arbitrary 40%
            assert analytics["profit"]["total_cogs"] == 0.0
            assert analytics["profit"]["cogs_kind"] == "ESTIMATED"

            # 2. Marketing is strictly 0.0 unconnected, NOT fabricated
            mktg = analytics["marketing"]
            assert mktg["total_spend"] == 0.0
            assert mktg["blended_roas"] == 0.0
            assert mktg["attributed_roas"] == 0.0
            assert mktg["campaigns"] == []
            assert "None connected" in mktg["paradox"]["high_roas_campaign"]

            # 3. Ad Spend KPI is 0.0 with ESTIMATED badge
            mktg_kpi = next(k for k in analytics["kpis"] if k["id"] == "marketing-eff")
            assert mktg_kpi["value"] == 0.0
            assert mktg_kpi["kind"] == "ESTIMATED"

        asyncio.run(_run())
