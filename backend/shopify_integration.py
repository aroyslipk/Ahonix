"""Shopify Integration Module for AHONIX.

Provides:
- Shopify OAuth authorization flow
- Secure, encrypted token storage
- Read-only store verification (shop, products, orders)
- Connection status and disconnection
- Strict workspace isolation

Shopify API Version: 2026-07 (Stable release per official Shopify version schedule)
"""
import os
import re
import hmac
import hashlib
import base64
import secrets
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet

import json
from auth import get_current_user
import shopify_sync
import shopify_webhooks

logger = logging.getLogger("ahonix.shopify")

# --- Configuration -----------------------------------------------------------
# Latest stable Shopify Admin API version per official quarterly schedule (2026-07)
DEFAULT_API_VERSION = "2026-07"
DEFAULT_SCOPES = "read_products,read_orders"

def get_shopify_config():
    return {
        "api_key": os.environ.get("SHOPIFY_API_KEY", "").strip(),
        "api_secret": os.environ.get("SHOPIFY_API_SECRET", "").strip(),
        "scopes": os.environ.get("SHOPIFY_SCOPES", DEFAULT_SCOPES).strip(),
        "api_version": os.environ.get("SHOPIFY_API_VERSION", DEFAULT_API_VERSION).strip(),
        "redirect_uri": os.environ.get("SHOPIFY_REDIRECT_URI", "").strip(),
    }

# Shared database and helper instances injected via init_shopify()
_db = None
_get_active_workspace_fn = None


def init_shopify(db, get_active_workspace_fn):
    global _db, _get_active_workspace_fn
    _db = db
    _get_active_workspace_fn = get_active_workspace_fn


# --- Domain Validation -------------------------------------------------------
SHOP_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?\.myshopify\.com$")


def clean_shop_domain(raw_shop: str) -> str:
    """Normalize and validate a myshopify.com domain.
    Rejects malformed domains, injection attempts, and invalid TLDs.
    """
    if not raw_shop or not isinstance(raw_shop, str):
        raise HTTPException(status_code=400, detail="Shop domain is required.")
    
    shop = raw_shop.strip().lower()
    shop = re.sub(r"^https?://", "", shop).split("/")[0].split("?")[0]
    
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
        
    if not SHOP_REGEX.match(shop):
        raise HTTPException(
            status_code=400,
            detail="Invalid Shopify store domain. Must be in the format 'store-name.myshopify.com'.",
        )
    return shop


# --- Cryptographic Helpers ---------------------------------------------------
def _get_cipher() -> Fernet:
    """Derive a deterministic Fernet encryption key from JWT_SECRET."""
    secret = os.environ.get("JWT_SECRET", "ahonix-default-fernet-secret-32-bytes!")
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_token(token: str) -> str:
    """Encrypt Shopify access token before writing to database."""
    cipher = _get_cipher()
    return cipher.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt Shopify access token for authorized server-side API calls."""
    cipher = _get_cipher()
    return cipher.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")


def verify_shopify_hmac(params: dict, secret: str) -> bool:
    """Verify the authenticity of a request from Shopify using HMAC-SHA256."""
    if not secret:
        logger.warning("SHOPIFY_API_SECRET not set; HMAC verification cannot succeed.")
        return False
    
    provided_hmac = params.get("hmac")
    if not provided_hmac:
        return False

    # Extract all query parameters except hmac and signature
    filtered = {k: v for k, v in params.items() if k not in ("hmac", "signature")}
    # Sort keys alphabetically and encode as key=value&...
    sorted_pairs = [f"{k}={filtered[k]}" for k in sorted(filtered.keys())]
    message = "&".join(sorted_pairs).encode("utf-8")
    
    computed = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, provided_hmac)


# --- Router ------------------------------------------------------------------
router = APIRouter(prefix="/api/integrations/shopify", tags=["Shopify"])


class ConnectBody(BaseModel):
    shop: str = Field(..., description="Shopify store domain (e.g. store.myshopify.com)")


@router.post("/connect")
async def connect_shopify(body: ConnectBody, user: dict = Depends(get_current_user)):
    """Initiate Shopify OAuth flow for the active workspace."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Shopify integration module not initialized.")

    cfg = get_shopify_config()
    if not cfg["api_key"]:
        raise HTTPException(
            status_code=503,
            detail="Shopify integration is not configured. Please set SHOPIFY_API_KEY in your environment.",
        )

    ws = await _get_active_workspace_fn(user)
    shop = clean_shop_domain(body.shop)

    # Generate secure random state nonce to protect against CSRF
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=15)).isoformat()

    # Store pending state linked to this user & workspace
    await _db.shopify_oauth_states.update_one(
        {"state": state},
        {"$set": {
            "state": state,
            "user_id": user["user_id"],
            "workspace_id": ws["workspace_id"],
            "shop": shop,
            "created_at": now.isoformat(),
            "expires_at": expires_at,
        }},
        upsert=True,
    )

    # Determine OAuth redirect URI
    app_url = os.environ.get("APP_URL", os.environ.get("BACKEND_URL", "http://localhost:8000")).rstrip("/")
    redirect_uri = cfg["redirect_uri"] or f"{app_url}/api/integrations/shopify/callback"

    # Build Shopify OAuth authorization URL
    auth_url = (
        f"https://{shop}/admin/oauth/authorize?"
        f"client_id={cfg['api_key']}&"
        f"scope={cfg['scopes']}&"
        f"redirect_uri={redirect_uri}&"
        f"state={state}"
    )

    return {"auth_url": auth_url, "shop": shop}


