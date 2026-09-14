"""Unit and Security Tests for Phase 5.4: Google Ads Insights Synchronization.

Coverage:
1. Micros Conversion & Metric Normalization:
   - Validates cost_micros conversion (micros / 1,000,000.0) without double division.
   - Normalizes impressions, clicks, conversions, conversion value, CTR, CPC, and CPM.
   - Enforces attribution_label="IMPORTED" for all platform-reported metrics.
2. Version Validation & Sync Windows:
   - Reuses and validates GOOGLE_ADS_API_VERSION format.
   - Configurable initial (28-day) and restatement (3-day) sync windows via environment variables.
3. GAQL Query & searchStream Execution:
   - Verifies GAQL query syntax and date filtering.
   - Developer token and login-customer-id header propagation.
   - Multiple stream batch parsing without silent truncation.
4. Idempotency & Duplicate Prevention:
   - Re-running sync with identical data updates in-place without generating duplicates.
5. Zero Fabrication & Absence Preservation:
   - Stores 0 only when explicitly reported by Google; never fabricates rows for missing dates.
6. Currency Safety:
   - Preserves raw customer account currency; flags currency_mismatch: True.
7. Transient Retries & Reauth Handling:
   - Bounded retries and exponential backoff on HTTP 5xx and RESOURCE_EXHAUSTED.
   - OAuth invalid_grant marks status as reauth_required and raises HTTP 401.
8. Workspace Isolation & Demo Protection:
   - Strict workspace isolation in queries and collections.
   - Northstar Goods demo workspace immutability (HTTP 400).
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

import google_ads_sync
from google_ads_sync import (
    get_sync_window_config,
    validate_google_ads_version,
    micros_to_currency,
    normalize_google_ads_daily_insight,
    google_ads_api_post,
    sync_google_ads_insights_for_workspace,
    GoogleAdsReauthRequiredError,
    GoogleAdsRateLimitError,
    GoogleAdsSyncError,
    DEFAULT_INITIAL_DAYS,
    DEFAULT_RESTATEMENT_DAYS,
)
import google_ads_integration
from google_ads_integration import (
    init_google_ads,
    trigger_google_ads_sync,
    get_google_ads_sync_status,
    get_google_ads_insights,
    get_google_ads_campaigns,
)
from shopify_integration import encrypt_token

_RealAsyncClient = httpx.AsyncClient


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
        self.google_ads_oauth_states = MockCollection("google_ads_oauth_states")


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def live_workspace():
    return {
        "workspace_id": "ws_live_gads_sync",
        "name": "Live Commerce Store",
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
# Test Suite 1: Micros Conversion & Configuration
# =============================================================================
class TestGoogleAdsMicrosAndConfig:
    def test_micros_to_currency_conversion(self):
        """Verifies accurate conversion from cost_micros to standard currency units (micros / 1,000,000)."""
        assert micros_to_currency(50_000_000) == 50.0
        assert micros_to_currency("50000000") == 50.0
        assert micros_to_currency(45_200_000) == 45.2
        assert micros_to_currency(1_250_000) == 1.25
        assert micros_to_currency(0) == 0.0
        assert micros_to_currency("0") == 0.0
        assert micros_to_currency(None) == 0.0
        assert micros_to_currency("invalid") == 0.0

    def test_version_validation(self):
        """Verifies Google Ads API version normalization and regex validation."""
        assert validate_google_ads_version("v19") == "v19"
        assert validate_google_ads_version("19") == "v19"
        assert validate_google_ads_version("v18") == "v18"

        with pytest.raises(ValueError, match="Invalid Google Ads API version"):
            validate_google_ads_version("v19.0.bad")

    def test_sync_windows_configurable(self):
        """Verifies initial and restatement sync windows are configurable via environment variables."""
        init_days, rest_days = get_sync_window_config()
        assert init_days == 28
        assert rest_days == 3

        with patch.dict(os.environ, {"GOOGLE_ADS_SYNC_DAYS_INITIAL": "45", "GOOGLE_ADS_SYNC_DAYS_RESTATEMENT": "5"}):
            i2, r2 = get_sync_window_config()
            assert i2 == 45
            assert r2 == 5


# =============================================================================
# Test Suite 2: Normalization & Attribution Labeling
# =============================================================================
class TestGoogleAdsDailyNormalization:
    def test_daily_normalization_fields_and_imported_label(self):
        """Verifies daily insight normalization sets attribution_label='IMPORTED' and converts micros."""
        raw_row = {
            "campaign": {
                "id": "887766",
                "name": "Search - Non-Brand High Intent",
                "status": "ENABLED",
                "advertisingChannelType": "SEARCH",
            },
            "segments": {
                "date": "2026-08-25",
            },
            "metrics": {
                "costMicros": "75500000",
                "impressions": "3200",
                "clicks": "140",
                "conversions": 6.0,
                "conversionsValue": 420.00,
                "ctr": 0.04375,
                "averageCpc": "539285",
                "averageCpm": "23593750",
            },
        }

        doc = normalize_google_ads_daily_insight(
            row=raw_row,
            workspace_id="ws_g1",
            customer_id="1234567890",
            account_currency="USD",
        )

        assert doc["workspace_id"] == "ws_g1"
        assert doc["platform"] == "google_ads"
        assert doc["account_id"] == "1234567890"
        assert doc["campaign_id"] == "887766"
        assert doc["campaign_name"] == "Search - Non-Brand High Intent"
        assert doc["date"] == "2026-08-25"
        assert doc["spend"] == 75.50
        assert doc["impressions"] == 3200
        assert doc["clicks"] == 140
        assert doc["imported_conversions"] == 6.0
        assert doc["imported_conversion_value"] == 420.00
        assert doc["currency"] == "USD"
        assert doc["attribution_label"] == "IMPORTED"
        assert doc["ctr"] == 0.04375
        assert doc["cpc"] == round(539285 / 1_000_000.0, 4)

    def test_zero_fabrication_preservation(self):
        """Verifies 0 spend / impressions / clicks are preserved only when Google explicitly reports 0."""
        zero_row = {
            "campaign": {"id": "99001", "name": "Display Awareness"},
            "segments": {"date": "2026-08-26"},
            "metrics": {"costMicros": 0, "impressions": 50, "clicks": 0, "conversions": 0.0, "conversionsValue": 0.0},
        }
        doc = normalize_google_ads_daily_insight(zero_row, "ws_g1", "1234567890", "USD")
        assert doc["spend"] == 0.0
        assert doc["impressions"] == 50
        assert doc["clicks"] == 0
        assert doc["imported_conversions"] == 0.0
        assert doc["imported_conversion_value"] == 0.0


# =============================================================================
# Test Suite 3: searchStream Batches & Rate Limiting
# =============================================================================
class TestGoogleAdsStreamingAndRateLimiting:
    def test_search_stream_multiple_batches_processed(self, mock_db, live_workspace):
        """Verifies searchStream processes multiple batches in array without silent truncation."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_refresh = encrypt_token("refresh_tok_123")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypted_refresh,
                    "selected_customer_id": "1234567890",
                    "account_currency": "USD",
                },
                upsert=True,
            )

            batch1 = {
                "results": [
                    {
                        "campaign": {"id": "c1", "name": "Camp 1", "status": "ENABLED", "advertisingChannelType": "SEARCH"},
                        "segments": {"date": "2026-08-20"},
                        "metrics": {"costMicros": "10000000", "impressions": "100", "clicks": "5"},
                    }
                ]
            }
            batch2 = {
                "results": [
                    {
                        "campaign": {"id": "c2", "name": "Camp 2", "status": "ENABLED", "advertisingChannelType": "PERFORMANCE_MAX"},
                        "segments": {"date": "2026-08-20"},
                        "metrics": {"costMicros": "20000000", "impressions": "200", "clicks": "10"},
                    }
                ]
            }

            async def mock_handler(request: httpx.Request):
                url_str = str(request.url)
                if "oauth2.googleapis.com/token" in url_str:
                    return httpx.Response(200, json={"access_token": "ya29.test_stream"})
                if "searchStream" in url_str:
                    assert request.headers.get("developer-token") == "dev_tok_xyz"
                    return httpx.Response(200, json=[batch1, batch2])
                return httpx.Response(404)

            transport = httpx.MockTransport(mock_handler)
            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "cid",
                "GOOGLE_ADS_CLIENT_SECRET": "csec",
                "GOOGLE_ADS_DEVELOPER_TOKEN": "dev_tok_xyz",
            }
            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    res = await sync_google_ads_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                    )

            assert res["ok"] is True
            assert res["synced_campaigns"] == 2
            assert res["synced_insights"] == 2

            # Verify all items from both batches were ingested
            c1 = await mock_db.marketing_daily_insights.find_one({"workspace_id": ws_id, "campaign_id": "c1"})
            assert c1 is not None
            assert c1["spend"] == 10.0

            c2 = await mock_db.marketing_daily_insights.find_one({"workspace_id": ws_id, "campaign_id": "c2"})
            assert c2 is not None
            assert c2["spend"] == 20.0

        asyncio.run(_run())

    def test_transient_retry_and_rate_limit(self):
        """Verifies HTTP 500 retries and HTTP 429 backoff."""
        async def _run():
            call_count = 0

            async def mock_handler(request: httpx.Request):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return httpx.Response(503, json={"error": {"message": "Service Unavailable"}})
                if call_count == 2:
                    return httpx.Response(429, headers={"Retry-After": "0.01"})
                return httpx.Response(200, json=[{"results": []}])

            transport = httpx.MockTransport(mock_handler)
            async with _RealAsyncClient(transport=transport) as client:
                res = await google_ads_api_post(
                    client=client,
                    url="https://googleads.googleapis.com/v19/test",
                    headers={"developer-token": "dev"},
                    payload={},
                    max_retries=4,
                )

            assert res == [{"results": []}]
            assert call_count == 3

        asyncio.run(_run())

    def test_invalid_grant_transitions_to_reauth_required(self, mock_db, live_workspace):
        """Verifies revoked/expired Google token marks status as reauth_required."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_refresh = encrypt_token("revoked_token_123")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypted_refresh,
                    "selected_customer_id": "1234567890",
                },
                upsert=True,
            )

            async def mock_token_err(request: httpx.Request):
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token revoked"})

            transport = httpx.MockTransport(mock_token_err)
            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "cid",
                "GOOGLE_ADS_CLIENT_SECRET": "csec",
                "GOOGLE_ADS_DEVELOPER_TOKEN": "dev_tok",
            }
            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    with pytest.raises(HTTPException) as exc_info:
                        await sync_google_ads_insights_for_workspace(
                            db=mock_db,
                            workspace_id=ws_id,
                            is_demo=False,
                        )

            assert exc_info.value.status_code == 401
            assert "reconnect" in exc_info.value.detail.lower()

            conn = await mock_db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "google_ads"})
            assert conn["status"] == "reauth_required"
            assert conn["sync_status"] == "reauth_required"

        asyncio.run(_run())


# =============================================================================
# Test Suite 4: End-to-End Sync Workflow, GAQL, & Login-Customer-ID
# =============================================================================
class TestGoogleAdsSyncWorkflowAndManagerAccount:
    def test_full_sync_with_manager_account_and_idempotent_upsert(self, mock_db, live_workspace):
        """Verifies initial 28d sync followed by 3d restatement sync with login-customer-id and idempotent upserts."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_refresh = encrypt_token("valid_refresh")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypted_refresh,
                    "selected_customer_id": "5556667777",
                    "selected_account_name": "Client Brand Under MCC",
                    "login_customer_id": "9998887777",  # Manager account
                    "account_currency": "USD",
                    "currency_mismatch": False,
                    "sync_status": "idle",
                },
                upsert=True,
            )

            stream_payload = [
                {
                    "results": [
                        {
                            "campaign": {
                                "id": "camp_g_10",
                                "name": "Brand Performance Max",
                                "status": "ENABLED",
                                "advertisingChannelType": "PERFORMANCE_MAX",
                                "startDate": "2026-01-01",
                            },
                            "segments": {
                                "date": "2026-08-20",
                            },
                            "metrics": {
                                "costMicros": "80000000",
                                "impressions": "5000",
                                "clicks": "220",
                                "conversions": 8.0,
                                "conversionsValue": 640.00,
                                "ctr": 0.044,
                            },
                        }
                    ]
                }
            ]

            gaql_query_captured = []

            async def mock_handler(request: httpx.Request):
                url_str = str(request.url)
                if "oauth2.googleapis.com/token" in url_str:
                    return httpx.Response(200, json={"access_token": "ya29.valid_sync_token"})
                if "searchStream" in url_str:
                    # Verify login-customer-id header from manager account
                    assert request.headers.get("login-customer-id") == "9998887777"
                    assert request.headers.get("developer-token") == "dev_tok_test"
                    body = json.loads(request.content.decode("utf-8"))
                    gaql_query_captured.append(body.get("query"))
                    return httpx.Response(200, json=stream_payload)
                return httpx.Response(404)

            transport = httpx.MockTransport(mock_handler)
            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "cid",
                "GOOGLE_ADS_CLIENT_SECRET": "csec",
                "GOOGLE_ADS_DEVELOPER_TOKEN": "dev_tok_test",
            }

            # 1. Initial Sync (28 days)
            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    res1 = await sync_google_ads_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                        full_refresh=False,
                    )

            assert res1["ok"] is True
            assert res1["window_type"] == "initial_28d"
            assert res1["synced_campaigns"] == 1
            assert res1["synced_insights"] == 1
            assert "BETWEEN" in gaql_query_captured[0]

            # Verify saved daily insight
            insight = await mock_db.marketing_daily_insights.find_one({"workspace_id": ws_id, "campaign_id": "camp_g_10"})
            assert insight["spend"] == 80.0
            assert insight["attribution_label"] == "IMPORTED"
            assert insight["currency"] == "USD"

            # 2. Second Sync (Incremental / 3-day restatement)
            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    res2 = await sync_google_ads_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                        full_refresh=False,
                    )

            assert res2["ok"] is True
            assert res2["window_type"] == "restatement_3d"

            # 3. Duplicate Prevention: Total count in DB must still be 1 (upsert updated in-place!)
            all_insights = await mock_db.marketing_daily_insights.find({"workspace_id": ws_id}).to_list(10)
            assert len(all_insights) == 1

        asyncio.run(_run())

    def test_currency_mismatch_isolation(self, mock_db, live_workspace):
        """Verifies currency mismatch (e.g. EUR ad account with USD store) flags metadata."""
        async def _run():
            ws_id = live_workspace["workspace_id"]
            encrypted_refresh = encrypt_token("valid_refresh")

            await mock_db.marketing_connections.replace_one(
                {"workspace_id": ws_id, "platform": "google_ads"},
                {
                    "workspace_id": ws_id,
                    "platform": "google_ads",
                    "status": "connected",
                    "encrypted_refresh_token": encrypted_refresh,
                    "selected_customer_id": "8889990000",
                    "account_currency": "EUR",
                    "currency_mismatch": True,  # EUR vs USD store
                },
                upsert=True,
            )

            stream_payload = [
                {
                    "results": [
                        {
                            "campaign": {"id": "c_eur", "name": "EU Search", "status": "ENABLED"},
                            "segments": {"date": "2026-08-20"},
                            "metrics": {"costMicros": "60000000", "impressions": "1000", "clicks": "50"},
                        }
                    ]
                }
            ]

            async def mock_handler(request: httpx.Request):
                url_str = str(request.url)
                if "oauth2.googleapis.com/token" in url_str:
                    return httpx.Response(200, json={"access_token": "ya29.test_eur"})
                if "searchStream" in url_str:
                    return httpx.Response(200, json=stream_payload)
                return httpx.Response(404)

            transport = httpx.MockTransport(mock_handler)
            env_vars = {
                "GOOGLE_ADS_CLIENT_ID": "cid",
                "GOOGLE_ADS_CLIENT_SECRET": "csec",
                "GOOGLE_ADS_DEVELOPER_TOKEN": "dev_tok",
            }
            with patch.dict(os.environ, env_vars):
                with patch("httpx.AsyncClient", side_effect=lambda *a, **kw: _RealAsyncClient(transport=transport)):
                    res = await sync_google_ads_insights_for_workspace(
                        db=mock_db,
                        workspace_id=ws_id,
                        is_demo=False,
                    )

            assert res["currency"] == "EUR"
            assert res["currency_mismatch"] is True

            sync_meta = await mock_db.marketing_sync_meta.find_one({"workspace_id": ws_id, "account_id": "8889990000"})
            assert sync_meta["currency_mismatch"] is True
            assert sync_meta["account_currency"] == "EUR"

            insight = await mock_db.marketing_daily_insights.find_one({"workspace_id": ws_id, "campaign_id": "c_eur"})
            assert insight["currency"] == "EUR"
            assert insight["spend"] == 60.0

        asyncio.run(_run())


