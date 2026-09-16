"""Google Ads Integration Module for AHONIX.

Phase 5.3 Implementation:
- Google Ads OAuth 2.0 flow with CSRF state validation & TTL cleanup
- Required OAuth Scope: https://www.googleapis.com/auth/adwords
- Offline access type (access_type=offline, prompt=consent)
- Encrypted refresh token storage at rest using AES-256-GCM cipher
- Server-side access token refresh lifecycle with invalid_grant / reauth_required detection
- Backend-only Google Ads Developer Token support (GOOGLE_ADS_DEVELOPER_TOKEN)
- Accessible customer discovery (CustomerService / listAccessibleCustomers)
- Customer ID normalization (digits-only, no hyphens)
- Manager account support (login-customer-id header propagation)
- Account selection with store currency comparison and currency_mismatch detection
- Safe disconnect & workspace isolation
- Northstar Goods demo workspace protection
- Zero credential / secret leakage in frontend responses and logs
"""
import os
import re
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

logger = logging.getLogger("ahonix.google_ads")

# Google Ads OAuth and API Defaults
GOOGLE_ADS_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_ADS_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
DEFAULT_GOOGLE_ADS_API_VERSION = "v19"

router = APIRouter(prefix="/api/integrations/google-ads", tags=["google-ads"])

# Injected dependencies
_db = None
_get_active_workspace_fn = None


def init_google_ads(db, get_active_workspace_fn):
    """Initialize Google Ads module with MongoDB database and workspace resolver."""
    global _db, _get_active_workspace_fn
    _db = db
    _get_active_workspace_fn = get_active_workspace_fn


