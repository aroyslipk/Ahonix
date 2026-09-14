# AHONIX — AI Commerce OS

> **Don't just see your data. Know what to do next.**

AHONIX is an AI-powered command center for e-commerce merchants. It connects commerce data across sales, profit, inventory, marketing, returns and operations — then uses AI to find money leaks, growth opportunities and operational risks, explain *why* they matter, and recommend what to do next, with projected financial impact.

---

## The Problem

Online merchants have dashboards everywhere — Shopify analytics, Amazon reports, Google Ads, shipping tools — but no single system that answers the critical question: *"What should I actually do next to make more money?"*

AHONIX closes that gap with an **intelligence loop**: Connect → Understand → Detect → Explain → Simulate → Recommend → Approve → Execute → Measure.

---

## Major Features

| Feature | Description |
|---|---|
| **Overview / Command Center** | Daily AI briefing, KPI cards with sparklines, revenue trends, AI priority alerts |
| **AI Intelligence (Business X-Ray)** | Full-body scan of the business with animated radar sequence. Surfaces money leaks, growth opportunities, operational risks, customer issues, and inventory risks — each with confidence scores, evidence, reasoning and recommendations |
| **True Profit Engine** | Shows real profit after ALL hidden costs: COGS, advertising, shipping, returns, discounts, payment fees, marketplace fees. Interactive waterfall chart and product-level profitability table |
| **Sales Analytics** | Revenue, orders, AOV. Trend charts (switchable metric). Sales by channel (Shopify / Amazon). Revenue by country (donut). Top products table |
| **Product Intelligence** | 12 products with a composite Health Score (0–100) across 5 dimensions: demand, profitability, returns, inventory, marketing. Product detail pages with AI recommendations |
| **Inventory Forecast** | Stock-out predictions per product with days-left countdown, reorder recommendations, and critical/low/healthy status badges |
| **Marketing Intelligence** | ROAS vs profit efficiency analysis. Highlights the **"Highest ROAS ≠ Most Profit"** paradox. Campaign-level spend, ROAS, profit efficiency and contribution table |
| **Customers & LTV** | RFM-style segments (Champions, Loyal, Promising, At Risk, Churned). Lifetime value, repeat rate, purchase frequency. Churn risk and retention insights |
| **Operations** | Three tabs — Shipping (carrier comparison), Payments (method analysis, fee breakdown), Returns (cost analysis, top return drivers by reason and product) |
| **Markets & Launch Simulator** | 6 international market opportunity cards. Interactive simulator: choose country, set price/demand/inventory/budget → get projected revenue, profit, break-even, risk and strategy |
| **Action Center** | 7 actionable AI recommendations with a full lifecycle: Detected → Explained → Simulated → Awaiting Approval → Approved → Executed → Measured. **All execution is sandboxed** — no live external actions are performed |
| **Ask AHONIX ✦** | AI commerce analyst powered by Claude Sonnet 4.6 via SSE streaming. Grounded on the workspace's data snapshot. Answers include structured evidence, reasoning, recommendations and expected impact |
| **Settings** | Workspace management (create, switch, list). Integration architecture (Shopify, Amazon, Stripe, Meta Ads, Google Ads, TikTok Ads, ShipStation) — UI-ready but not connected in demo mode |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, JavaScript (CRA via craco), TailwindCSS v3, shadcn/ui, Recharts, Axios, TanStack Query v5 |
| **Backend** | Python 3, FastAPI, Motor (async MongoDB driver), Uvicorn |
| **Database** | MongoDB (collections: users, user_sessions, workspaces, workspace_data, chat_messages, password_reset_tokens, login_attempts) |
| **AI** | Claude Sonnet 4.6 via Emergent LLM key (Server-Sent Events streaming) |
| **Fonts** | Plus Jakarta Sans (headings), Inter (body), JetBrains Mono (metrics) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React 19)                  │
│   CRA/craco · Tailwind · shadcn/ui · Recharts · Axios   │
│                                                         │
│   Pages: Landing, Login, Register, Onboarding, Overview, │
│   AI Intelligence, True Profit, Sales, Products (+Detail)│
│   Inventory, Marketing, Customers, Operations, Markets,  │
│   Action Center, Settings                                │
│   Components: AskAhonix (SSE drawer), Sidebar, TopBar   │
└──────────────────────┬──────────────────────────────────┘
                       │  Axios → /api (withCredentials)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend (FastAPI / Uvicorn)             │
│                                                         │
│   server.py — API routes, workspace helpers              │
│   auth.py   — JWT + Google OAuth, session management     │
│   demo_data.py — Deterministic analytics engine          │
│                                                         │
│   Auth: httpOnly JWT cookies (access + refresh)          │
│         Emergent Google OAuth (session_token cookie)      │
│   Data: Per-user workspace isolation on every endpoint    │
└──────────────────────┬──────────────────────────────────┘
                       │  Motor (async)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                       MongoDB                            │
