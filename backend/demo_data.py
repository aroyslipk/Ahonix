"""
AHONIX demo analytics engine.
Generates internally consistent demo data for the fictional merchant "Northstar Goods".
All values reconcile: revenue, COGS, fees, returns and profit derive from the same
underlying product + weekly-trend model. Deterministic (no randomness) so the same
workspace always produces the same numbers.
"""
import math
from datetime import datetime, timezone, timedelta

WEEKS = 12  # weeks of history
DATA_VERSION = 2  # bump to force regeneration of stored demo analytics

# --- Product catalogue -------------------------------------------------------
# Each product drives units, revenue, cost, ad spend, returns and inventory.
PRODUCTS = [
    # name, category, price, unit_cost, base_weekly_units, return_rate, weekly_ad_spend, stock, daily_demand, channel
    ("Aurora Merino Sweater", "Apparel", 128.0, 41.0, 62, 0.14, 1450, 210, 9.2, "Shopify"),
    ("Nomad Leather Wallet", "Accessories", 64.0, 17.5, 95, 0.04, 720, 640, 13.8, "Shopify"),
    ("Drift Running Jacket", "Apparel", 149.0, 52.0, 48, 0.19, 1680, 96, 7.1, "Shopify"),
    ("Halo Wireless Earbuds", "Tech", 89.0, 34.0, 138, 0.07, 2650, 74, 20.4, "Amazon"),
    ("Terra Ceramic Mug Set", "Home", 42.0, 11.0, 74, 0.03, 210, 880, 10.6, "Shopify"),
    ("Lumen Desk Lamp", "Home", 76.0, 28.5, 41, 0.06, 430, 320, 6.0, "Amazon"),
    ("Pulse Smart Water Bottle", "Tech", 39.0, 12.5, 122, 0.05, 980, 540, 17.8, "Amazon"),
    ("Meridian Travel Backpack", "Accessories", 118.0, 39.0, 57, 0.08, 1320, 148, 8.4, "Shopify"),
    ("Vertex Yoga Mat", "Fitness", 58.0, 16.0, 68, 0.05, 540, 410, 9.8, "Shopify"),
    ("Solace Linen Bedsheet", "Home", 134.0, 47.0, 33, 0.11, 620, 128, 4.9, "Shopify"),
    ("Kinetic Resistance Bands", "Fitness", 29.0, 6.5, 156, 0.03, 410, 720, 22.6, "Amazon"),
    ("Ember Scented Candle Trio", "Home", 48.0, 13.0, 88, 0.02, 300, 560, 12.7, "Shopify"),
]

MARKETS = [
    # country, code, flag, revenue_share, conversion, competition(1-100), return_risk, shipping_complexity, existing_traffic
    ("United States", "US", "🇺🇸", 0.46, 0.031, 78, "Low", "Low", "High"),
    ("United Kingdom", "UK", "🇬🇧", 0.18, 0.028, 64, "Low", "Medium", "High"),
    ("Germany", "DE", "🇩🇪", 0.13, 0.019, 58, "Medium", "Medium", "High"),
    ("Canada", "CA", "🇨🇦", 0.11, 0.026, 49, "Low", "Low", "Medium"),
    ("Australia", "AU", "🇦🇺", 0.07, 0.024, 41, "Low", "High", "Medium"),
    ("France", "FR", "🇫🇷", 0.05, 0.016, 55, "Medium", "Medium", "Low"),
]

CAMPAIGNS = [
    # name, platform, weekly_spend(weight), roas, conv_rate, contribution_margin
    # margin varies by product mix, so ROAS alone does not determine real profit.
    ("Evergreen Prospecting", "Meta Ads", 3800, 2.9, 0.021, 0.45),
    ("Retargeting - Warm", "Meta Ads", 1600, 6.4, 0.052, 0.30),
    ("Brand Search", "Google Ads", 2100, 8.1, 0.061, 0.22),
    ("Shopping - Catalog", "Google Ads", 2400, 3.4, 0.024, 0.55),
    ("Creator Spark", "TikTok Ads", 1900, 1.8, 0.014, 0.40),
]

SHIPPING_PER_ORDER = 6.9
DISCOUNT_RATE = 0.075
PAYMENT_PCT = 0.029
PAYMENT_FIXED = 0.30
AMAZON_FEE_PCT = 0.15
ITEMS_PER_ORDER = 1.65
RESTOCK_LOSS = 0.72  # fraction of a returned unit's price lost (refund + handling - salvage)


def _week_factor(w):
    growth = 1 + 0.028 * w
    seasonal = 1 + 0.03 * math.sin(w / 2.4)
    return growth * seasonal


def _weekly_units(p_idx, w):
    base = PRODUCTS[p_idx][4]
    return base * _week_factor(w)


