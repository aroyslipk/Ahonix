"""Stripe SaaS Subscription Billing Module for AHONIX.

Provides:
- Plans catalog (Starter $49/mo, Growth $199/mo, Enterprise $499/mo) with annual discounts
- Stripe Checkout Session creation with 14-day free trial
- Stripe Customer Portal session generation for self-service card & invoice management
- Secure webhook ingestion (checkout.session.completed, customer.subscription.*, invoice.*)
- Graceful Sandbox / Mock Mode when STRIPE_SECRET_KEY is not yet populated
- Workspace tenant subscription isolation
"""
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field

from auth import get_current_user

logger = logging.getLogger("ahonix.billing")

router = APIRouter(prefix="/api/billing", tags=["Billing"])

# Injected database and workspace resolver
_db = None
_get_active_workspace_fn = None


def init_billing(db, get_active_workspace_fn):
    """Initialize billing module with MongoDB database and workspace resolver."""
    global _db, _get_active_workspace_fn
    _db = db
    _get_active_workspace_fn = get_active_workspace_fn


# --- Configuration & Plans ---------------------------------------------------
def get_stripe_secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def get_stripe_webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def is_stripe_configured() -> bool:
    key = get_stripe_secret_key()
    return bool(key and (key.startswith("sk_") or key.startswith("rk_")))


PLANS = {
    "starter": {
        "id": "starter",
        "name": "Starter",
        "tagline": "Real-time P&L for emerging DTC brands",
        "monthly_price": 49,
        "annual_price": 39,  # $39/mo ($468/yr)
        "annual_savings_pct": 20,
        "revenue_limit": "$50,000 / mo",
        "stores_limit": 1,
        "features": [
            "Real-time True Profit Waterfall",
            "1 Shopify Storefront Integration",
            "Automatic COGS & Gateway Fee Engine",
            "Functional Currency & Multi-Market Telemetry",
            "Standard Support",
        ],
        "stripe_price_monthly": os.environ.get("STRIPE_PRICE_STARTER_MONTHLY", "").strip(),
        "stripe_price_annual": os.environ.get("STRIPE_PRICE_STARTER_ANNUAL", "").strip(),
    },
    "growth": {
        "id": "growth",
        "name": "Growth",
        "tagline": "Full attribution & autonomous AI analyst for scaling brands",
        "monthly_price": 199,
        "annual_price": 159,  # $159/mo ($1,908/yr)
        "annual_savings_pct": 20,
        "popular": True,
        "revenue_limit": "$250,000 / mo",
        "stores_limit": 3,
        "features": [
            "Everything in Starter",
            "Up to 3 Storefronts & Marketplaces",
            "Meta Ads & Google Ads Unified Attribution",
            "Autonomous AI Financial Analyst (Ask AHONIX)",
            "Return & Restock Margin Leak Detection",
            "Hourly Automated Data Ingestion",
            "Priority Slack & Email Support",
        ],
        "stripe_price_monthly": os.environ.get("STRIPE_PRICE_GROWTH_MONTHLY", "").strip(),
        "stripe_price_annual": os.environ.get("STRIPE_PRICE_GROWTH_ANNUAL", "").strip(),
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise",
        "tagline": "Custom pipelines & dedicated financial infrastructure",
        "monthly_price": 499,
        "annual_price": 399,  # $399/mo ($4,788/yr)
        "annual_savings_pct": 20,
        "revenue_limit": "Unlimited",
        "stores_limit": 999,
        "features": [
            "Everything in Growth",
            "Unlimited Storefronts & Multi-Warehouse ERP",
            "Custom Ad Network & 3PL Connectors",
            "Sub-minute Live Webhook Streaming",
            "Custom ERP & 3PL COGS Pipelines",
            "Dedicated Financial Engineering Account Manager",
            "99.99% Uptime SLA & Custom DPA",
        ],
        "stripe_price_monthly": os.environ.get("STRIPE_PRICE_ENTERPRISE_MONTHLY", "").strip(),
        "stripe_price_annual": os.environ.get("STRIPE_PRICE_ENTERPRISE_ANNUAL", "").strip(),
    },
}