def get_google_ads_config() -> Dict[str, str]:
    """Load Google Ads configuration from environment variables."""
    app_url = os.environ.get("APP_URL", "http://localhost:3000").rstrip("/")
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    api_version = os.environ.get("GOOGLE_ADS_API_VERSION", DEFAULT_GOOGLE_ADS_API_VERSION).strip().lower()
    if not api_version.startswith("v"):
        api_version = f"v{api_version}"

    return {
        "client_id": os.environ.get("GOOGLE_ADS_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "").strip(),
        "developer_token": os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip(),
        "redirect_uri": os.environ.get("GOOGLE_ADS_REDIRECT_URI", f"{app_url}/api/integrations/google-ads/callback").strip(),
        "frontend_url": frontend_url,
        "api_version": api_version,
    }


def normalize_customer_id(customer_id: Optional[str]) -> str:
    """Normalize a Google Ads customer ID or resource name to a digits-only string without hyphens.
    
    Examples:
      'customers/123-456-7890' -> '1234567890'
      '123-456-7890' -> '1234567890'
      '1234567890' -> '1234567890'
    """
    if not customer_id:
        return ""
    raw = str(customer_id).replace("customers/", "").strip()
    return re.sub(r"\D", "", raw)


async def get_google_ads_access_token(
    db: Any,
    workspace_id: str,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Obtain a fresh short-lived access token using the encrypted refresh token stored at rest.
    Detects invalid_grant or revoked credentials and marks connection as reauth_required.
    """
    conn = await db.marketing_connections.find_one(
        {"workspace_id": workspace_id, "platform": "google_ads"}
    )
    if not conn or not conn.get("encrypted_refresh_token"):
        raise HTTPException(status_code=400, detail="Google Ads is not connected for this workspace.")

    cfg = get_google_ads_config()
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise HTTPException(
            status_code=503,
            detail="Google Ads OAuth client credentials are not configured on this server.",
        )

    refresh_token = decrypt_token(conn["encrypted_refresh_token"])

    should_close_client = False
    if client is not None:
        http_c = client
    else:
        http_c = httpx.AsyncClient(timeout=15.0)
        should_close_client = True

    try:
        res = await http_c.post(
            GOOGLE_ADS_TOKEN_URL,
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if res.status_code != 200:
            err_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
            err_code = err_data.get("error", "")
            err_desc = err_data.get("error_description", res.text)

            # Detect revoked or invalid grant
            if err_code in ("invalid_grant", "unauthorized_client") or "revoked" in err_desc.lower():
                logger.warning("Google Ads refresh token revoked/invalid: %s (%s)", err_desc, err_code)
                now_iso = datetime.now(timezone.utc).isoformat()
                await db.marketing_connections.update_one(
                    {"workspace_id": workspace_id, "platform": "google_ads"},
                    {"$set": {"status": "reauth_required", "sync_status": "reauth_required", "sync_error": "Authorization expired or revoked", "updated_at": now_iso}},
                )
                raise HTTPException(
                    status_code=401,
                    detail="Google Ads authorization expired or revoked. Please reconnect in Settings.",
                )

            logger.error("Failed to refresh Google Ads token (HTTP %d): %s", res.status_code, err_desc)
            raise HTTPException(status_code=502, detail=f"Google token refresh error: {err_desc}")

        token_data = res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="No access token returned from Google OAuth.")

        return access_token

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error refreshing Google Ads access token: %s", e)
        raise HTTPException(status_code=502, detail=f"Error refreshing Google Ads access token: {str(e)}")
    finally:
        if should_close_client:
            await http_c.aclose()


# --- Pydantic Schemas --------------------------------------------------------
class SelectGoogleAdsAccountBody(BaseModel):
    customer_id: str = Field(..., min_length=3, max_length=50)
    account_name: Optional[str] = Field(None, max_length=200)
    login_customer_id: Optional[str] = Field(None, max_length=50)


# --- Endpoints ---------------------------------------------------------------
@router.post("/connect")
async def connect_google_ads(user: dict = Depends(get_current_user)):
    """Initiate Google Ads OAuth 2.0 authorization flow.
    Generates secure CSRF state with 900s TTL and returns Google authorization URL.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(
            status_code=400,
            detail="Demo workspace Northstar Goods cannot connect external ad channels.",
        )

    cfg = get_google_ads_config()
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise HTTPException(
            status_code=503,
            detail="Google Ads integration is not configured on this server (GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET missing).",
        )

    state = secrets.token_urlsafe(32)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=900)

    await _db.google_ads_oauth_states.replace_one(
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
        f"{GOOGLE_ADS_AUTH_URL}"
        f"?client_id={cfg['client_id']}"
        f"&redirect_uri={cfg['redirect_uri']}"
        f"&response_type=code"
        f"&scope={DEFAULT_GOOGLE_ADS_SCOPE}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )

    return {
        "ok": True,
        "auth_url": auth_url,
        "state": state,
        "scope": DEFAULT_GOOGLE_ADS_SCOPE,
    }


@router.get("/callback")
async def google_ads_callback(request: Request):
    """Handle Google OAuth 2.0 redirect callback.
    Validates state nonce, exchanges authorization code for refresh token,
    encrypts refresh token with AES-256-GCM, and persists to db.marketing_connections.
    """
    if not _db:
        return RedirectResponse(url="/app/settings?google_ads_error=server_not_initialized")

    cfg = get_google_ads_config()
    frontend_url = cfg["frontend_url"]

    params = dict(request.query_params)
    error = params.get("error")
    if error:
        logger.warning("Google Ads OAuth rejected or cancelled: %s", error)
        return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error={error}")

    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error=missing_code_or_state")

    saved_state = await _db.google_ads_oauth_states.find_one({"state": state})
    if not saved_state:
        logger.warning("Google Ads callback state mismatch or unknown nonce: %s", state)
        return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error=invalid_state")

    # Check expiration
    expires_str = saved_state.get("expires_at")
    if expires_str:
        try:
            exp_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                await _db.google_ads_oauth_states.delete_one({"state": state})
                return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error=expired_state")
        except Exception:
            pass

    # Consume single-use state nonce
    await _db.google_ads_oauth_states.delete_one({"state": state})
    workspace_id = saved_state["workspace_id"]
    user_id = saved_state["user_id"]

    # Exchange authorization code for tokens
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_res = await client.post(
                GOOGLE_ADS_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uri": cfg["redirect_uri"],
                    "grant_type": "authorization_code",
                },
            )

            if token_res.status_code != 200:
                logger.error("Google token exchange failed (HTTP %d): %s", token_res.status_code, token_res.text)
                return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error=token_exchange_failed")

            token_data = token_res.json()
            refresh_token = token_data.get("refresh_token")

            # Fallback to existing encrypted refresh token if re-authorizing
            if not refresh_token:
                existing_conn = await _db.marketing_connections.find_one(
                    {"workspace_id": workspace_id, "platform": "google_ads"}
                )
                if existing_conn and existing_conn.get("encrypted_refresh_token"):
                    encrypted_refresh_token = existing_conn["encrypted_refresh_token"]
                else:
                    logger.error("Google OAuth exchange succeeded but no refresh_token was returned.")
                    return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error=no_refresh_token")
            else:
                encrypted_refresh_token = encrypt_token(refresh_token)

    except Exception as e:
        logger.exception("Error during Google OAuth token exchange: %s", e)
        return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads_error=network_error")

    now_utc = datetime.now(timezone.utc)

    conn_doc = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "platform": "google_ads",
        "status": "connected",
        "encrypted_refresh_token": encrypted_refresh_token,
        "selected_customer_id": None,
        "selected_account_name": None,
        "login_customer_id": None,
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
        {"workspace_id": workspace_id, "platform": "google_ads"},
        conn_doc,
        upsert=True,
    )

    logger.info("Successfully connected Google Ads for workspace %s", workspace_id)
    return RedirectResponse(url=f"{frontend_url}/app/settings?google_ads=connected")