def _product_stats(p_idx, weeks):
    p = PRODUCTS[p_idx]
    name, cat, price, cost, base, ret, ad, stock, daily, channel = p
    units = sum(_weekly_units(p_idx, w) for w in weeks)
    units = round(units)
    revenue = units * price
    cogs = units * cost
    returned_units = round(units * ret)
    returns_cost = returned_units * price * RESTOCK_LOSS
    ad_spend = ad * len(weeks)
    orders = units / ITEMS_PER_ORDER
    shipping = orders * SHIPPING_PER_ORDER
    payment_fees = revenue * PAYMENT_PCT + orders * PAYMENT_FIXED
    marketplace_fees = revenue * AMAZON_FEE_PCT if channel == "Amazon" else 0.0
    discounts = revenue * DISCOUNT_RATE
    net_revenue = revenue - discounts - (returned_units * price)
    gross_profit = revenue - cogs
    true_profit = (revenue - discounts - cogs - ad_spend - shipping
                   - payment_fees - marketplace_fees - returns_cost)
    margin = (true_profit / revenue * 100) if revenue else 0
    return {
        "name": name, "category": cat, "channel": channel, "price": price,
        "unit_cost": cost, "units": units, "orders": round(orders),
        "revenue": round(revenue, 2), "cogs": round(cogs, 2),
        "gross_profit": round(gross_profit, 2), "true_profit": round(true_profit, 2),
        "margin": round(margin, 1), "return_rate": ret, "returned_units": returned_units,
        "returns_cost": round(returns_cost, 2), "ad_spend": round(ad_spend, 2),
        "shipping": round(shipping, 2), "payment_fees": round(payment_fees, 2),
        "marketplace_fees": round(marketplace_fees, 2), "discounts": round(discounts, 2),
        "stock": stock, "daily_demand": daily,
    }


def _health_score(s):
    # composite 0-100 across demand, profitability, returns, inventory, marketing.
    # Uses period-independent signals (daily demand, margin, return rate, cover, roas)
    # so the score is stable regardless of the reporting window.
    demand = min(100, s["daily_demand"] * 4.2)
    profit = max(0, min(100, s["margin"] * 2.2))
    returns = max(0, 100 - s["return_rate"] * 400)
    days_left = s["stock"] / s["daily_demand"] if s["daily_demand"] else 60
    inventory = max(0, min(100, days_left * 3))
    roas = s["revenue"] / s["ad_spend"] if s["ad_spend"] else 5
    marketing = max(0, min(100, roas * 18))
    score = round(demand * 0.22 + profit * 0.3 + returns * 0.2 + inventory * 0.13 + marketing * 0.15)
    return {
        "score": score,
        "breakdown": {
            "demand": round(demand), "profitability": round(profit),
            "returns": round(returns), "inventory": round(inventory),
            "marketing": round(marketing),
        },
    }


def _sum(stats, key):
    return round(sum(s[key] for s in stats), 2)


def _period_totals(weeks):
    stats = [_product_stats(i, weeks) for i in range(len(PRODUCTS))]
    revenue = _sum(stats, "revenue")
    cogs = _sum(stats, "cogs")
    ad = _sum(stats, "ad_spend")
    shipping = _sum(stats, "shipping")
    pay = _sum(stats, "payment_fees")
    mkt = _sum(stats, "marketplace_fees")
    ret = _sum(stats, "returns_cost")
    disc = _sum(stats, "discounts")
    orders = sum(s["orders"] for s in stats)
    units = sum(s["units"] for s in stats)
    returned_units = sum(s["returned_units"] for s in stats)
    true_profit = round(revenue - disc - cogs - ad - shipping - pay - mkt - ret, 2)
    return {
        "revenue": revenue, "cogs": cogs, "ad": ad, "shipping": shipping,
        "payment_fees": pay, "marketplace_fees": mkt, "returns_cost": ret,
        "discounts": disc, "orders": orders, "units": units,
        "returned_units": returned_units, "true_profit": true_profit,
        "gross_profit": round(revenue - cogs, 2),
        "aov": round(revenue / orders, 2) if orders else 0,
        "return_rate": round(returned_units / units * 100, 1) if units else 0,
        "margin": round(true_profit / revenue * 100, 1) if revenue else 0,
        "roas": round(revenue / ad, 2) if ad else 0,
    }


def _pct_change(cur, prev):
    if not prev:
        return 0.0
    return round((cur - prev) / prev * 100, 1)