@router.get("/callback")
async def shopify_callback(request: Request):
    """Handle Shopify OAuth redirect callback, exchange code, and store connection."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    params = dict(request.query_params)
    code = params.get("code")
    raw_shop = params.get("shop")
    state = params.get("state")

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    if not code or not raw_shop or not state:
        logger.error("Shopify callback missing required parameters.")
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=missing_parameters")

    try:
        shop = clean_shop_domain(raw_shop)
    except HTTPException:
        logger.error("Shopify callback received invalid shop domain: %s", raw_shop)
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=invalid_shop")

    # Validate state nonce from database
    try:
        oauth_state = await _db.shopify_oauth_states.find_one({"state": state})
    except Exception as e:
        logger.error("Shopify callback state lookup failed (%s)", type(e).__name__)
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=db_error")

    if not oauth_state:
        logger.error("Shopify callback state nonce not found or already consumed.")
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=invalid_state")

    # Verify state has not expired
    if datetime.fromisoformat(oauth_state["expires_at"]) < datetime.now(timezone.utc):
        try:
            await _db.shopify_oauth_states.delete_one({"state": state})
        except Exception:
            pass
        logger.error("Shopify callback state nonce expired.")
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=expired_state")

    # Consume the state nonce immediately (one-time use)
    try:
        await _db.shopify_oauth_states.delete_one({"state": state})
    except Exception:
        pass

    cfg = get_shopify_config()
    # Verify HMAC signature
    if not verify_shopify_hmac(params, cfg["api_secret"]):
        logger.error("Shopify callback HMAC verification failed for shop: %s", shop)
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=hmac_failed")

    # Exchange authorization code for permanent access token
    token_url = f"https://{shop}/admin/oauth/access_token"
    token_payload = {
        "client_id": cfg["api_key"],
        "client_secret": cfg["api_secret"],
        "code": code,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(token_url, json=token_payload)
            
        if res.status_code != 200:
            logger.error("Shopify token exchange failed: HTTP %s %s", res.status_code, res.text)
            return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=token_exchange_failed")

        data = res.json()
        access_token = data.get("access_token")
        granted_scope = data.get("scope", cfg["scopes"])

        if not access_token:
            logger.error("Shopify response did not contain access_token.")
            return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=missing_token")

    except Exception as e:
        logger.exception("Error exchanging Shopify authorization code: %s", type(e).__name__)
        return RedirectResponse(f"{frontend_url}/app/settings?shopify_error=network_error")

    # Encrypt access token before storing
    encrypted_token = encrypt_token(access_token)
    now = datetime.now(timezone.utc).isoformat()
    workspace_id = oauth_state["workspace_id"]
    user_id = oauth_state["user_id"]

    connection_doc = {
        "connection_id": f"shop_conn_{uuid.uuid4().hex[:12]}",
        "workspace_id": workspace_id,
        "user_id": user_id,
        "shop": shop,
        "encrypted_access_token": encrypted_token,
        "scopes": [s.strip() for s in granted_scope.split(",") if s.strip()],
        "api_version": cfg["api_version"],
        "status": "connected",
        "connected_at": now,
        "last_sync_at": None,
        "sync_status": "idle",
        "sync_error": None,
    }

    # Upsert connection scoped strictly to this workspace
    await _db.shopify_connections.replace_one(
        {"workspace_id": workspace_id},
        connection_doc,
        upsert=True,
    )

    logger.info("Successfully connected Shopify store %s for workspace %s", shop, workspace_id)

    # Register webhook subscriptions if webhook URL configured
    webhook_url = os.environ.get("SHOPIFY_WEBHOOK_URL", "")
    if not webhook_url and cfg.get("redirect_uri"):
        webhook_url = cfg["redirect_uri"].replace("/callback", "/webhooks")
    if webhook_url:
        try:
            wb_headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }
            wb_base_url = f"https://{shop}/admin/api/{cfg['api_version']}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                await shopify_webhooks.register_shopify_webhooks(client, wb_base_url, wb_headers, webhook_url)
        except Exception as e:
            logger.warning("Could not auto-register webhooks during OAuth: %s", str(e))

    return RedirectResponse(f"{frontend_url}/app/settings?shopify=connected&shop={shop}")


@router.get("/status")
async def get_shopify_status(user: dict = Depends(get_current_user)):
    """Return the Shopify connection and sync status for the user's active workspace.
    NEVER exposes access tokens or client secrets.
    """
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Module not initialized.")

    ws = await _get_active_workspace_fn(user)
    conn = await _db.shopify_connections.find_one(
        {"workspace_id": ws["workspace_id"]},
        {"_id": 0, "encrypted_access_token": 0},
    )

    if not conn or conn.get("status") != "connected":
        return {
            "connected": False,
            "shop": None,
            "sync_status": "disconnected",
        }

    sync_meta = await _db.shopify_sync_meta.find_one(
        {"workspace_id": ws["workspace_id"]},
        {"_id": 0},
    )
    synced = await _db.shopify_synced_data.find_one(
        {"workspace_id": ws["workspace_id"]},
        {"_id": 0},
    )

    summary = None
    if sync_meta and sync_meta.get("counts"):
        summary = {
            "product_count": sync_meta["counts"].get("total_products", 0),
            "order_count": sync_meta["counts"].get("total_orders", 0),
            "new_products": sync_meta["counts"].get("products_synced", 0),
            "new_orders": sync_meta["counts"].get("orders_synced", 0),
        }
    elif conn.get("summary"):
        summary = conn.get("summary")
    elif synced and synced.get("summary"):
        summary = synced.get("summary")

    return {
        "connected": True,
        "shop": conn.get("shop"),
        "scopes": conn.get("scopes", []),
        "api_version": conn.get("api_version", DEFAULT_API_VERSION),
        "connected_at": conn.get("connected_at"),
        "last_sync_at": conn.get("last_sync_at"),
        "sync_status": conn.get("sync_status", "idle"),
        "sync_error": conn.get("sync_error"),
        "summary": summary,
        "shop_details": synced.get("shop_details") if synced else None,
    }


@router.post("/sync")
async def sync_shopify_data(user: dict = Depends(get_current_user)):
    """Execute read-only synchronization of products & orders, advance incremental cursor,
    and aggregate live analytics into workspace_data. Does NOT modify merchant store data.
    """
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Module not initialized.")

    ws = await _get_active_workspace_fn(user)
    if ws.get("is_demo") or ws.get("name") == "Northstar Goods" or ws.get("workspace_id") == "ws_demo_northstar":
        raise HTTPException(status_code=400, detail="Demo workspace Northstar Goods cannot be synced.")

    conn = await _db.shopify_connections.find_one({"workspace_id": ws["workspace_id"]})
    if not conn or conn.get("status") != "connected":
        raise HTTPException(status_code=400, detail="No Shopify store is connected to this workspace.")

    return await shopify_sync.run_shopify_sync(
        db=_db,
        workspace=ws,
        conn=conn,
        decrypt_fn=decrypt_token,
        full_refresh=False,
    )


@router.post("/disconnect")
async def disconnect_shopify(user: dict = Depends(get_current_user)):
    """Disconnect Shopify from the user's active workspace and purge synced data."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Module not initialized.")

    ws = await _get_active_workspace_fn(user)
    
    conn = await _db.shopify_connections.find_one({"workspace_id": ws["workspace_id"]})
    if not conn:
        return {"ok": True, "message": "No active connection found."}

    # Delete connection and synced records for this workspace
    await _db.shopify_connections.delete_one({"workspace_id": ws["workspace_id"]})
    await _db.shopify_synced_data.delete_one({"workspace_id": ws["workspace_id"]})
    await _db.shopify_products.delete_many({"workspace_id": ws["workspace_id"]})
    await _db.shopify_orders.delete_many({"workspace_id": ws["workspace_id"]})
    await _db.shopify_sync_meta.delete_one({"workspace_id": ws["workspace_id"]})

    # Clean up workspace_data ONLY if it's NOT a demo workspace (protect demo workspace!)
    if not ws.get("is_demo"):
        await _db.workspace_data.delete_one({"workspace_id": ws["workspace_id"]})

    logger.info("Disconnected Shopify store for workspace %s", ws["workspace_id"])
    return {"ok": True, "message": "Shopify store disconnected successfully."}