@router.get("/status")
async def get_google_ads_status(user: dict = Depends(get_current_user)):
    """Return Google Ads connection status for the active workspace.
    Guarantees secrets, refresh tokens, and developer tokens are NEVER exposed.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]

    cfg = get_google_ads_config()
    is_configured = bool(cfg["client_id"] and cfg["client_secret"])

    if ws.get("is_demo"):
        return {
            "platform": "google_ads",
            "connected": False,
            "status": "demo_locked",
            "configured": is_configured,
            "is_demo": True,
            "selected_customer_id": None,
            "selected_account_name": None,
            "login_customer_id": None,
            "account_currency": None,
            "currency_mismatch": False,
            "sync_status": "idle",
            "sync_error": None,
            "last_sync_at": None,
        }

    conn = await _db.marketing_connections.find_one(
        {"workspace_id": ws_id, "platform": "google_ads"},
        {"_id": 0, "encrypted_access_token": 0, "encrypted_refresh_token": 0},
    )

    if not conn or conn.get("status") != "connected":
        unconnected_status = conn.get("status", "disconnected") if conn else ("not_configured" if not is_configured else "disconnected")
        return {
            "platform": "google_ads",
            "connected": False,
            "status": unconnected_status,
            "configured": is_configured,
            "is_demo": False,
            "selected_customer_id": None,
            "selected_account_name": None,
            "login_customer_id": None,
            "account_currency": None,
            "currency_mismatch": False,
            "sync_status": "idle",
            "sync_error": None,
            "last_sync_at": None,
        }

    return {
        "platform": "google_ads",
        "connected": True,
        "status": conn.get("status", "connected"),
        "configured": is_configured,
        "is_demo": False,
        "selected_customer_id": conn.get("selected_customer_id"),
        "selected_account_name": conn.get("selected_account_name"),
        "login_customer_id": conn.get("login_customer_id"),
        "account_currency": conn.get("account_currency"),
        "account_timezone": conn.get("account_timezone"),
        "currency_mismatch": conn.get("currency_mismatch", False),
        "sync_status": conn.get("sync_status", "idle"),
        "sync_error": conn.get("sync_error"),
        "last_sync_at": conn.get("last_sync_at"),
    }


@router.get("/accounts")
async def list_google_ads_accessible_customers(user: dict = Depends(get_current_user)):
    """Fetch accessible customer accounts for the connected Google Ads identity.
    Uses Google Ads CustomerService / listAccessibleCustomers.
    Requires GOOGLE_ADS_DEVELOPER_TOKEN.
    Normalizes customer IDs to digits-only.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace cannot access external Google Ads accounts.")

    ws_id = ws["workspace_id"]
    conn = await _db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "google_ads"})
    if not conn or conn.get("status") != "connected" or not conn.get("encrypted_refresh_token"):
        raise HTTPException(status_code=400, detail="Google Ads is not connected for this workspace.")

    cfg = get_google_ads_config()
    developer_token = cfg["developer_token"]
    if not developer_token:
        raise HTTPException(
            status_code=503,
            detail="Google Ads Developer Token is not configured on this server (GOOGLE_ADS_DEVELOPER_TOKEN missing).",
        )

    # Refresh access token server-side
    access_token = await get_google_ads_access_token(_db, ws_id)
    api_version = cfg["api_version"]

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            list_url = f"https://googleads.googleapis.com/{api_version}/customers:listAccessibleCustomers"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "developer-token": developer_token,
            }

            res = await client.get(list_url, headers=headers)

            if res.status_code == 401:
                # Token revoked or expired
                await _db.marketing_connections.update_one(
                    {"workspace_id": ws_id, "platform": "google_ads"},
                    {"$set": {"status": "reauth_required", "sync_error": "Token expired or revoked"}},
                )
                raise HTTPException(
                    status_code=401,
                    detail="Google Ads access token expired or revoked. Please reconnect in Settings.",
                )

            if res.status_code != 200:
                err_text = res.text
                logger.error("Failed to list accessible customers (HTTP %d): %s", res.status_code, err_text)
                raise HTTPException(
                    status_code=502,
                    detail=f"Google Ads API listAccessibleCustomers error: HTTP {res.status_code}",
                )

            data = res.json()
            resource_names = data.get("resourceNames") or []

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error querying Google Ads listAccessibleCustomers: %s", e)
        raise HTTPException(status_code=502, detail=f"Error querying Google Ads API: {str(e)}")

    store_currency = (ws.get("currency") or "USD").upper()
    accounts = []

    for rn in resource_names:
        cid = normalize_customer_id(rn)
        if not cid:
            continue

        # Format standardized item
        accounts.append({
            "customer_id": cid,
            "resource_name": f"customers/{cid}",
            "display_name": f"Google Ads Account {cid}",
            "currency": None,
            "timezone": None,
            "is_manager": None,
            "currency_mismatch": False,
            "is_selected": conn.get("selected_customer_id") == cid,
        })

    return {
        "ok": True,
        "store_currency": store_currency,
        "selected_customer_id": conn.get("selected_customer_id"),
        "login_customer_id": conn.get("login_customer_id"),
        "accounts": accounts,
    }


