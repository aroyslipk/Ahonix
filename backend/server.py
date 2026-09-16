import os
import json
import asyncio
import logging
import uuid
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Any

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from rate_limit import make_rate_limiter

import auth
from auth import get_current_user
from demo_data import build_workspace_analytics, simulate_market_entry
import shopify_integration
import shopify_sync
import meta_integration
import google_ads_integration
import marketing_cron
import billing
import stripe_integration
import ai_analyst
from ai_analyst import (
    SYSTEM_PROMPT,
    AIProviderNotConfiguredError,
    AIProviderError,
    stream_analyst_response,
    get_active_ai_provider,
)

mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
db_name = os.environ.get("DB_NAME", "ahonix_db")
if not mongo_url:
    mongo_url = "mongodb://localhost:27017"
if not db_name:
    db_name = "ahonix_db"

client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[db_name]
auth.init_auth(db)

app = FastAPI(title="AHONIX API", docs_url=None, redoc_url=None)
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ahonix")

# --- Rate limiters -----------------------------------------------------------
ask_limiter = make_rate_limiter(max_calls=15, window_seconds=60, scope="ask")


# --- Security headers middleware ---------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


# ----------------------------------------------------------------------------
# Workspace helpers
# ----------------------------------------------------------------------------
async def get_active_workspace(user: dict):
    ws_id = user.get("active_workspace_id")
    if not ws_id:
        raise HTTPException(status_code=404, detail="No active workspace")
    ws = await db.workspaces.find_one({"workspace_id": ws_id, "user_id": user["user_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


# Initialize Shopify integration with db and workspace helper
shopify_integration.init_shopify(db, get_active_workspace)
meta_integration.init_meta(db, get_active_workspace)
google_ads_integration.init_google_ads(db, get_active_workspace)
billing.init_billing(db, get_active_workspace)
stripe_integration.init_stripe(db, get_active_workspace)
marketing_cron.init_cron(db)


async def get_workspace_data(user: dict):
    ws = await get_active_workspace(user)
    data = await db.workspace_data.find_one({"workspace_id": ws["workspace_id"]}, {"_id": 0})
    return ws, data


# ----------------------------------------------------------------------------
# Onboarding / workspace management
# ----------------------------------------------------------------------------
class CreateWorkspace(BaseModel):
    name: str = Field("", max_length=200)
    business_type: str = Field("DTC Brand", max_length=100)
    channels: list[str] = Field(default_factory=list, max_length=20)
    size: str = Field("", max_length=100)
    country: str = Field("", max_length=100)
    currency: str = Field("USD", max_length=10)
    mode: Literal["demo", "real"] = "demo"


@api.post("/workspaces")
async def create_workspace(body: CreateWorkspace, user: dict = Depends(get_current_user)):
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    is_demo = body.mode == "demo"
    name = body.name.strip() or ("Northstar Goods" if is_demo else "My Store")
    ws = {
        "workspace_id": ws_id, "user_id": user["user_id"], "name": name,
        "business_type": body.business_type, "channels": body.channels,
        "size": body.size, "country": body.country, "currency": body.currency,
        "is_demo": is_demo, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workspaces.insert_one(ws)
    if is_demo:
        analytics = build_workspace_analytics(store_name=name, currency=body.currency)
        analytics["workspace_id"] = ws_id
        await db.workspace_data.insert_one({**analytics})
    else:
        # Create empty clean shell so all endpoints work seamlessly
        starter = {
            "workspace_id": ws_id,
            "meta": {
                "store_name": name,
                "currency": body.currency,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_demo": False,
            },
            "kpis": [
                {"label": "Gross Revenue", "value": 0.0, "format": "currency", "change": 0.0, "tooltip": "Awaiting store connection"},
                {"label": "True Profit", "value": 0.0, "format": "currency", "change": 0.0, "tooltip": "Awaiting store connection"},
                {"label": "True Margin", "value": 0.0, "format": "percent", "change": 0.0, "tooltip": "Awaiting store connection"},
                {"label": "Ad Spend", "value": 0.0, "format": "currency", "change": 0.0, "tooltip": "Awaiting ad connectors"},
                {"label": "Blended ROAS", "value": 0.0, "format": "multiple", "change": 0.0, "tooltip": "Awaiting ad connectors"},
            ],
            "profit": {
                "gross_revenue": 0.0,
                "steps": [
                    {"label": "Gross Revenue", "value": 0.0, "type": "total"},
                    {"label": "Discounts", "value": 0.0, "type": "cost"},
                    {"label": "Returns", "value": 0.0, "type": "cost"},
                    {"label": "Product Cost (COGS)", "value": 0.0, "type": "cost"},
                    {"label": "Shipping", "value": 0.0, "type": "cost"},
                    {"label": "Advertising", "value": 0.0, "type": "cost"},
                    {"label": "Payment Fees", "value": 0.0, "type": "cost"},
                    {"label": "Marketplace Fees", "value": 0.0, "type": "cost"},
                    {"label": "True Profit", "value": 0.0, "type": "result"},
                ],
                "gross_profit": 0.0,
                "contribution_margin": 0.0,
                "true_profit": 0.0,
                "margin": 0.0,
                "product_profit": [],
            },
            "sales": {"revenue": 0.0, "orders": 0, "aov": 0.0, "units": 0},
            "products": [],
            "marketing": {"total_spend": 0.0, "roas": 0.0, "campaigns": []},
            "channels": {
                "payments": {"total_fees": 0.0, "avg_fee_pct": 2.9, "methods": []}
            },
            "priorities": [],
            "briefing": {
                "headline": f"{name} initialized in Live Production Mode.",
                "subline": "Connect your Shopify store, Meta Ads, Google Ads, or Stripe in Settings to begin live data ingestion.",
                "action": "Go to Settings",
            },
            "insights": [],
            "weekly": [],
        }
        await db.workspace_data.insert_one(starter)

    await db.users.update_one({"user_id": user["user_id"]},
                              {"$set": {"active_workspace_id": ws_id, "onboarding_completed": True}})
    return {"workspace_id": ws_id, "name": name, "is_demo": is_demo}


@api.get("/workspaces")
async def list_workspaces(user: dict = Depends(get_current_user)):
    items = await db.workspaces.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(50)
    return {"workspaces": items, "active_workspace_id": user.get("active_workspace_id")}


@api.post("/workspaces/{workspace_id}/select")
async def select_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id, "user_id": user["user_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"active_workspace_id": workspace_id}})
    return {"ok": True}


@api.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id, "user_id": user["user_id"]})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    count = await db.workspaces.count_documents({"user_id": user["user_id"]})
    if count <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your only workspace. Please create another workspace first."
        )

    # Clean up workspace from database
    await db.workspaces.delete_one({"workspace_id": workspace_id})
    await db.workspace_data.delete_one({"workspace_id": workspace_id})
    await db.shopify_connections.delete_many({"workspace_id": workspace_id})
    await db.meta_connections.delete_many({"workspace_id": workspace_id})
    await db.google_connections.delete_many({"workspace_id": workspace_id})
    await db.stripe_merchant_connections.delete_many({"workspace_id": workspace_id})
    await db.subscriptions.delete_many({"workspace_id": workspace_id})
    await db.shopify_oauth_states.delete_many({"workspace_id": workspace_id})

    # If deleted workspace was active, switch to a remaining workspace
    new_active_id = user.get("active_workspace_id")
    if user.get("active_workspace_id") == workspace_id:
        remaining_ws = await db.workspaces.find_one({"user_id": user["user_id"]}, {"_id": 0})
        new_active_id = remaining_ws["workspace_id"] if remaining_ws else None
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"active_workspace_id": new_active_id}}
        )

    return {
        "ok": True,
        "deleted_workspace_id": workspace_id,
        "active_workspace_id": new_active_id,
        "message": f"Workspace '{ws.get('name', 'Workspace')}' deleted successfully."
    }


