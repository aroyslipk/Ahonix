# AHONIX — The AI Commerce OS · PRD

## Original problem statement
Build a production-quality full-stack "AI Commerce OS" for online merchants. Central loop:
Connect → Understand → Detect → Explain → Simulate → Recommend → Approve → Execute → Measure.
Primary question: "What should I do next?". Must feel like an intelligent business command center,
not a BI dashboard or generic chatbot.

## Architecture
- **Backend**: FastAPI + MongoDB (motor). Modules: `server.py` (workspace + analytics + actions + Ask SSE),
  `auth.py` (unified JWT + Emergent Google OAuth, UUID `user_id` canonical), `demo_data.py`
  (internally-consistent demo analytics engine + market-entry simulator).
- **Frontend**: React (CRA/craco) + Tailwind + shadcn/ui + Recharts + framer. `@`→`src` alias.
  Contexts: Auth, Workspace, UI(Ask drawer). AppLayout (sidebar + topbar + mobile bottom nav + Ask drawer).
- **AI**: Ask AHONIX uses Claude Sonnet 4.6 via Emergent Universal Key, SSE streaming, grounded on a
  JSON snapshot of the workspace so answers cite real (demo) figures.
- **Data model**: users, user_sessions, workspaces, workspace_data (full analytics snapshot),
  chat_messages, password_reset_tokens, login_attempts. Per-user isolation enforced on every endpoint.

## User personas
- DTC brand owner / marketplace seller / agency wanting to know what to fix and grow next.

## Core requirements (static)
- Auth (JWT + Google), protected routes, per-user workspace isolation, password reset.
- 8-step onboarding → Demo Workspace (Northstar Goods) or connect-real (empty states).
- Sections: Overview, AI Intelligence (Business X-Ray), True Profit, Sales, Products (health score),
  Inventory (forecast), Marketing (ROAS vs profit), Customers (LTV/segments), Operations
  (shipping/payments/returns), Markets (opportunities + launch simulator), Action Center, Settings.
- Value labelling: ACTUAL / ESTIMATED / PROJECTED / FORECAST / DEMO. AI confidence badges.
- No fake execution: actions run in a clearly-labelled sandboxed layer.

## Implemented (2026-06)
- ✅ Unified auth (email/password JWT + Emergent Google), brute-force lockout, reset architecture.
- ✅ Onboarding wizard + demo/real workspace creation; admin auto-seeded with demo workspace.
- ✅ Internally-consistent demo analytics (revenue/COGS/fees/returns/profit reconcile).
- ✅ Overview command center (KPIs, sparklines, daily briefing, AI priorities).
- ✅ Business X-Ray scan animation + grouped findings with confidence/impact.
- ✅ True Profit waterfall + product profitability + best-seller≠most-profitable insight.
- ✅ Sales, Products + detail (health rings), Inventory forecast, Marketing (ROAS vs profit paradox +
  Content→Revenue), Customers, Operations tabs, Markets + Launch Simulator.
- ✅ Action Center lifecycle (Detected→…→Measured) with sandboxed execution.
- ✅ Ask AHONIX streaming analyst (Claude Sonnet 4.6). Responsive desktop/tablet/mobile.
- ✅ Tested: 30/30 backend pytest + all critical frontend flows (100%).

## Backlog (P1/P2)
- P1: Real integrations (Shopify/Stripe/Meta/Google Ads) behind the existing architecture.
- P1: Persisted Ask AHONIX chat history UI; per-insight "Ask" deep-links with pre-computed context.
- P2: Date/country/channel filters wired to server-side recompute; business-memory timeline.
- P2: Multi-currency FX; CSV export; notifications feed.

## Next tasks
- Wire real OAuth integrations when credentials available; expand demo dataset volume for pagination demos.
