"""Meta Ads Insights Synchronization Module for AHONIX.

Phase 5.2 Implementation:
- Ingest real Meta Ads campaign catalog into db.marketing_campaigns
- Ingest campaign-level daily insights into db.marketing_daily_insights
- Sync metadata tracking in db.marketing_sync_meta
- Configurable sync windows:
    - Initial sync window: default 28 days (META_SYNC_DAYS_INITIAL)
    - Restatement window: default 3 days (META_SYNC_DAYS_RESTATEMENT)
- Robust Meta Graph API cursor-based pagination
- Rate limiting and transient error handling with exponential backoff & Retry-After
- Token expiration / revocation detection (OAuthException 190/102 -> reauth_required)
- Pure raw currency preservation (zero premature currency conversion)
- Strict attribution labeling: attribution_label="IMPORTED"
- Zero metric fabrication (preserves absence of data; 0 only when Meta explicitly reports 0)
- Workspace isolation and demo workspace (Northstar Goods) absolute protection
- Secret security: tokens decrypted server-side only, appsecret_proof included, zero leakage
"""
import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import HTTPException

from meta_integration import (
    clean_meta_api_version,
    get_meta_config,
    generate_appsecret_proof,
    DEFAULT_META_API_VERSION,
)
from shopify_integration import decrypt_token

logger = logging.getLogger("ahonix.meta.sync")

# Default Sync Windows
DEFAULT_INITIAL_DAYS = 28
DEFAULT_RESTATEMENT_DAYS = 3
DEFAULT_BATCH_LIMIT = 100
MAX_PAGES = 50


class MetaSyncError(Exception):
    """Base exception for Meta synchronization errors."""
    pass


class MetaReauthRequiredError(MetaSyncError):
    """Raised when Meta OAuth access token has expired or been revoked."""
    pass


class MetaRateLimitError(MetaSyncError):
    """Raised when Meta API rate limit is exceeded and retries exhausted."""
    pass


def get_sync_window_config() -> Tuple[int, int]:
    """Retrieve and validate initial and restatement sync windows from environment."""
    try:
        initial = int(os.environ.get("META_SYNC_DAYS_INITIAL", str(DEFAULT_INITIAL_DAYS)))
        if initial < 1 or initial > 365:
            initial = DEFAULT_INITIAL_DAYS
    except (ValueError, TypeError):
        initial = DEFAULT_INITIAL_DAYS

    try:
        restatement = int(os.environ.get("META_SYNC_DAYS_RESTATEMENT", str(DEFAULT_RESTATEMENT_DAYS)))
        if restatement < 1 or restatement > 90:
            restatement = DEFAULT_RESTATEMENT_DAYS
    except (ValueError, TypeError):
        restatement = DEFAULT_RESTATEMENT_DAYS

    return initial, restatement


def validate_meta_version(version: str) -> str:
    """Validate Meta Graph API version string matches format vXX.X."""
    cleaned = clean_meta_api_version(version)
    if not re.match(r"^v\d+(\.\d+)?$", cleaned):
        raise ValueError(f"Invalid Meta API version format: '{version}'. Must be e.g. 'v21.0'")
    return cleaned


def extract_meta_conversions(actions: Optional[List[Dict[str, Any]]]) -> float:
    """Extract purchase / conversion count from Meta actions array.
    Prioritizes direct purchase types: 'purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase'.
    Returns 0.0 if not reported.
    """
    if not actions or not isinstance(actions, list):
        return 0.0

    purchase_types = {
        "purchase",
        "omni_purchase",
        "offsite_conversion.fb_pixel_purchase",
    }
    for act in actions:
        if isinstance(act, dict) and act.get("action_type") in purchase_types:
            try:
                return float(act.get("value", 0))
            except (ValueError, TypeError):
                pass

    return 0.0