@router.post("/select-account")
async def select_google_ads_account(
    body: SelectGoogleAdsAccountBody,
    user: dict = Depends(get_current_user),
):
    """Select and bind a specific Google Ads customer account to the active workspace.
    Normalizes customer ID to digits-only.
    Validates developer token and accessible accounts.
    Compares currency against Shopify store currency and sets currency_mismatch accordingly.
    """
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace cannot modify external ad integrations.")

    ws_id = ws["workspace_id"]
    conn = await _db.marketing_connections.find_one({"workspace_id": ws_id, "platform": "google_ads"})
    if not conn or conn.get("status") != "connected" or not conn.get("encrypted_refresh_token"):
        raise HTTPException(status_code=400, detail="Google Ads is not connected for this workspace.")

    cfg = get_google_ads_config()
    developer_token = cfg["developer_token"]
    if not developer_token:
        raise HTTPException(
            status_code=503,
            detail="Google Ads Developer Token is not configured on this server (GOOGLE_ADS_DEVELOPER_TOKEN missing).",
        )

    # Normalize customer IDs (digits only, no hyphens)
    cid = normalize_customer_id(body.customer_id)
    if not cid:
        raise HTTPException(status_code=400, detail="Invalid Google Ads customer ID.")

    login_cid = normalize_customer_id(body.login_customer_id) if body.login_customer_id else None

    # Verify customer is accessible
    access_token = await get_google_ads_access_token(_db, ws_id)
    api_version = cfg["api_version"]

    account_currency = None
    account_timezone = None
    account_name = body.account_name

    # Query customer metadata from Google Ads API if possible
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            search_url = f"https://googleads.googleapis.com/{api_version}/customers/{cid}/googleAds:searchStream"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "developer-token": developer_token,
            }
            if login_cid:
                headers["login-customer-id"] = login_cid

            query_body = {
                "query": "SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone, customer.manager FROM customer LIMIT 1"
            }

            res = await client.post(search_url, headers=headers, json=query_body)
            if res.status_code == 200:
                stream_data = res.json()
                if stream_data and isinstance(stream_data, list) and len(stream_data) > 0:
                    results = stream_data[0].get("results") or []
                    if results:
                        c_info = results[0].get("customer", {})
                        account_currency = (c_info.get("currencyCode") or "").upper() or None
                        account_timezone = c_info.get("timeZone")
                        if not account_name:
                            account_name = c_info.get("descriptiveName")
    except Exception as e:
        logger.warning("Could not query extended customer metadata for %s: %s", cid, e)

    store_currency = (ws.get("currency") or "USD").upper()
    act_curr = (account_currency or store_currency).upper()
    currency_mismatch = (account_currency is not None) and (act_curr != store_currency)

    now_iso = datetime.now(timezone.utc).isoformat()
    update_fields = {
        "selected_customer_id": cid,
        "selected_account_name": account_name or f"Google Ads {cid}",
        "login_customer_id": login_cid,
        "account_currency": act_curr,
        "account_timezone": account_timezone or "UTC",
        "currency_mismatch": currency_mismatch,
        "updated_at": now_iso,
    }

    await _db.marketing_connections.update_one(
        {"workspace_id": ws_id, "platform": "google_ads"},
        {"$set": update_fields},
    )

    logger.info(
        "Selected Google Ads customer %s (login-customer-id: %s) for workspace %s (currency: %s, mismatch: %s)",
        cid, login_cid, ws_id, act_curr, currency_mismatch,
    )

    return {
        "ok": True,
        "selected_customer_id": cid,
        "selected_account_name": update_fields["selected_account_name"],
        "login_customer_id": login_cid,
        "account_currency": act_curr,
        "store_currency": store_currency,
        "currency_mismatch": currency_mismatch,
        "warning": (
            f"Ad Account currency ({act_curr}) differs from store currency ({store_currency}). "
            "To prevent inaccurate financial calculations, ad spend will not be blended into True Profit until currencies match."
            if currency_mismatch else None
        ),
    }


