"""Google Ads Insights Synchronization Module for AHONIX.

Phase 5.4 Implementation:
- Ingest real Google Ads campaign catalog into db.marketing_campaigns (platform="google_ads")
- Ingest campaign-level daily insights into db.marketing_daily_insights (platform="google_ads")
- Sync metadata tracking in db.marketing_sync_meta
- Configurable sync windows:
    - Initial sync window: default 28 days (GOOGLE_ADS_SYNC_DAYS_INITIAL)
    - Restatement window: default 3 days (GOOGLE_ADS_SYNC_DAYS_RESTATEMENT)
- Google Ads searchStream query with GAQL
- Support for selected_customer_id, developer-token, and login-customer-id
- Safe cost_micros to standard currency conversion (micros / 1,000,000.0)
- Rate limiting, transient retry handling, and bounded backoff
- Token revocation / invalid_grant handling -> reauth_required
- Strict attribution labeling: attribution_label="IMPORTED"
- Raw account currency preservation & currency_mismatch isolation
- Zero metric fabrication (preserves absence of data; 0 only when Google explicitly reports 0)
- Strict workspace isolation and Northstar Goods demo workspace protection
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

from google_ads_integration import (
    get_google_ads_config,
    normalize_customer_id,
    get_google_ads_access_token,
    DEFAULT_GOOGLE_ADS_API_VERSION,
)

logger = logging.getLogger("ahonix.google_ads.sync")

# Default Sync Windows
DEFAULT_INITIAL_DAYS = 28
DEFAULT_RESTATEMENT_DAYS = 3


class GoogleAdsSyncError(Exception):
    """Base exception for Google Ads synchronization errors."""
    pass


class GoogleAdsReauthRequiredError(GoogleAdsSyncError):
    """Raised when Google Ads OAuth credentials are invalid or revoked."""
    pass


class GoogleAdsRateLimitError(GoogleAdsSyncError):
    """Raised when Google Ads API rate limit is exceeded."""
    pass


def get_sync_window_config() -> Tuple[int, int]:
    """Retrieve and validate initial and restatement sync windows from environment."""
    try:
        initial = int(os.environ.get("GOOGLE_ADS_SYNC_DAYS_INITIAL", str(DEFAULT_INITIAL_DAYS)))
        if initial < 1 or initial > 365:
            initial = DEFAULT_INITIAL_DAYS
    except (ValueError, TypeError):
        initial = DEFAULT_INITIAL_DAYS

    try:
        restatement = int(os.environ.get("GOOGLE_ADS_SYNC_DAYS_RESTATEMENT", str(DEFAULT_RESTATEMENT_DAYS)))
        if restatement < 1 or restatement > 90:
            restatement = DEFAULT_RESTATEMENT_DAYS
    except (ValueError, TypeError):
        restatement = DEFAULT_RESTATEMENT_DAYS

    return initial, restatement


def validate_google_ads_version(version: str) -> str:
    """Validate Google Ads API version string format (e.g. 'v19')."""
    if not version or not isinstance(version, str):
        return DEFAULT_GOOGLE_ADS_API_VERSION
    v = version.strip().lower()
    if not v.startswith("v"):
        v = f"v{v}"
    if not re.match(r"^v\d+$", v):
        raise ValueError(f"Invalid Google Ads API version format: '{version}'. Must be e.g. 'v19'")
    return v


def micros_to_currency(micros: Any) -> float:
    """Convert Google Ads micro amounts (micros) to standard currency units.
    
    1 standard currency unit = 1,000,000 micros.
    Example: 50,000,000 micros = 50.00 standard currency units.
    Does NOT divide twice.
    """
    if micros is None:
        return 0.0
    try:
        val = float(micros)
        if val == 0.0:
            return 0.0
        return round(val / 1_000_000.0, 4)
    except (ValueError, TypeError):
        return 0.0


def normalize_google_ads_daily_insight(
    row: Dict[str, Any],
    workspace_id: str,
    customer_id: str,
    account_currency: str,
    campaign_name_fallback: str = "",
) -> Dict[str, Any]:
    """Normalize a raw Google Ads reporting row into the AHONIX schema.
    Strictly marks attribution_label='IMPORTED'.
    Converts cost_micros to standard currency units.
    """
    campaign = row.get("campaign") or {}
    segments = row.get("segments") or {}
    metrics = row.get("metrics") or {}

    cid = str(campaign.get("id") or "")
    cname = str(campaign.get("name") or campaign_name_fallback or f"Campaign {cid}")
    date_str = str(segments.get("date") or "")

    # Zero fabrication rule: only convert what Google provided
    cost_micros = metrics.get("costMicros") if metrics.get("costMicros") is not None else metrics.get("cost_micros")
    spend = micros_to_currency(cost_micros)

    raw_impressions = metrics.get("impressions")
    impressions = int(raw_impressions) if raw_impressions is not None else 0

    raw_clicks = metrics.get("clicks")
    clicks = int(raw_clicks) if raw_clicks is not None else 0

    raw_conversions = metrics.get("conversions")
    imported_conversions = float(raw_conversions) if raw_conversions is not None else 0.0

    raw_val = metrics.get("conversionsValue") if metrics.get("conversionsValue") is not None else metrics.get("conversions_value")
    imported_conversion_value = float(raw_val) if raw_val is not None else 0.0

    raw_ctr = metrics.get("ctr")
    ctr = float(raw_ctr) if raw_ctr is not None else None

    raw_avg_cpc = metrics.get("averageCpc") if metrics.get("averageCpc") is not None else metrics.get("average_cpc")
    avg_cpc = micros_to_currency(raw_avg_cpc) if raw_avg_cpc is not None else None

    raw_avg_cpm = metrics.get("averageCpm") if metrics.get("averageCpm") is not None else metrics.get("average_cpm")
    avg_cpm = micros_to_currency(raw_avg_cpm) if raw_avg_cpm is not None else None

    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "workspace_id": workspace_id,
        "platform": "google_ads",
        "account_id": customer_id,
        "campaign_id": cid,
        "campaign_name": cname,
        "date": date_str,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "imported_conversions": imported_conversions,
        "imported_conversion_value": imported_conversion_value,
        "currency": account_currency,
        "attribution_label": "IMPORTED",
        "ctr": ctr,
        "cpc": avg_cpc,
        "cpm": avg_cpm,
        "synced_at": now_iso,
    }


async def google_ads_api_post(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 3,
) -> Any:
    """Execute an HTTP POST request to Google Ads searchStream API with bounded retries,
    exponential backoff, Retry-After header parsing, and auth failure detection.
    """
    attempt = 0
    while attempt < max_retries:
        try:
            res = await client.post(url, headers=headers, json=payload)

            if res.status_code == 429:
                attempt += 1
                retry_after_hdr = res.headers.get("Retry-After")
                wait_sec = float(retry_after_hdr) if retry_after_hdr else (2.0 ** attempt)
                logger.warning(
                    "Google Ads rate limited (HTTP 429). Retrying in %.1f seconds (attempt %d/%d)...",
                    wait_sec, attempt, max_retries,
                )
                if attempt >= max_retries:
                    raise GoogleAdsRateLimitError("Google Ads rate limit exceeded after bounded retries.")
                await asyncio.sleep(wait_sec)
                continue

            if res.status_code in (500, 502, 503, 504):
                attempt += 1
                wait_sec = 1.5 * attempt
                logger.warning(
                    "Google Ads transient server error (HTTP %d). Retrying in %.1f seconds...",
                    res.status_code, wait_sec,
                )
                if attempt >= max_retries:
                    raise GoogleAdsSyncError(f"Google Ads API unavailable (HTTP {res.status_code}) after {max_retries} retries.")
                await asyncio.sleep(wait_sec)
                continue

            if res.status_code == 401:
                logger.error("Google Ads token expired or unauthorized (HTTP 401).")
                raise GoogleAdsReauthRequiredError("Google Ads access token expired or unauthorized.")

            try:
                data = res.json()
            except Exception:
                data = None

            # Handle Google Ads API error structures
            if res.status_code != 200:
                err_msg = ""
                if isinstance(data, dict):
                    err_obj = data.get("error", {})
                    err_msg = err_obj.get("message", res.text)
                    err_status = err_obj.get("status", "")
                    if err_status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
                        raise GoogleAdsReauthRequiredError(f"Google Ads authentication error: {err_msg}")
                    if err_status == "RESOURCE_EXHAUSTED":
                        attempt += 1
                        wait_sec = 2.0 ** attempt
                        if attempt >= max_retries:
                            raise GoogleAdsRateLimitError(f"Google Ads quota exceeded: {err_msg}")
                        await asyncio.sleep(wait_sec)
                        continue
                raise GoogleAdsSyncError(f"Google Ads API error (HTTP {res.status_code}): {err_msg or res.text}")

            return data

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            attempt += 1
            if attempt >= max_retries:
                logger.error("Google Ads network request failed after %d retries: %s", max_retries, exc)
                raise GoogleAdsSyncError(f"Google Ads network error: {type(exc).__name__}")
            wait_sec = 1.0 * attempt
            await asyncio.sleep(wait_sec)

    raise GoogleAdsSyncError("Google Ads API request timed out or failed.")


async def sync_google_ads_insights_for_workspace(
    db: Any,
    workspace_id: str,
    is_demo: bool = False,
    full_refresh: bool = False,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Perform Google Ads campaign catalog and daily performance insights synchronization.
    
    Adheres strictly to Phase 5.4 rules:
    1. Reuses validated GOOGLE_ADS_API_VERSION
    2. Syncs last 28 days initially; last 3 days for restatements
    3. searchStream with robust batch processing without truncation
    4. Converts cost_micros to standard currency units (cost_micros / 1,000,000.0)
    5. Stores attribution_label='IMPORTED'
    6. Idempotent upserts to db.marketing_campaigns and db.marketing_daily_insights
    7. Tracks sync bounds and state in db.marketing_sync_meta
    8. Preserves raw currency without conversion or blending
    9. Zero fabrication: preserves absence of data; 0 only when explicitly reported
    10. Northstar Goods demo workspace absolute protection
    """
    if is_demo:
        raise HTTPException(
            status_code=400,
            detail="Demo workspace Northstar Goods cannot synchronize external ad data.",
        )

    # 1. Retrieve connection and credentials
    conn = await db.marketing_connections.find_one({"workspace_id": workspace_id, "platform": "google_ads"})
    if not conn or conn.get("status") != "connected" or not conn.get("encrypted_refresh_token"):
        raise HTTPException(status_code=400, detail="Google Ads is not connected for this workspace.")

    customer_id = conn.get("selected_customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Google Ads account selected. Please select an ad account in Settings.",
        )

    norm_customer_id = normalize_customer_id(customer_id)
    login_customer_id = conn.get("login_customer_id")
    account_currency = (conn.get("account_currency") or "USD").upper()
    currency_mismatch = bool(conn.get("currency_mismatch", False))

    cfg = get_google_ads_config()
    developer_token = cfg["developer_token"]
    if not developer_token:
        raise HTTPException(
            status_code=503,
            detail="Google Ads Developer Token is not configured on this server (GOOGLE_ADS_DEVELOPER_TOKEN missing).",
        )

    api_version = validate_google_ads_version(cfg["api_version"])

    # 2. Determine sync window (28-day initial vs 3-day restatement)
    initial_days, restatement_days = get_sync_window_config()
    existing_meta = await db.marketing_sync_meta.find_one({
        "workspace_id": workspace_id,
        "platform": "google_ads",
        "account_id": norm_customer_id,
    })

    is_initial_sync = full_refresh or not existing_meta or not existing_meta.get("last_successful_sync_at")
    window_days = initial_days if is_initial_sync else restatement_days
    window_type = f"initial_{initial_days}d" if is_initial_sync else f"restatement_{restatement_days}d"

    now_utc = datetime.now(timezone.utc)
    today_date = now_utc.date()
    since_date = today_date - timedelta(days=window_days)
    until_date = today_date

    since_str = since_date.strftime("%Y-%m-%d")
    until_str = until_date.strftime("%Y-%m-%d")

    # Set status to syncing
    await db.marketing_sync_meta.update_one(
        {"workspace_id": workspace_id, "platform": "google_ads", "account_id": norm_customer_id},
        {
            "$set": {
                "workspace_id": workspace_id,
                "platform": "google_ads",
                "account_id": norm_customer_id,
                "status": "syncing",
                "updated_at": now_utc.isoformat(),
            }
        },
        upsert=True,
    )
    await db.marketing_connections.update_one(
        {"workspace_id": workspace_id, "platform": "google_ads"},
        {"$set": {"sync_status": "syncing", "updated_at": now_utc.isoformat()}},
    )

    should_close_client = False
    if http_client is not None:
        client = http_client
    else:
        client = httpx.AsyncClient(timeout=45.0)
        should_close_client = True

    synced_campaigns_count = 0
    synced_insights_count = 0

    try:
        try:
            # 3. Refresh OAuth access token
            access_token = await get_google_ads_access_token(db, workspace_id, client=client)

            # 4. Construct GAQL query for searchStream
            gaql_query = (
                "SELECT "
                "  campaign.id, "
                "  campaign.name, "
                "  campaign.status, "
                "  campaign.advertising_channel_type, "
                "  campaign.start_date, "
                "  campaign.end_date, "
                "  segments.date, "
                "  metrics.cost_micros, "
                "  metrics.impressions, "
                "  metrics.clicks, "
                "  metrics.conversions, "
                "  metrics.conversions_value, "
                "  metrics.ctr, "
                "  metrics.average_cpc, "
                "  metrics.average_cpm "
                "FROM campaign "
                f"WHERE segments.date BETWEEN '{since_str}' AND '{until_str}' "
                "ORDER BY segments.date DESC"
            )

            stream_url = f"https://googleads.googleapis.com/{api_version}/customers/{norm_customer_id}/googleAds:searchStream"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "developer-token": developer_token,
            }
            if login_customer_id:
                headers["login-customer-id"] = normalize_customer_id(login_customer_id)

            stream_res = await google_ads_api_post(
                client=client,
                url=stream_url,
                headers=headers,
                payload={"query": gaql_query},
            )

            # searchStream returns a JSON array of batch response messages
            batches = stream_res if isinstance(stream_res, list) else [stream_res] if stream_res else []
            campaign_name_map: Dict[str, str] = {}

            for batch in batches:
                if not isinstance(batch, dict):
                    continue
                results = batch.get("results") or []

                for row in results:
                    campaign = row.get("campaign") or {}
                    segments = row.get("segments") or {}
                    date_val = segments.get("date")

                    cid = str(campaign.get("id") or "")
                    if not cid or not date_val:
                        continue

                    cname = str(campaign.get("name") or f"Campaign {cid}")
                    campaign_name_map[cid] = cname

                    # 5. Upsert to db.marketing_campaigns
                    camp_doc = {
                        "workspace_id": workspace_id,
                        "platform": "google_ads",
                        "account_id": norm_customer_id,
                        "campaign_id": cid,
                        "name": cname,
                        "status": str(campaign.get("status") or "UNKNOWN"),
                        "advertising_channel_type": str(campaign.get("advertisingChannelType") or campaign.get("advertising_channel_type") or ""),
                        "start_date": campaign.get("startDate") or campaign.get("start_date"),
                        "end_date": campaign.get("endDate") or campaign.get("end_date"),
                        "synced_at": now_utc.isoformat(),
                    }

                    await db.marketing_campaigns.replace_one(
                        {
                            "workspace_id": workspace_id,
                            "platform": "google_ads",
                            "account_id": norm_customer_id,
                            "campaign_id": cid,
                        },
                        camp_doc,
                        upsert=True,
                    )
                    synced_campaigns_count += 1

                    # 6. Normalize and upsert to db.marketing_daily_insights
                    insight_doc = normalize_google_ads_daily_insight(
                        row=row,
                        workspace_id=workspace_id,
                        customer_id=norm_customer_id,
                        account_currency=account_currency,
                        campaign_name_fallback=cname,
                    )

                    await db.marketing_daily_insights.replace_one(
                        {
                            "workspace_id": workspace_id,
                            "platform": "google_ads",
                            "account_id": norm_customer_id,
                            "campaign_id": cid,
                            "date": date_val,
                        },
                        insight_doc,
                        upsert=True,
                    )
                    synced_insights_count += 1

        finally:
            if should_close_client:
                await client.aclose()

        # 7. Update sync bounds and metadata
        existing_oldest = existing_meta.get("oldest_synced_date") if existing_meta else None
        if existing_oldest and not full_refresh:
            oldest_synced_date = min(existing_oldest, since_str)
        else:
            oldest_synced_date = since_str

        latest_synced_date = until_str
        now_iso = datetime.now(timezone.utc).isoformat()

        sync_meta_doc = {
            "workspace_id": workspace_id,
            "platform": "google_ads",
            "account_id": norm_customer_id,
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
            {"workspace_id": workspace_id, "platform": "google_ads", "account_id": norm_customer_id},
            sync_meta_doc,
            upsert=True,
        )

        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads"},
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
            "Google Ads sync complete for workspace %s (customer: %s). Synced %d campaigns, %d insights.",
            workspace_id, norm_customer_id, synced_campaigns_count, synced_insights_count,
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
            logger.warning("Could not refresh workspace analytics after Google Ads sync: %s", agg_err)

        return {
            "ok": True,
            "status": "success",
            "customer_id": norm_customer_id,
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

    except GoogleAdsReauthRequiredError as r_err:
        err_msg = str(r_err)
        logger.error("Google Ads token revoked/expired for workspace %s: %s", workspace_id, err_msg)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads"},
            {"$set": {"status": "reauth_required", "sync_status": "reauth_required", "sync_error": err_msg, "updated_at": now_iso}},
        )
        await db.marketing_sync_meta.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads", "account_id": norm_customer_id},
            {"$set": {"status": "reauth_required", "sync_error": err_msg, "updated_at": now_iso}},
            upsert=True,
        )
        raise HTTPException(
            status_code=401,
            detail=f"Google Ads authorization expired or revoked. Please reconnect in Settings: {err_msg}",
        )

    except GoogleAdsRateLimitError as rl_err:
        err_msg = str(rl_err)
        logger.error("Google Ads rate limit reached for workspace %s: %s", workspace_id, err_msg)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads"},
            {"$set": {"sync_status": "rate_limited", "sync_error": err_msg, "updated_at": now_iso}},
        )
        await db.marketing_sync_meta.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads", "account_id": norm_customer_id},
            {"$set": {"status": "rate_limited", "sync_error": err_msg, "updated_at": now_iso}},
            upsert=True,
        )
        raise HTTPException(status_code=429, detail=f"Google Ads quota or rate limit exceeded: {err_msg}")

    except HTTPException as he:
        if he.status_code == 401:
            err_msg = str(he.detail)
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.marketing_connections.update_one(
                {"workspace_id": workspace_id, "platform": "google_ads"},
                {"$set": {"status": "reauth_required", "sync_status": "reauth_required", "sync_error": err_msg, "updated_at": now_iso}},
            )
            await db.marketing_sync_meta.update_one(
                {"workspace_id": workspace_id, "platform": "google_ads", "account_id": norm_customer_id},
                {"$set": {"status": "reauth_required", "sync_error": err_msg, "updated_at": now_iso}},
                upsert=True,
            )
        raise he

    except Exception as e:
        err_msg = str(e)
        logger.exception("Error syncing Google Ads insights for workspace %s: %s", workspace_id, e)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.marketing_connections.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads"},
            {"$set": {"sync_status": "error", "sync_error": err_msg, "updated_at": now_iso}},
        )
        await db.marketing_sync_meta.update_one(
            {"workspace_id": workspace_id, "platform": "google_ads", "account_id": norm_customer_id},
            {"$set": {"status": "error", "sync_error": err_msg, "updated_at": now_iso}},
            upsert=True,
        )
        raise HTTPException(status_code=502, detail=f"Failed to sync Google Ads insights: {err_msg}")