│   users · workspaces · workspace_data · chat_messages    │
│   user_sessions · password_reset_tokens · login_attempts │
└─────────────────────────────────────────────────────────┘
```

---

## Demo Data Model

AHONIX ships with a self-contained demo workspace called **"Northstar Goods"** — a fictional DTC brand selling 12 products across Shopify and Amazon.

- **Deterministic**: Same inputs always produce the same outputs (no randomness)
- **Internally consistent**: Revenue, COGS, fees, returns and profit all derive from the same 12-product × 12-week model and reconcile mathematically
- **Comprehensive**: 12 products, 6 markets, 5 ad campaigns, 3 shipping carriers, 4 payment methods, 5 customer segments, 5 return reasons
- **Value-labelled**: Every metric is tagged as ACTUAL, ESTIMATED, PROJECTED, FORECAST or DEMO so it is always clear what kind of figure the user is seeing

The demo engine lives in `backend/demo_data.py`. Analytics are generated once per workspace creation and stored in the `workspace_data` collection. Data auto-regenerates when `DATA_VERSION` changes.

---

## Authentication

- **Email/password** — JWT via httpOnly cookies (`access_token` 60 min, `refresh_token` 7 days, HS256)
- **Google OAuth** — Via Emergent platform, exchanges `session_id` for a persistent `session_token` cookie
- **Brute-force protection** — Account locked for 15 minutes after 5 failed login attempts
- **Password reset** — Token-based architecture (token logged to server console in demo; no email service connected)
- **Demo credentials** — `alex@northstargoods.com` / `Ahonix2026!` (prefilled on the login page for easy access)

---

## Ask AHONIX ✦

The AI analyst is a real conversational interface powered by Claude Sonnet 4.6:

- **SSE streaming** — Responses stream token-by-token via Server-Sent Events
- **Context-grounded** — Receives a JSON snapshot of the workspace's analytics (sales, profit, inventory, marketing, returns) as system context
- **Structured output** — Responses include: Answer, Evidence, Reasoning, Recommendation, Expected Impact
- **Session persistence** — Chat messages are stored in MongoDB
- **Quick prompts** — 6 pre-built questions for common merchant queries
- **Accessible everywhere** — Global "Ask AHONIX" button in the top bar, plus per-insight "Ask AHONIX" buttons throughout the app

---

## Action Center — Sandbox Behavior

The Action Center presents AI-recommended actions with a full lifecycle:

```
Detected → Explained → Simulated → Awaiting Approval → Approved → Executed → Measured
```

**Important:** All execution is sandboxed. When an action is "Executed," AHONIX performs a simulated execution — **no live external systems are modified.** This is clearly communicated in the UI with:
- A persistent "Sandboxed — no live external actions" badge
- A yellow warning after execution: "Simulated execution — no live integration was changed"
- The `simulated: true` flag on all executed actions

---

## How to Run Locally

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB (local instance or MongoDB Atlas)
- A `.env` file in `backend/` with the required environment variables

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001
```

Required environment variables in `backend/.env`:
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
JWT_SECRET=<your-secret>
ADMIN_EMAIL=alex@northstargoods.com
ADMIN_PASSWORD=Ahonix2026!
EMERGENT_LLM_KEY=<your-key>  # Required for Ask AHONIX
```

### Frontend

```bash
cd frontend
yarn install
yarn dev
```

The frontend runs on `http://localhost:3000` and proxies API requests to the backend.

Set `REACT_APP_BACKEND_URL=http://localhost:8001` in `frontend/.env` for local development.

### Tests

```bash
cd backend
python -m pytest tests/ -v
```

51 tests covering auth, workspace isolation, data reconciliation, action lifecycle, and security.

---

---

## Shopify Integration (Phase 3.1 Foundation)

AHONIX supports real merchant store connectivity through Shopify OAuth:

- **OAuth 2.0 Flow**: Direct merchant authorization via Shopify Partner App credentials.
- **Read-Only Scopes**: Only `read_products` and `read_orders` scopes are requested. AHONIX never performs write operations to a merchant's store.
- **Official API Version**: Configured to `2026-07` (the latest supported stable release per Shopify's quarterly release schedule), configurable via `SHOPIFY_API_VERSION`.
- **Token Security**: Shopify access tokens are symmetrically encrypted at rest using AES/Fernet with keys derived from `JWT_SECRET`. Tokens are never exposed to the frontend or logged.
- **Read-Only Verification Sync**: Verifies store connectivity, retrieves store profile details, and fetches sample products and orders to prove integration health.
- **Clean Workspace Separation**: Demo workspaces (`Northstar Goods`) continue to use generated data without interference. Shopify connections are attached strictly to live workspaces.

### Shopify Environment Variables:
```
SHOPIFY_API_KEY=<your-shopify-client-id>
SHOPIFY_API_SECRET=<your-shopify-client-secret>
SHOPIFY_SCOPES=read_products,read_orders
SHOPIFY_API_VERSION=2026-07
```

---

## What Is and Isn't Connected

| Capability | Status |
|---|---|
| Auth (email + Google OAuth) | ✅ Fully functional |
| Demo data engine | ✅ Fully functional |
| All 14 analytics pages | ✅ Fully functional |
| Ask AHONIX (AI analyst) | ✅ Functional (requires `EMERGENT_LLM_KEY`) |
| Action Center lifecycle | ✅ Functional (sandboxed) |
| Market launch simulator | ✅ Functional |
| Shopify Integration (Phase 3.1) | ✅ OAuth + Read-Only Store Verification live |
| Other Integrations (Amazon, Stripe, Ads, etc.) | ❌ Architecture only — planned for future phases |
| Password reset email delivery | ❌ Token generated, no email sent |

---

## License

Proprietary. © 2026 AHONIX.
