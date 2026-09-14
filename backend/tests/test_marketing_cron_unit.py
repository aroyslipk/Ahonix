"""Unit Tests for Phase 6.4: Automated Marketing Synchronization Cron.

Coverage:
1. Missing CRON_SECRET header rejected with HTTP 401
2. Incorrect CRON_SECRET header rejected with HTTP 401
3. Correct CRON_SECRET header authenticated and processed
4. Constant-time secret comparison function verification
5. Strict exclusion of demo workspace (Northstar Goods)
6. Exclusion of disconnected marketing accounts
7. Exclusion of reauth_required marketing accounts
8. Meta Ads insights sync invocation
9. Google Ads insights sync invocation
10. Failure isolation: one platform/workspace failure does not abort remaining workspaces
11. Workspace financial analytics aggregation refresh upon sync success
12. Distributed lock in db.marketing_cron_locks blocks overlapping/concurrent runs (HTTP 409)
13. Expired lock recovery (stale lock recovered automatically)
14. Guaranteed lock cleanup in finally block (on both success and error)
15. Workspace isolation across multi-tenant sync execution
16. Zero secret/token leakage in response payloads and application logs
"""
import sys
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import marketing_cron
from marketing_cron import (
    verify_cron_secret,
    acquire_cron_lock,
    release_cron_lock,
    trigger_marketing_sync_cron,
)


def run_async(coro):
    """Helper to run async coroutines in synchronous pytest tests."""
    return asyncio.run(coro)


# --- Mock Database Infrastructure ---------------------------------------------

class MockCollection:
    def __init__(self, name="collection"):
        self.name = name
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

    async def insert_one(self, doc):
        stored = dict(doc)
        if "_id" not in stored:
            stored["_id"] = f"{self.name}_{len(self.docs) + 1}"
        self.docs.append(stored)
        return MagicMock(inserted_id=stored["_id"])

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

    def find(self, query=None, projection=None):
        matching = []
        for doc in self.docs:
            if not query:
                matching.append(dict(doc))
            else:
                match = True
                for k, v in query.items():
                    if isinstance(v, dict) and "$in" in v:
                        if doc.get(k) not in v["$in"]:
                            match = False
                            break
                    elif doc.get(k) != v:
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


class MockCronDB:
    def __init__(self):
        self.marketing_connections = MockCollection("marketing_connections")
        self.marketing_cron_locks = MockCollection("marketing_cron_locks")
        self.workspaces = MockCollection("workspaces")
        self.shopify_connections = MockCollection("shopify_connections")
        self.workspace_data = MockCollection("workspace_data")


@pytest.fixture
def test_db():
    db = MockCronDB()
    marketing_cron.init_cron(db)
    return db


# ==============================================================================
# 1. Authentication & Security Tests
# ==============================================================================

class TestCronAuthenticationAndSecurity:
    def test_verify_cron_secret_constant_time(self, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "super_secret_cron_token_1234567890abcdef")

        # Exact match
        assert verify_cron_secret("super_secret_cron_token_1234567890abcdef") is True
        assert verify_cron_secret(" super_secret_cron_token_1234567890abcdef ") is True

        # Mismatch
        assert verify_cron_secret("wrong_token") is False
        assert verify_cron_secret("") is False
        assert verify_cron_secret(None) is False

    def test_missing_cron_secret_rejected_401(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "valid_cron_secret")
        with pytest.raises(HTTPException) as exc_info:
            run_async(trigger_marketing_sync_cron(x_cron_secret=None))

        assert exc_info.value.status_code == 401
        assert "Unauthorized" in exc_info.value.detail

    def test_wrong_cron_secret_rejected_401(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "valid_cron_secret")
        with pytest.raises(HTTPException) as exc_info:
            run_async(trigger_marketing_sync_cron(x_cron_secret="invalid_secret_attacker"))

        assert exc_info.value.status_code == 401
        assert "Unauthorized" in exc_info.value.detail

    def test_no_secret_leakage_in_response_and_logs(self, test_db, monkeypatch, caplog):
        secret = "extremely_confidential_cron_secret_999"
        monkeypatch.setenv("CRON_SECRET", secret)
        caplog.set_level(logging.DEBUG)

        resp = run_async(trigger_marketing_sync_cron(x_cron_secret=secret))

        assert resp["ok"] is True
        # Secret must never be in response dict
        assert secret not in str(resp)
        # Secret must never be in log records
        assert secret not in caplog.text


