"""Automated Marketing Synchronization Cron Module for AHONIX.

Phase 6.4 Implementation:
- Secure internal HTTP cron endpoint: POST /api/internal/cron/sync-marketing
- Header-based authentication: X-Cron-Secret: <CRON_SECRET>
- Constant-time secret comparison with zero logging of secrets
- Multi-workspace active connection discovery (real merchant connections only)
- Strict exclusion of demo workspace (Northstar Goods) and inactive connections
- Failure-isolated orchestration: one merchant failure never blocks others
- MongoDB distributed locking via db.marketing_cron_locks with automatic expiration
- Real-time financial analytics aggregation refresh upon platform sync success
- Sanitized summary responses with zero credential or token leakage
"""
import os
import hmac
import secrets
import time
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Header, HTTPException

from meta_sync import sync_meta_insights_for_workspace
from google_ads_sync import sync_google_ads_insights_for_workspace
from shopify_sync import aggregate_shopify_workspace_data

logger = logging.getLogger("ahonix.marketing.cron")

router = APIRouter(prefix="/api/internal/cron", tags=["cron"])

_db = None

# Default locking timeout: 15 minutes (900 seconds)
DEFAULT_LOCK_TIMEOUT_SECONDS = 900
# Default max workspaces per single cron invocation (bounded processing)
DEFAULT_MAX_WORKSPACES_PER_CRON = 50


def init_cron(db: Any):
    """Initialize database handle for the marketing cron router."""
    global _db
    _db = db


def verify_cron_secret(provided_secret: Optional[str]) -> bool:
    """Verify X-Cron-Secret against the environment using constant-time comparison.
    
    Security: Never logs the secret or provided values.
    """
    expected = os.environ.get("CRON_SECRET", "").strip()
    if not expected or not provided_secret:
        return False
    return hmac.compare_digest(provided_secret.strip(), expected)


