"""Meta Ads Integration Module for AHONIX.

Phase 5.1 Implementation:
- Meta OAuth 2.0 flow with CSRF state validation & TTL cleanup
- Configurable Meta Graph API version (default: v21.0, configurable via META_API_VERSION)
- Version cleaning and normalization
- App Secret Proof calculation (HMAC-SHA256) for secure Graph API calls
- 60-day long-lived access token exchange
- AES-256-GCM token encryption at rest using shared AHONIX cipher
- Zero secret exposure: access tokens and client secrets are never returned in responses or logs
- Ad accounts discovery (/me/adaccounts) with appsecret_proof
- Account selection with currency mismatch detection (preventing incompatible currency blending)
- Safe disconnect & reauth_required error handling
- Strict workspace isolation and Northstar Goods demo workspace protection
"""
import os
import hmac
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from auth import get_current_user
from shopify_integration import encrypt_token, decrypt_token

logger = logging.getLogger("ahonix.meta")

# Default Meta Graph API version
DEFAULT_META_API_VERSION = "v21.0"
DEFAULT_META_SCOPES = "ads_read,read_insights"

router = APIRouter(prefix="/api/integrations/meta", tags=["meta"])

# Injected dependencies
_db = None
_get_active_workspace_fn = None


def init_meta(db, get_active_workspace_fn):
    """Initialize Meta Ads module with MongoDB database and workspace resolver."""
    global _db, _get_active_workspace_fn
    _db = db
    _get_active_workspace_fn = get_active_workspace_fn


def clean_meta_api_version(ver: Optional[str]) -> str:
    """Normalize and validate a Meta Graph API version string.
    Ensures format like 'v21.0' or 'v20.0'.
    """
    if not ver or not isinstance(ver, str) or not ver.strip():
        return DEFAULT_META_API_VERSION
    v = ver.strip().lower()
    if not v.startswith("v"):
        v = f"v{v}"
    return v


def get_meta_config() -> Dict[str, str]:
    """Load Meta integration configuration from environment variables."""
    app_url = os.environ.get("APP_URL", "http://localhost:3000").rstrip("/")
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    api_version = clean_meta_api_version(os.environ.get("META_API_VERSION", DEFAULT_META_API_VERSION))

    return {
        "app_id": os.environ.get("META_APP_ID", "").strip(),
        "app_secret": os.environ.get("META_APP_SECRET", "").strip(),
        "api_version": api_version,
        "scopes": os.environ.get("META_SCOPES", DEFAULT_META_SCOPES).strip(),
        "redirect_uri": os.environ.get("META_REDIRECT_URI", f"{app_url}/api/integrations/meta/callback").strip(),
        "frontend_url": frontend_url,
    }


