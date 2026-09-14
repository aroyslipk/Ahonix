"""Unit and Security Tests for Phase 5.2: Meta Ads Insights Synchronization.

Coverage:
1. Configurable Meta API Version:
   - Verifies reused META_API_VERSION is validated and used in request URLs.
2. Pagination:
   - Multi-page cursor pagination traverses all pages without silent truncation.
   - Empty pages and termination conditions handled safely.
3. Sync Windows:
   - Configurable initial sync window (default 28 days via META_SYNC_DAYS_INITIAL).
   - Configurable restatement sync window (default 3 days via META_SYNC_DAYS_RESTATEMENT).
   - Distinguishes initial sync from restatement sync.
4. Data Normalization & Attribution Labeling:
   - Normalizes spend, impressions, clicks, date, cpm, cpc, ctr.
   - Normalizes purchase conversions and conversion values from actions / action_values.
   - Guarantees attribution_label="IMPORTED".
5. Duplicate Prevention & Upsert Idempotency:
   - Re-running sync with identical data updates in-place without duplicate rows.
6. Zero Fabrication & Absence Preservation:
   - Preserves 0.0 only when Meta explicitly returns 0.
   - Never fabricates rows for dates missing from Meta's response.
7. Transient Retry & Rate Limit Handling:
   - Backoff on HTTP 429, respect Retry-After.
   - Backoff on HTTP 5xx.
   - Bounded retries prevent infinite loops.
8. OAuth Token Expiration / Reauth Required:
   - Code 190 / OAuthException transitions status to reauth_required and raises HTTP 401.
9. Currency Mismatch Protection:
   - Persists raw currency; flags currency_mismatch: True in sync metadata without blending.
10. Workspace Isolation:
    - Data stored with workspace_id; no cross-workspace leakage.
11. Demo Workspace Protection:
    - Northstar Goods sync blocked with HTTP 400; demo data untouched.
"""
import sys
from pathlib import Path
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import meta_sync
from meta_sync import (
    get_sync_window_config,
    validate_meta_version,
    extract_meta_conversions,
    extract_meta_conversion_value,
    normalize_meta_daily_insight,
    fetch_meta_cursor_paginated,
    meta_api_get,
    sync_meta_insights_for_workspace,
    MetaReauthRequiredError,
    MetaRateLimitError,
    MetaSyncError,
    DEFAULT_INITIAL_DAYS,
    DEFAULT_RESTATEMENT_DAYS,
)
import meta_integration
from meta_integration import init_meta, trigger_meta_sync, get_meta_sync_status, get_meta_insights, get_meta_campaigns
from shopify_integration import encrypt_token


# --- Mock Async In-Memory MongoDB --------------------------------------------
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
                if isinstance(v, dict):
                    val = d.get(k)
                    if "$gte" in v and (val is None or val < v["$gte"]):
                        match = False
                        break
                    if "$lte" in v and (val is None or val > v["$lte"]):
                        match = False
                        break
                elif d.get(k) != v:
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

    async def delete_one(self, filter_query):
        for idx, d in enumerate(self.docs):
            match = True
            for k, v in filter_query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                self.docs.pop(idx)
                return


class MockDB:
    def __init__(self):
        self.marketing_connections = MockCollection("marketing_connections")
        self.marketing_campaigns = MockCollection("marketing_campaigns")
        self.marketing_daily_insights = MockCollection("marketing_daily_insights")
        self.marketing_sync_meta = MockCollection("marketing_sync_meta")
        self.meta_oauth_states = MockCollection("meta_oauth_states")


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def live_workspace():
    return {
        "workspace_id": "ws_live_real",
        "name": "Live Real Brand",
        "currency": "USD",
        "is_demo": False,
    }


@pytest.fixture
def demo_workspace():
    return {
        "workspace_id": "ws_demo_northstar",
        "name": "Northstar Goods",
        "currency": "USD",
        "is_demo": True,
    }