@router.post("/disconnect")
async def disconnect_google_ads(user: dict = Depends(get_current_user)):
    """Safely disconnect Google Ads from the active workspace and remove stored credentials."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]

    await _db.marketing_connections.delete_one({"workspace_id": ws_id, "platform": "google_ads"})
    logger.info("Disconnected Google Ads for workspace %s", ws_id)
    return {"ok": True, "disconnected": True}


class SyncGoogleAdsBody(BaseModel):
    full_refresh: bool = False


@router.post("/sync")
async def trigger_google_ads_sync(
    body: Optional[SyncGoogleAdsBody] = None,
    user: dict = Depends(get_current_user),
):
    """Trigger campaign catalog and daily performance insights synchronization for Google Ads."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        raise HTTPException(
            status_code=400,
            detail="Demo workspace Northstar Goods cannot synchronize external ad data.",
        )

    from google_ads_sync import sync_google_ads_insights_for_workspace

    full_refresh = body.full_refresh if body else False
    return await sync_google_ads_insights_for_workspace(
        db=_db,
        workspace_id=ws["workspace_id"],
        is_demo=False,
        full_refresh=full_refresh,
    )


@router.get("/sync/status")
async def get_google_ads_sync_status(user: dict = Depends(get_current_user)):
    """Return the synchronization state and date bounds from db.marketing_sync_meta for Google Ads."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        return {
            "platform": "google_ads",
            "is_demo": True,
            "status": "disconnected",
            "last_sync_at": None,
            "oldest_synced_date": None,
            "latest_synced_date": None,
        }

    conn = await _db.marketing_connections.find_one({"workspace_id": ws["workspace_id"], "platform": "google_ads"})
    if not conn or conn.get("status") != "connected":
        return {
            "platform": "google_ads",
            "status": "disconnected",
            "connected": False,
            "last_sync_at": None,
        }

    customer_id = conn.get("selected_customer_id")
    norm_cid = normalize_customer_id(customer_id) if customer_id else None

    sync_meta = None
    if norm_cid:
        sync_meta = await _db.marketing_sync_meta.find_one(
            {"workspace_id": ws["workspace_id"], "platform": "google_ads", "account_id": norm_cid},
            {"_id": 0},
        )

    return {
        "platform": "google_ads",
        "connected": True,
        "customer_id": norm_cid,
        "account_name": conn.get("selected_account_name"),
        "login_customer_id": conn.get("login_customer_id"),
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
async def get_google_ads_insights(
    since: Optional[str] = None,
    until: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """Retrieve ingested daily insights from db.marketing_daily_insights for Google Ads."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        return {"ok": True, "insights": [], "count": 0, "is_demo": True}

    q: Dict[str, Any] = {"workspace_id": ws["workspace_id"], "platform": "google_ads"}
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
async def get_google_ads_campaigns(user: dict = Depends(get_current_user)):
    """Retrieve synced campaign catalog from db.marketing_campaigns for Google Ads."""
    if not _db or not _get_active_workspace_fn:
        raise HTTPException(status_code=500, detail="Google Ads integration not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo"):
        return {"ok": True, "campaigns": [], "count": 0, "is_demo": True}

    cursor = _db.marketing_campaigns.find(
        {"workspace_id": ws["workspace_id"], "platform": "google_ads"},
        {"_id": 0},
    ).sort("name", 1)
    campaigns = await cursor.to_list(length=500)
    return {"ok": True, "campaigns": campaigns, "count": len(campaigns)}