def build_workspace_analytics(store_name="Northstar Goods", currency="USD"):
    cur_weeks = list(range(WEEKS - 4, WEEKS))       # last 4 weeks
    prev_weeks = list(range(WEEKS - 8, WEEKS - 4))  # prior 4 weeks
    cur = _period_totals(cur_weeks)
    prev = _period_totals(prev_weeks)

    # Per-product stats for the CURRENT period (last 4 weeks) so that every absolute
    # breakdown (sales, products, profit, returns, markets) reconciles with the KPI values.
    all_stats = [_product_stats(i, cur_weeks) for i in range(len(PRODUCTS))]
    for s in all_stats:
        s["health"] = _health_score(s)

    # weekly trend arrays
    weekly = []
    for w in range(WEEKS):
        t = _period_totals([w])
        weekly.append({
            "week": f"W{w + 1}",
            "revenue": t["revenue"], "profit": t["true_profit"],
            "orders": t["orders"], "aov": t["aov"],
        })

    # KPI cards
    kpis = [
        {"id": "revenue", "label": "Revenue", "value": cur["revenue"], "prev": prev["revenue"],
         "change": _pct_change(cur["revenue"], prev["revenue"]), "format": "currency", "kind": "ACTUAL",
         "tooltip": "Gross sales across all channels for the last 4 weeks.",
         "spark": [w["revenue"] for w in weekly[-8:]]},
        {"id": "true-profit", "label": "True Profit", "value": cur["true_profit"], "prev": prev["true_profit"],
         "change": _pct_change(cur["true_profit"], prev["true_profit"]), "format": "currency", "kind": "ACTUAL",
         "tooltip": "Revenue minus COGS, ads, shipping, fees, returns and discounts.",
         "spark": [w["profit"] for w in weekly[-8:]]},
        {"id": "orders", "label": "Orders", "value": cur["orders"], "prev": prev["orders"],
         "change": _pct_change(cur["orders"], prev["orders"]), "format": "number", "kind": "ACTUAL",
         "tooltip": "Total paid orders in the last 4 weeks.",
         "spark": [w["orders"] for w in weekly[-8:]]},
        {"id": "aov", "label": "Avg Order Value", "value": cur["aov"], "prev": prev["aov"],
         "change": _pct_change(cur["aov"], prev["aov"]), "format": "currency", "kind": "ACTUAL",
         "tooltip": "Average revenue per order.",
         "spark": [w["aov"] for w in weekly[-8:]]},
        {"id": "return-rate", "label": "Return Rate", "value": cur["return_rate"], "prev": prev["return_rate"],
         "change": _pct_change(cur["return_rate"], prev["return_rate"]), "format": "percent", "kind": "ACTUAL",
         "invert": True, "tooltip": "Share of units returned. Lower is better.",
         "spark": [round(_period_totals([w])["return_rate"], 1) for w in range(WEEKS - 8, WEEKS)]},
        {"id": "marketing-eff", "label": "Marketing Efficiency", "value": cur["roas"], "prev": prev["roas"],
         "change": _pct_change(cur["roas"], prev["roas"]), "format": "ratio", "kind": "ACTUAL",
         "tooltip": "Blended ROAS = revenue / ad spend.",
         "spark": [round(_period_totals([w])["roas"], 2) for w in range(WEEKS - 8, WEEKS)]},
    ]

    # True profit waterfall
    profit = {
        "gross_revenue": cur["revenue"],
        "steps": [
            {"label": "Gross Revenue", "value": cur["revenue"], "type": "total"},
            {"label": "Discounts", "value": -cur["discounts"], "type": "cost"},
            {"label": "Returns", "value": -cur["returns_cost"], "type": "cost"},
            {"label": "Product Cost (COGS)", "value": -cur["cogs"], "type": "cost"},
            {"label": "Shipping", "value": -cur["shipping"], "type": "cost"},
            {"label": "Advertising", "value": -cur["ad"], "type": "cost"},
            {"label": "Payment Fees", "value": -cur["payment_fees"], "type": "cost"},
            {"label": "Marketplace Fees", "value": -cur["marketplace_fees"], "type": "cost"},
            {"label": "True Profit", "value": cur["true_profit"], "type": "result"},
        ],
        "gross_profit": cur["gross_profit"],
        "contribution_margin": round(cur["revenue"] - cur["cogs"] - cur["shipping"] - cur["payment_fees"] - cur["marketplace_fees"], 2),
        "true_profit": cur["true_profit"],
        "margin": cur["margin"],
        "product_profit": sorted(
            [{"name": s["name"], "revenue": s["revenue"], "units": s["units"],
              "true_profit": s["true_profit"], "margin": s["margin"]} for s in all_stats],
            key=lambda x: x["true_profit"], reverse=True),
    }

    # Best-seller vs most-profitable insight (generated from data)
    best_seller = max(all_stats, key=lambda s: s["units"])
    most_profit = max(all_stats, key=lambda s: s["true_profit"])
    best_margin = max(all_stats, key=lambda s: s["margin"])
    profit["insight"] = {
        "best_seller": best_seller["name"],
        "most_profitable": most_profit["name"],
        "best_margin": best_margin["name"],
        "mismatch": best_seller["name"] != most_profit["name"],
    }

    # Returns intelligence
    ret_products = sorted(all_stats, key=lambda s: s["returns_cost"], reverse=True)
    top3_ret_cost = sum(s["returns_cost"] for s in ret_products[:3])
    total_ret_cost = sum(s["returns_cost"] for s in all_stats)
    returns = {
        "total_returns": sum(s["returned_units"] for s in all_stats),
        "return_rate": round(sum(s["returned_units"] for s in all_stats) / sum(s["units"] for s in all_stats) * 100, 1),
        "return_cost": round(total_ret_cost, 2),
        "top3_share": round(top3_ret_cost / total_ret_cost * 100) if total_ret_cost else 0,
        "by_product": [{"name": s["name"], "returned_units": s["returned_units"],
                        "return_rate": round(s["return_rate"] * 100, 1),
                        "cost": s["returns_cost"]} for s in ret_products],
        "by_reason": [
            {"reason": "Sizing / fit", "share": 34},
            {"reason": "Not as described", "share": 22},
            {"reason": "Quality expectations", "share": 18},
            {"reason": "Shipping damage", "share": 14},
            {"reason": "Changed mind", "share": 12},
        ],
        "by_country": [{"country": m[0], "code": m[1], "flag": m[2],
                        "share": round(m[3] * 100)} for m in MARKETS[:5]],
    }

    # Inventory forecast
    inv_items = []
    for s in all_stats:
        days_left = round(s["stock"] / s["daily_demand"], 1) if s["daily_demand"] else 999
        stockout = (datetime.now(timezone.utc) + timedelta(days=days_left)).strftime("%b %d")
        weekly_price_units = s["daily_demand"] * 7
        lost_rev_weekly = round(weekly_price_units * s["price"], 2)
        reorder = round(s["daily_demand"] * 45)  # 45-day cover
        inv_items.append({
            "name": s["name"], "category": s["category"], "stock": s["stock"],
            "daily_demand": s["daily_demand"], "days_left": days_left,
            "stockout_date": stockout, "lost_revenue_weekly": lost_rev_weekly,
            "reorder_qty": reorder, "value": round(s["stock"] * s["unit_cost"], 2),
            "status": "critical" if days_left < 10 else ("low" if days_left < 21 else "healthy"),
        })
    inv_items_sorted = sorted(inv_items, key=lambda x: x["days_left"])
    inventory = {
        "total_value": round(sum(i["value"] for i in inv_items), 2),
        "total_units": sum(i["stock"] for i in inv_items),
        "critical_count": len([i for i in inv_items if i["status"] == "critical"]),
        "low_count": len([i for i in inv_items if i["status"] == "low"]),
        "items": inv_items_sorted,
        "fast_moving": [i["name"] for i in sorted(inv_items, key=lambda x: -x["daily_demand"])[:3]],
        "slow_moving": [i["name"] for i in sorted(inv_items, key=lambda x: x["daily_demand"])[:3]],
    }

    # Marketing — total ad spend is the SAME pool that flows into True Profit (cur["ad"]),
    # distributed across campaigns by their relative weight so everything reconciles.
    total_ad = cur["ad"]
    weight_sum = sum(c[2] for c in CAMPAIGNS)
    mk_campaigns = []
    for name, plat, spend_w, roas, cvr, margin in CAMPAIGNS:
        c_spend = round(total_ad * (spend_w / weight_sum), 2)
        attr_rev = round(c_spend * roas, 2)
        # contribution uses each campaign's own margin, so a lower-ROAS campaign selling
        # higher-margin products can out-earn a higher-ROAS campaign on low-margin items.
        contribution = round(attr_rev * margin - c_spend, 2)
        prof_eff = round((attr_rev * margin) / c_spend, 2) if c_spend else 0
        cac = round(c_spend / (attr_rev / cur["aov"]), 2) if attr_rev else 0
        mk_campaigns.append({
            "name": name, "platform": plat, "spend": c_spend,
            "attributed_revenue": attr_rev, "roas": roas, "conv_rate": round(cvr * 100, 2),
            "cac": cac, "contribution": contribution, "profit_efficiency": prof_eff,
        })
    total_spend = round(sum(c["spend"] for c in mk_campaigns), 2)
    total_attr = round(sum(c["attributed_revenue"] for c in mk_campaigns), 2)
    marketing = {
        "total_spend": total_spend,                       # == profit "Advertising" line
        "attributed_revenue": total_attr,                 # modelled attribution (< total revenue)
        "blended_roas": round(cur["revenue"] / total_spend, 2) if total_spend else 0,   # == KPI (revenue / spend)
        "attributed_roas": round(total_attr / total_spend, 2) if total_spend else 0,    # attributed revenue / spend
        "blended_cac": round(total_spend / cur["orders"], 2) if cur["orders"] else 0,
        "conv_rate": 2.7,
        "campaigns": sorted(mk_campaigns, key=lambda c: c["contribution"], reverse=True),
        "by_platform": [
            {"platform": p, "spend": round(sum(c["spend"] for c in mk_campaigns if c["platform"] == p), 2),
             "revenue": round(sum(c["attributed_revenue"] for c in mk_campaigns if c["platform"] == p), 2)}
            for p in ["Meta Ads", "Google Ads", "TikTok Ads"]
        ],
    }
    # ROAS-vs-profit paradox flag
    hi_roas = max(mk_campaigns, key=lambda c: c["roas"])
    hi_profit = max(mk_campaigns, key=lambda c: c["contribution"])
    marketing["paradox"] = {
        "high_roas_campaign": hi_roas["name"],
        "high_profit_campaign": hi_profit["name"],
        "note": f"{hi_profit['name']} contributes more real profit than the highest-ROAS campaign.",
    }

    # Customers
    total_customers = round(cur["orders"] * 3.4)
    repeat_rate = 0.38
    customers = {
        "total": total_customers,
        "new": round(total_customers * 0.62),
        "repeat": round(total_customers * repeat_rate),
        "repeat_rate": round(repeat_rate * 100, 1),
        "avg_ltv": round(cur["aov"] * 2.7, 2),
        "purchase_frequency": 1.9,
        "segments": [
            {"name": "Champions", "share": 14, "ltv": round(cur["aov"] * 5.8, 2), "return_rate": 4},
            {"name": "Loyal", "share": 22, "ltv": round(cur["aov"] * 3.4, 2), "return_rate": 6},
            {"name": "Promising", "share": 27, "ltv": round(cur["aov"] * 1.8, 2), "return_rate": 9},
            {"name": "At Risk", "share": 21, "ltv": round(cur["aov"] * 1.2, 2), "return_rate": 15},
            {"name": "Churned", "share": 16, "ltv": round(cur["aov"] * 0.9, 2), "return_rate": 19},
        ],
        "by_country": [{"country": m[0], "flag": m[2], "share": round(m[3] * 100)} for m in MARKETS[:5]],
    }

    # Operations / shipping
    operations = {
        "shipments": cur["orders"],
        "avg_delivery_days": 4.2,
        "failed_delivery_rate": 1.8,
        "return_to_sender_rate": 0.9,
        "avg_shipping_cost": SHIPPING_PER_ORDER,
        "carriers": [
            {"name": "SwiftPost", "cost": 6.2, "avg_days": 3.6, "reliability": 96.4, "failure_rate": 1.2, "volume_share": 42},
            {"name": "GlobalEx", "cost": 7.8, "avg_days": 4.1, "reliability": 94.1, "failure_rate": 2.1, "volume_share": 33},
            {"name": "MetroShip", "cost": 5.4, "avg_days": 5.2, "reliability": 91.2, "failure_rate": 3.4, "volume_share": 25},
        ],
        "payments": {
            "success_rate": 97.3,
            "failure_rate": 2.7,
            "avg_fee_pct": 2.9,
            "total_fees": cur["payment_fees"],
            "methods": [
                {"method": "Card", "share": 64, "success": 97.8},
                {"method": "PayPal", "share": 19, "success": 98.9},
                {"method": "Apple/Google Pay", "share": 12, "success": 99.1},
                {"method": "Klarna", "share": 5, "success": 92.4},
            ],
        },
    }

    # Sales
    sales = {
        "revenue": cur["revenue"],
        "orders": cur["orders"],
        "aov": cur["aov"],
        "weekly": weekly,
        "by_channel": [
            {"channel": "Shopify", "revenue": _sum([s for s in all_stats if s["channel"] == "Shopify"], "revenue"),
             "orders": sum(s["orders"] for s in all_stats if s["channel"] == "Shopify")},
            {"channel": "Amazon", "revenue": _sum([s for s in all_stats if s["channel"] == "Amazon"], "revenue"),
             "orders": sum(s["orders"] for s in all_stats if s["channel"] == "Amazon")},
        ],
        "by_country": [{"country": m[0], "code": m[1], "flag": m[2],
                        "revenue": round(sum(s["revenue"] for s in all_stats) * m[3], 2)} for m in MARKETS],
        "top_products": sorted(
            [{"name": s["name"], "units": s["units"], "revenue": s["revenue"], "margin": s["margin"]}
             for s in all_stats], key=lambda x: x["revenue"], reverse=True)[:6],
    }

    # Products (with health + detail)
    products = []
    for i, s in enumerate(all_stats):
        products.append({
            "id": f"p{i+1}",
            "name": s["name"], "category": s["category"], "channel": s["channel"],
            "price": s["price"], "unit_cost": s["unit_cost"], "units": s["units"],
            "revenue": s["revenue"], "true_profit": s["true_profit"], "margin": s["margin"],
            "return_rate": round(s["return_rate"] * 100, 1), "stock": s["stock"],
            "ad_spend": s["ad_spend"], "health": s["health"],
            "weekly": [round(_weekly_units(i, w) * s["price"]) for w in range(WEEKS)],
        })

    # Markets
    markets = []
    total_rev_all = sum(s["revenue"] for s in all_stats)
    for country, code, flag, share, cvr, comp, ret_risk, ship_cx, traffic in MARKETS:
        demand = round(min(100, share * 180 + cvr * 800))
        margin_proj = round(28 - comp * 0.08 + (10 if ret_risk == "Low" else 0), 1)
        opp = round(demand * 0.4 + margin_proj * 1.4 + (20 if traffic == "High" else 10) - comp * 0.15)
        markets.append({
            "country": country, "code": code, "flag": flag,
            "opportunity_score": max(35, min(96, opp)),
            "current_revenue": round(total_rev_all * share, 2),
            "demand": demand, "competition": comp, "projected_margin": margin_proj,
            "shipping_complexity": ship_cx, "return_risk": ret_risk,
            "existing_traffic": traffic, "conversion": round(cvr * 100, 2),
        })
    markets.sort(key=lambda m: m["opportunity_score"], reverse=True)

    # AI insights (Business X-Ray) - all generated from the data above
    worst_ret = ret_products[0]
    critical_inv = inv_items_sorted[0]
    at_risk_seg = next(s for s in customers["segments"] if s["name"] == "At Risk")
    de_market = next(m for m in markets if m["code"] == "DE")

    insights = {
        "money_leaks": [
            {"id": "leak-returns", "severity": "critical", "confidence": 91,
             "title": f"Returns on {worst_ret['name']} are draining margin",
             "impact": round(worst_ret["returns_cost"] / 3, 2), "impact_kind": "ESTIMATED",
             "impact_period": "month",
             "evidence": [f"Return rate of {round(worst_ret['return_rate']*100,1)}% vs {returns['return_rate']}% store average",
                          f"{worst_ret['returned_units']} units returned in the last 4 weeks",
                          f"${round(worst_ret['returns_cost'],0):,.0f} in refund + handling cost"],
             "reasoning": "Return rate is well above the store average, and each return also incurs reverse shipping and restocking loss. Sizing and expectation gaps are the most common drivers for this category.",
             "recommendation": "Add a detailed size guide and fit photos, then re-measure return rate over 3 weeks.",
             "action": "Investigate"},
            {"id": "leak-tiktok", "severity": "warning", "confidence": 84,
             "title": f"{hi_roas['name'] if hi_roas['profit_efficiency'] < 1 else 'Creator Spark'} spend is unprofitable",
             "impact": abs(min(c["contribution"] for c in mk_campaigns)), "impact_kind": "ESTIMATED",
             "impact_period": "month",
             "evidence": ["Profit efficiency below 1.0 after COGS & fees",
                          "ROAS looks acceptable but contribution is negative",
                          "Spend is concentrated in cold prospecting"],
             "reasoning": "A ROAS above 1 does not guarantee profit once product cost, fees and returns are removed. This campaign converts but not profitably.",
             "recommendation": "Cut the campaign budget by 20% and shift toward the highest-contribution campaign.",
             "action": "Simulate"},
        ],
        "growth_opportunities": [
            {"id": "grow-de", "severity": "opportunity", "confidence": 88,
             "title": f"{de_market['country']} traffic is converting below potential",
             "impact": round(de_market["current_revenue"] * 0.35, 2), "impact_kind": "PROJECTED",
             "impact_period": "month",
             "evidence": [f"Conversion {de_market['conversion']}% vs top market ~3.1%",
                          f"Existing traffic level: {de_market['existing_traffic']}",
                          f"Projected margin {de_market['projected_margin']}%"],
             "reasoning": "Germany already has high traffic but converts below your strongest market. Closing the localization and payment gap could lift revenue without new acquisition cost.",
             "recommendation": "Localize checkout (language + local payment methods) and re-test conversion.",
             "action": "Review"},
            {"id": "grow-margin", "severity": "opportunity", "confidence": 90,
             "title": f"Push {best_margin['name']} — your best-margin product",
             "impact": round(best_margin["true_profit"] * 0.25, 2), "impact_kind": "PROJECTED",
             "impact_period": "month",
             "evidence": [f"Margin {best_margin['margin']}% (highest in catalogue)",
                          f"Only ${round(best_margin['ad_spend'],0):,.0f} ad spend in the last 4 weeks",
                          "Healthy inventory cover"],
             "reasoning": "This product has the strongest unit economics but limited marketing behind it. Reallocating spend here should convert efficiently.",
             "recommendation": "Shift 15% of prospecting budget toward this product's best-performing creative.",
             "action": "Simulate"},
        ],
        "operational_risks": [
            {"id": "risk-stockout", "severity": "critical", "confidence": 93,
             "title": f"{critical_inv['name']} may stock out in {critical_inv['days_left']} days",
             "impact": critical_inv["lost_revenue_weekly"], "impact_kind": "FORECAST",
             "impact_period": "week",
             "evidence": [f"Current stock: {critical_inv['stock']} units",
                          f"Avg daily demand: {critical_inv['daily_demand']} units",
                          f"Projected stock-out: {critical_inv['stockout_date']}"],
             "reasoning": "At the current sell-through rate, inventory runs out before a standard reorder lead time completes, risking lost sales and ranking.",
             "recommendation": f"Reorder {critical_inv['reorder_qty']} units now to maintain a 45-day cover.",
             "action": "Approve"},
        ],
        "customer_issues": [
            {"id": "cust-churn", "severity": "warning", "confidence": 79,
             "title": f"{at_risk_seg['share']}% of customers are drifting to At-Risk",
             "impact": round(customers["avg_ltv"] * total_customers * 0.05, 2), "impact_kind": "ESTIMATED",
             "impact_period": "quarter",
             "evidence": [f"At-Risk segment return rate {at_risk_seg['return_rate']}%",
                          f"Avg LTV of segment ${at_risk_seg['ltv']:,.0f}",
                          f"Repeat purchase rate {customers['repeat_rate']}%"],
             "reasoning": "A meaningful share of customers has not purchased recently and shows elevated returns, signalling churn risk and eroding LTV.",
             "recommendation": "Trigger a win-back flow with a targeted offer to the At-Risk segment.",
             "action": "Review"},
        ],
        "inventory_risks": [
            {"id": "inv-slow", "severity": "warning", "confidence": 82,
             "title": f"Overstock building on {inventory['slow_moving'][0]}",
             "impact": round(next(i['value'] for i in inv_items if i['name'] == inventory['slow_moving'][0]) * 0.15, 2),
             "impact_kind": "ESTIMATED", "impact_period": "quarter",
             "evidence": ["Lowest daily demand in catalogue",
                          "High inventory cover ratio",
                          "Capital tied up in slow stock"],
             "reasoning": "Slow-moving stock ties up working capital and storage. A modest promotion can free cash without heavy discounting.",
             "recommendation": "Run a small bundle promotion to accelerate sell-through.",
             "action": "Review"},
        ],
    }

    # Overview priorities (top 3) - pulled from insights
    priorities = [
        {**insights["money_leaks"][0], "category": "Money Leak"},
        {**insights["growth_opportunities"][0], "category": "Growth Opportunity"},
        {**insights["operational_risks"][0], "category": "Operational Risk"},
    ]

    # Daily briefing
    yday = _period_totals([WEEKS - 1])
    briefing = {
        "yesterday": {
            "revenue": round(yday["revenue"] / 7, 2),
            "true_profit": round(yday["true_profit"] / 7, 2),
            "orders": round(yday["orders"] / 7),
            "return_rate": yday["return_rate"],
            "marketing_eff": yday["roas"],
        },
        "noticed": [
            f"{de_market['country']} sessions rose while conversion stayed below your top market.",
            f"{worst_ret['name']} returns ticked up again this week.",
            f"{critical_inv['name']} inventory cover dropped to {critical_inv['days_left']} days.",
            f"{hi_profit['name']} delivered the most real profit of any campaign.",
        ],
        "recommendation": insights["operational_risks"][0],
    }

    # Action center seed items (lifecycle)
    actions = [
        {"action_id": "act-1", "title": "Reduce Creator Spark budget",
         "description": "Cut weekly TikTok prospecting spend from $1,900 to $1,520 (-20%).",
         "category": "Marketing", "stage": "Awaiting Approval",
         "current": "$1,900 / week", "recommended": "$1,520 / week",
         "projected_impact": 730, "impact_kind": "PROJECTED", "impact_period": "month",
         "confidence": 84},
        {"action_id": "act-2", "title": f"Reorder {critical_inv['name']}",
         "description": f"Place a reorder of {critical_inv['reorder_qty']} units to keep a 45-day cover.",
         "category": "Inventory", "stage": "Simulated",
         "current": f"{critical_inv['stock']} units", "recommended": f"+{critical_inv['reorder_qty']} units",
         "projected_impact": critical_inv["lost_revenue_weekly"], "impact_kind": "FORECAST",
         "impact_period": "week", "confidence": 93},
        {"action_id": "act-3", "title": f"Add size guide to {worst_ret['name']}",
         "description": "Publish a detailed size guide and fit photos to reduce sizing returns.",
         "category": "Returns", "stage": "Explained",
         "current": f"{round(worst_ret['return_rate']*100,1)}% return rate", "recommended": "Target < 10%",
         "projected_impact": round(worst_ret["returns_cost"] / 4, 2), "impact_kind": "ESTIMATED",
         "impact_period": "month", "confidence": 76},
        {"action_id": "act-4", "title": f"Boost {best_margin['name']} creative",
         "description": "Shift 15% of prospecting budget to the best-margin product.",
         "category": "Marketing", "stage": "Detected",
         "current": "No dedicated budget", "recommended": "+15% reallocation",
         "projected_impact": round(best_margin["true_profit"] * 0.25, 2), "impact_kind": "PROJECTED",
         "impact_period": "month", "confidence": 80},
        {"action_id": "act-5", "title": "Localize Germany checkout",
         "description": "Enable local payment methods and German translation at checkout.",
         "category": "Markets", "stage": "Detected",
         "current": "English checkout", "recommended": "Localized checkout",
         "projected_impact": round(de_market["current_revenue"] * 0.35, 2), "impact_kind": "PROJECTED",
         "impact_period": "month", "confidence": 71},
        {"action_id": "act-6", "title": "Win-back At-Risk customers",
         "description": "Launch a targeted win-back flow to the At-Risk segment.",
         "category": "Customers", "stage": "Explained",
         "current": f"{at_risk_seg['share']}% At-Risk", "recommended": "Re-engage top 40%",
         "projected_impact": round(customers["avg_ltv"] * total_customers * 0.03, 2),
         "impact_kind": "ESTIMATED", "impact_period": "quarter", "confidence": 68},
        {"action_id": "act-7", "title": f"Promote {inventory['slow_moving'][0]} bundle",
         "description": "Bundle slow-moving stock to free working capital.",
         "category": "Inventory", "stage": "Detected",
         "current": "Slow sell-through", "recommended": "Bundle promo",
         "projected_impact": round(next(i['value'] for i in inv_items if i['name'] == inventory['slow_moving'][0]) * 0.15, 2),
         "impact_kind": "ESTIMATED", "impact_period": "quarter", "confidence": 65},
    ]

    return {
        "store_name": store_name,
        "currency": currency,
        "kpis": kpis,
        "weekly": weekly,
        "priorities": priorities,
        "briefing": briefing,
        "profit": profit,
        "sales": sales,
        "products": products,
        "inventory": inventory,
        "returns": returns,
        "marketing": marketing,
        "customers": customers,
        "operations": operations,
        "markets": markets,
        "insights": insights,
        "actions": actions,
        "meta": {
            "orders_analyzed": sum(s["orders"] for s in all_stats),
            "period_label": "last 4 weeks",
            "weeks_of_data": WEEKS,
            "datasets": 8,
            "version": DATA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def simulate_market_entry(analytics, country, price, demand_units, inventory_units, marketing_budget):
    """Deterministic market-entry projection."""
    market = next((m for m in analytics["markets"] if m["country"].lower() == country.lower()
                   or m["code"].lower() == country.lower()), analytics["markets"][0])
    conv = market["conversion"] / 100
    est_orders = round(demand_units * conv * 4)  # over 4 weeks
    est_orders = max(est_orders, round(marketing_budget / 45))
    proj_revenue = round(est_orders * price, 2)
    margin = market["projected_margin"] / 100
    gross = proj_revenue * margin
    cac = round(marketing_budget / est_orders, 2) if est_orders else 0
    ret_risk_pct = {"Low": 0.05, "Medium": 0.1, "High": 0.16}.get(market["return_risk"], 0.08)
    returns_cost = proj_revenue * ret_risk_pct * RESTOCK_LOSS
    proj_profit = round(gross - marketing_budget - returns_cost, 2)
    required_inventory = max(inventory_units, round(est_orders * 1.2))
    breakeven_weeks = round(marketing_budget / (proj_profit / 4), 1) if proj_profit > 0 else None
    return {
        "country": market["country"], "flag": market["flag"], "code": market["code"],
        "inputs": {"price": price, "demand_units": demand_units,
                   "inventory_units": inventory_units, "marketing_budget": marketing_budget},
        "projected_revenue": proj_revenue,
        "projected_profit": proj_profit,
        "required_inventory": required_inventory,
        "estimated_orders": est_orders,
        "estimated_cac": cac,
        "estimated_return_risk": round(ret_risk_pct * 100, 1),
        "return_risk_label": market["return_risk"],
        "breakeven_weeks": breakeven_weeks,
        "opportunity_score": market["opportunity_score"],
        "main_risk": f"{market['shipping_complexity']} shipping complexity and {market['return_risk'].lower()} return risk.",
        "strategy": ("Enter with a focused hero-product launch and localized checkout."
                     if proj_profit > 0 else
                     "Start with a small test budget — current inputs project a thin or negative margin."),
    }