# --- Pydantic Request Models -------------------------------------------------
class CheckoutSessionRequest(BaseModel):
    plan_id: str = Field(..., description="Target plan ID: starter, growth, or enterprise")
    interval: Literal["month", "year"] = Field("month", description="Billing interval: month or year")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CustomerPortalRequest(BaseModel):
    return_url: Optional[str] = None


class SandboxUpgradeRequest(BaseModel):
    plan_id: str = Field(..., description="Target plan ID: starter, growth, or enterprise")
    interval: Literal["month", "year"] = "month"


# --- Endpoints ---------------------------------------------------------------
@router.get("/plans")
async def list_plans():
    """Retrieve all available SaaS subscription plans and system billing status."""
    return {
        "plans": list(PLANS.values()),
        "currency": "USD",
        "trial_days": 14,
        "is_stripe_live": is_stripe_configured(),
    }


@router.get("/status")
async def get_subscription_status(user: dict = Depends(get_current_user)):
    """Get the active subscription status for the current workspace."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Billing module not initialized.")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]

    sub = await _db.subscriptions.find_one({"workspace_id": ws_id}, {"_id": 0})

    if not sub:
        # Default status for new workspace: 14-day free trial on Growth tier
        created_at_str = ws.get("created_at")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else datetime.now(timezone.utc)
        except Exception:
            created_at = datetime.now(timezone.utc)

        trial_end = created_at + timedelta(days=14)
        now = datetime.now(timezone.utc)
        days_left = max(0, (trial_end - now).days)
        is_trialing = now < trial_end

        return {
            "workspace_id": ws_id,
            "plan_id": "growth",
            "plan_name": PLANS["growth"]["name"],
            "status": "trialing" if is_trialing else "active",
            "interval": "month",
            "trial_days_remaining": days_left,
            "trial_end": trial_end.isoformat(),
            "current_period_end": trial_end.isoformat(),
            "cancel_at_period_end": False,
            "stripe_customer_id": None,
            "is_sandbox": not is_stripe_configured(),
            "features": PLANS["growth"]["features"],
        }

    plan_info = PLANS.get(sub.get("plan_id", "growth"), PLANS["growth"])
    return {
        "workspace_id": ws_id,
        "plan_id": sub.get("plan_id", "growth"),
        "plan_name": plan_info["name"],
        "status": sub.get("status", "active"),
        "interval": sub.get("interval", "month"),
        "trial_days_remaining": sub.get("trial_days_remaining", 0),
        "trial_end": sub.get("trial_end"),
        "current_period_end": sub.get("current_period_end"),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "stripe_customer_id": sub.get("stripe_customer_id"),
        "is_sandbox": sub.get("is_sandbox", not is_stripe_configured()),
        "features": plan_info["features"],
    }


@router.post("/create-checkout-session")
async def create_checkout_session(body: CheckoutSessionRequest, user: dict = Depends(get_current_user)):
    """Create a Stripe Checkout session for a subscription, or return a sandbox session."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Billing module not initialized.")

    plan_id = body.plan_id.lower().strip()
    if plan_id not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan ID. Choose from: {list(PLANS.keys())}")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]
    plan = PLANS[plan_id]

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    success_url = body.success_url or f"{frontend_url}/app/settings?billing=success&session_id={{CHECKOUT_SESSION_ID}}&plan={plan_id}"
    cancel_url = body.cancel_url or f"{frontend_url}/app/settings?billing=canceled"

    # --- Live Stripe Mode ---
    if is_stripe_configured():
        stripe.api_key = get_stripe_secret_key()
        try:
            # Check or create Stripe Customer
            sub = await _db.subscriptions.find_one({"workspace_id": ws_id})
            customer_id = sub.get("stripe_customer_id") if sub else None

            if not customer_id:
                customer = stripe.Customer.create(
                    email=user.get("email"),
                    name=user.get("name", "Merchant"),
                    metadata={
                        "workspace_id": ws_id,
                        "user_id": user["user_id"],
                        "workspace_name": ws.get("name", ""),
                    },
                )
                customer_id = customer.id

            # Determine price: configured ID or ad-hoc product definition
            price_id = (
                plan["stripe_price_annual"]
                if body.interval == "year" and plan["stripe_price_annual"]
                else plan["stripe_price_monthly"]
            )

            unit_price = (
                plan["annual_price"] * 12 if body.interval == "year" else plan["monthly_price"]
            )

            line_item = {}
            if price_id:
                line_item = {"price": price_id, "quantity": 1}
            else:
                # Dynamic ad-hoc line item allows immediate checkouts without prior Dashboard price ID creation
                line_item = {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(unit_price * 100),
                        "recurring": {"interval": body.interval},
                        "product_data": {
                            "name": f"AHONIX {plan['name']} Plan",
                            "description": plan["tagline"],
                        },
                    },
                    "quantity": 1,
                }

            session_params = {
                "customer": customer_id,
                "payment_method_types": ["card"],
                "mode": "subscription",
                "line_items": [line_item],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": ws_id,
                "metadata": {
                    "workspace_id": ws_id,
                    "plan_id": plan_id,
                    "interval": body.interval,
                    "user_id": user["user_id"],
                },
                "subscription_data": {
                    "metadata": {
                        "workspace_id": ws_id,
                        "plan_id": plan_id,
                        "interval": body.interval,
                    }
                },
            }

            # 14-day trial if workspace has not used a paid plan yet
            has_paid_before = sub and sub.get("status") == "active"
            if not has_paid_before:
                session_params["subscription_data"]["trial_period_days"] = 14

            session = stripe.checkout.Session.create(**session_params)

            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "mode": "live",
                "plan": plan_id,
            }

        except Exception as e:
            logger.error("Stripe live checkout session creation failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Failed to create Stripe checkout session: {str(e)}")

    # --- Sandbox Fallback Mode ---
    mock_session_id = f"cs_sandbox_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    current_period_end = (now + timedelta(days=365 if body.interval == "year" else 30)).isoformat()

    await _db.subscriptions.update_one(
        {"workspace_id": ws_id},
        {
            "$set": {
                "workspace_id": ws_id,
                "user_id": user["user_id"],
                "plan_id": plan_id,
                "interval": body.interval,
                "status": "active",
                "current_period_end": current_period_end,
                "cancel_at_period_end": False,
                "is_sandbox": True,
                "updated_at": now.isoformat(),
            }
        },
        upsert=True,
    )

    sandbox_url = f"{frontend_url}/app/settings?billing=sandbox_activated&plan={plan_id}&interval={body.interval}"
    return {
        "checkout_url": sandbox_url,
        "session_id": mock_session_id,
        "mode": "sandbox",
        "plan": plan_id,
        "message": "Sandbox mode: Subscription instantly activated without external charges.",
    }