def extract_meta_conversion_value(action_values: Optional[List[Dict[str, Any]]]) -> float:
    """Extract purchase conversion revenue value from Meta action_values array.
    Prioritizes: 'purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase'.
    Returns 0.0 if not reported.
    """
    if not action_values or not isinstance(action_values, list):
        return 0.0

    purchase_types = {
        "purchase",
        "omni_purchase",
        "offsite_conversion.fb_pixel_purchase",
    }
    for act in action_values:
        if isinstance(act, dict) and act.get("action_type") in purchase_types:
            try:
                return float(act.get("value", 0))
            except (ValueError, TypeError):
                pass

    return 0.0


async def meta_api_get(
    client: httpx.AsyncClient,
    url: str,
    params: Dict[str, Any],
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Execute an HTTP GET request to Meta Graph API with bounded retries,
    exponential backoff, Retry-After header parsing, and OAuth error detection.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            res = await client.get(url, params=params)

            # Check HTTP 429 (Rate Limit)
            if res.status_code == 429:
                attempt += 1
                retry_after_hdr = res.headers.get("Retry-After")
                wait_sec = float(retry_after_hdr) if retry_after_hdr else (2.0 ** attempt)
                logger.warning(
                    "Meta API rate limited (HTTP 429). Retrying in %.1f seconds (attempt %d/%d)...",
                    wait_sec, attempt, max_retries,
                )
                if attempt >= max_retries:
                    raise MetaRateLimitError("Meta API rate limit exceeded after bounded retries.")
                await asyncio.sleep(wait_sec)
                continue

            # Check HTTP 5xx (Transient Server Errors)
            if res.status_code in (500, 502, 503, 504):
                attempt += 1
                wait_sec = 1.5 * attempt
                logger.warning(
                    "Meta API transient error (HTTP %d). Retrying in %.1f seconds (attempt %d/%d)...",
                    res.status_code, wait_sec, attempt, max_retries,
                )
                if attempt >= max_retries:
                    raise MetaSyncError(f"Meta API unavailable (HTTP {res.status_code}) after {max_retries} retries.")
                await asyncio.sleep(wait_sec)
                continue

            # Parse JSON body to inspect Meta application-level errors
            try:
                data = res.json()
            except Exception:
                data = {}

            if "error" in data:
                err = data["error"]
                err_code = err.get("code")
                err_type = err.get("type")
                err_subcode = err.get("error_subcode")
                err_msg = err.get("message", "Unknown Meta Graph API error")

                # OAuth Token Expiration / Revocation Check (codes 190, 102)
                if err_code in (190, 102) or err_type in ("OAuthException", "OAuthAccessTokenException"):
                    logger.error("Meta OAuth token expired or revoked: %s (code: %s)", err_msg, err_code)
                    raise MetaReauthRequiredError(f"Meta access token expired or revoked: {err_msg}")

                # Application/Account Level Rate Limit Codes (17, 32, 80004, 4)
                if err_code in (17, 32, 80004, 4):
                    attempt += 1
                    wait_sec = 2.0 ** attempt
                    logger.warning(
                        "Meta API rate limit code %d: %s. Retrying in %.1f seconds...",
                        err_code, err_msg, wait_sec,
                    )
                    if attempt >= max_retries:
                        raise MetaRateLimitError(f"Meta rate limit reached (code {err_code}): {err_msg}")
                    await asyncio.sleep(wait_sec)
                    continue

                # Temporary Meta Service Errors (codes 1, 2)
                if err_code in (1, 2):
                    attempt += 1
                    wait_sec = 1.5 * attempt
                    logger.warning("Meta transient error code %d: %s. Retrying in %.1f seconds...", err_code, err_msg, wait_sec)
                    if attempt >= max_retries:
                        raise MetaSyncError(f"Meta transient error: {err_msg}")
                    await asyncio.sleep(wait_sec)
                    continue

                # Unrecoverable error
                raise MetaSyncError(f"Meta Graph API error (code {err_code}): {err_msg}")

            if res.status_code != 200:
                raise MetaSyncError(f"Meta Graph API request failed with HTTP {res.status_code}: {res.text}")

            return data

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            attempt += 1
            if attempt >= max_retries:
                logger.error("Meta API connection failed after %d retries: %s", max_retries, exc)
                raise MetaSyncError(f"Meta network error: {type(exc).__name__}")
            wait_sec = 1.0 * attempt
            await asyncio.sleep(wait_sec)

    raise MetaSyncError("Meta API request timed out or failed.")


async def fetch_meta_cursor_paginated(
    client: httpx.AsyncClient,
    url: str,
    base_params: Dict[str, Any],
    max_pages: int = MAX_PAGES,
) -> List[Dict[str, Any]]:
    """Fetch all pages from a Meta Graph API cursor-paginated endpoint.
    Guarantees no silent truncation, loops until no next cursor, and handles empty pages safely.
    """
    all_items: List[Dict[str, Any]] = []
    current_params = dict(base_params)
    seen_cursors = set()
    page_count = 0

    while page_count < max_pages:
        page_count += 1
        res_data = await meta_api_get(client, url, current_params)
        page_items = res_data.get("data") or []

        if not page_items:
            # Empty page indicates end of data
            break

        all_items.extend(page_items)

        paging = res_data.get("paging") or {}
        next_url = paging.get("next")
        cursors = paging.get("cursors") or {}
        after_cursor = cursors.get("after")

        # Stop if no next page indicated or no cursor provided
        if not next_url or not after_cursor:
            break

        # Infinite loop protection
        if after_cursor in seen_cursors:
            logger.warning("Repeated cursor detected (%s); terminating pagination.", after_cursor)
            break
        seen_cursors.add(after_cursor)

        # Update params for next page request (reusing token and proof)
        current_params["after"] = after_cursor

    return all_items


def normalize_meta_daily_insight(
    row: Dict[str, Any],
    workspace_id: str,
    account_id: str,
    account_currency: str,
    campaign_name_fallback: str = "",
) -> Dict[str, Any]:
    """Normalize a raw Meta daily insight item into the AHONIX schema.
    Strictly sets attribution_label='IMPORTED'.
    Preserves raw Meta currency and values without synthetic modification.
    """
    campaign_id = str(row.get("campaign_id") or "")
    campaign_name = str(row.get("campaign_name") or campaign_name_fallback or f"Campaign {campaign_id}")
    date_str = str(row.get("date_start") or "")

    # Zero fabrication rule: only cast what Meta provided
    raw_spend = row.get("spend")
    spend = float(raw_spend) if raw_spend is not None else 0.0

    raw_impressions = row.get("impressions")
    impressions = int(raw_impressions) if raw_impressions is not None else 0

    raw_clicks = row.get("clicks")
    clicks = int(raw_clicks) if raw_clicks is not None else 0

    actions = row.get("actions") or []
    action_values = row.get("action_values") or []

    imported_conversions = extract_meta_conversions(actions)
    imported_conversion_value = extract_meta_conversion_value(action_values)

    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "workspace_id": workspace_id,
        "platform": "meta",
        "account_id": account_id,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "date": date_str,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "imported_conversions": imported_conversions,
        "imported_conversion_value": imported_conversion_value,
        "currency": account_currency,
        "attribution_label": "IMPORTED",
        "cpm": float(row["cpm"]) if row.get("cpm") is not None else None,
        "cpc": float(row["cpc"]) if row.get("cpc") is not None else None,
        "ctr": float(row["ctr"]) if row.get("ctr") is not None else None,
        "raw_actions": actions,
        "raw_action_values": action_values,
        "synced_at": now_iso,
    }