# =============================================================================
# Test Suite 5: Workspace Isolation & Demo Protection
# =============================================================================
class TestWorkspaceIsolationAndDemoProtection:
    def test_demo_workspace_sync_strictly_blocked(self, mock_db, demo_workspace):
        """Verifies attempts to sync Google Ads for Northstar Goods demo workspace are rejected with HTTP 400."""
        async def _run():
            with pytest.raises(HTTPException) as exc_info:
                await sync_google_ads_insights_for_workspace(
                    db=mock_db,
                    workspace_id=demo_workspace["workspace_id"],
                    is_demo=True,
                )
            assert exc_info.value.status_code == 400
            assert "Demo workspace Northstar Goods" in exc_info.value.detail

            # API route also rejects demo workspace
            init_google_ads(mock_db, AsyncMock(return_value=demo_workspace))
            user = {"user_id": "u_demo", "email": "demo@northstargoods.com"}

            with pytest.raises(HTTPException) as ep_exc:
                await trigger_google_ads_sync(body=None, user=user)
            assert ep_exc.value.status_code == 400

        asyncio.run(_run())

    def test_workspace_isolation_insights_query(self, mock_db):
        """Verifies Workspace B cannot query or read Workspace A's Google Ads insights."""
        async def _run():
            await mock_db.marketing_daily_insights.replace_one(
                {"workspace_id": "ws_g_a", "platform": "google_ads", "account_id": "cust_a", "campaign_id": "cg_a", "date": "2026-08-25"},
                {
                    "workspace_id": "ws_g_a",
                    "platform": "google_ads",
                    "account_id": "cust_a",
                    "campaign_id": "cg_a",
                    "date": "2026-08-25",
                    "spend": 120.0,
                    "attribution_label": "IMPORTED",
                },
                upsert=True,
            )

            ws_b = {"workspace_id": "ws_g_b", "name": "Brand B", "currency": "USD", "is_demo": False}
            init_google_ads(mock_db, AsyncMock(return_value=ws_b))
            user_b = {"user_id": "u_b", "email": "b@example.com"}

            res = await get_google_ads_insights(limit=100, user=user_b)
            assert res["ok"] is True
            assert res["count"] == 0
            assert res["insights"] == []

        asyncio.run(_run())