# ----------------------------------------------------------------------------
# Analytics section endpoints
# ----------------------------------------------------------------------------
def _empty(ws):
    return {"empty": True, "workspace": {"name": ws["name"], "is_demo": ws.get("is_demo", False)}}


def _meta(ws, data, extra):
    return {"empty": False, "workspace": {"name": ws["name"], "currency": ws.get("currency", "USD"),
                                          "is_demo": ws.get("is_demo", False)},
            "meta": data.get("meta"), **extra}


@api.get("/overview")
async def overview(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"kpis": data["kpis"], "weekly": data["weekly"],
                            "priorities": data["priorities"], "briefing": data["briefing"]})


@api.get("/intelligence")
async def intelligence(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"insights": data["insights"]})


@api.get("/profit")
async def profit(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"profit": data["profit"]})


@api.get("/sales")
async def sales(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"sales": data["sales"]})


@api.get("/products")
async def products(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"products": data["products"]})


@api.get("/products/{product_id}")
async def product_detail(product_id: str, user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    p = next((x for x in data["products"] if x["id"] == product_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return _meta(ws, data, {"product": p})


# ----------------------------------------------------------------------------
# Merchant COGS Configuration Endpoints
# ----------------------------------------------------------------------------
class VariantCostItem(BaseModel):
    variant_id: Any
    title: str | None = None
    sku: str | None = None
    unit_cost: float | None = Field(None, ge=0)


class UpdateCogsBody(BaseModel):
    unit_cost: float | None = Field(None, ge=0)
    variants: list[VariantCostItem] = Field(default_factory=list)


class BatchCogsItem(BaseModel):
    product_id: str
    unit_cost: float | None = Field(None, ge=0)
    variants: list[VariantCostItem] = Field(default_factory=list)


class BatchUpdateCogsBody(BaseModel):
    items: list[BatchCogsItem]


VariantCostItem.model_rebuild()
UpdateCogsBody.model_rebuild()
BatchCogsItem.model_rebuild()
BatchUpdateCogsBody.model_rebuild()


@api.get("/cogs")
async def get_cogs_catalog(user: dict = Depends(get_current_user)):
    ws = await get_active_workspace(user)
    ws_id = ws["workspace_id"]
    is_demo = ws.get("is_demo", False)

    if is_demo:
        data = await db.workspace_data.find_one({"workspace_id": ws_id}, {"_id": 0, "products": 1})
        prods = (data or {}).get("products") or []
        items = []
        for p in prods:
            items.append({
                "product_id": p.get("id"),
                "shopify_id": None,
                "title": p.get("name"),
                "handle": p.get("id"),
                "image_url": None,
                "category": p.get("category"),
                "stock": p.get("stock", 0),
                "min_price": p.get("price", 0.0),
                "max_price": p.get("price", 0.0),
                "unit_cost": p.get("unit_cost", 0.0),
                "configured_unit_cost": p.get("unit_cost", 0.0),
                "cogs_source": "demo",
                "cogs_status": "CONFIGURED",
                "margin": p.get("margin", 0.0),
                "variants": [
                    {
                        "variant_id": f"{p.get('id')}_v1",
                        "title": "Default Variant",
                        "price": p.get("price", 0.0),
                        "sku": p.get("id", ""),
                        "inventory_quantity": p.get("stock", 0),
                        "imported_cost": None,
                        "configured_cost": p.get("unit_cost", 0.0),
                        "resolved_cost": p.get("unit_cost", 0.0),
                        "status": "CONFIGURED",
                    }
                ],
                "updated_at": None,
            })
        return {
            "workspace_id": ws_id,
            "is_demo": True,
            "total_products": len(items),
            "configured_count": len(items),
            "imported_count": 0,
            "unconfigured_count": 0,
            "coverage_pct": 100.0,
            "products": items,
        }

    products_cursor = db.shopify_products.find({"workspace_id": ws_id})
    raw_products = await products_cursor.to_list(1000)

    cogs_map = {}
    if hasattr(db, "merchant_cogs"):
        cogs_cursor = db.merchant_cogs.find({"workspace_id": ws_id})
        async for c in cogs_cursor:
            cogs_map[c.get("product_id")] = c

    items = []
    conf_count = 0
    imp_count = 0
    unconf_count = 0

    for p in raw_products:
        pid = p["product_id"]
        cogs_rec = cogs_map.get(pid) or cogs_map.get(p.get("shopify_id"))

        p_variants = p.get("variants") or []
        variant_items = []
        has_any_conf_var = False
        has_any_imp_var = False

        for v in p_variants:
            vid = v.get("variant_id")
            v_price = float(v.get("price", 0.0))
            imp_cost = float(v.get("cost")) if v.get("cost") is not None else None

            conf_cost = None
            if cogs_rec:
                for cv in cogs_rec.get("variants") or []:
                    if str(cv.get("variant_id")) == str(vid) and cv.get("unit_cost") is not None:
                        conf_cost = float(cv["unit_cost"])
                        break
                if conf_cost is None and cogs_rec.get("unit_cost") is not None:
                    conf_cost = float(cogs_rec["unit_cost"])

            resolved_cost, source, status = shopify_sync.resolve_variant_cogs(p, vid, cogs_rec)
            if status == "CONFIGURED":
                has_any_conf_var = True
            elif status == "IMPORTED":
                has_any_imp_var = True

            variant_items.append({
                "variant_id": vid,
                "title": v.get("title") or "Default Title",
                "price": v_price,
                "sku": v.get("sku") or "",
                "inventory_quantity": int(v.get("inventory_quantity", 0)),
                "imported_cost": imp_cost,
                "configured_cost": conf_cost,
                "resolved_cost": resolved_cost,
                "status": status,
            })

        p_unit_cost, p_source, p_status = shopify_sync.resolve_product_cogs(p, cogs_rec)
        if p_status == "UNCONFIGURED" and has_any_conf_var:
            p_status = "CONFIGURED"
            p_source = "merchant"
            p_unit_cost = round(sum(vi["resolved_cost"] for vi in variant_items) / len(variant_items), 2) if variant_items else 0.0
        elif p_status == "UNCONFIGURED" and has_any_imp_var:
            p_status = "IMPORTED"
            p_source = "imported"
            p_unit_cost = round(sum(vi["resolved_cost"] for vi in variant_items) / len(variant_items), 2) if variant_items else 0.0

        if p_status == "CONFIGURED":
            conf_count += 1
        elif p_status == "IMPORTED":
            imp_count += 1
        else:
            unconf_count += 1

        ref_price = float(p.get("min_price", 0.0) or 0.0)
        margin = round(((ref_price - p_unit_cost) / ref_price * 100), 1) if ref_price > 0 and p_unit_cost > 0 else 0.0

        items.append({
            "product_id": pid,
            "shopify_id": p.get("shopify_id"),
            "title": p.get("title"),
            "handle": p.get("handle"),
            "image_url": p.get("image_url"),
            "category": p.get("category"),
            "stock": p.get("stock", 0),
            "min_price": p.get("min_price", 0.0),
            "max_price": p.get("max_price", 0.0),
            "unit_cost": p_unit_cost,
            "configured_unit_cost": cogs_rec.get("unit_cost") if cogs_rec else None,
            "cogs_source": p_source,
            "cogs_status": p_status,
            "margin": margin,
            "variants": variant_items,
            "updated_at": cogs_rec.get("updated_at") if cogs_rec else None,
        })

    total = len(items)
    coverage = round(((conf_count + imp_count) / total * 100), 1) if total > 0 else 0.0

    return {
        "workspace_id": ws_id,
        "is_demo": False,
        "total_products": total,
        "configured_count": conf_count,
        "imported_count": imp_count,
        "unconfigured_count": unconf_count,
        "coverage_pct": coverage,
        "products": items,
    }


@api.put("/cogs/{product_id}")
async def update_product_cogs(product_id: str, body: UpdateCogsBody, user: dict = Depends(get_current_user)):
    ws = await get_active_workspace(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace COGS is locked for Northstar Goods.")

    ws_id = ws["workspace_id"]
    prod = await db.shopify_products.find_one(
        {"workspace_id": ws_id, "$or": [{"product_id": product_id}, {"product_id": f"sp_{product_id}"}, {"shopify_id": product_id}]},
        {"_id": 0}
    )
    if not prod:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found in workspace.")

    canonical_pid = prod["product_id"]
    now = datetime.now(timezone.utc).isoformat()

    variants_data = []
    for v in (body.variants or []):
        v_dict = v.model_dump() if hasattr(v, "model_dump") else v.dict()
        if v_dict.get("unit_cost") is not None:
            v_dict["unit_cost"] = float(v_dict["unit_cost"])
        variants_data.append(v_dict)

    doc = {
        "workspace_id": ws_id,
        "product_id": canonical_pid,
        "shopify_id": prod.get("shopify_id"),
        "unit_cost": float(body.unit_cost) if body.unit_cost is not None else None,
        "variants": variants_data,
        "updated_at": now,
        "updated_by": user.get("email") or user.get("user_id"),
    }

    await db.merchant_cogs.replace_one(
        {"workspace_id": ws_id, "product_id": canonical_pid},
        doc,
        upsert=True,
    )

    await shopify_sync.aggregate_shopify_workspace_data(
        db=db,
        workspace_id=ws_id,
        store_name=ws.get("name", "Store"),
        currency=ws.get("currency", "USD"),
    )

    return {
        "ok": True,
        "product_id": canonical_pid,
        "unit_cost": doc["unit_cost"],
        "variants_count": len(variants_data),
        "updated_at": now,
    }


@api.post("/cogs/batch")
async def batch_update_cogs(body: BatchUpdateCogsBody, user: dict = Depends(get_current_user)):
    ws = await get_active_workspace(user)
    if ws.get("is_demo"):
        raise HTTPException(status_code=400, detail="Demo workspace COGS is locked for Northstar Goods.")

    ws_id = ws["workspace_id"]
    now = datetime.now(timezone.utc).isoformat()
    user_id = user.get("email") or user.get("user_id")

    updated_count = 0
    for item in body.items:
        pid = item.product_id
        prod = await db.shopify_products.find_one(
            {"workspace_id": ws_id, "$or": [{"product_id": pid}, {"product_id": f"sp_{pid}"}, {"shopify_id": pid}]},
            {"_id": 0}
        )
        if not prod:
            continue

        canonical_pid = prod["product_id"]
        variants_data = []
        for v in (item.variants or []):
            v_dict = v.model_dump() if hasattr(v, "model_dump") else v.dict()
            if v_dict.get("unit_cost") is not None:
                v_dict["unit_cost"] = float(v_dict["unit_cost"])
            variants_data.append(v_dict)

        doc = {
            "workspace_id": ws_id,
            "product_id": canonical_pid,
            "shopify_id": prod.get("shopify_id"),
            "unit_cost": float(item.unit_cost) if item.unit_cost is not None else None,
            "variants": variants_data,
            "updated_at": now,
            "updated_by": user_id,
        }
        await db.merchant_cogs.replace_one(
            {"workspace_id": ws_id, "product_id": canonical_pid},
            doc,
            upsert=True,
        )
        updated_count += 1

    if updated_count > 0:
        await shopify_sync.aggregate_shopify_workspace_data(
            db=db,
            workspace_id=ws_id,
            store_name=ws.get("name", "Store"),
            currency=ws.get("currency", "USD"),
        )

    return {"ok": True, "updated_count": updated_count}


@api.get("/inventory")
async def inventory(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"inventory": data["inventory"]})


@api.get("/returns")
async def returns(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"returns": data["returns"]})


@api.get("/marketing")
async def marketing(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"marketing": data["marketing"]})


@api.get("/customers")
async def customers(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"customers": data["customers"]})


