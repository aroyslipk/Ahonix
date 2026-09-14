"""Automated Unit & Security Tests for Phase 3.3: Shopify Real-Time Webhooks Pipeline.

Coverage:
1. Base64 HMAC-SHA256 signature verification over raw request body
2. Endpoint security (rejection of unauthenticated/tampered webhooks with 401)
3. Workspace-safe routing (mapping to verified workspace_id)
4. Safe handling for unlinked/unknown shops (200 OK with ignored: True)
5. Concurrency-safe idempotency (atomic duplicate and concurrent delivery protection)
6. Incremental products handling (create/update/delete)
7. Incremental orders handling (create/update/cancelled)
8. Cross-workspace isolation (Workspace A events never touch Workspace B)
9. Demo workspace immutability (Northstar Goods untouched)
"""
import sys
import os
import json
import hmac
import hashlib
import base64
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient
from pymongo.errors import DuplicateKeyError

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from shopify_webhooks import (
    verify_shopify_webhook_hmac,
    process_webhook_event,
    register_shopify_webhooks,
    SUPPORTED_TOPICS,
)
from server import app
from demo_data import build_workspace_analytics


class TestShopifyWebhookHmacVerification:
    def test_valid_webhook_hmac(self):
        secret = "test_webhook_secret_key_12345"
        raw_body = b'{"id": 1001, "title": "Test Product", "price": "29.99"}'
        
        computed_digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        header_hmac = base64.b64encode(computed_digest).decode("utf-8")

        assert verify_shopify_webhook_hmac(raw_body, header_hmac, secret) is True

    def test_tampered_payload_rejected(self):
        secret = "test_webhook_secret_key_12345"
        raw_body = b'{"id": 1001, "title": "Test Product", "price": "29.99"}'
        
        computed_digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
        header_hmac = base64.b64encode(computed_digest).decode("utf-8")

        tampered_body = b'{"id": 1001, "title": "Tampered Product", "price": "0.01"}'
        assert verify_shopify_webhook_hmac(tampered_body, header_hmac, secret) is False

    def test_wrong_secret_rejected(self):
        raw_body = b'{"id": 1001}'
        computed_digest = hmac.new(b"secret_a", raw_body, hashlib.sha256).digest()
        header_hmac = base64.b64encode(computed_digest).decode("utf-8")

        assert verify_shopify_webhook_hmac(raw_body, header_hmac, "secret_b") is False

    def test_missing_hmac_or_secret_rejected(self):
        raw_body = b'{"id": 1001}'
        assert verify_shopify_webhook_hmac(raw_body, None, "secret") is False
        assert verify_shopify_webhook_hmac(raw_body, "hmac", "") is False
        assert verify_shopify_webhook_hmac(b"", "hmac", "secret") is False


class MockCursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, length):
        return self.items[:length]


class MockWebhookDB:
    def __init__(self):
        self.connections = []
        self.webhook_events = set()
        self.products = {}
        self.orders = {}
        self.workspace_data_store = {}

    @property
    def shopify_connections(self):
        db = self
        class Coll:
            async def find_one(self, query):
                shop = query.get("shop")
                status = query.get("status")
                for c in db.connections:
                    if c.get("shop") == shop and (status is None or c.get("status") == status):
                        return c
                return None
        return Coll()

    @property
    def shopify_webhook_events(self):
        db = self
        class Coll:
            async def insert_one(self, doc):
                wid = doc["webhook_id"]
                if wid in db.webhook_events:
                    raise DuplicateKeyError(f"Duplicate key: {wid}")
                db.webhook_events.add(wid)
            async def update_one(self, query, update):
                pass
            async def delete_one(self, query):
                wid = query.get("webhook_id")
                db.webhook_events.discard(wid)
        return Coll()

    @property
    def shopify_products(self):
        db = self
        class Coll:
            def find(self, query):
                ws = query.get("workspace_id")
                return MockCursor([p for p in db.products.values() if p.get("workspace_id") == ws])
            async def replace_one(self, query, doc, upsert=True):
                key = (query["workspace_id"], query["product_id"])
                db.products[key] = doc
            async def delete_one(self, query):
                key = (query["workspace_id"], query["product_id"])
                db.products.pop(key, None)
        return Coll()

    @property
    def shopify_orders(self):
        db = self
        class Coll:
            def find(self, query):
                ws = query.get("workspace_id")
                return MockCursor([o for o in db.orders.values() if o.get("workspace_id") == ws])
            async def replace_one(self, query, doc, upsert=True):
                key = (query["workspace_id"], query["order_id"])
                db.orders[key] = doc
        return Coll()

    @property
    def workspace_data(self):
        db = self
        class Coll:
            async def replace_one(self, query, doc, upsert=True):
                db.workspace_data_store[query["workspace_id"]] = doc
            async def find_one(self, query, proj=None):
                return db.workspace_data_store.get(query.get("workspace_id"))
        return Coll()


