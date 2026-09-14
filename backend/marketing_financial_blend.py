"""AHONIX Real Marketing Financial Blending Engine.

Phase 5.5 Implementation:
- Shopify is the single source of truth for revenue (gross sales, discounts, refunds, orders).
- Eligible ad spend: Meta Ads + Google Ads with matching currency.
- Strict currency mismatch isolation: non-matching currencies are excluded from eligible spend and flagged.
- Deduplication: unique composite key (platform, account_id, campaign_id, date) prevents double counting.
- True Profit = Gross Revenue - Discounts - Refunds - Resolved COGS - Eligible Real Ad Spend.
- Blended ROAS = Gross Revenue / Eligible Real Ad Spend (denominator 0 -> 0.0).
- Blended CAC = Eligible Real Ad Spend / Shopify Order Count (denominator 0 -> 0.0).
- First-party UTM attribution: orders matched to campaigns via UTM parameters and referrer data.
- Attributed Campaign Contribution = Attributed Revenue - Attributed COGS - Campaign Spend.
- Distinct labels: CONFIGURED, IMPORTED, ATTRIBUTED, ESTIMATED.
- Platform-reported conversion value is NEVER added to Shopify revenue.
- Strict financial completeness states: FULL, PARTIAL, UNAVAILABLE.
- Explicit business calendar date timezone normalization (no midnight date shifting).
- Demo workspace (Northstar Goods) immutability preserved.
"""

import logging
from datetime import datetime, date, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("ahonix.marketing.blend")


# -----------------------------------------------------------------------------
# Timezone & Business Calendar Date Alignment Strategy
# -----------------------------------------------------------------------------
def parse_order_calendar_date(created_at_str: Optional[str]) -> Optional[str]:
    """Extract canonical business calendar date (YYYY-MM-DD) from order timestamp.
    
    Preserves the transaction's local calendar date as recorded by Shopify rather
    than shifting across midnight into UTC. For example:
    - '2026-08-20T23:59:59-04:00' -> '2026-08-20' (Local business date)
    - '2026-08-21T00:00:01-04:00' -> '2026-08-21' (Next day local business date)
    """
    if not created_at_str:
        return None
    try:
        # ISO string with 'T': the date portion before 'T' is the calendar date in that offset
        if "T" in created_at_str:
            return created_at_str.split("T")[0]
        return created_at_str[:10]
    except Exception:
        return None


def get_reporting_calendar_window(now_utc: Optional[datetime] = None, days: int = 28) -> Tuple[str, str]:
    """Calculate explicit canonical reporting window [since_date, until_date] (inclusive)."""
    now = now_utc or datetime.now(timezone.utc)
    until_date = now.date()
    since_date = until_date - timedelta(days=days - 1)
    return since_date.isoformat(), until_date.isoformat()


