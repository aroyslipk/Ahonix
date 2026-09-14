# AHONIX — Restored App Spec (source-of-truth backup, restored 2026-09-12)

Restored from `AHONIX_FULL_SOURCE_BACKUP.zip` — the existing working app, not rebuilt.
Stack: **FastAPI + motor/MongoDB** backend (self-contained `server.py` + `auth.py` +
`demo_data.py`), **CRA/craco + JavaScript** frontend (React 19, Tailwind v3, shadcn/ui,
Recharts, axios). NOTE: this is a CRA/JS app — it has no `yarn typecheck`; build proof is
`yarn build`. Frontend dev script: `yarn dev` → `craco start` (added so the pod supervisor's
`yarn dev` command works; otherwise untouched).

## What the app does
AI Commerce OS for online merchants: Connect → Understand → Detect → Explain → Simulate →
Recommend → Approve → Execute → Measure. Sections: Overview, AI Intelligence (Business X-Ray),
True Profit, Sales, Products (+ detail), Inventory, Marketing, Customers, Operations, Markets
(opportunities + launch simulator), Action Center (sandboxed approve/simulate/execute/measure
pipeline), Settings. 8-step onboarding creates a Demo Workspace ("Northstar Goods") or a real
(empty-state) workspace. Ask AHONIX: SSE chat drawer grounded on workspace snapshot (Claude via
Emergent LLM key). Value labels: ACTUAL / ESTIMATED / PROJECTED / FORECAST / DEMO.

## Data model (Mongo, DB_NAME="test_database")
users, user_sessions, workspaces, workspace_data (full analytics snapshot), chat_messages,
password_reset_tokens, login_attempts. Per-user isolation on every endpoint. Ids are uuid strings.

## Auth
- JWT email/password via httpOnly cookies (access_token, refresh_token; secure, samesite=none).
- Emergent-managed Google OAuth (`POST /api/auth/session` {session_id}).
- Endpoints under `/api/auth`: register, login, logout, me, refresh, session, forgot-password,
  reset-password.
- Seeded admin (owns demo workspace): alex@northstargoods.com / Ahonix2026! — see
  memory/test_credentials.md. Login seeds/loads the demo workspace automatically.

## Key API (prefix /api, auth required unless noted)
POST /workspaces {name,mode:"demo"|"real",...}; GET overview | intelligence | profit | sales |
products | products/{id} | inventory | returns | marketing | customers | operations | markets |
actions; POST /markets/simulate; POST /actions/{action_id} {op}; POST /ask (SSE).

## Env (backend/.env) — required vars, all present
MONGO_URL, DB_NAME, CORS_ORIGINS, FRONTEND_URL, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD,
EMERGENT_LLM_KEY (Ask AHONIX). URLs repointed to this pod: https://ahonix-backup.preview.emergentagent.com
Frontend/.env: REACT_APP_BACKEND_URL (same public URL), WDS_SOCKET_PORT=443, ENABLE_HEALTH_CHECK=false.