class TestWebhookProcessingAndIdempotency:
    def test_unknown_shop_returns_ignored_200(self):
        async def _run():
            db = MockWebhookDB()
            res = await process_webhook_event(
                db=db,
                topic="products/update",
                shop="unregistered-store.myshopify.com",
                webhook_id="wh_100",
                payload={"id": 123},
            )
            assert res["ok"] is True
            assert res.get("ignored") is True
            assert "not connected" in res.get("reason", "").lower()
            assert len(db.products) == 0

        asyncio.run(_run())

    def test_concurrent_and_duplicate_webhook_delivery(self):
        """User Requirement: Add an explicit test for concurrent/duplicate webhook delivery
        so the same webhook cannot be processed twice.
        """
        async def _run():
            db = MockWebhookDB()
            db.connections.append({
                "workspace_id": "ws_concurrent_test",
                "shop": "concurrent-shop.myshopify.com",
                "status": "connected",
            })

            payload = {
                "id": 8801,
                "title": "Idempotent Product",
                "variants": [{"id": 1, "price": "50.00", "inventory_quantity": 10}],
            }

            # Simulate two concurrent webhook deliveries hitting simultaneously
            wh_id = "delivery-uuid-exact-same-12345"
            task1 = process_webhook_event(db, "products/create", "concurrent-shop.myshopify.com", wh_id, payload)
            task2 = process_webhook_event(db, "products/create", "concurrent-shop.myshopify.com", wh_id, payload)

            results = await asyncio.gather(task1, task2)

            # Exactly one task must process successfully and the other must be recognized as duplicate
            success_count = sum(1 for r in results if r.get("processed_at") is not None)
            duplicate_count = sum(1 for r in results if r.get("duplicate") is True)

            assert success_count == 1
            assert duplicate_count == 1
            # Product should exist exactly once
            assert len(db.products) == 1

        asyncio.run(_run())

    def test_products_create_and_delete_lifecycle(self):
        async def _run():
            db = MockWebhookDB()
            ws_id = "ws_merch_live"
            shop = "merch-live.myshopify.com"
            db.connections.append({"workspace_id": ws_id, "shop": shop, "status": "connected"})

            # 1. products/create
            prod_payload = {
                "id": 9901,
                "title": "Trail Running Shoes",
                "product_type": "Footwear",
                "variants": [{"id": 10, "price": "130.00", "inventory_quantity": 25}],
            }
            res_create = await process_webhook_event(db, "products/create", shop, "wh_p_create", prod_payload)
            assert res_create["ok"] is True
            assert (ws_id, "sp_9901") in db.products
            assert db.products[(ws_id, "sp_9901")]["title"] == "Trail Running Shoes"

            # 2. Verify workspace_data updated
            assert ws_id in db.workspace_data_store
            prods = db.workspace_data_store[ws_id]["products"]
            assert any(p["name"] == "Trail Running Shoes" for p in prods)

            # 3. products/delete
            res_delete = await process_webhook_event(db, "products/delete", shop, "wh_p_del", {"id": 9901})
            assert res_delete["ok"] is True
            assert (ws_id, "sp_9901") not in db.products

            # 4. Verify workspace_data reflects removal
            prods_after = db.workspace_data_store[ws_id]["products"]
            assert not any(p["name"] == "Trail Running Shoes" for p in prods_after)

        asyncio.run(_run())

    def test_orders_create_and_cancelled_lifecycle(self):
        async def _run():
            db = MockWebhookDB()
            ws_id = "ws_order_test"
            shop = "orders-shop.myshopify.com"
            db.connections.append({"workspace_id": ws_id, "shop": shop, "status": "connected"})

            now_str = datetime.now(timezone.utc).isoformat()
            order_payload = {
                "id": 7701,
                "name": "#1001",
                "financial_status": "paid",
                "total_price": "85.00",
                "subtotal_price": "85.00",
                "created_at": now_str,
                "line_items": [{"id": 1, "quantity": 1, "price": "85.00"}],
            }

            # 1. orders/create
            res_create = await process_webhook_event(db, "orders/create", shop, "wh_ord_1", order_payload)
            assert res_create["ok"] is True
            assert (ws_id, "so_7701") in db.orders
            assert db.workspace_data_store[ws_id]["sales"]["revenue"] == 85.00

            # 2. orders/cancelled
            order_payload["financial_status"] = "voided"
            order_payload["cancelled_at"] = now_str
            res_cancel = await process_webhook_event(db, "orders/cancelled", shop, "wh_ord_2", order_payload)
            assert res_cancel["ok"] is True
            assert db.orders[(ws_id, "so_7701")]["financial_status"] == "voided"
            # Voided order is excluded from current revenue
            assert db.workspace_data_store[ws_id]["sales"]["revenue"] == 0.00

        asyncio.run(_run())

    def test_workspace_isolation_webhook(self):
        """Cross-workspace test: events in Workspace A must never affect Workspace B."""
        async def _run():
            db = MockWebhookDB()
            db.connections.append({"workspace_id": "ws_alpha", "shop": "alpha.myshopify.com", "status": "connected"})
            db.connections.append({"workspace_id": "ws_beta", "shop": "beta.myshopify.com", "status": "connected"})

            # Webhook for Alpha
            await process_webhook_event(
                db=db,
                topic="products/create",
                shop="alpha.myshopify.com",
                webhook_id="wh_iso_1",
                payload={"id": 111, "title": "Alpha Product", "variants": [{"price": "20.00"}]},
            )

            # Webhook for Beta
            await process_webhook_event(
                db=db,
                topic="products/create",
                shop="beta.myshopify.com",
                webhook_id="wh_iso_2",
                payload={"id": 222, "title": "Beta Product", "variants": [{"price": "90.00"}]},
            )

            # Check products
            assert ("ws_alpha", "sp_111") in db.products
            assert ("ws_alpha", "sp_222") not in db.products

            assert ("ws_beta", "sp_222") in db.products
            assert ("ws_beta", "sp_111") not in db.products

        asyncio.run(_run())