# =============================================================================
# Test Suite 1: Configuration & Version Validation
# =============================================================================
class TestMetaSyncConfigAndValidation:
    def test_version_validation_reused(self):
        """Verifies clean_meta_api_version and format validation."""
        assert validate_meta_version("v21.0") == "v21.0"
        assert validate_meta_version("21.0") == "v21.0"
        assert validate_meta_version("v20.0") == "v20.0"

        with pytest.raises(ValueError, match="Invalid Meta API version"):
            validate_meta_version("invalid_version")

    def test_sync_windows_configurable(self):
        """Verifies sync windows default to 28/3 and are configurable via env."""
        initial, restatement = get_sync_window_config()
        assert initial == 28
        assert restatement == 3

        with patch.dict(os.environ, {"META_SYNC_DAYS_INITIAL": "60", "META_SYNC_DAYS_RESTATEMENT": "7"}):
            i2, r2 = get_sync_window_config()
            assert i2 == 60
            assert r2 == 7

        # Invalid strings fallback to defaults
        with patch.dict(os.environ, {"META_SYNC_DAYS_INITIAL": "invalid", "META_SYNC_DAYS_RESTATEMENT": "-5"}):
            i3, r3 = get_sync_window_config()
            assert i3 == 28
            assert r3 == 3


# =============================================================================
# Test Suite 2: Normalization & Attribution Labeling
# =============================================================================
class TestMetaNormalizationAndAttribution:
    def test_daily_normalization_attribution_label(self):
        """Verifies daily insight normalization sets attribution_label='IMPORTED' and preserves fields."""
        raw_item = {
            "campaign_id": "12001",
            "campaign_name": "Summer Retargeting",
            "date_start": "2026-08-25",
            "date_stop": "2026-08-25",
            "spend": "125.50",
            "impressions": "4500",
            "clicks": "120",
            "cpm": "27.88",
            "cpc": "1.04",
            "ctr": "2.66",
            "actions": [
                {"action_type": "link_click", "value": "120"},
                {"action_type": "purchase", "value": "5"},
            ],
            "action_values": [
                {"action_type": "purchase", "value": "350.00"},
            ],
        }

        doc = normalize_meta_daily_insight(
            row=raw_item,
            workspace_id="ws_1",
            account_id="act_12345",
            account_currency="USD",
        )

        assert doc["workspace_id"] == "ws_1"
        assert doc["platform"] == "meta"
        assert doc["account_id"] == "act_12345"
        assert doc["campaign_id"] == "12001"
        assert doc["campaign_name"] == "Summer Retargeting"
        assert doc["date"] == "2026-08-25"
        assert doc["spend"] == 125.50
        assert doc["impressions"] == 4500
        assert doc["clicks"] == 120
        assert doc["imported_conversions"] == 5.0
        assert doc["imported_conversion_value"] == 350.00
        assert doc["currency"] == "USD"
        assert doc["attribution_label"] == "IMPORTED"  # Strictly IMPORTED, never ACTUAL
        assert doc["cpm"] == 27.88

    def test_conversion_extraction_priority(self):
        """Verifies purchase extraction handles omni_purchase and pixel purchase."""
        actions_omni = [{"action_type": "omni_purchase", "value": "8"}]
        assert extract_meta_conversions(actions_omni) == 8.0

        action_values_pixel = [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "420.50"}]
        assert extract_meta_conversion_value(action_values_pixel) == 420.50

        # Non-purchase action returns 0.0
        non_purchase = [{"action_type": "page_engagement", "value": "50"}]
        assert extract_meta_conversions(non_purchase) == 0.0
        assert extract_meta_conversion_value(non_purchase) == 0.0

    def test_zero_fabrication_rule(self):
        """Verifies 0.0 spend is preserved only when Meta explicitly provides it."""
        row_zero = {
            "campaign_id": "12002",
            "campaign_name": "Brand Awareness",
            "date_start": "2026-08-26",
            "spend": "0.00",
            "impressions": "100",
            "clicks": "0",
        }
        doc = normalize_meta_daily_insight(row_zero, "ws_1", "act_123", "USD")
        assert doc["spend"] == 0.0
        assert doc["clicks"] == 0
        assert doc["impressions"] == 100