# -----------------------------------------------------------------------------
# First-Party UTM & Referrer Order Extraction
# -----------------------------------------------------------------------------
def extract_order_utm_data(order: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extract first-party UTM parameters and referrer signals from a Shopify order payload.
    
    Inspects:
    1. customer_journey_summary.last_visit.utm_parameters (modern Shopify API)
    2. customer_journey_summary.first_visit.utm_parameters
    3. landing_site URL query parameters
    4. referring_site URL
    5. note_attributes list
    """
    utm_data: Dict[str, Optional[str]] = {
        "utm_source": None,
        "utm_medium": None,
        "utm_campaign": None,
        "utm_id": None,
        "utm_content": None,
        "utm_term": None,
        "referring_site": None,
        "landing_site": None,
    }

    raw = order.get("raw") or {}

    # 1. Inspect customer_journey_summary
    cjs = raw.get("customer_journey_summary") or {}
    for visit_key in ("last_visit", "first_visit"):
        visit = cjs.get(visit_key) or {}
        params = visit.get("utm_parameters") or {}
        if isinstance(params, dict):
            for k in ("source", "medium", "campaign", "content", "term"):
                val = params.get(k)
                mapped_key = f"utm_{k}"
                if val and not utm_data[mapped_key]:
                    utm_data[mapped_key] = str(val).strip()
        if visit.get("referrer_url") and not utm_data["referring_site"]:
            utm_data["referring_site"] = str(visit["referrer_url"])

    # 2. Inspect landing_site query parameters
    landing_site = raw.get("landing_site") or raw.get("landing_site_ref") or order.get("landing_site")
    if landing_site:
        utm_data["landing_site"] = str(landing_site)
        try:
            parsed = urlparse(landing_site)
            q = parse_qs(parsed.query)
            for k in ("utm_source", "utm_medium", "utm_campaign", "utm_id", "utm_content", "utm_term"):
                if k in q and not utm_data[k]:
                    utm_data[k] = str(q[k][0]).strip()
        except Exception:
            pass

    # 3. Inspect referring_site
    ref_site = raw.get("referring_site") or order.get("referring_site")
    if ref_site and not utm_data["referring_site"]:
        utm_data["referring_site"] = str(ref_site)

    # 4. Inspect note_attributes
    notes = raw.get("note_attributes") or []
    if isinstance(notes, list):
        for item in notes:
            if isinstance(item, dict):
                n_name = str(item.get("name") or "").lower().strip()
                n_val = str(item.get("value") or "").strip()
                if n_name in utm_data and not utm_data[n_name]:
                    utm_data[n_name] = n_val

    return utm_data


# -----------------------------------------------------------------------------
# Ad Spend Aggregation with Currency Mismatch & Duplicate Protection
# -----------------------------------------------------------------------------
async def aggregate_marketing_ad_spend(
    db: Any,
    workspace_id: str,
    store_currency: str,
    since_date: str,
    until_date: str,
) -> Dict[str, Any]:
    """Query and aggregate daily ad spend from db.marketing_daily_insights.
    
    Guarantees:
    1. Zero double counting: enforces compound uniqueness (platform, account_id, campaign_id, date).
    2. Strict currency mismatch isolation: spend with non-matching currency is excluded from
       eligible_ad_spend and tracked separately in excluded_ad_spend.
    3. Platform separation: Meta Ads vs Google Ads broken down explicitly.
    4. Imported platform conversions are marked IMPORTED and never added to Shopify revenue.
    """
    store_curr = (store_currency or "USD").upper().strip()

    # Discover connected ad accounts from db.marketing_connections
    connections = []
    if hasattr(db, "marketing_connections") and db.marketing_connections is not None:
        conn_cursor = db.marketing_connections.find({"workspace_id": workspace_id})
        connections = await conn_cursor.to_list(10)

    connected_platforms: List[str] = []
    platform_connections: Dict[str, Dict[str, Any]] = {}
    platform_sync_statuses: Dict[str, str] = {}

    for c in connections:
        p = c.get("platform")
        if not p or p not in ("meta", "google_ads"):
            continue
        # Active connection has status connected or has account/customer selected
        is_conn = c.get("status") in ("connected", "idle", "active") or bool(
            c.get("selected_account_id") or c.get("selected_customer_id")
        )
        if is_conn:
            connected_platforms.append(p)
            platform_connections[p] = c
            platform_sync_statuses[p] = c.get("sync_status") or c.get("status") or "idle"

    # Query daily insights within the date range [since_date, until_date]
    insights_list = []
    if hasattr(db, "marketing_daily_insights") and db.marketing_daily_insights is not None:
        insights_cursor = db.marketing_daily_insights.find({
            "workspace_id": workspace_id,
            "date": {"$gte": since_date, "$lte": until_date},
        })
        insights_list = await insights_cursor.to_list(5000)

    # Deterministic deduplication across (platform, account_id, campaign_id, date)
    seen_keys: Set[Tuple[str, str, str, str]] = set()
    deduped_insights: List[Dict[str, Any]] = []

    for ins in insights_list:
        platform = ins.get("platform")
        account_id = str(ins.get("account_id") or "")
        campaign_id = str(ins.get("campaign_id") or "")
        d_val = str(ins.get("date") or "")

        if not platform or not campaign_id or not d_val:
            continue

        dedup_key = (platform, account_id, campaign_id, d_val)
        if dedup_key in seen_keys:
            logger.warning("Skipping duplicate insight row for key %s", dedup_key)
            continue
        seen_keys.add(dedup_key)
        deduped_insights.append(ins)

    eligible_ad_spend = 0.0
    excluded_ad_spend = 0.0
    spend_by_platform: Dict[str, float] = {"meta": 0.0, "google_ads": 0.0}
    excluded_by_platform: Dict[str, float] = {"meta": 0.0, "google_ads": 0.0}
    currency_mismatches: List[Dict[str, Any]] = []

    imported_conversions_total = 0.0
    imported_conversion_value_total = 0.0

    # Campaign-level breakdown for attribution
    campaign_metrics: Dict[str, Dict[str, Any]] = {}

    for ins in deduped_insights:
        platform = ins.get("platform")
        cid = str(ins.get("campaign_id"))
        cname = str(ins.get("campaign_name") or f"Campaign {cid}")
        ins_currency = (ins.get("currency") or store_curr).upper().strip()
        spend = float(ins.get("spend") or 0.0)

        conv = float(ins.get("conversions") or 0.0)
        conv_val = float(ins.get("conversions_value") or 0.0)
        impressions = int(ins.get("impressions") or 0)
        clicks = int(ins.get("clicks") or 0)

        # Check currency match against store currency
        conn = platform_connections.get(platform, {})
        conn_mismatch = conn.get("currency_mismatch", False)
        is_currency_match = (ins_currency == store_curr) and not conn_mismatch

        if is_currency_match:
            eligible_ad_spend += spend
            if platform in spend_by_platform:
                spend_by_platform[platform] += spend
        else:
            excluded_ad_spend += spend
            if platform in excluded_by_platform:
                excluded_by_platform[platform] += spend
            mismatch_entry = {
                "platform": platform,
                "account_id": ins.get("account_id"),
                "campaign_id": cid,
                "ad_currency": ins_currency,
                "store_currency": store_curr,
                "spend": spend,
                "reason": "currency_mismatch",
            }
            if mismatch_entry not in currency_mismatches:
                currency_mismatches.append(mismatch_entry)

        # Platform-reported metrics remain reference-only IMPORTED metrics
        imported_conversions_total += conv
        imported_conversion_value_total += conv_val

        # Aggregate per-campaign metrics
        camp_key = f"{platform}:{cid}"
        if camp_key not in campaign_metrics:
            campaign_metrics[camp_key] = {
                "campaign_id": cid,
                "name": cname,
                "platform": platform,
                "currency": ins_currency,
                "currency_match": is_currency_match,
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "imported_conversions": 0.0,
                "imported_conversion_value": 0.0,
            }
        campaign_metrics[camp_key]["spend"] += spend
        campaign_metrics[camp_key]["impressions"] += impressions
        campaign_metrics[camp_key]["clicks"] += clicks
        campaign_metrics[camp_key]["imported_conversions"] += conv
        campaign_metrics[camp_key]["imported_conversion_value"] += conv_val

    # Discover active campaign catalog records from db.marketing_campaigns
    catalog_camps = []
    if hasattr(db, "marketing_campaigns") and db.marketing_campaigns is not None:
        camp_cursor = db.marketing_campaigns.find({"workspace_id": workspace_id})
        catalog_camps = await camp_cursor.to_list(500)
    for cc in catalog_camps:
        p = cc.get("platform")
        cid = str(cc.get("campaign_id"))
        ckey = f"{p}:{cid}"
        if ckey in campaign_metrics:
            campaign_metrics[ckey]["name"] = cc.get("name") or campaign_metrics[ckey]["name"]
        else:
            # Campaign in catalog but 0 spend in this window
            campaign_metrics[ckey] = {
                "campaign_id": cid,
                "name": cc.get("name") or f"Campaign {cid}",
                "platform": p,
                "currency": store_curr,
                "currency_match": True,
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "imported_conversions": 0.0,
                "imported_conversion_value": 0.0,
            }

    return {
        "eligible_ad_spend": round(eligible_ad_spend, 2),
        "excluded_ad_spend": round(excluded_ad_spend, 2),
        "spend_by_platform": {k: round(v, 2) for k, v in spend_by_platform.items()},
        "excluded_by_platform": {k: round(v, 2) for k, v in excluded_by_platform.items()},
        "currency_mismatches": currency_mismatches,
        "connected_platforms": connected_platforms,
        "platform_connections": platform_connections,
        "platform_sync_statuses": platform_sync_statuses,
        "campaign_metrics": campaign_metrics,
        "imported_conversions_total": round(imported_conversions_total, 2),
        "imported_conversion_value_total": round(imported_conversion_value_total, 2),
        "insights_count": len(deduped_insights),
    }


# -----------------------------------------------------------------------------
# First-Party Shopify Order Attribution & Campaign Contribution
# -----------------------------------------------------------------------------
def perform_first_party_attribution(
    orders: List[Dict[str, Any]],
    campaign_metrics: Dict[str, Dict[str, Any]],
    cogs_map: Dict[str, Any],
    products_by_id: Dict[str, Any],
    resolve_variant_cogs_func: Any,
) -> Tuple[List[Dict[str, Any]], float, int]:
    """Match Shopify orders to advertising campaigns using first-party UTM data.
    
    Rules:
    1. Only assign orders where reliable UTM parameters (utm_campaign, utm_id, utm_source) match.
    2. Do NOT invent campaign revenue for unmatched orders.
    3. Formula:
       Attributed Campaign Contribution = Attributed Revenue - Attributed COGS - Campaign Spend
    4. When attribution is insufficient, state: 'Attribution unavailable'.
    5. Platform-reported conversion value is NEVER used as revenue.
    """
    # Build campaign lookup indexes
    id_to_key: Dict[str, str] = {}
    name_to_key: Dict[str, str] = {}

    for ckey, cdata in campaign_metrics.items():
        cid = cdata["campaign_id"].lower()
        cname = cdata["name"].lower().strip()
        id_to_key[cid] = ckey
        if cname:
            name_to_key[cname] = ckey

    # Campaign attribution buckets
    attributed_orders_by_campaign: Dict[str, List[Dict[str, Any]]] = {k: [] for k in campaign_metrics}
    total_attributed_revenue = 0.0
    total_attributed_orders_count = 0

    for o in orders:
        if o.get("financial_status") == "voided":
            continue

        utm = extract_order_utm_data(o)
        utm_campaign = (utm.get("utm_campaign") or "").lower().strip()
        utm_id = (utm.get("utm_id") or "").lower().strip()
        utm_source = (utm.get("utm_source") or "").lower().strip()
        ref_site = (utm.get("referring_site") or "").lower()

        matched_ckey: Optional[str] = None

        # 1. Match by utm_id
        if utm_id and utm_id in id_to_key:
            matched_ckey = id_to_key[utm_id]
        # 2. Match by utm_campaign as ID
        elif utm_campaign and utm_campaign in id_to_key:
            matched_ckey = id_to_key[utm_campaign]
        # 3. Match by utm_campaign as name
        elif utm_campaign and utm_campaign in name_to_key:
            matched_ckey = name_to_key[utm_campaign]
        # 4. Fallback source matching if single campaign exists for platform
        elif utm_source:
            target_platform = None
            if any(s in utm_source or s in ref_site for s in ("facebook", "meta", "instagram")):
                target_platform = "meta"
            elif any(s in utm_source or s in ref_site for s in ("google", "adwords")):
                target_platform = "google_ads"

            if target_platform:
                candidates = [k for k, v in campaign_metrics.items() if v["platform"] == target_platform]
                if len(candidates) == 1:
                    matched_ckey = candidates[0]

        if matched_ckey and matched_ckey in attributed_orders_by_campaign:
            attributed_orders_by_campaign[matched_ckey].append(o)
            total_attributed_revenue += float(o.get("total_price") or 0.0)
            total_attributed_orders_count += 1

    # Compute per-campaign Attributed Campaign Contribution
    campaigns_output: List[Dict[str, Any]] = []

    for ckey, cdata in campaign_metrics.items():
        matched_orders = attributed_orders_by_campaign.get(ckey, [])
        spend = round(cdata["spend"], 2)
        has_attribution = len(matched_orders) > 0

        if has_attribution:
            attr_rev = sum(float(o.get("total_price") or 0.0) for o in matched_orders)
            attr_cogs = 0.0
            for o in matched_orders:
                for item in o.get("line_items", []):
                    pid = item.get("product_id")
                    vid = item.get("variant_id")
                    qty = int(item.get("quantity") or 1)
                    prod = products_by_id.get(pid, {})
                    cogs_rec = cogs_map.get(pid)
                    u_cost, _, _ = resolve_variant_cogs_func(prod, vid, cogs_rec)
                    attr_cogs += round(qty * u_cost, 2)

            attr_rev = round(attr_rev, 2)
            attr_cogs = round(attr_cogs, 2)
            contribution = round(attr_rev - attr_cogs - spend, 2)
            roas = round(attr_rev / spend, 2) if spend > 0 else 0.0
            profit_eff = round(contribution / spend, 2) if spend > 0 else 0.0

            campaigns_output.append({
                "id": cdata["campaign_id"],
                "name": cdata["name"],
                "platform": "Meta Ads" if cdata["platform"] == "meta" else "Google Ads",
                "platform_raw": cdata["platform"],
                "spend": spend,
                "currency": cdata["currency"],
                "impressions": int(cdata.get("impressions") or 0),
                "clicks": int(cdata.get("clicks") or 0),
                "attribution_status": "ATTRIBUTED",
                "attribution_label": "ATTRIBUTED",
                "attributed_orders_count": len(matched_orders),
                "attributed_revenue": attr_rev,
                "attributed_cogs": attr_cogs,
                "attributed_contribution": contribution,
                "attributed_contribution_label": "Attributed Campaign Contribution",
                "contribution": contribution,
                "roas": roas,
                "profit_efficiency": profit_eff,
                "imported_conversions": round(cdata["imported_conversions"], 2),
                "imported_conversion_value": round(cdata["imported_conversion_value"], 2),
            })
        else:
            campaigns_output.append({
                "id": cdata["campaign_id"],
                "name": cdata["name"],
                "platform": "Meta Ads" if cdata["platform"] == "meta" else "Google Ads",
                "platform_raw": cdata["platform"],
                "spend": spend,
                "currency": cdata["currency"],
                "impressions": int(cdata.get("impressions") or 0),
                "clicks": int(cdata.get("clicks") or 0),
                "attribution_status": "Attribution unavailable",
                "attribution_label": "IMPORTED",
                "attributed_orders_count": 0,
                "attributed_revenue": None,
                "attributed_cogs": None,
                "attributed_contribution": None,
                "attributed_contribution_label": "Attribution unavailable",
                "contribution": 0.0,
                "roas": 0.0,
                "profit_efficiency": 0.0,
                "imported_conversions": round(cdata["imported_conversions"], 2),
                "imported_conversion_value": round(cdata["imported_conversion_value"], 2),
            })

    # Sort campaigns by spend descending
    campaigns_output.sort(key=lambda x: x["spend"], reverse=True)

    return campaigns_output, round(total_attributed_revenue, 2), total_attributed_orders_count


# -----------------------------------------------------------------------------
# Strict Financial Data Completeness Evaluation
# -----------------------------------------------------------------------------
def evaluate_financial_completeness(
    orders_count: int,
    products_count: int,
    cogs_kind: str,
    unconfigured_units: int,
    connected_platforms: List[str],
    platform_sync_statuses: Dict[str, str],
    eligible_ad_spend: float,
    currency_mismatches: List[Dict[str, Any]],
) -> str:
    """Evaluate financial data completeness state: FULL, PARTIAL, or UNAVAILABLE.
    
    Decision Rules:
    FULL:
      - Shopify revenue and orders available (orders_count > 0, products_count > 0).
      - COGS coverage complete (cogs_kind in CONFIGURED, IMPORTED and unconfigured_units == 0).
      - At least one eligible ad platform connected and successfully synced.
      - All connected ad platforms synced without error or reauth_required status.
      - No currency mismatches on active spend.
      
    PARTIAL:
      - Orders exist, but COGS coverage is incomplete (unconfigured_units > 0), OR
      - One connected ad platform failed to sync (status error, reauth_required, rate_limited), OR
      - Currency mismatch exists on an ad platform, OR
      - Ad platforms connected but 0 ad spend recorded yet, OR
      - Shopify data present but no ad accounts connected yet.
      
    UNAVAILABLE:
      - No orders recorded (orders_count == 0), OR
      - No products mapped, OR
      - Fundamental financial inputs completely missing.
    """
    if orders_count == 0 or products_count == 0:
        return "UNAVAILABLE"

    # Check for any sync errors across connected platforms
    has_sync_error = any(
        status in ("error", "reauth_required", "rate_limited")
        for status in platform_sync_statuses.values()
    )
    has_currency_mismatch = len(currency_mismatches) > 0
    cogs_complete = (cogs_kind in ("CONFIGURED", "IMPORTED")) and (unconfigured_units == 0)
    has_eligible_ad_platform = len(connected_platforms) > 0 and eligible_ad_spend > 0

    if (
        cogs_complete
        and has_eligible_ad_platform
        and not has_sync_error
        and not has_currency_mismatch
    ):
        return "FULL"

    # Incomplete COGS, partial ad sync, or currency mismatch falls into PARTIAL
    return "PARTIAL"


# -----------------------------------------------------------------------------
# Blended Executive Insights Generator
# -----------------------------------------------------------------------------
def generate_blended_insights(
    mapped_products: List[Dict[str, Any]],
    campaigns: List[Dict[str, Any]],
    spend_by_platform: Dict[str, float],
    eligible_ad_spend: float,
    cur_revenue: float,
) -> Dict[str, Any]:
    """Generate executive insights strictly grounded in underlying data.
    
    Never fabricates values when inputs are missing.
    """
    # 1. Product insights
    best_seller = "N/A"
    most_profitable = "N/A"
    best_margin = "N/A"

    if mapped_products:
        sorted_by_units = sorted(mapped_products, key=lambda x: x.get("units", 0), reverse=True)
        sorted_by_profit = sorted(mapped_products, key=lambda x: x.get("true_profit", 0.0), reverse=True)
        sorted_by_margin = sorted([p for p in mapped_products if p.get("units", 0) > 0], key=lambda x: x.get("margin", 0.0), reverse=True)

        best_seller = sorted_by_units[0].get("name", "N/A")
        most_profitable = sorted_by_profit[0].get("name", "N/A")
        best_margin = sorted_by_margin[0].get("name", "N/A") if sorted_by_margin else best_seller

    # 2. Platform spend comparison
    highest_spend_platform = "None"
    if eligible_ad_spend > 0:
        meta_sp = spend_by_platform.get("meta", 0.0)
        google_sp = spend_by_platform.get("google_ads", 0.0)
        if meta_sp > google_sp:
            highest_spend_platform = "Meta Ads"
        elif google_sp > meta_sp:
            highest_spend_platform = "Google Ads"
        else:
            highest_spend_platform = "Equal Spend"

    # 3. Campaign ROAS vs Profit efficiency paradox
    attributed_camps = [c for c in campaigns if c.get("attribution_status") == "ATTRIBUTED" and c.get("spend", 0) > 0]
    high_roas_camp = "None connected"
    high_profit_camp = "None connected"
    paradox_note = "Connect and attribute marketing channels to view revenue vs profit efficiency."

    if attributed_camps:
        sorted_roas = sorted(attributed_camps, key=lambda x: x.get("roas", 0.0), reverse=True)
        sorted_contrib = sorted(attributed_camps, key=lambda x: x.get("contribution", 0.0), reverse=True)

        high_roas_camp = sorted_roas[0]["name"]
        high_profit_camp = sorted_contrib[0]["name"]
        if high_roas_camp != high_profit_camp:
            paradox_note = f"Highest ROAS campaign ({high_roas_camp}) differs from highest profit contributor ({high_profit_camp}). Optimize for true net contribution."
        else:
            paradox_note = f"{high_roas_camp} is currently your most efficient marketing campaign across both ROAS and net contribution."

    return {
        "best_seller": best_seller,
        "most_profitable": most_profitable,
        "best_margin": best_margin,
        "mismatch": best_seller != most_profitable and len(mapped_products) > 1,
        "highest_spend_platform": highest_spend_platform,
        "high_roas_campaign": high_roas_camp,
        "high_profit_campaign": high_profit_camp,
        "paradox_note": paradox_note,
    }


# -----------------------------------------------------------------------------
# True Profit Waterfall Steps Builder
# -----------------------------------------------------------------------------
def build_true_profit_waterfall(
    cur_revenue: float,
    cur_discounts: float,
    cur_refunds: float,
    total_cogs: float,
    cogs_label: str,
    spend_by_platform: Dict[str, float],
    connected_platforms: List[str],
    true_profit: float,
    profit_label: str,
) -> List[Dict[str, Any]]:
    """Build the step-by-step waterfall distinguishing revenue, COGS, and real advertising."""
    steps = [
        {"label": "Gross Revenue", "value": round(cur_revenue, 2), "type": "total"},
        {"label": "Discounts", "value": -round(cur_discounts, 2), "type": "cost"},
        {"label": "Returns / Refunds", "value": -round(cur_refunds, 2), "type": "cost"},
        {"label": cogs_label, "value": -round(total_cogs, 2), "type": "cost"},
    ]

    has_meta = "meta" in connected_platforms
    has_google = "google_ads" in connected_platforms

    if has_meta:
        meta_spend = spend_by_platform.get("meta", 0.0)
        steps.append({
            "label": "Advertising (Meta Ads)",
            "value": -round(meta_spend, 2),
            "type": "cost",
        })

    if has_google:
        google_spend = spend_by_platform.get("google_ads", 0.0)
        steps.append({
            "label": "Advertising (Google Ads)",
            "value": -round(google_spend, 2),
            "type": "cost",
        })

    if not has_meta and not has_google:
        steps.append({
            "label": "Advertising (Unconnected)",
            "value": 0.0,
            "type": "cost",
        })

    steps.append({
        "label": profit_label,
        "value": round(true_profit, 2),
        "type": "result",
    })

    return steps