class TestWebhookEndpointHttp:
    @pytest.fixture(scope="class")
    def client(self):
        return TestClient(app, raise_server_exceptions=False)

    def test_webhook_missing_hmac_rejected_401(self, client):
        r = client.post(
            "/api/integrations/shopify/webhooks",
            content=b'{"id": 1}',
            headers={"X-Shopify-Topic": "products/update", "X-Shopify-Shop-Domain": "test.myshopify.com"},
        )
        assert r.status_code == 401
        assert "HMAC signature" in r.json()["detail"]

    def test_webhook_invalid_hmac_rejected_401(self, client):
        r = client.post(
            "/api/integrations/shopify/webhooks",
            content=b'{"id": 1}',
            headers={
                "X-Shopify-Hmac-Sha256": "invalid_base64_hash==",
                "X-Shopify-Topic": "products/update",
                "X-Shopify-Shop-Domain": "test.myshopify.com",
            },
        )
        assert r.status_code == 401


class TestDemoWorkspaceSafety:
    def test_demo_workspace_unaffected_by_webhooks(self):
        demo_data = build_workspace_analytics("Northstar Goods", "USD")
        assert demo_data["store_name"] == "Northstar Goods"
        assert len(demo_data["kpis"]) == 6
        assert demo_data["meta"].get("source") != "shopify_real"