@api.get("/operations")
async def operations(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"operations": data["operations"]})


@api.get("/markets")
async def markets(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"markets": data["markets"]})


class SimBody(BaseModel):
    country: str = Field(..., max_length=100)
    price: float = Field(..., ge=0, le=1_000_000)
    demand_units: int = Field(..., ge=0, le=10_000_000)
    inventory_units: int = Field(..., ge=0, le=10_000_000)
    marketing_budget: float = Field(..., ge=0, le=100_000_000)


@api.post("/markets/simulate")
async def market_simulate(body: SimBody, user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        raise HTTPException(status_code=400, detail="Simulation requires a demo workspace.")
    result = simulate_market_entry(data, body.country, body.price, body.demand_units,
                                   body.inventory_units, body.marketing_budget)
    return {"result": result}


# ----------------------------------------------------------------------------
# Action center
# ----------------------------------------------------------------------------
LIFECYCLE = ["Detected", "Explained", "Simulated", "Awaiting Approval",
             "Approved", "Executed", "Measured"]


@api.get("/actions")
async def get_actions(user: dict = Depends(get_current_user)):
    ws, data = await get_workspace_data(user)
    if not data:
        return _empty(ws)
    return _meta(ws, data, {"actions": data["actions"], "lifecycle": LIFECYCLE})


class ActionOp(BaseModel):
    op: Literal["simulate", "approve", "execute", "measure", "archive", "restore"]


@api.post("/actions/{action_id}")
async def mutate_action(action_id: str, body: ActionOp, user: dict = Depends(get_current_user)):
    # Validate action_id format
    if not action_id or len(action_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid action ID")
    transitions = {"simulate": "Simulated", "approve": "Approved",
                   "execute": "Executed", "measure": "Measured"}
    if body.op not in transitions:
        raise HTTPException(status_code=400, detail=f"Invalid operation '{body.op}'. Choose from: {list(transitions.keys())}")
    ws, data = await get_workspace_data(user)
    if not data:
        raise HTTPException(status_code=400, detail="No demo workspace")
    actions = data["actions"]
    act = next((a for a in actions if a["action_id"] == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail="Action not found")
    new_stage = transitions[body.op]
    old_stage = act["stage"]
    # Only allow forward transitions — prevents duplicate execution / invalid state jumps.
    if LIFECYCLE.index(new_stage) <= LIFECYCLE.index(old_stage):
        raise HTTPException(status_code=409, detail=f"Action already at '{old_stage}'.")
    act["stage"] = new_stage
    if body.op == "execute":
        act["executed_at"] = datetime.now(timezone.utc).isoformat()
        act["simulated"] = True  # clearly a sandboxed / simulated execution
    if body.op == "measure":
        act["measured_impact"] = act.get("projected_impact")
    # Compare-and-swap: only update if the action's stage hasn't been changed concurrently.
    result = await db.workspace_data.update_one(
        {"workspace_id": ws["workspace_id"],
         "actions": {"$elemMatch": {"action_id": action_id, "stage": old_stage}}},
        {"$set": {"actions": actions}})
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="Action was modified concurrently. Please refresh.")
    return {"action": act}


# ----------------------------------------------------------------------------
# Ask AHONIX (LLM analyst, streaming)
# ----------------------------------------------------------------------------
class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    session_id: str | None = Field(None, max_length=100)


def _context_summary(data: dict | None) -> str:
    if not data:
        return json.dumps({
            "status": "Awaiting merchant data ingestion",
            "message": "No workspace telemetry available yet. Integrations are awaiting connection in Settings."
        })

    meta = data.get("meta") or {}
    store_name = data.get("store_name") or meta.get("store_name") or "Merchant Store"
    currency = data.get("currency") or meta.get("currency") or "USD"
    is_demo = meta.get("is_demo", True if "ws_demo" in str(data.get("workspace_id", "")) else False)

    # Safe KPI extraction (supports id-based and label-based)
    kpis = data.get("kpis") or []
    k_map = {}
    for x in kpis:
        if isinstance(x, dict):
            if "id" in x and x["id"]:
                k_map[str(x["id"])] = x
            if "label" in x and x["label"]:
                clean_label = str(x["label"]).lower().replace(" ", "_")
                k_map[clean_label] = x

    def get_kpi_val(key, default=0.0):
        item = k_map.get(key)
        if item is not None and isinstance(item, dict):
            return item.get("value", default)
        return default

    def get_kpi_change(key, default=0.0):
        item = k_map.get(key)
        if item is not None and isinstance(item, dict):
            return item.get("change", default)
        return default

    # Profit
    p = data.get("profit") or {}
    p_insight = p.get("insight") or {}
    steps = p.get("steps") or []
    cost_breakdown = {
        s.get("label", f"step_{i}"): s.get("value", 0.0)
        for i, s in enumerate(steps) if isinstance(s, dict)
    }

    # Sales
    s = data.get("sales") or {}
    orders_count = get_kpi_val("orders", s.get("orders", 0))
    revenue_val = get_kpi_val("revenue", s.get("revenue", 0.0))
    revenue_change = get_kpi_change("revenue", 0.0)
    true_profit_val = get_kpi_val("true-profit", p.get("true_profit", 0.0))
    profit_change = get_kpi_change("true-profit", 0.0)
    profit_margin = p.get("margin", 0.0)
    aov_val = get_kpi_val("aov", s.get("aov", 0.0))

    # Inventory
    inv = data.get("inventory") or {}
    inv_items = inv.get("items") or []
    crit = inv_items[0] if inv_items and isinstance(inv_items[0], dict) else None

    # Returns
    ret = data.get("returns") or {}
    ret_by_prod = ret.get("by_product") or []
    top_ret = ret_by_prod[0] if ret_by_prod and isinstance(ret_by_prod[0], dict) else None
    return_rate_val = get_kpi_val("return-rate", ret.get("overall_rate", 0.0))

    # Marketing
    mk = data.get("marketing") or {}
    campaigns = mk.get("campaigns") or []
    roas_val = get_kpi_val("marketing-eff", mk.get("roas", 0.0))

    # Markets
    markets = data.get("markets") or []
    top_market = markets[0].get("country") if markets and isinstance(markets[0], dict) else None

    has_activity = (orders_count > 0 or revenue_val > 0 or len(campaigns) > 0 or len(inv_items) > 0)

    summary = {
        "store": store_name,
        "currency": currency,
        "is_demo_data": bool(is_demo),
        "data_status": "Active store dataset" if has_activity else "Live store initialized (Awaiting sales/order telemetry ingestion)",
        "has_recorded_activity": bool(has_activity),
        "period": "last 4 weeks vs prior 4 weeks",
        "revenue": revenue_val,
        "revenue_change_pct": revenue_change,
        "true_profit": true_profit_val,
        "profit_change_pct": profit_change,
        "profit_margin_pct": profit_margin,
        "orders": orders_count,
        "aov": aov_val,
        "return_rate_pct": return_rate_val,
        "blended_roas": roas_val,
        "best_seller": p_insight.get("best_seller"),
        "most_profitable": p_insight.get("most_profitable"),
        "best_margin_product": p_insight.get("best_margin"),
        "top_return_product": {
            "name": top_ret.get("name"),
            "rate_pct": top_ret.get("return_rate"),
            "cost": top_ret.get("cost"),
        } if top_ret else None,
        "critical_inventory": {
            "name": crit.get("name"),
            "days_left": crit.get("days_left"),
            "stockout": crit.get("stockout_date"),
            "reorder_qty": crit.get("reorder_qty"),
        } if crit else None,
        "marketing_paradox": mk.get("paradox"),
        "campaigns": [
            {"name": c.get("name"), "roas": c.get("roas"), "contribution": c.get("contribution")}
            for c in campaigns if isinstance(c, dict)
        ],
        "top_market_opportunity": top_market,
        "cost_breakdown": cost_breakdown,
    }
    return json.dumps(summary, default=str)


SYSTEM_PROMPT = """You are AHONIX, an AI commerce analyst inside the AHONIX Commerce OS. \
You are NOT a generic chatbot. You are a sharp, concise commerce analyst who reasons over the merchant's own data.

You will be given a JSON snapshot of the merchant's commerce data (which may be active demo data, or a live merchant store awaiting or synchronizing data). Answer the user's question ONLY using that data.
If has_recorded_activity is false or values are 0 / null, explicitly inform the merchant that their store currently has no recorded transactions or order activity yet, and recommend connecting their store (Shopify, Meta Ads, Google Ads) in Settings.
Under AHONIX Zero Fabrication Policy: Never invent external facts, fictional numbers, or claim certainty on unrecorded data.

Always respond in GitHub-flavoured markdown using EXACTLY these sections (omit a section only if truly not applicable):

### Answer
One or two sentences with the key conclusion.

### Evidence
- 2-4 bullet points citing specific numbers from the data.

### Reasoning
A concise 1-2 sentence explanation of *why*.

### Recommendation
The single most valuable next action.

### Expected Impact
An estimated or projected figure, clearly labelled as Estimated/Projected (or Next Step if awaiting telemetry).

Keep it tight and executive. Use the currency and figures from the snapshot. Do not use tables."""


@api.get("/ask/status")
async def ask_status(user: dict = Depends(get_current_user)):
    """Return configured AI provider information (without exposing any secret keys)."""
    return get_active_ai_provider()


@api.post("/ask")
async def ask_ahonix(body: AskBody, user: dict = Depends(get_current_user), _rl=Depends(ask_limiter)):
    # Reject whitespace-only questions
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    ws, data = await get_workspace_data(user)
    session_id = body.session_id or f"ask_{uuid.uuid4().hex[:10]}"
    try:
        context = _context_summary(data)
    except Exception as e:
        logger.exception("Error generating context summary (%s): %s", type(e).__name__, e)
        store_name = ws.get("name", "Store")
        context = json.dumps({
            "store": store_name,
            "has_recorded_activity": False,
            "data_status": "Awaiting initial data sync",
            "revenue": 0.0,
            "orders": 0,
            "true_profit": 0.0,
        })

    try:
        await db.chat_messages.insert_one({
            "user_id": user["user_id"], "workspace_id": ws["workspace_id"],
            "session_id": session_id, "role": "user", "content": body.question,
            "created_at": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.warning("Could not persist user chat message: %s", type(e).__name__)

    async def gen():
        collected = []
        try:
            async for delta in stream_analyst_response(
                question=body.question,
                context=context,
                session_id=session_id,
            ):
                collected.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except AIProviderNotConfiguredError as e:
            logger.warning("Ask AHONIX unconfigured: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except AIProviderError as e:
            logger.error("Ask AHONIX provider error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception as e:
            logger.exception("ask stream error (%s)", type(e).__name__)
            yield f"data: {json.dumps({'error': 'An internal error occurred. Please try again.'})}\n\n"

        full = "".join(collected)
        if full:
            try:
                await db.chat_messages.insert_one({
                    "user_id": user["user_id"], "workspace_id": ws["workspace_id"],
                    "session_id": session_id, "role": "assistant", "content": full,
                    "created_at": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                logger.warning("Could not persist assistant chat message: %s", type(e).__name__)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"


    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api.get("/")
async def root():
    return {"message": "AHONIX API", "status": "ok"}


@api.get("/health")
async def health():
    """Production health check endpoint for monitoring."""
    try:
        # Fast 2-second timeout so health probes never hang when database is unreachable
        await asyncio.wait_for(db.command("ping"), timeout=2.0)
        db_ok = True
    except Exception as e:
        logger.warning("Health check: MongoDB ping failed (%s)", type(e).__name__)
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "version": "2.0.0",
    }


# ----------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(shopify_integration.router)
app.include_router(meta_integration.router)
app.include_router(google_ads_integration.router)
app.include_router(billing.router)
app.include_router(stripe_integration.router)
app.include_router(marketing_cron.router)
app.include_router(api)

# --- Global exception handler — never leak internals to the client -----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path,
                 traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

# Filter empty strings and invalid wildcard origins from CORS origins
raw_cors = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip().rstrip("/") for o in raw_cors.split(",") if o.strip() and o.strip() != "*"]
frontend_origin = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
if frontend_origin and frontend_origin != "*" and frontend_origin not in _cors_origins:
    _cors_origins.append(frontend_origin)
if not _cors_origins:
    # Default safe origins for development
    _cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await asyncio.wait_for(db.command("ping"), timeout=5.0)
        await db.users.create_index("email", unique=True)
        await db.users.create_index("user_id", unique=True)
        await db.user_sessions.create_index("session_token")
        await db.workspaces.create_index("workspace_id")
        await db.workspace_data.create_index("workspace_id")
        await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=3600)
        await db.login_attempts.create_index("identifier")
        await db.shopify_connections.create_index("workspace_id", unique=True)
        await db.shopify_connections.create_index("shop")
        await db.shopify_oauth_states.create_index("state", unique=True)
        await db.shopify_oauth_states.create_index("expires_at", expireAfterSeconds=900)
        await db.shopify_synced_data.create_index("workspace_id", unique=True)
        await db.shopify_products.create_index([("workspace_id", 1), ("product_id", 1)], unique=True)
        await db.shopify_products.create_index([("workspace_id", 1), ("updated_at", -1)])
        await db.shopify_orders.create_index([("workspace_id", 1), ("order_id", 1)], unique=True)
        await db.shopify_orders.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.shopify_sync_meta.create_index("workspace_id", unique=True)
        await db.shopify_webhook_events.create_index("webhook_id", unique=True)
        await db.shopify_webhook_events.create_index("received_at", expireAfterSeconds=604800)
        await db.shopify_webhook_events.create_index([("workspace_id", 1), ("received_at", -1)])
        await db.merchant_cogs.create_index([("workspace_id", 1), ("product_id", 1)], unique=True)
        await db.merchant_cogs.create_index([("workspace_id", 1), ("updated_at", -1)])
        await db.marketing_connections.create_index([("workspace_id", 1), ("platform", 1)], unique=True)
        await db.meta_oauth_states.create_index("state", unique=True)
        await db.meta_oauth_states.create_index("expires_at", expireAfterSeconds=900)
        await db.google_ads_oauth_states.create_index("state", unique=True)
        await db.google_ads_oauth_states.create_index("expires_at", expireAfterSeconds=900)
        await db.google_auth_states.create_index("state", unique=True)
        await db.google_auth_states.create_index("expires_at", expireAfterSeconds=900)
        await db.marketing_campaigns.create_index(
            [("workspace_id", 1), ("platform", 1), ("account_id", 1), ("campaign_id", 1)],
            unique=True,
        )
        await db.marketing_daily_insights.create_index(
            [("workspace_id", 1), ("platform", 1), ("account_id", 1), ("campaign_id", 1), ("date", 1)],
            unique=True,
        )
        await db.marketing_daily_insights.create_index(
            [("workspace_id", 1), ("platform", 1), ("date", 1)],
        )
        await db.marketing_sync_meta.create_index(
            [("workspace_id", 1), ("platform", 1), ("account_id", 1)],
            unique=True,
        )
        await db.marketing_cron_locks.create_index("lock_key", unique=True)
        await db.marketing_cron_locks.create_index("expires_at", expireAfterSeconds=0)
        await auth.seed_admin()
        await seed_demo_workspace()
        logger.info("AHONIX startup complete")
    except Exception as e:
        logger.error(
            "MongoDB unavailable during startup (%s: %s). Server running in degraded mode.",
            type(e).__name__, e
        )


async def seed_demo_workspace():
    """Ensure the seeded admin has a ready-to-use demo workspace, and regenerate any
    demo analytics that were produced by an older data version."""
    from demo_data import DATA_VERSION
    # Regenerate stale demo analytics (data model / calculations changed)
    async for ws in db.workspaces.find({"is_demo": True}, {"_id": 0}):
        data = await db.workspace_data.find_one({"workspace_id": ws["workspace_id"]}, {"meta": 1, "_id": 0})
        if not data or (data.get("meta") or {}).get("version") != DATA_VERSION:
            fresh = build_workspace_analytics(store_name=ws["name"], currency=ws.get("currency", "USD"))
            fresh["workspace_id"] = ws["workspace_id"]
            await db.workspace_data.replace_one({"workspace_id": ws["workspace_id"]}, fresh, upsert=True)
            logger.info("Regenerated demo analytics for %s (v%s)", ws["name"], DATA_VERSION)

    admin_email = os.environ.get("ADMIN_EMAIL", "").lower()
    admin = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if not admin:
        return
    existing = await db.workspaces.find_one({"user_id": admin["user_id"], "is_demo": True}, {"_id": 0})
    if existing:
        if not admin.get("active_workspace_id"):
            await db.users.update_one({"user_id": admin["user_id"]},
                                      {"$set": {"active_workspace_id": existing["workspace_id"],
                                                "onboarding_completed": True}})
        return
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    await db.workspaces.insert_one({
        "workspace_id": ws_id, "user_id": admin["user_id"], "name": "Northstar Goods",
        "business_type": "DTC Brand", "channels": ["Shopify", "Amazon"],
        "size": "Scaling ($100k–$1M/mo)", "country": "United States", "currency": "USD",
        "is_demo": True, "created_at": datetime.now(timezone.utc).isoformat()})
    analytics = build_workspace_analytics(store_name="Northstar Goods", currency="USD")
    analytics["workspace_id"] = ws_id
    await db.workspace_data.insert_one({**analytics})
    await db.users.update_one({"user_id": admin["user_id"]},
                              {"$set": {"active_workspace_id": ws_id, "onboarding_completed": True}})
    logger.info("Seeded demo workspace for admin")


@app.on_event("shutdown")
async def shutdown():
    client.close()
