"""Unit Tests for Phase 6.3: Shopify Initial Sync Scale Hardening.

Coverage:
1. Default production behavior is uncapped (SHOPIFY_SYNC_MAX_PAGES=0, batch_size=250)
2. Environment configuration parsing and boundary clamping (max 250)
3. Explicit SHOPIFY_SYNC_MAX_PAGES=3 stops after exactly 3 pages
4. SHOPIFY_SYNC_MAX_PAGES=0 paginates until exhaustion
5. Multi-page product sync (all pages ingested and normalized)
6. Multi-page order sync (all pages ingested and normalized)
7. Pagination termination conditions (empty items, missing Link header, missing rel=next)
8. Repeated page/token protection (detects cycling cursor, prevents infinite loops)
9. Safety ceiling guard (breaks if runaways exceed safety ceiling)
10. HTTP 429 retry and backoff behavior (succeeds after backoff)
11. Bounded retry exhaustion (stops after max retries, raises 502/504)
12. Partial sync failure resilience (earlier pages preserved, status marked failed)
13. Idempotent repeated sync (no duplicate products or orders)
14. Workspace isolation across sync operations
15. Northstar Goods demo workspace protection (sync blocked with HTTP 400)
"""
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import httpx
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from shopify_sync import (
    get_shopify_sync_config,
    sync_products,
    sync_orders,
    run_shopify_sync,
    shopify_get_request,
    extract_next_page_info,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_PAGES,
    MAX_SHOPIFY_PAGE_SIZE,
)
import shopify_integration
from demo_data import build_workspace_analytics


def run_async(coro):
    """Helper to run async coroutines in synchronous pytest tests."""
    return asyncio.run(coro)


# --- In-Memory Mock Database for Sync Testing ---------------------------------

class MockCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None

    async def replace_one(self, query, replacement, upsert=False):
        for i, doc in enumerate(self.docs):
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                self.docs[i] = dict(replacement)
                return MagicMock(modified_count=1)
        if upsert:
            self.docs.append(dict(replacement))
            return MagicMock(upserted_id="upserted")
        return MagicMock(modified_count=0)

    async def update_one(self, query, update, upsert=False):
        for i, doc in enumerate(self.docs):
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    self.docs[i].update(update["$set"])
                return MagicMock(modified_count=1)
        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            self.docs.append(new_doc)
            return MagicMock(upserted_id="upserted")
        return MagicMock(modified_count=0)

    async def delete_one(self, query):
        for i, doc in enumerate(self.docs):
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                self.docs.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    async def count_documents(self, query):
        count = 0
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count

    def find(self, query=None, projection=None):
        matching = []
        for doc in self.docs:
            if not query:
                matching.append(dict(doc))
            else:
                match = True
                for k, v in query.items():
                    if doc.get(k) != v:
                        match = False
                        break
                if match:
                    matching.append(dict(doc))
        
        class Cursor:
            def __init__(self, items):
                self.items = items
            async def to_list(self, length=1000):
                return self.items[:length]
        return Cursor(matching)


class MockSyncDB:
    def __init__(self):
        self.shopify_products = MockCollection()
        self.shopify_orders = MockCollection()
        self.shopify_sync_meta = MockCollection()
        self.shopify_connections = MockCollection()
        self.workspace_data = MockCollection()
        self.merchant_cogs = MockCollection()
        self.meta_connections = MockCollection()
        self.google_ads_connections = MockCollection()
        self.meta_campaign_insights = MockCollection()
        self.google_ads_campaign_insights = MockCollection()


# ==============================================================================
# 1. Configuration & Boundary Parsing Tests
# ==============================================================================