def generate_appsecret_proof(access_token: str, app_secret: str) -> str:
    """Compute HMAC-SHA256 appsecret_proof for Meta Graph API security.
    https://developers.facebook.com/docs/graph-api/security#appsecret_proof
    """
    if not access_token or not app_secret:
        return ""
    return hmac.new(
        app_secret.encode("utf-8"),
        access_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# --- Pydantic Schemas --------------------------------------------------------
class SelectMetaAccountBody(BaseModel):
    account_id: str = Field(..., min_length=3, max_length=100)
    account_name: Optional[str] = Field(None, max_length=200)


# --- Endpoints ---------------------------------------------------------------
@router.post("/connect")
async def connect_meta(user: dict = Depends(get_current_user)):
    """Initiate Meta OAuth 2.0 authorization flow.
    Generates CSRF state, stores nonce with 900s TTL, and returns authorization URL.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace Northstar Goods cannot connect external ad channels.")

    cfg = get_meta_config()
    if not cfg["app_id"] or not cfg["app_secret"]:
        raise HTTPException(
            status_code=503,
            detail="Meta Ads integration is not configured on this server (META_APP_ID / META_APP_SECRET missing).",
        )

    # Generate cryptographically secure state nonce
    state = secrets.token_urlsafe(32)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=900)

    await _db.meta_oauth_states.replace_one(
        {"state": state},
        {
            "state": state,
            "workspace_id": ws["workspace_id"],
            "user_id": user["user_id"],
            "created_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat(),
        },
        upsert=True,
    )

    auth_url = (
        f"https://www.facebook.com/{cfg['api_version']}/dialog/oauth"
        f"?client_id={cfg['app_id']}"
        f"&redirect_uri={cfg['redirect_uri']}"
        f"&state={state}"
        f"&scope={cfg['scopes']}"
        f"&response_type=code"
    )

    return {
        "ok": True,
        "auth_url": auth_url,
        "state": state,
        "api_version": cfg["api_version"],
    }


@router.get("/callback")
async def meta_callback(request: Request):
    """Handle Meta OAuth 2.0 redirect callback.
    Exchanges code for short-lived token, then exchanges for 60-day long-lived token.
    Encrypts token and saves connection to db.marketing_connections.
    """
    if not _db:
        return RedirectResponse(url="/app/settings?meta_error=server_not_initialized")

    cfg = get_meta_config()
    frontend_url = cfg["frontend_url"]

    params = dict(request.query_params)
    error = params.get("error") or params.get("error_reason")
    if error:
        error_desc = params.get("error_description") or error
        logger.warning("Meta OAuth rejected by user or platform: %s", error_desc)
        return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error={error}")

    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error=missing_code_or_state")

    # Validate state nonce
    saved_state = await _db.meta_oauth_states.find_one({"state": state})
    if not saved_state:
        logger.warning("Meta callback state mismatch or unknown nonce: %s", state)
        return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error=invalid_state")

    # Check expiration
    expires_str = saved_state.get("expires_at")
    if expires_str:
        try:
            exp_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                await _db.meta_oauth_states.delete_one({"state": state})
                return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error=expired_state")
        except Exception:
            pass

    # Consume state nonce (single-use)
    await _db.meta_oauth_states.delete_one({"state": state})
    workspace_id = saved_state["workspace_id"]
    user_id = saved_state["user_id"]

    # Exchange authorization code for short-lived user access token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_url = f"https://graph.facebook.com/{cfg['api_version']}/oauth/access_token"
            token_res = await client.get(
                token_url,
                params={
                    "client_id": cfg["app_id"],
                    "client_secret": cfg["app_secret"],
                    "redirect_uri": cfg["redirect_uri"],
                    "code": code,
                },
            )

            if token_res.status_code != 200:
                logger.error("Meta token exchange failed (HTTP %s): %s", token_res.status_code, token_res.text)
                return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error=token_exchange_failed")

            token_data = token_res.json()
            short_lived_token = token_data.get("access_token")
            if not short_lived_token:
                return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error=no_token_returned")

            # Exchange for long-lived access token (~60 days)
            long_lived_res = await client.get(
                token_url,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": cfg["app_id"],
                    "client_secret": cfg["app_secret"],
                    "fb_exchange_token": short_lived_token,
                },
            )

            if long_lived_res.status_code == 200:
                long_lived_data = long_lived_res.json()
                final_token = long_lived_data.get("access_token", short_lived_token)
                expires_in = int(long_lived_data.get("expires_in", 5184000))  # Default 60 days
            else:
                logger.warning("Long-lived token exchange fell back to short-lived token: %s", long_lived_res.text)
                final_token = short_lived_token
                expires_in = int(token_data.get("expires_in", 7200))

    except Exception as e:
        logger.exception("Error contacting Meta token API: %s", e)
        return RedirectResponse(url=f"{frontend_url}/app/settings?meta_error=network_error")

    # Encrypt access token before storing
    encrypted_token = encrypt_token(final_token)
    now_utc = datetime.now(timezone.utc)
    token_expires_at = (now_utc + timedelta(seconds=expires_in)).isoformat()

    conn_doc = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "platform": "meta",
        "status": "connected",
        "api_version": cfg["api_version"],
        "encrypted_access_token": encrypted_token,
        "token_expires_at": token_expires_at,
        "selected_account_id": None,
        "selected_account_name": None,
        "account_currency": None,
        "account_timezone": None,
        "currency_mismatch": False,
        "sync_status": "idle",
        "sync_error": None,
        "last_sync_at": None,
        "connected_at": now_utc.isoformat(),
        "updated_at": now_utc.isoformat(),
    }

    # Upsert connection record (strict workspace isolation)
    await _db.marketing_connections.replace_one(
        {"workspace_id": workspace_id, "platform": "meta"},
        conn_doc,
        upsert=True,
    )

    logger.info("Successfully connected Meta Ads for workspace %s (API: %s)", workspace_id, cfg["api_version"])
    return RedirectResponse(url=f"{frontend_url}/app/settings?meta=connected")


@router.get("/status")
async def get_meta_status(user: dict = Depends(get_current_user)):
    """Return Meta connection status for the active workspace.
    Guarantees secrets and access tokens are NEVER exposed.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]
    cfg = get_meta_config()

    if ws.get("is_demo"):
        return {
            "platform": "meta",
            "connected": False,
            "status": "disconnected",
            "is_demo": True,
            "api_version": cfg["api_version"],
            "selected_account_id": None,
            "selected_account_name": None,
            "account_currency": None,
            "currency_mismatch": False,
            "sync_status": "idle",
            "sync_error": None,
            "last_sync_at": None,
        }

    conn = await _db.marketing_connections.find_one(
        {"workspace_id": ws_id, "platform": "meta"},
        {"_id": 0, "encrypted_access_token": 0, "encrypted_refresh_token": 0},
    )

    if not conn or conn.get("status") != "connected":
        return {
            "platform": "meta",
            "connected": False,
            "status": conn.get("status", "disconnected") if conn else "disconnected",
            "is_demo": False,
            "api_version": conn.get("api_version", cfg["api_version"]) if conn else cfg["api_version"],
            "selected_account_id": None,
            "selected_account_name": None,
            "account_currency": None,
            "currency_mismatch": False,
            "sync_status": "idle",
            "sync_error": None,
            "last_sync_at": None,
        }

    return {
        "platform": "meta",
        "connected": True,
        "status": conn.get("status", "connected"),
        "is_demo": False,
        "api_version": conn.get("api_version", cfg["api_version"]),
        "selected_account_id": conn.get("selected_account_id"),
        "selected_account_name": conn.get("selected_account_name"),
        "account_currency": conn.get("account_currency"),
        "currency_mismatch": conn.get("currency_mismatch", False),
        "sync_status": conn.get("sync_status", "idle"),
        "sync_error": conn.get("sync_error"),
        "last_sync_at": conn.get("last_sync_at"),
    }