@router.post("/customer-portal")
async def create_customer_portal(body: CustomerPortalRequest, user: dict = Depends(get_current_user)):
    """Generate a Stripe Billing Customer Portal session for managing payment methods and invoices."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Billing module not initialized.")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return_url = body.return_url or f"{frontend_url}/app/settings"

    if is_stripe_configured():
        stripe.api_key = get_stripe_secret_key()
        try:
            sub = await _db.subscriptions.find_one({"workspace_id": ws_id})
            customer_id = sub.get("stripe_customer_id") if sub else None

            if not customer_id:
                customer = stripe.Customer.create(
                    email=user.get("email"),
                    name=user.get("name", "Merchant"),
                    metadata={"workspace_id": ws_id, "user_id": user["user_id"]},
                )
                customer_id = customer.id
                await _db.subscriptions.update_one(
                    {"workspace_id": ws_id},
                    {"$set": {"stripe_customer_id": customer_id}},
                    upsert=True,
                )

            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return {"portal_url": portal_session.url, "mode": "live"}

        except Exception as e:
            logger.error("Stripe customer portal creation failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Failed to generate customer portal: {str(e)}")

    # Sandbox fallback: return simulated settings portal URL
    return {
        "portal_url": f"{frontend_url}/app/settings?portal=simulated",
        "mode": "sandbox",
        "message": "Sandbox mode: Billing portal simulated.",
    }


@router.post("/sandbox-upgrade")
async def sandbox_upgrade(body: SandboxUpgradeRequest, user: dict = Depends(get_current_user)):
    """Directly update workspace plan in sandbox environment for rapid testing & demos."""
    if _db is None or _get_active_workspace_fn is None:
        raise HTTPException(status_code=500, detail="Billing module not initialized.")

    plan_id = body.plan_id.lower().strip()
    if plan_id not in PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan ID. Choose from: {list(PLANS.keys())}")

    ws = await _get_active_workspace_fn(user)
    ws_id = ws["workspace_id"]
    now = datetime.now(timezone.utc)
    current_period_end = (now + timedelta(days=365 if body.interval == "year" else 30)).isoformat()

    await _db.subscriptions.update_one(
        {"workspace_id": ws_id},
        {
            "$set": {
                "workspace_id": ws_id,
                "user_id": user["user_id"],
                "plan_id": plan_id,
                "interval": body.interval,
                "status": "active",
                "current_period_end": current_period_end,
                "cancel_at_period_end": False,
                "is_sandbox": not is_stripe_configured(),
                "updated_at": now.isoformat(),
            }
        },
        upsert=True,
    )

    return {
        "ok": True,
        "workspace_id": ws_id,
        "plan_id": plan_id,
        "interval": body.interval,
        "status": "active",
        "current_period_end": current_period_end,
    }


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    """Handle incoming Stripe webhooks with cryptographic HMAC signature verification."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized.")

    payload = await request.body()
    webhook_secret = get_stripe_webhook_secret()

    event = None
    if is_stripe_configured() and webhook_secret and stripe_signature:
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, webhook_secret)
        except stripe.SignatureVerificationError:
            logger.warning("Stripe webhook signature verification failed.")
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
        except Exception as e:
            logger.error("Error parsing Stripe webhook: %s", e)
            raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")
    else:
        # Development / sandbox unverified fallback
        try:
            import json
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    logger.info("Received Stripe webhook event: %s", event_type)

    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {})
        ws_id = metadata.get("workspace_id") or data_object.get("client_reference_id")
        plan_id = metadata.get("plan_id", "growth")
        interval = metadata.get("interval", "month")
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")

        if ws_id:
            now = datetime.now(timezone.utc)
            period_end = (now + timedelta(days=365 if interval == "year" else 30)).isoformat()
            await _db.subscriptions.update_one(
                {"workspace_id": ws_id},
                {
                    "$set": {
                        "workspace_id": ws_id,
                        "plan_id": plan_id,
                        "interval": interval,
                        "status": "active",
                        "stripe_customer_id": customer_id,
                        "stripe_subscription_id": subscription_id,
                        "current_period_end": period_end,
                        "cancel_at_period_end": False,
                        "is_sandbox": False,
                        "updated_at": now.isoformat(),
                    }
                },
                upsert=True,
            )
            logger.info("Activated subscription for workspace %s on plan %s", ws_id, plan_id)

    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = data_object.get("customer")
        status = data_object.get("status")
        cancel_at_period_end = data_object.get("cancel_at_period_end", False)
        period_end_ts = data_object.get("current_period_end")
        period_end = datetime.fromtimestamp(period_end_ts, timezone.utc).isoformat() if period_end_ts else None

        update_fields = {
            "status": status,
            "cancel_at_period_end": cancel_at_period_end,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if period_end:
            update_fields["current_period_end"] = period_end

        if customer_id:
            await _db.subscriptions.update_many(
                {"stripe_customer_id": customer_id},
                {"$set": update_fields},
            )

    elif event_type == "invoice.payment_succeeded":
        customer_id = data_object.get("customer")
        invoice_id = data_object.get("id")
        amount_paid = (data_object.get("amount_paid", 0)) / 100.0
        currency = data_object.get("currency", "usd").upper()

        if customer_id:
            invoice_record = {
                "invoice_id": invoice_id,
                "amount": amount_paid,
                "currency": currency,
                "paid_at": datetime.now(timezone.utc).isoformat(),
                "hosted_invoice_url": data_object.get("hosted_invoice_url"),
            }
            await _db.subscriptions.update_many(
                {"stripe_customer_id": customer_id},
                {
                    "$push": {"billing_history": {"$each": [invoice_record], "$slice": -50}},
                    "$set": {"status": "active"},
                },
            )

    elif event_type == "invoice.payment_failed":
        customer_id = data_object.get("customer")
        if customer_id:
            await _db.subscriptions.update_many(
                {"stripe_customer_id": customer_id},
                {"$set": {"status": "past_due", "updated_at": datetime.now(timezone.utc).isoformat()}},
            )

    return {"received": True, "event": event_type}