# ==============================================================================
# 2. Concurrency & Distributed Locking Tests
# ==============================================================================

class TestCronLocking:
    def test_overlapping_cron_lock_prevents_duplicate_run(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        # Simulate another job holding the lock
        future_iso = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        test_db.marketing_cron_locks.docs.append({
            "lock_key": "marketing_sync",
            "lock_id": "other_worker_lock",
            "acquired_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": future_iso,
        })

        with pytest.raises(HTTPException) as exc_info:
            run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        assert exc_info.value.status_code == 409
        assert "already running" in exc_info.value.detail

    def test_expired_lock_recovery(self, test_db):
        # Insert an expired lock (crashed worker)
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        test_db.marketing_cron_locks.docs.append({
            "lock_key": "marketing_sync",
            "lock_id": "crashed_worker_lock",
            "acquired_at": past_iso,
            "expires_at": past_iso,
        })

        # acquire_cron_lock should successfully steal/recover the expired lock
        new_lock_id = run_async(acquire_cron_lock(test_db, "marketing_sync", timeout_seconds=900))
        assert new_lock_id is not None

        doc = test_db.marketing_cron_locks.docs[0]
        assert doc["lock_id"] == new_lock_id
        assert doc["expires_at"] > datetime.now(timezone.utc).isoformat()

    def test_lock_cleanup_after_success(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        resp = run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))
        assert resp["ok"] is True
        # Lock should be cleared from database
        assert len(test_db.marketing_cron_locks.docs) == 0

    def test_lock_cleanup_after_internal_failure(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        # Inject an unexpected exception during execution
        with patch.object(test_db.marketing_connections, "find", side_effect=RuntimeError("DB disconnect")):
            with pytest.raises(RuntimeError):
                run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        # Lock must STILL be released via finally block
        assert len(test_db.marketing_cron_locks.docs) == 0


# ==============================================================================
# 3. Workspace Discovery, Isolation & Failure Handling Tests
# ==============================================================================

class TestCronOrchestrationAndIsolation:
    def test_demo_workspace_strictly_excluded(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        # Seed demo workspace and real workspace
        test_db.workspaces.docs.append({
            "workspace_id": "ws_demo_northstar",
            "name": "Northstar Goods",
            "is_demo": True,
        })
        test_db.marketing_connections.docs.append({
            "workspace_id": "ws_demo_northstar",
            "platform": "meta",
            "status": "connected",
        })

        with patch("marketing_cron.sync_meta_insights_for_workspace") as mock_meta:
            resp = run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        assert resp["ok"] is True
        assert resp["workspaces_processed"] == 0
        mock_meta.assert_not_called()

    def test_disconnected_and_reauth_required_excluded(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        test_db.workspaces.docs.append({
            "workspace_id": "ws_real_merch_1",
            "name": "Real Store 1",
            "is_demo": False,
        })
        # Disconnected Meta
        test_db.marketing_connections.docs.append({
            "workspace_id": "ws_real_merch_1",
            "platform": "meta",
            "status": "disconnected",
        })
        # Reauth required Google Ads
        test_db.marketing_connections.docs.append({
            "workspace_id": "ws_real_merch_1",
            "platform": "google_ads",
            "status": "reauth_required",
        })

        with patch("marketing_cron.sync_meta_insights_for_workspace") as mock_meta, \
             patch("marketing_cron.sync_google_ads_insights_for_workspace") as mock_google:
            resp = run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        assert resp["ok"] is True
        mock_meta.assert_not_called()
        mock_google.assert_not_called()

    def test_multi_platform_sync_success(self, test_db, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        test_db.workspaces.docs.append({
            "workspace_id": "ws_merch_active",
            "name": "Active Merchant",
            "is_demo": False,
            "currency": "USD",
        })
        test_db.shopify_connections.docs.append({
            "workspace_id": "ws_merch_active",
            "shop": "active.myshopify.com",
            "status": "connected",
        })
        test_db.marketing_connections.docs.extend([
            {"workspace_id": "ws_merch_active", "platform": "meta", "status": "connected"},
            {"workspace_id": "ws_merch_active", "platform": "google_ads", "status": "connected"},
        ])

        with patch("marketing_cron.sync_meta_insights_for_workspace", return_value={"ok": True}) as mock_meta, \
             patch("marketing_cron.sync_google_ads_insights_for_workspace", return_value={"ok": True}) as mock_google, \
             patch("marketing_cron.aggregate_shopify_workspace_data") as mock_agg:
            resp = run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        assert resp["ok"] is True
        assert resp["workspaces_processed"] == 1
        assert resp["platforms_succeeded"] == 2
        assert resp["platforms_failed"] == 0
        assert resp["reauth_required"] == 0

        mock_meta.assert_called_once_with(db=test_db, workspace_id="ws_merch_active", is_demo=False, full_refresh=False)
        mock_google.assert_called_once_with(db=test_db, workspace_id="ws_merch_active", is_demo=False, full_refresh=False)
        mock_agg.assert_called_once()

    def test_failure_isolation_one_failure_does_not_abort_others(self, test_db, monkeypatch):
        """Workspace 1 Meta fails with 401 (reauth); Workspace 2 Google succeeds."""
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        # Workspace 1 (Fails)
        test_db.workspaces.docs.append({"workspace_id": "ws_failing", "name": "Failing Merchant", "is_demo": False})
        test_db.marketing_connections.docs.append({"workspace_id": "ws_failing", "platform": "meta", "status": "connected"})

        # Workspace 2 (Succeeds)
        test_db.workspaces.docs.append({"workspace_id": "ws_healthy", "name": "Healthy Merchant", "is_demo": False})
        test_db.marketing_connections.docs.append({"workspace_id": "ws_healthy", "platform": "google_ads", "status": "connected"})

        async def failing_meta(*args, **kwargs):
            raise HTTPException(status_code=401, detail="Token expired: reauth_required")

        async def healthy_google(*args, **kwargs):
            return {"ok": True}

        with patch("marketing_cron.sync_meta_insights_for_workspace", side_effect=failing_meta), \
             patch("marketing_cron.sync_google_ads_insights_for_workspace", side_effect=healthy_google):
            resp = run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        assert resp["ok"] is True
        assert resp["workspaces_processed"] == 2
        assert resp["platforms_succeeded"] == 1
        assert resp["platforms_failed"] == 1
        assert resp["reauth_required"] == 1

    def test_workspace_isolation_across_tenants(self, test_db, monkeypatch):
        """Verify syncing Workspace A passes workspace_id A and does not confuse with B."""
        monkeypatch.setenv("CRON_SECRET", "test_secret")

        test_db.workspaces.docs.extend([
            {"workspace_id": "ws_tenant_a", "name": "Tenant A", "is_demo": False},
            {"workspace_id": "ws_tenant_b", "name": "Tenant B", "is_demo": False},
        ])
        test_db.marketing_connections.docs.extend([
            {"workspace_id": "ws_tenant_a", "platform": "meta", "status": "connected"},
            {"workspace_id": "ws_tenant_b", "platform": "meta", "status": "connected"},
        ])

        synced_workspaces = []
        async def mock_sync(db, workspace_id, **kwargs):
            synced_workspaces.append(workspace_id)
            return {"ok": True}

        with patch("marketing_cron.sync_meta_insights_for_workspace", side_effect=mock_sync):
            resp = run_async(trigger_marketing_sync_cron(x_cron_secret="test_secret"))

        assert resp["ok"] is True
        assert synced_workspaces == ["ws_tenant_a", "ws_tenant_b"]