@router.post("/webhooks")
async def shopify_webhook_receiver(request: Request):
    """Receive and securely process Shopify real-time webhooks.
    Authenticates requests using official Base64 HMAC-SHA256 signature verification over the raw body.
    """
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    raw_body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    topic = request.headers.get("X-Shopify-Topic")
    shop = request.headers.get("X-Shopify-Shop-Domain")
    webhook_id = request.headers.get("X-Shopify-Webhook-Id")

    cfg = get_shopify_config()
    secret = cfg.get("api_secret")

    if not shopify_webhooks.verify_shopify_webhook_hmac(raw_body, hmac_header, secret):
        logger.warning("Shopify webhook rejected: invalid or missing HMAC signature from shop '%s'", shop)
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook HMAC signature.")

    if not topic or not shop:
        raise HTTPException(status_code=400, detail="Missing required Shopify webhook headers.")

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        logger.warning("Failed to parse Shopify webhook JSON payload: %s", str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    res = await shopify_webhooks.process_webhook_event(
        db=_db,
        topic=topic,
        shop=shop,
        webhook_id=webhook_id,
        payload=payload,
    )
    return res


@router.post("/webhooks/register")
async def trigger_webhook_registration(user: dict = Depends(get_current_user)):
    """Manually register Shopify webhooks for the active workspace."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Module not initialized.")

    ws = await _get_active_workspace_fn(user)
    conn = await _db.shopify_connections.find_one({"workspace_id": ws["workspace_id"]})
    if not conn or conn.get("status") != "connected":
        raise HTTPException(status_code=400, detail="No active Shopify connection for this workspace.")

    cfg = get_shopify_config()
    token = decrypt_token(conn["encrypted_access_token"])
    shop = conn["shop"]
    webhook_url = os.environ.get("SHOPIFY_WEBHOOK_URL", "")
    if not webhook_url and cfg.get("redirect_uri"):
        webhook_url = cfg["redirect_uri"].replace("/callback", "/webhooks")

    if not webhook_url:
        raise HTTPException(status_code=400, detail="Webhook callback URL not configured.")

    wb_headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }
    wb_base_url = f"https://{shop}/admin/api/{conn.get('api_version', DEFAULT_API_VERSION)}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        topics = await shopify_webhooks.register_shopify_webhooks(client, wb_base_url, wb_headers, webhook_url)

    return {"ok": True, "registered_topics": topics, "callback_url": webhook_url}