class TestShopifySyncConfiguration:
    def test_default_config_is_uncapped(self, monkeypatch):
        monkeypatch.delenv("SHOPIFY_SYNC_BATCH_SIZE", raising=False)
        monkeypatch.delenv("SHOPIFY_SYNC_MAX_PAGES", raising=False)

        batch_size, max_pages = get_shopify_sync_config()
        assert batch_size == 250
        assert max_pages == 0  # 0 = uncapped production pagination

    def test_custom_valid_config(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_SYNC_BATCH_SIZE", "100")
        monkeypatch.setenv("SHOPIFY_SYNC_MAX_PAGES", "5")

        batch_size, max_pages = get_shopify_sync_config()
        assert batch_size == 100
        assert max_pages == 5

    def test_clamping_to_shopify_max_limit_250(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_SYNC_BATCH_SIZE", "500")  # Exceeds Shopify REST API 250
        batch_size, max_pages = get_shopify_sync_config()
        assert batch_size == 250

    def test_invalid_string_fallbacks(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_SYNC_BATCH_SIZE", "invalid_num")
        monkeypatch.setenv("SHOPIFY_SYNC_MAX_PAGES", "not_a_page")

        batch_size, max_pages = get_shopify_sync_config()
        assert batch_size == DEFAULT_BATCH_SIZE
        assert max_pages == DEFAULT_MAX_PAGES

    def test_negative_values_handled_safely(self, monkeypatch):
        monkeypatch.setenv("SHOPIFY_SYNC_BATCH_SIZE", "-50")
        monkeypatch.setenv("SHOPIFY_SYNC_MAX_PAGES", "-2")

        batch_size, max_pages = get_shopify_sync_config()
        assert batch_size == DEFAULT_BATCH_SIZE
        assert max_pages == 0


# ==============================================================================
# 2. Multi-Page Pagination & Scale Tests
# ==============================================================================

class TestShopifyPaginationAndScale:
    def test_explicit_max_pages_caps_sync(self):
        """Verify SHOPIFY_SYNC_MAX_PAGES=3 stops after exactly 3 pages even if 5 pages exist."""
        db = MockSyncDB()
        ws_id = "ws_test_scale"
        shop = "scale-test.myshopify.com"

        # Construct 5 pages of products (10 per page = 50 products)
        def mock_page_response(page_num):
            prods = [{"id": (page_num * 100) + i, "title": f"Product P{page_num}_{i}"} for i in range(10)]
            headers = {}
            if page_num < 5:
                headers["Link"] = f'<https://{shop}/admin/api/2026-07/products.json?limit=10&page_info=token_p{page_num + 1}>; rel="next"'
            return httpx.Response(status_code=200, json={"products": prods}, headers=headers)

        call_count = 0
        async def mock_shopify_get(client, url, headers=None, params=None, max_retries=3):
            nonlocal call_count
            call_count += 1
            return mock_page_response(call_count)

        with patch("shopify_sync.shopify_get_request", side_effect=mock_shopify_get):
            total, max_up = run_async(
                sync_products(
                    client=MagicMock(),
                    base_url=f"https://{shop}/admin/api/2026-07",
                    headers={},
                    db=db,
                    workspace_id=ws_id,
                    shop=shop,
                    max_pages=3,  # Explicit cap at 3 pages
                )
            )

        assert call_count == 3
        assert total == 30
        assert len(db.shopify_products.docs) == 30

    def test_uncapped_pagination_continues_until_exhaustion(self):
        """Verify SHOPIFY_SYNC_MAX_PAGES=0 paginates until Shopify Link header is exhausted."""
        db = MockSyncDB()
        ws_id = "ws_test_scale"
        shop = "scale-test.myshopify.com"

        # 4 pages of orders
        def mock_order_response(page_num):
            orders = [{"id": (page_num * 1000) + i, "total_price": "50.00"} for i in range(5)]
            headers = {}
            if page_num < 4:
                headers["Link"] = f'<https://{shop}/admin/api/2026-07/orders.json?limit=5&page_info=order_token_{page_num + 1}>; rel="next"'
            return httpx.Response(status_code=200, json={"orders": orders}, headers=headers)

        call_count = 0
        async def mock_shopify_get(client, url, headers=None, params=None, max_retries=3):
            nonlocal call_count
            call_count += 1
            return mock_order_response(call_count)

        with patch("shopify_sync.shopify_get_request", side_effect=mock_shopify_get):
            total, max_up = run_async(
                sync_orders(
                    client=MagicMock(),
                    base_url=f"https://{shop}/admin/api/2026-07",
                    headers={},
                    db=db,
                    workspace_id=ws_id,
                    shop=shop,
                    max_pages=0,  # Uncapped: continues until no next link
                )
            )

        assert call_count == 4
        assert total == 20
        assert len(db.shopify_orders.docs) == 20

    def test_repeated_page_token_protection_prevents_infinite_loop(self):
        """Verify repeated/cycling cursor token triggers safety loop break."""
        db = MockSyncDB()
        ws_id = "ws_test_scale"
        shop = "scale-test.myshopify.com"

        # Page 1 gives token_A, Page 2 gives token_A again (cycling)
        responses = [
            httpx.Response(
                status_code=200,
                json={"products": [{"id": 1, "title": "P1"}]},
                headers={"Link": '<https://test/products.json?limit=10&page_info=duplicate_token>; rel="next"'},
            ),
            httpx.Response(
                status_code=200,
                json={"products": [{"id": 2, "title": "P2"}]},
                headers={"Link": '<https://test/products.json?limit=10&page_info=duplicate_token>; rel="next"'},
            ),
        ]
        call_count = 0
        async def mock_shopify_get(client, url, headers=None, params=None, max_retries=3):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        with patch("shopify_sync.shopify_get_request", side_effect=mock_shopify_get):
            total, _ = run_async(
                sync_products(
                    client=MagicMock(),
                    base_url=f"https://{shop}/admin/api/2026-07",
                    headers={},
                    db=db,
                    workspace_id=ws_id,
                    shop=shop,
                    max_pages=0,
                )
            )

        # Must break after detecting duplicate_token on page 2
        assert call_count == 2
        assert total == 2

    def test_safety_ceiling_breaks_runaway(self, monkeypatch):
        """Verify configured SHOPIFY_SYNC_SAFETY_CEILING terminates runaways."""
        monkeypatch.setenv("SHOPIFY_SYNC_SAFETY_CEILING", "3")
        db = MockSyncDB()
        ws_id = "ws_test_ceiling"
        shop = "scale-test.myshopify.com"

        call_count = 0
        async def mock_infinite_pages(client, url, headers=None, params=None, max_retries=3):
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                status_code=200,
                json={"products": [{"id": call_count, "title": f"Product {call_count}"}]},
                headers={"Link": f'<https://test/products.json?limit=10&page_info=unique_token_{call_count}>; rel="next"'},
            )

        with patch("shopify_sync.shopify_get_request", side_effect=mock_infinite_pages):
            total, _ = run_async(
                sync_products(
                    client=MagicMock(),
                    base_url=f"https://{shop}/admin/api/2026-07",
                    headers={},
                    db=db,
                    workspace_id=ws_id,
                    shop=shop,
                    max_pages=0,
                )
            )

        assert call_count == 3
        assert total == 3


# ==============================================================================
# 3. Rate Limit & Failure Handling Tests
# ==============================================================================

class TestRateLimitAndFailureHandling:
    def test_http_429_retry_and_backoff(self):
        """Verify shopify_get_request handles 429 Retry-After header and succeeds on retry."""
        mock_client = MagicMock()
        resp_429 = httpx.Response(
            status_code=429,
            headers={"Retry-After": "0.01", "X-Shopify-Shop-Api-Call-Limit": "40/40"},
        )
        resp_200 = httpx.Response(
            status_code=200,
            json={"products": [{"id": 101, "title": "Recovered Product"}]},
            headers={"X-Shopify-Shop-Api-Call-Limit": "10/40"},
        )

        responses = [resp_429, resp_200]
        async def mock_get(*args, **kwargs):
            return responses.pop(0)

        mock_client.get = mock_get

        res = run_async(shopify_get_request(mock_client, "https://test.myshopify.com/products.json", {}))
        assert res.status_code == 200

    def test_bounded_retry_exhaustion_raises_504(self):
        """Verify continuous 429 stops after max_retries and raises 504."""
        mock_client = MagicMock()
        resp_429 = httpx.Response(status_code=429, headers={"Retry-After": "0.01"})

        async def always_429(*args, **kwargs):
            return resp_429

        mock_client.get = always_429

        with pytest.raises(HTTPException) as exc_info:
            run_async(shopify_get_request(mock_client, "https://test.myshopify.com/products.json", {}, max_retries=3))

        assert exc_info.value.status_code == 504

    def test_partial_sync_failure_preserves_earlier_pages(self):
        """Verify when page 2 fails, page 1 data remains preserved in database and status is failed."""
        db = MockSyncDB()
        ws = {"workspace_id": "ws_partial_test", "name": "Partial Store", "currency": "USD"}
        conn = {
            "workspace_id": "ws_partial_test",
            "shop": "partial.myshopify.com",
            "encrypted_access_token": "enc_token_123",
            "status": "connected",
        }
        # Pre-seed the connection record
        db.shopify_connections.docs.append(dict(conn))

        # Page 1 succeeds, Page 2 fails with 500
        call_count = 0
        async def mock_shopify_get(client, url, headers=None, params=None, max_retries=3):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    status_code=200,
                    json={"products": [{"id": 1, "title": "Page 1 Item 1"}, {"id": 2, "title": "Page 1 Item 2"}]},
                    headers={"Link": '<https://test/products.json?limit=10&page_info=token_2>; rel="next"'},
                )
            else:
                return httpx.Response(status_code=500, json={"error": "Internal Server Error"})

        with patch("shopify_sync.shopify_get_request", side_effect=mock_shopify_get):
            with pytest.raises(HTTPException) as exc_info:
                run_async(
                    run_shopify_sync(
                        db=db,
                        workspace=ws,
                        conn=conn,
                        decrypt_fn=lambda x: "decrypted_token",
                    )
                )

        assert exc_info.value.status_code == 502
        # Verify page 1 items are NOT deleted or rolled back
        assert len(db.shopify_products.docs) == 2
        # Verify connection status reflects failure
        conn_doc = run_async(db.shopify_connections.find_one({"workspace_id": "ws_partial_test"}))
        assert conn_doc is not None
        assert conn_doc["sync_status"] == "failed"


# ==============================================================================
# 4. Idempotency & Isolation Tests
# ==============================================================================

class TestIdempotencyAndIsolation:
    def test_repeated_sync_is_fully_idempotent(self):
        """Verify syncing the same records twice does not create duplicates."""
        db = MockSyncDB()
        ws_id = "ws_idempotent_test"
        shop = "idempotent.myshopify.com"

        resp = httpx.Response(
            status_code=200,
            json={"products": [
                {"id": 101, "title": "Beanie", "variants": [{"id": 1, "price": "25.00"}]},
                {"id": 102, "title": "Scarf", "variants": [{"id": 2, "price": "30.00"}]},
            ]},
        )

        with patch("shopify_sync.shopify_get_request", return_value=resp):
            # First sync
            run_async(sync_products(MagicMock(), f"https://{shop}", {}, db, ws_id, shop))
            assert len(db.shopify_products.docs) == 2

            # Second identical sync
            run_async(sync_products(MagicMock(), f"https://{shop}", {}, db, ws_id, shop))
            assert len(db.shopify_products.docs) == 2  # Exactly 2, zero duplicates!

    def test_workspace_isolation(self):
        """Verify syncing Workspace A does not leak or contaminate Workspace B."""
        db = MockSyncDB()
        ws_a = "ws_brand_alpha"
        ws_b = "ws_brand_beta"
        shop = "alpha.myshopify.com"

        resp = httpx.Response(
            status_code=200,
            json={"products": [{"id": 999, "title": "Alpha Product"}]},
        )

        with patch("shopify_sync.shopify_get_request", return_value=resp):
            run_async(sync_products(MagicMock(), f"https://{shop}", {}, db, ws_a, shop))

        # Check Alpha has product
        count_a = run_async(db.shopify_products.count_documents({"workspace_id": ws_a}))
        count_b = run_async(db.shopify_products.count_documents({"workspace_id": ws_b}))
        assert count_a == 1
        assert count_b == 0


# ==============================================================================
# 5. Northstar Goods Demo Protection Tests
# ==============================================================================

class TestNorthstarGoodsDemoProtection:
    def test_run_shopify_sync_rejects_demo_workspace(self):
        """Verify run_shopify_sync blocks Northstar Goods demo workspace with HTTP 400."""
        db = MockSyncDB()
        demo_ws = {
            "workspace_id": "ws_demo_northstar",
            "name": "Northstar Goods",
            "is_demo": True,
            "currency": "USD",
        }
        conn = {"shop": "northstar.myshopify.com", "encrypted_access_token": "xxx"}

        with pytest.raises(HTTPException) as exc_info:
            run_async(run_shopify_sync(db, demo_ws, conn, decrypt_fn=lambda x: "token"))

        assert exc_info.value.status_code == 400
        assert "disabled for demo workspace Northstar Goods" in exc_info.value.detail

    def test_sync_shopify_data_endpoint_rejects_demo_workspace(self):
        """Verify /api/integrations/shopify/sync endpoint blocks Northstar Goods demo workspace."""
        db = MockSyncDB()
        demo_ws = {
            "workspace_id": "ws_demo_northstar",
            "name": "Northstar Goods",
            "is_demo": True,
        }

        async def mock_get_active(user):
            return demo_ws

        shopify_integration.init_shopify(db, mock_get_active)

        with pytest.raises(HTTPException) as exc_info:
            run_async(shopify_integration.sync_shopify_data(user={"user_id": "u_admin"}))

        assert exc_info.value.status_code == 400
        assert "Demo workspace Northstar Goods cannot be synced" in exc_info.value.detail

    def test_demo_analytics_remains_intact(self):
        """Verify Northstar Goods static demo data is untouched."""
        data = build_workspace_analytics("Northstar Goods", "USD")
        assert data["store_name"] == "Northstar Goods"
        assert len(data["products"]) == 12
        assert len(data["kpis"]) == 6