@router.get("/accounts")
async def list_meta_ad_accounts(user: dict = Depends(get_current_user)):
    """Fetch accessible Meta ad accounts for the connected merchant.
    Requires appsecret_proof for secure API access.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace cannot access external Meta ad accounts.")

    ws_id = ws["workspace_id"]
    conn = await _db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
    if not conn or conn.get("status") != "connected" or not conn.get("encrypted_access_token"):
        raise HTTPException(status_code=400, detail="Meta Ads is not connected for this workspace.")

    cfg = get_meta_config()
    token = decrypt_token(conn["encrypted_access_token"])
    proof = generate_appsecret_proof(token, cfg["app_secret"])
    api_ver = conn.get("api_version", cfg["api_version"])

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"https://graph.facebook.com/{api_ver}/me/adaccounts"
            res = await client.get(
                url,
                params={
                    "fields": "id,name,account_id,account_status,currency,timezone_name",
                    "access_token": token,
                    "appsecret_proof": proof,
                    "limit": 50,
                },
            )

            if res.status_code == 401 or res.status_code == 400:
                err_body = res.json().get("error", {})
                # Check for OAuth token expiration or invalid session
                if err_body.get("type") in ("OAuthException", "OAuthAccessTokenException") or err_body.get("code") in (190, 102):
                    logger.warning("Meta access token revoked or expired: %s", err_body.get("message"))
                    await _db.marketing_connections.update_one(
                        {"workspace_id": ws_id, "platform": "meta"},
                        {"$set": {"status": "reauth_required", "sync_error": "Token expired or revoked"}},
                    )
                    raise HTTPException(
                        status_code=401,
                        detail="Meta access token expired or revoked. Please reconnect your Meta account in Settings.",
                    )
                raise HTTPException(status_code=502, detail=f"Meta API error: {err_body.get('message', 'Unknown error')}")

            if res.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Failed to fetch Meta ad accounts (HTTP {res.status_code})")

            data = res.json()
            raw_accounts = data.get("data") or []

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error querying Meta Graph API: %s", e)
        raise HTTPException(status_code=502, detail=f"Error connecting to Meta Graph API: {str(e)}")

    store_currency = (ws.get("currency") or "USD").upper()
    accounts = []
    for a in raw_accounts:
        acc_currency = (a.get("currency") or "USD").upper()
        accounts.append({
            "id": a.get("id"),  # e.g., "act_1029384"
            "account_id": a.get("account_id"),  # e.g., "1029384"
            "name": a.get("name") or f"Ad Account {a.get('account_id')}",
            "currency": acc_currency,
            "currency_mismatch": acc_currency != store_currency,
            "timezone": a.get("timezone_name") or "UTC",
            "status": a.get("account_status"),  # 1 = ACTIVE
            "is_selected": conn.get("selected_account_id") == a.get("id") or conn.get("selected_account_id") == a.get("account_id"),
        })

    return {
        "ok": True,
        "store_currency": store_currency,
        "selected_account_id": conn.get("selected_account_id"),
        "accounts": accounts,
    }


@router.post("/select-account")
async def select_meta_ad_account(body: SelectMetaAccountBody, user: dict = Depends(get_current_user)):
    """Bind a specific Meta Ad Account to the active workspace.
    Verifies currency compatibility against the store currency.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace cannot modify external ad integrations.")

    ws_id = ws["workspace_id"]
    conn = await _db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "meta"})
    if not conn or conn.get("status") != "connected" or not conn.get("encrypted_access_token"):
        raise HTTPException(status_code=400, detail="Meta Ads is not connected for this workspace.")

    cfg = get_meta_config()
    token = decrypt_token(conn["encrypted_access_token"])
    proof = generate_appsecret_proof(token, cfg["app_secret"])
    api_ver = conn.get("api_version", cfg["api_version"])

    raw_act_id = body.account_id.strip()
    canonical_act_id = raw_act_id if raw_act_id.startswith("act_") else f"act_{raw_act_id}"

    # Verify account exists on Meta Graph API and retrieve currency
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"https://graph.facebook.com/{api_ver}/{canonical_act_id}"
            res = await client.get(
                url,
                params={
                    "fields": "id,name,account_id,currency,timezone_name,account_status",
                    "access_token": token,
                    "appsecret_proof": proof,
                },
            )
            if res.status_code != 200:
                raise HTTPException(
                    status_code=404,
                    detail=f"Ad Account '{body.account_id}' not found or not accessible with current permissions.",
                )
            act_info = res.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error validating Meta ad account: %s", e)
        raise HTTPException(status_code=502, detail=f"Error validating Meta ad account: {str(e)}")

    store_currency = (ws.get("currency") or "USD").upper()
    act_currency = (act_info.get("currency") or "USD").upper()
    currency_mismatch = act_currency != store_currency

    update_fields = {
        "selected_account_id": canonical_act_id,
        "selected_account_name": body.account_name or act_info.get("name") or canonical_act_id,
        "account_currency": act_currency,
        "account_timezone": act_info.get("timezone_name") or "UTC",
        "currency_mismatch": currency_mismatch,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await _db.marketing_connections.update_one(
        {"workspace_id": ws_id, "platform": "meta"},
        {"$set": update_fields},
    )

    logger.info(
        "Selected Meta ad account %s for workspace %s (currency: %s, mismatch: %s)",
        canonical_act_id, ws_id, act_currency, currency_mismatch,
    )

    return {
        "ok": True,
        "selected_account_id": canonical_act_id,
        "selected_account_name": update_fields["selected_account_name"],
        "account_currency": act_currency,
        "store_currency": store_currency,
        "currency_mismatch": currency_mismatch,
        "warning": (
            f"Ad Account currency ({act_currency}) differs from store currency ({store_currency}). "
            "To prevent inaccurate financial calculations, ad spend will not be blended into True Profit until currencies match."
            if currency_mismatch else None
        ),
    }


@router.post("/disconnect")
async def disconnect_meta(user: dict = Depends(get_current_user)):
    """Safely disconnect Meta Ads from the active workspace and remove stored credentials."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]

    await _db.marketing_connections.delete_one({"workspace_id": ws_id, "platform": "meta"})
    logger.info("Disconnected Meta Ads for workspace %s", ws_id)
    return {"ok": True, "disconnected": True}


class SyncMetaBody(BaseModel):
    full_refresh: bool = False


@router.post("/sync")
async def trigger_meta_sync(
    body: Optional[SyncMetaBody] = None,
    user: dict = Depends(get_current_user),
):
    """Trigger campaign catalog and daily insights synchronization for Meta Ads."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(
            status_code=400,
            detail="Demo workspace Northstar Goods cannot synchronize external ad data.",
        )

    from meta_sync import sync_meta_insights_for_workspace

    full_refresh = body.full_refresh if body else False
    return await sync_meta_insights_for_workspace(
        db=_db,
        workspace_id=ws["workspace_id"],
        is_demo=False,
        full_refresh=full_refresh,
    )