async def acquire_cron_lock(db: Any, lock_key: str = "marketing_sync", timeout_seconds: int = DEFAULT_LOCK_TIMEOUT_SECONDS) -> Optional[str]:
    """Atomically acquire cron execution lock in db.marketing_cron_locks.
    
    Supports crash recovery: if an existing lock has passed its expires_at timestamp,
    it is atomically superseded.
    
    Returns:
        lock_id (str) if successfully acquired, None if another active run holds the lock.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    expires_at = (now + timedelta(seconds=timeout_seconds)).isoformat()
    lock_id = secrets.token_hex(16)

    # Check for existing lock
    existing = await db.marketing_cron_locks.find_one({"lock_key": lock_key})
    if existing:
        exp_str = existing.get("expires_at")
        try:
            exp_dt = datetime.fromisoformat(exp_str) if exp_str else None
        except Exception:
            exp_dt = None

        if exp_dt and exp_dt > now:
            # An active, unexpired lock is held by another process
            logger.warning("Marketing cron lock '%s' is actively held (expires at %s). Skipping run.", lock_key, exp_str)
            return None
        else:
            # Lock exists but has expired (prior crash or timeout) -> atomic recovery
            logger.info("Marketing cron lock '%s' was expired (%s). Recovering lock.", lock_key, exp_str)
            res = await db.marketing_cron_locks.update_one(
                {"lock_key": lock_key, "expires_at": exp_str},
                {"$set": {"lock_id": lock_id, "acquired_at": now_iso, "expires_at": expires_at}},
            )
            if hasattr(res, "modified_count") and res.modified_count > 0:
                return lock_id
            # Another process raced and acquired it
            return None

    # No existing lock -> attempt insert
    try:
        await db.marketing_cron_locks.insert_one({
            "lock_key": lock_key,
            "lock_id": lock_id,
            "acquired_at": now_iso,
            "expires_at": expires_at,
        })
        return lock_id
    except Exception:
        # Race condition or unique index collision
        return None


async def release_cron_lock(db: Any, lock_key: str = "marketing_sync", lock_id: Optional[str] = None):
    """Release the cron execution lock."""
    if not lock_id or db is None:
        return
    try:
        await db.marketing_cron_locks.delete_one({"lock_key": lock_key, "lock_id": lock_id})
        logger.info("Released marketing cron lock '%s'", lock_key)
    except Exception as e:
        logger.warning("Could not cleanly release cron lock %s: %s", lock_key, e)


@router.post("/sync-marketing")
async def trigger_marketing_sync_cron(x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret")):
    """Protected internal cron endpoint to synchronize marketing insights across active merchant workspaces.
    
    Authentication:
    - Header: X-Cron-Secret: <CRON_SECRET>
    - Rejects with HTTP 401 on missing or incorrect secret.
    
    Safety:
    - Distributed MongoDB lock prevents duplicate / overlapping runs.
    - Failure isolation: errors in one platform/workspace do not interrupt others.
    - Demo workspace (Northstar Goods) is strictly excluded.
    """
    if not verify_cron_secret(x_cron_secret):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: missing or invalid cron secret.",
        )

    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    start_utc = datetime.now(timezone.utc)
    start_iso = start_utc.isoformat()

    # 1. Acquire distributed lock
    lock_id = await acquire_cron_lock(_db, lock_key="marketing_sync", timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS)
    if not lock_id:
        raise HTTPException(
            status_code=409,
            detail="Marketing sync cron is already running (active lock held).",
        )

    try:
        # 2. Discover active merchant connections
        raw_conns = await _db.marketing_connections.find({
            "platform": {"$in": ["meta", "google_ads"]},
            "status": "connected",
        }).to_list(1000)

        # Group eligible connections by workspace
        workspaces_map: Dict[str, List[Dict[str, Any]]] = {}
        for c in raw_conns:
            ws_id = c.get("workspace_id")
            if not ws_id:
                continue
            workspaces_map.setdefault(ws_id, []).append(c)

        # Bounded processing limit
        try:
            max_ws = int(os.environ.get("CRON_MAX_WORKSPACES", str(DEFAULT_MAX_WORKSPACES_PER_CRON)))
        except (ValueError, TypeError):
            max_ws = DEFAULT_MAX_WORKSPACES_PER_CRON

        workspace_ids = list(workspaces_map.keys())[:max_ws]

        workspaces_processed = 0
        platforms_succeeded = 0
        platforms_failed = 0
        reauth_required_count = 0

        # 3. Process workspaces with failure isolation
        for ws_id in workspace_ids:
            # Validate workspace is real and NOT demo
            ws = await _db.workspaces.find_one({"workspace_id": ws_id})
            if not ws:
                continue
            if (
                ws.get("is_demo")
                or ws_id == "ws_demo_northstar"
                or ws.get("name") == "Northstar Goods"
            ):
                logger.info("Skipping demo workspace %s in marketing cron", ws_id)
                continue

            workspaces_processed += 1
            workspace_had_success = False
            conns = workspaces_map[ws_id]

            for conn in conns:
                platform = conn.get("platform")
                if conn.get("status") != "connected":
                    continue

                t0 = time.monotonic()
                if platform == "meta":
                    try:
                        await sync_meta_insights_for_workspace(
                            db=_db,
                            workspace_id=ws_id,
                            is_demo=False,
                            full_refresh=False,
                        )
                        platforms_succeeded += 1
                        workspace_had_success = True
                        elapsed = round(time.monotonic() - t0, 2)
                        logger.info("Marketing cron synced Meta for workspace %s in %.2fs", ws_id[:12], elapsed)
                    except HTTPException as he:
                        platforms_failed += 1
                        if he.status_code == 401 or "reauth" in str(he.detail).lower():
                            reauth_required_count += 1
                        logger.warning(
                            "Marketing cron failed Meta for workspace %s (HTTP %d: %s)",
                            ws_id[:12], he.status_code, str(he.detail)[:150],
                        )
                    except Exception as e:
                        platforms_failed += 1
                        logger.warning(
                            "Marketing cron failed Meta for workspace %s (%s)",
                            ws_id[:12], type(e).__name__,
                        )

                elif platform == "google_ads":
                    try:
                        await sync_google_ads_insights_for_workspace(
                            db=_db,
                            workspace_id=ws_id,
                            is_demo=False,
                            full_refresh=False,
                        )
                        platforms_succeeded += 1
                        workspace_had_success = True
                        elapsed = round(time.monotonic() - t0, 2)
                        logger.info("Marketing cron synced Google Ads for workspace %s in %.2fs", ws_id[:12], elapsed)
                    except HTTPException as he:
                        platforms_failed += 1
                        if he.status_code == 401 or "reauth" in str(he.detail).lower():
                            reauth_required_count += 1
                        logger.warning(
                            "Marketing cron failed Google Ads for workspace %s (HTTP %d: %s)",
                            ws_id[:12], he.status_code, str(he.detail)[:150],
                        )
                    except Exception as e:
                        platforms_failed += 1
                        logger.warning(
                            "Marketing cron failed Google Ads for workspace %s (%s)",
                            ws_id[:12], type(e).__name__,
                        )

            # 4. Refresh workspace financial aggregation if any platform succeeded
            if workspace_had_success:
                try:
                    shopify_conn = await _db.shopify_connections.find_one({
                        "workspace_id": ws_id,
                        "status": "connected",
                    })
                    if shopify_conn:
                        await aggregate_shopify_workspace_data(
                            db=_db,
                            workspace_id=ws_id,
                            store_name=ws.get("name") or shopify_conn.get("shop") or "Store",
                            currency=ws.get("currency") or shopify_conn.get("currency") or "USD",
                        )
                except Exception as agg_err:
                    logger.warning("Could not refresh financial analytics for workspace %s: %s", ws_id[:12], agg_err)

        completed_utc = datetime.now(timezone.utc)
        completed_iso = completed_utc.isoformat()

        return {
            "ok": True,
            "started_at": start_iso,
            "completed_at": completed_iso,
            "workspaces_processed": workspaces_processed,
            "platforms_succeeded": platforms_succeeded,
            "platforms_failed": platforms_failed,
            "reauth_required": reauth_required_count,
        }

    finally:
        # 5. Guarantee release of lock
        await release_cron_lock(_db, lock_key="marketing_sync", lock_id=lock_id)