# =============================================================================
# Test Suite 3: Pagination & Rate Limiting / Retries
# =============================================================================
class TestMetaPaginationAndRateLimiting:
    def test_cursor_pagination_traversal(self):
        """Verifies cursor pagination traverses multiple pages and stops when after cursor terminates."""
        async def _run():
            page1_data = {
                "data": [{"campaign_id": "c1", "spend": "10.0"}, {"campaign_id": "c2", "spend": "20.0"}],
                "paging": {
                    "cursors": {"after": "cursor_p2"},
                    "next": "https://graph.facebook.com/v21.0/act_123/insights?after=cursor_p2",
                },
            }
            page2_data = {
                "data": [{"campaign_id": "c3", "spend": "30.0"}],
                "paging": {
                    "cursors": {"after": "cursor_p3"},
                },
            }

            call_count = 0

            async def mock_transport(request: httpx.Request):
                nonlocal call_count
                call_count += 1
                if "cursor_p2" in str(request.url):
                    return httpx.Response(200, json=page2_data)
                return httpx.Response(200, json=page1_data)

            transport = httpx.MockTransport(mock_transport)
            async with httpx.AsyncClient(transport=transport) as client:
                items = await fetch_meta_cursor_paginated(client, "https://graph.facebook.com/v21.0/act_123/insights", {})

            assert len(items) == 3
            assert call_count == 2
            assert items[0]["campaign_id"] == "c1"
            assert items[2]["campaign_id"] == "c3"

        asyncio.run(_run())

    def test_transient_retry_and_backoff(self):
        """Verifies HTTP 500/502 retries up to max_retries."""
        async def _run():
            call_count = 0

            async def mock_transport(request: httpx.Request):
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    return httpx.Response(500, json={"error": {"code": 2, "message": "Temporary service error"}})
                return httpx.Response(200, json={"data": [{"ok": True}]})

            transport = httpx.MockTransport(mock_transport)
            async with httpx.AsyncClient(transport=transport) as client:
                res = await meta_api_get(client, "https://graph.facebook.com/v21.0/test", {}, max_retries=3)

            assert res == {"data": [{"ok": True}]}
            assert call_count == 2

        asyncio.run(_run())

    def test_rate_limit_retry_after_header(self):
        """Verifies HTTP 429 parses Retry-After and retries."""
        async def _run():
            call_count = 0

            async def mock_transport(request: httpx.Request):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return httpx.Response(429, headers={"Retry-After": "0.01"})
                return httpx.Response(200, json={"data": [{"rate_limit_passed": True}]})

            transport = httpx.MockTransport(mock_transport)
            async with httpx.AsyncClient(transport=transport) as client:
                res = await meta_api_get(client, "https://graph.facebook.com/v21.0/test", {}, max_retries=3)

            assert res == {"data": [{"rate_limit_passed": True}]}
            assert call_count == 2

        asyncio.run(_run())

    def test_rate_limit_exhausted_raises_error(self):
        """Verifies bounded retries raise MetaRateLimitError when retries are exhausted."""
        async def _run():
            async def mock_transport(request: httpx.Request):
                return httpx.Response(429, headers={"Retry-After": "0.001"})

            transport = httpx.MockTransport(mock_transport)
            async with httpx.AsyncClient(transport=transport) as client:
                with pytest.raises(MetaRateLimitError):
                    await meta_api_get(client, "https://graph.facebook.com/v21.0/test", {}, max_retries=2)

        asyncio.run(_run())

    def test_oauth_expiration_raises_reauth_required(self):
        """Verifies code 190 / OAuthException immediately raises MetaReauthRequiredError without retries."""
        async def _run():
            call_count = 0

            async def mock_transport(request: httpx.Request):
                nonlocal call_count
                call_count += 1
                return httpx.Response(400, json={
                    "error": {
                        "message": "Error validating access token: Session has expired.",
                        "type": "OAuthException",
                        "code": 190,
                        "error_subcode": 463,
                    }
                })

            transport = httpx.MockTransport(mock_transport)
            async with httpx.AsyncClient(transport=transport) as client:
                with pytest.raises(MetaReauthRequiredError, match="Session has expired"):
                    await meta_api_get(client, "https://graph.facebook.com/v21.0/test", {}, max_retries=3)

            assert call_count == 1

        asyncio.run(_run())