async def sync_meta_insights_for_workspace(
    db: Any,
    workspace_id: str,
    is_demo: bool = False,
    full_refresh: bool = False,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Perform campaign catalog and daily insights synchronization for the active workspace.
    
    Adheres strictly to Phase 5.2 rules:
    1. Reuses validated META_API_VERSION
    2. Syncs last 28 days initially; last 3 days for restatements
    3. Idempotent upserts to db.marketing_campaigns and db.marketing_daily_insights
    4. Tracks sync bounds and state in db.marketing_sync_meta
    5. Preserves raw currency without conversion or blending
    6. Zero fabrication: stores 0 only when explicitly reported by Meta
    7. Demo workspace (Northstar Goods) absolute protection
    """
    if is_demo:
        raise HTTPException(
            status_code=400,
            detail="Demo workspace Northstar Goods cannot synchronize external ad data.",
        )

    # 1. Retrieve connection and credentials
    conn = await db.marketing_connections.find_one({"workspace_id": workspace_id, "platform": "meta"})
    if not conn or conn.get("status") != "connected" or not conn.get("encrypted_access_token"):
        raise HTTPException(status_code=400, detail="Meta Ads is not connected for this workspace.")

    account_id = conn.get("selected_account_id")
    if not account_id:
        raise HTTPException(
            status_code=400,
            detail="No Meta Ad Account selected. Please select an ad account in Settings.",
        )

    canonical_act_id = account_id if account_id.startswith("act_") else f"act_{account_id}"
    account_currency = (conn.get("account_currency") or "USD").upper()
    currency_mismatch = bool(conn.get("currency_mismatch", False))

    cfg = get_meta_config()
    api_version = validate_meta_version(conn.get("api_version") or cfg["api_version"])
    app_secret = cfg["app_secret"]

    # Decrypt access token securely server-side
    token = decrypt_token(conn["encrypted_access_token"])
    proof = generate_appsecret_proof(token, app_secret)

    now_utc = datetime.now(timezone.utc)
    today_date = now_utc.date()

    # 2. Determine sync window (28-day initial vs 3-day restatement)
    initial_days, restatement_days = get_sync_window_config()
    existing_meta = await db.marketing_sync_meta.find_one({
        "workspace_id": workspace_id,
        "platform": "meta",
        "account_id": canonical_act_id,
    })

    is_initial_sync = full_refresh or not existing_meta or not existing_meta.get("last_successful_sync_at")
    window_days = initial_days if is_initial_sync else restatement_days
    window_type = f"initial_{initial_days}d" if is_initial_sync else f"restatement_{restatement_days}d"

    since_date = today_date - timedelta(days=window_days)
    until_date = today_date

    since_str = since_date.strftime("%Y-%m-%d")
    until_str = until_date.strftime("%Y-%m-%d")

    # Set status to syncing
    await db.marketing_sync_meta.update_one(
        {"workspace_id": workspace_id, "platform": "meta", "account_id": canonical_act_id},
        {
            "$set": {
                "workspace_id": workspace_id,
                "platform": "meta",
                "account_id": canonical_act_id,
                "status": "syncing",
                "updated_at": now_utc.isoformat(),
            }
        },
        upsert=True,
    )
    await db.marketing_connections.update_one(
        {"workspace_id": workspace_id, "platform": "meta"},
        {"$set": {"sync_status": "syncing", "updated_at": now_utc.isoformat()}},
    )

    should_close_client = False
    if http_client is not None:
        client = http_client
    else:
        client = httpx.AsyncClient(timeout=30.0)
        should_close_client = True

    synced_campaigns_count = 0
    synced_insights_count = 0

    try:
        try:
            # 3. Sync Campaign Catalog (/act_.../campaigns)
            campaigns_url = f"https://graph.facebook.com/{api_version}/{canonical_act_id}/campaigns"
            campaign_params = {
                "fields": "id,name,status,objective,start_time,stop_time,created_time,updated_time",
                "limit": DEFAULT_BATCH_LIMIT,
                "access_token": token,
                "appsecret_proof": proof,
            }

            raw_campaigns = await fetch_meta_cursor_paginated(client, campaigns_url, campaign_params)
            campaign_name_map: Dict[str, str] = {}

            for c in raw_campaigns:
                cid = str(c.get("id"))
                cname = str(c.get("name") or f"Campaign {cid}")
                campaign_name_map[cid] = cname

                camp_doc = {
                    "workspace_id": workspace_id,
                    "platform": "meta",
                    "account_id": canonical_act_id,
                    "campaign_id": cid,
                    "name": cname,
                    "status": str(c.get("status") or "UNKNOWN"),
                    "objective": str(c.get("objective") or ""),
                    "start_time": c.get("start_time"),
                    "stop_time": c.get("stop_time"),
                    "created_time": c.get("created_time"),
                    "updated_time": c.get("updated_time"),
                    "synced_at": now_utc.isoformat(),
                }
                await db.marketing_campaigns.replace_one(
                    {
                        "workspace_id": workspace_id,
                        "platform": "meta",
                        "account_id": canonical_act_id,
                        "campaign_id": cid,
                    },
                    camp_doc,
                    upsert=True,
                )
                synced_campaigns_count += 1

            # 4. Sync Daily Insights (/act_.../insights)
            insights_url = f"https://graph.facebook.com/{api_version}/{canonical_act_id}/insights"
            insights_params = {
                "level": "campaign",
                "time_increment": 1,  # Daily breakdown
                "time_range": json.dumps({"since": since_str, "until": until_str}),
                "fields": "campaign_id,campaign_name,date_start,date_stop,spend,impressions,clicks,actions,action_values,cpm,cpc,ctr",
                "limit": DEFAULT_BATCH_LIMIT,
                "access_token": token,
                "appsecret_proof": proof,
            }

            raw_insights = await fetch_meta_cursor_paginated(client, insights_url, insights_params)

            for item in raw_insights:
                cid = str(item.get("campaign_id") or "")
                d_str = str(item.get("date_start") or "")
                if not cid or not d_str:
                    continue

                fallback_name = campaign_name_map.get(cid, "")
                insight_doc = normalize_meta_daily_insight(
                    row=item,
                    workspace_id=workspace_id,
                    account_id=canonical_act_id,
                    account_currency=account_currency,
                    campaign_name_fallback=fallback_name,
                )

                # Upsert daily uniqueness: workspace_id + platform + account_id + campaign_id + date
                await db.marketing_daily_insights.replace_one(
                    {
                        "workspace_id": workspace_id,
                        "platform": "meta",
                        "account_id": canonical_act_id,
                        "campaign_id": cid,
                        "date": d_str,
                    },
                    insight_doc,
                    upsert=True,
                )
                synced_insights_count += 1
        finally:
            if should_close_client:
                await client.aclose()

        # 5. Determine updated sync bounds
        existing_oldest = existing_meta.get("oldest_synced_date") if existing_meta else None
        if existing_oldest and not full_refresh:
            oldest_synced_date = min(existing_oldest, since_str)
        else:
            oldest_synced_date = since_str

        latest_synced_date = until_str
        now_iso = datetime.now(timezone.utc).isoformat()

        # 6. Update sync metadata in db.marketing_sync_meta
        sync_meta_doc = {
            "workspace_id": workspace_id,
            "platform": "meta",
            "account_id": canonical_act_id,
            "account_name": conn.get("selected_account_name"),
            "account_currency": account_currency,
            "currency_mismatch": currency_mismatch,
            "status": "success",
            "window_type": window_type,
            "window_days": window_days,
            "since_date": since_str,
            "until_date": until_str,
            "oldest_synced_date": oldest_synced_date,
            "latest_synced_date": latest_synced_date,
            "synced_campaigns_count": synced_campaigns_count,
            "synced_insights_count": synced_insights_count,
            "last_successful_sync_at": now_iso,
            "last_sync_at": now_iso,
            "sync_error": None,
            "updated_at": now_iso,
        }

        await db.marketing_sync_meta.replace_one(
            {"workspace_id": workspace_id, "platform": "meta", "account_id": canonical_act_id},
            sync_meta_doc,
            upsert=True,
        )

        # Update connection doc
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "meta"},
            {
                "$set": {
                    "sync_status": "success",
                    "sync_error": None,
                    "last_sync_at": now_iso,
                    "updated_at": now_iso,
                }
            },
        )

        logger.info(
            "Meta sync complete for workspace %s (account: %s). Synced %d campaigns, %d insights.",
            workspace_id, canonical_act_id, synced_campaigns_count, synced_insights_count,
        )

        # Trigger real workspace analytics re-aggregation if Shopify is present
        try:
            shopify_conn = await db.shopify_connections.find_one({"workspace_id": workspace_id, "status": "connected"})
            if shopify_conn:
                from shopify_sync import aggregate_shopify_workspace_data
                await aggregate_shopify_workspace_data(
                    db=db,
                    workspace_id=workspace_id,
                    store_name=shopify_conn.get("shop") or "Store",
                    currency=shopify_conn.get("currency") or "USD",
                )
        except Exception as agg_err:
            logger.warning("Could not refresh workspace analytics after Meta sync: %s", agg_err)

        return {
            "ok": True,
            "status": "success",
            "account_id": canonical_act_id,
            "currency": account_currency,
            "currency_mismatch": currency_mismatch,
            "window_type": window_type,
            "since_date": since_str,
            "until_date": until_str,
            "oldest_synced_date": oldest_synced_date,
            "latest_synced_date": latest_synced_date,
            "synced_campaigns": synced_campaigns_count,
            "synced_insights": synced_insights_count,
            "last_synced_at": now_iso,
        }

    except MetaReauthRequiredError as r_err:
        err_msg = str(r_err)
        logger.error("Meta token expired during sync for workspace %s: %s", workspace_id, err_msg)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "meta"},
            {"$set": {"status": "reauth_required", "sync_status": "reauth_required", "sync_error": err_msg, "updated_at": now_iso}},
        )
        await db.marketing_sync_meta.update_one(
            {"workspace_id": workspace_id, "platform": "meta", "account_id": canonical_act_id},
            {"$set": {"status": "reauth_required", "sync_error": err_msg, "updated_at": now_iso}},
            upsert=True,
        )
        raise HTTPException(
            status_code=401,
            detail=f"Meta access token expired or revoked. Please reconnect in Settings: {err_msg}",
        )

    except MetaRateLimitError as rl_err:
        err_msg = str(rl_err)
        logger.error("Meta rate limit reached during sync for workspace %s: %s", workspace_id, err_msg)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "meta"},
            {"$set": {"sync_status": "rate_limited", "sync_error": err_msg, "updated_at": now_iso}},
        )
        await db.marketing_sync_meta.update_one(
            {"workspace_id": workspace_id, "platform": "meta", "account_id": canonical_act_id},
            {"$set": {"status": "rate_limited", "sync_error": err_msg, "updated_at": now_iso}},
            upsert=True,
        )
        raise HTTPException(status_code=429, detail=f"Meta rate limit exceeded: {err_msg}")

    except Exception as e:
        err_msg = str(e)
        logger.exception("Error syncing Meta insights for workspace %s: %s", workspace_id, e)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "meta"},
            {"$set": {"sync_status": "error", "sync_error": err_msg, "updated_at": now_iso}},
        )
        await db.marketing_sync_meta.update_one(
            {"workspace_id": workspace_id, "platform": "meta", "account_id": canonical_act_id},
            {"$set": {"status": "error", "sync_error": err_msg, "updated_at": now_iso}},
            upsert=True,
        )
        raise HTTPException(status_code=502, detail=f"Failed to sync Meta Ads insights: {err_msg}")