@router.get("/sync/status")
async def get_meta_sync_status(user: dict = Depends(get_current_user)):
    """Return the synchronization state and date bounds from db.marketing_sync_meta."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        return {
            "platform": "meta",
            "is_demo": True,
            "status": "disconnected",
            "last_sync_at": None,
            "oldest_synced_date": None,
            "latest_synced_date": None,
        }

    conn = await _db.marketing_connections.find_one({"workspace_id": ws["workspace_id"], "platform": "meta"})
    if not conn or conn.get("status") != "connected":
        return {
            "platform": "meta",
            "status": "disconnected",
            "connected": False,
            "last_sync_at": None,
        }

    account_id = conn.get("selected_account_id")
    canonical_act_id = account_id if (account_id and account_id.startswith("act_")) else (f"act_{account_id}" if account_id else None)

    sync_meta = None
    if canonical_act_id:
        sync_meta = await _db.marketing_sync_meta.find_one(
            {"workspace_id": ws["workspace_id"], "platform": "meta", "account_id": canonical_act_id},
            {"_id": 0},
        )

    return {
        "platform": "meta",
        "connected": True,
        "account_id": canonical_act_id,
        "account_name": conn.get("selected_account_name"),
        "account_currency": conn.get("account_currency"),
        "currency_mismatch": conn.get("currency_mismatch", False),
        "sync_status": sync_meta.get("status", conn.get("sync_status", "idle")) if sync_meta else conn.get("sync_status", "idle"),
        "sync_error": sync_meta.get("sync_error", conn.get("sync_error")) if sync_meta else conn.get("sync_error"),
        "last_sync_at": sync_meta.get("last_sync_at", conn.get("last_sync_at")) if sync_meta else conn.get("last_sync_at"),
        "oldest_synced_date": sync_meta.get("oldest_synced_date") if sync_meta else None,
        "latest_synced_date": sync_meta.get("latest_synced_date") if sync_meta else None,
        "synced_campaigns_count": sync_meta.get("synced_campaigns_count", 0) if sync_meta else 0,
        "synced_insights_count": sync_meta.get("synced_insights_count", 0) if sync_meta else 0,
    }


@router.get("/insights")
async def get_meta_insights(
    since: Optional[str] = None,
    until: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """Retrieve ingested daily insights from db.marketing_daily_insights for the active workspace."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        return {"ok": True, "insights": [], "count": 0, "is_demo": True}

    q: Dict[str, Any] = {"workspace_id": ws["workspace_id"], "platform": "meta"}
    if campaign_id:
        q["campaign_id"] = campaign_id
    if since and until:
        q["date"] = {"$gte": since, "$lte": until}
    elif since:
        q["date"] = {"$gte": since}
    elif until:
        q["date"] = {"$lte": until}

    cursor = _db.marketing_daily_insights.find(q, {"_id": 0}).sort("date", -1).limit(min(limit, 1000))
    insights = await cursor.to_list(length=min(limit, 1000))
    return {"ok": True, "insights": insights, "count": len(insights)}


@router.get("/campaigns")
async def get_meta_campaigns(user: dict = Depends(get_current_user)):
    """Retrieve synced campaign catalog from db.marketing_campaigns for the active workspace."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Meta integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        return {"ok": True, "campaigns": [], "count": 0, "is_demo": True}

    cursor = _db.marketing_campaigns.find(
        {"workspace_id": ws["workspace_id"], "platform": "meta"},
        {"_id": 0},
    ).sort("name", 1)
    campaigns = await cursor.to_list(length=500)
    return {"ok": True, "campaigns": campaigns, "count": len(campaigns)}

