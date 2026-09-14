"""Shopify Real-Time Webhooks Processing Module for AHONIX.

Phase 3.3 Implementation:
- Webhook verification using official Shopify Base64 HMAC-SHA256 over raw request body
- Concurrency-safe idempotency via atomic unique constraint on X-Shopify-Webhook-Id
- Strict workspace isolation: resolves workspace_id from verified shop connection
- Safe handling for unlinked/unknown shops (returns 200 OK without corrupting data)
- Incremental updates for:
  * products/create
  * products/update
  * products/delete
  * orders/create
  * orders/updated
  * orders/cancelled
- Live analytical refresh via aggregate_shopify_workspace_data
- Automatic webhook subscription registration helper
- Strict secret hygiene: no sensitive tokens or payload credentials logged
"""
import os
import hmac
import hashlib
import base64
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import httpx
from pymongo.errors import DuplicateKeyError

from shopify_sync import (
    normalize_shopify_product,
    normalize_shopify_order,
    aggregate_shopify_workspace_data,
    DEFAULT_API_VERSION,
)

logger = logging.getLogger("ahonix.shopify.webhooks")

SUPPORTED_TOPICS = {
    "products/create",
    "products/update",
    "products/delete",
    "orders/create",
    "orders/updated",
    "orders/cancelled",
}


def verify_shopify_webhook_hmac(raw_body: bytes, header_hmac: Optional[str], secret: Optional[str]) -> bool:
    """Verify Shopify webhook authenticity using Base64-encoded HMAC-SHA256 computed on raw request bytes."""
    if not secret or not header_hmac or not raw_body:
        return False

    computed_digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(computed_digest).decode("utf-8")
    return hmac.compare_digest(computed_hmac, header_hmac)


async def register_shopify_webhooks(
    client: httpx.AsyncClient,
    base_url: str,
    headers: Dict[str, str],
    webhook_callback_url: str,
) -> List[str]:
    """Register AHONIX webhook subscriptions with Shopify Admin API if not already registered."""
    if not webhook_callback_url or not webhook_callback_url.startswith("http"):
        logger.warning("Invalid or missing webhook callback URL (%s); skipping subscription.", webhook_callback_url)
        return []

    registered: List[str] = []
    try:
        # Check existing webhooks
        res = await client.get(f"{base_url}/webhooks.json", headers=headers)
        existing_topics = set()
        if res.status_code == 200:
            for wh in res.json().get("webhooks", []):
                if wh.get("address") == webhook_callback_url:
                    existing_topics.add(wh.get("topic"))

        for topic in SUPPORTED_TOPICS:
            if topic in existing_topics:
                registered.append(topic)
                continue

            sub_res = await client.post(
                f"{base_url}/webhooks.json",
                headers=headers,
                json={
                    "webhook": {
                        "topic": topic,
                        "address": webhook_callback_url,
                        "format": "json",
                    }
                },
            )
            if sub_res.status_code in (200, 201):
                registered.append(topic)
                logger.info("Successfully subscribed to Shopify webhook '%s'", topic)
            else:
                logger.warning(
                    "Failed to register webhook '%s' (status %d): %s",
                    topic,
                    sub_res.status_code,
                    sub_res.text[:200],
                )

    except Exception as e:
        logger.warning("Error during Shopify webhook registration: %s", str(e))

    return registered


async def process_webhook_event(
    db: Any,
    topic: str,
    shop: str,
    webhook_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Process an authenticated Shopify webhook event with atomic idempotency and workspace safety."""
    clean_shop = shop.strip().lower()
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.isoformat()

    # 1. Resolve workspace connection
    conn = await db.shopify_connections.find_one({"shop": clean_shop, "status": "connected"})
    if not conn:
        logger.warning("Received Shopify webhook '%s' for unknown or disconnected shop '%s'.", topic, clean_shop)
        return {"ok": True, "ignored": True, "reason": "Store not connected to any active workspace"}

    workspace_id = conn["workspace_id"]

    # 2. Concurrency-Safe Idempotency Check
    # Insert webhook_id atomically into db.shopify_webhook_events
    if webhook_id:
        try:
            await db.shopify_webhook_events.insert_one({
                "webhook_id": webhook_id,
                "shop": clean_shop,
                "topic": topic,
                "workspace_id": workspace_id,
                "received_at": now_str,
                "status": "processing",
            })
        except DuplicateKeyError:
            logger.info("Duplicate or concurrent webhook delivery detected for ID '%s'. Skipping.", webhook_id)
            return {"ok": True, "duplicate": True, "message": "Webhook already received or processed"}

    try:
        # 3. Handle by topic
        if topic in ("products/create", "products/update"):
            doc = normalize_shopify_product(payload, workspace_id, clean_shop, now_str)
            await db.shopify_products.replace_one(
                {"workspace_id": workspace_id, "product_id": doc["product_id"]},
                doc,
                upsert=True,
            )
            logger.info("Updated product %s for workspace %s via webhook", doc["product_id"], workspace_id)

        elif topic == "products/delete":
            shopify_id = payload.get("id")
            if shopify_id:
                product_id = f"sp_{shopify_id}"
                await db.shopify_products.delete_one({"workspace_id": workspace_id, "product_id": product_id})
                logger.info("Deleted product %s for workspace %s via webhook", product_id, workspace_id)

        elif topic in ("orders/create", "orders/updated", "orders/cancelled"):
            doc = normalize_shopify_order(payload, workspace_id, clean_shop, now_str)
            await db.shopify_orders.replace_one(
                {"workspace_id": workspace_id, "order_id": doc["order_id"]},
                doc,
                upsert=True,
            )
            logger.info("Updated order %s for workspace %s via webhook", doc["order_id"], workspace_id)

        else:
            logger.warning("Unhandled Shopify webhook topic '%s'", topic)
            return {"ok": True, "unhandled_topic": topic}

        # 4. Refresh workspace analytics snapshot
        await aggregate_shopify_workspace_data(
            db=db,
            workspace_id=workspace_id,
            store_name=conn.get("shop_name", clean_shop),
            currency=conn.get("currency", "USD"),
        )

        # 5. Mark webhook event completed
        if webhook_id:
            await db.shopify_webhook_events.update_one(
                {"webhook_id": webhook_id},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}},
            )

        return {
            "ok": True,
            "topic": topic,
            "shop": clean_shop,
            "workspace_id": workspace_id,
            "processed_at": now_str,
        }

    except Exception as e:
        logger.exception("Error processing webhook %s (%s): %s", topic, webhook_id, str(e))
        # Remove processing lock so Shopify retry can proceed
        if webhook_id:
            await db.shopify_webhook_events.delete_one({"webhook_id": webhook_id})
        raise