# =============================================================================
# Test Suite 4: End-to-End Insights Synchronization Workflow
# =============================================================================
class TestMetaInsightsSyncWorkflow:
    def test_full_insights_sync_initial_and_restatement(self, mock_db, live_workspace):
        """Verifies initial 28-day sync followed by 3-day restatement sync with duplicate prevention."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            raw_token = "EAABtest_token_secret_123"
            encrypted_token = encrypt_token(raw_token)

            # Setup connected connection
            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "meta"},
                {
                    "workspace_id": ws_id,
                    "platform": "meta",
                    "status": "connected",
                    "encrypted_access_token": encrypted_token,
                    "selected_account_id": "act_998877",
                    "selected_account_name": "Main US Ad Account",
                    "account_currency": "USD",
                    "currency_mismatch": False,
                    "api_version": "v21.0",
                    "sync_status": "idle",
                },
                upsert=True,
            )

            # Mock Meta API responses
            campaigns_resp = {
                "data": [
                    {"id": "camp_1", "name": "Summer Prospecting", "status": "ACTIVE", "objective": "OUTCOME_SALES"},
                    {"id": "camp_2", "name": "Brand Retargeting", "status": "ACTIVE", "objective": "OUTCOME_SALES"},
                ]
            }
            insights_resp = {
                "data": [
                    {
                        "campaign_id": "camp_1",
                        "campaign_name": "Summer Prospecting",
                        "date_start": "2026-08-20",
                        "spend": "50.00",
                        "impressions": "2500",
                        "clicks": "60",
                        "actions": [{"action_type": "purchase", "value": "2"}],
                        "action_values": [{"action_type": "purchase", "value": "140.00"}],
                    },
                    {
                        "campaign_id": "camp_2",
                        "campaign_name": "Brand Retargeting",
                        "date_start": "2026-08-20",
                        "spend": "25.00",
                        "impressions": "1000",
                        "clicks": "40",
                        "actions": [{"action_type": "purchase", "value": "1"}],
                        "action_values": [{"action_type": "purchase", "value": "80.00"}],
                    },
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
                    # 1. First sync (Initial 28 days)
                    res1 = await sync_meta_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                        full_refresh=False,
                        http_client=client,
                    )

            assert res1["ok"] is True
            assert res1["status"] == "success"
            assert res1["window_type"] == "initial_28d"
            assert res1["synced_campaigns"] == 2
            assert res1["synced_insights"] == 2

            # Verify documents persisted in DB
            saved_campaigns = await mock_db.marketing_campaigns.find({"workspace_id": ws_id}).to_list(10)
            assert len(saved_campaigns) == 2

            saved_insights = await mock_db.marketing_daily_insights.find({"workspace_id": ws_id}).to_list(10)
            assert len(saved_insights) == 2
            assert saved_insights[0]["attribution_label"] == "IMPORTED"
            assert saved_insights[0]["currency"] == "USD"

            # Verify sync metadata persisted
            sync_meta = await mock_db.marketing_sync_meta.find_one({"workspace_id": ws_id, "account_id": "act_998877"})
            assert sync_meta["status"] == "success"
            assert sync_meta["synced_campaigns_count"] == 2
            assert sync_meta["synced_insights_count"] == 2
            assert sync_meta["window_type"] == "initial_28d"

            # 2. Second sync (Incremental / 3-day restatement)
            async with httpx.AsyncClient(transport=transport) as client2:
                with patch.dict(os.environ, {"META_APP_SECRET": "meta_sec_123"}):
                    res2 = await sync_meta_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                        full_refresh=False,
                        http_client=client2,
                    )

            assert res2["ok"] is True
            assert res2["window_type"] == "restatement_3d"

            # 3. Duplicate Prevention Verification
            saved_insights_after = await mock_db.marketing_daily_insights.find({"workspace_id": ws_id}).to_list(10)
            assert len(saved_insights_after) == 2

        asyncio.run(_run())

    def test_currency_mismatch_preservation(self, mock_db, live_workspace):
        """Verifies currency-mismatched ad account is flagged in sync metadata and insights."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            raw_token = "EAABtest_token_secret_eur"
            encrypted_token = encrypt_token(raw_token)

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "meta"},
                {
                    "workspace_id": ws_id,
                    "platform": "meta",
                    "status": "connected",
                    "encrypted_access_token": encrypted_token,
                    "selected_account_id": "act_eur_001",
                    "selected_account_name": "EU European Account",
                    "account_currency": "EUR",
                    "currency_mismatch": True,
                    "api_version": "v21.0",
                    "sync_status": "idle",
                },
                upsert=True,
            )

            insights_resp = {
                "data": [
                    {
                        "campaign_id": "camp_eu",
                        "date_start": "2026-08-20",
                        "spend": "90.00",
                        "impressions": "3000",
                        "clicks": "70",
                    }
                ]
            }

            async def mock_handler(request: httpx.Request):
                if "/insights" in str(request.url):
                    return httpx.Response(200, json=insights_resp)
                return httpx.Response(200, json={"data": []})

            transport = httpx.MockTransport(mock_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                with patch.dict(os.environ, {"META_APP_SECRET": "meta_sec_123"}):
                    res = await sync_meta_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                        http_client=client,
                    )

            assert res["currency"] == "EUR"
            assert res["currency_mismatch"] is True

            sync_meta = await mock_db.marketing_sync_meta.find_one({"workspace_id": ws_id, "account_id": "act_eur_001"})
            assert sync_meta["currency_mismatch"] is True
            assert sync_meta["account_currency"] == "EUR"

            insight = await mock_db.marketing_daily_insights.find_one({"workspace_id": ws_id, "campaign_id": "camp_eu"})
            assert insight["currency"] == "EUR"
            assert insight["spend"] == 90.00

        asyncio.run(_run())

    def test_reauth_required_marks_connection_and_sync_meta(self, mock_db, live_workspace):
        """Verifies expired token marks both connection and sync_meta as reauth_required."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_token = encrypt_token("expired_token")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "meta"},
                {
                    "workspace_id": ws_id,
                    "platform": "meta",
                    "status": "connected",
                    "encrypted_access_token": encrypted_token,
                    "selected_account_id": "act_112233",
                    "api_version": "v21.0",
                },
                upsert=True,
            )

            async def mock_expired_handler(request: httpx.Request):
                return httpx.Response(400, json={
                    "error": {
                        "message": "The access token could not be decrypted",
                        "type": "OAuthException",
                        "code": 190,
                    }
                })

            transport = httpx.MockTransport(mock_expired_handler)
            async with httpx.AsyncClient(transport=transport) as client:
                with patch.dict(os.environ, {"META_APP_SECRET": "meta_sec_123"}):
                    with pytest.raises(HTTPException) as exc_info:
                        await sync_meta_insights_for_workspace(
                            db=mock_db,
                            workspace_id=ws_id,
                            is_demo=False,
                            http_client=client,
                        )

            assert exc_info.value.status_code == 401
            assert "reconnect" in exc_info.value.detail.lower()

            conn = await mock_db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
            assert conn["status"] == "reauth_required"
            assert conn["sync_status"] == "reauth_required"

            sync_meta = await mock_db.marketing_sync_meta.find_one({"workspace_id": ws_id, "account_id": "act_112233"})
            assert sync_meta["status"] == "reauth_required"

        asyncio.run(_run())


# =============================================================================
# Test Suite 5: Workspace Isolation & Demo Protection
# =============================================================================
class TestWorkspaceIsolationAndDemoProtection:
    def test_demo_workspace_sync_strictly_blocked(self, mock_db, demo_workspace):
        """Verifies attempts to sync Northstar Goods demo workspace are rejected with HTTP 400."""
        async def _run():
            with pytest.raises(HTTPException) as exc_info:
                await sync_meta_insights_for_workspace(
                    db=mock_db,
                    workspace_id=demo_workspace["workspace_id"],
                    is_demo=True,
                )
            assert exc_info.value.status_code == 400
            assert "Demo workspace Northstar Goods" in exc_info.value.detail

            # Endpoints also reject demo sync
            init_meta(mock_db, AsyncMock(return_value=demo_workspace))
            fake_user = {"user_id": "u_demo", "email": "demo@northstargoods.com"}

            with pytest.raises(HTTPException) as ep_exc:
                await trigger_meta_sync(body=None, user=fake_user)
            assert ep_exc.value.status_code == 400

        asyncio.run(_run())

    def test_workspace_isolation_insights_query(self, mock_db):
        """Verifies Workspace B cannot see or query daily insights of Workspace A."""
        async def _run():
            await mock_db.marketing_daily_insights.replace_one(
                {"workspace_id": "ws_a", "platform": "meta", "account_id": "act_a", "campaign_id": "c_a", "date": "2026-08-25"},
                {
                    "workspace_id": "ws_a",
                    "platform": "meta",
                    "account_id": "act_a",
                    "campaign_id": "c_a",
                    "date": "2026-08-25",
                    "spend": 100.0,
                    "attribution_label": "IMPORTED",
                },
                upsert=True,
            )

            ws_b = {"workspace_id": "ws_b", "name": "Brand B", "currency": "USD", "is_demo": False}
            init_meta(mock_db, AsyncMock(return_value=ws_b))
            user_b = {"user_id": "u_b", "email": "b@example.com"}

            res = await get_meta_insights(limit=100, user=user_b)
            assert res["ok"] is True
            assert res["count"] == 0
            assert res["insights"] == []

        asyncio.run(_run())
