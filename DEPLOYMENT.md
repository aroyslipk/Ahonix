# AHONIX — Production Deployment Guide

This guide provides step-by-step instructions for deploying the AHONIX AI Commerce OS to production environments, Docker containers, cloud virtual private servers (VPS), or serverless container platforms.

---

## 1. Architecture & Required Services

AHONIX consists of three distinct components:

| Component | Technology | Default Port | Production Runtime |
| :--- | :--- | :--- | :--- |
| **Backend API** | FastAPI, Uvicorn, Python 3.11 | `8000` | Docker Container / Python Process |
| **Frontend Web** | React 19, CRA / Craco, TailwindCSS | `3000` (dev) / `80` (prod) | Nginx Web Server / Static Hosting |
| **Database** | MongoDB 6.0+ / MongoDB Atlas | `27017` | Managed MongoDB Atlas or Container |

### Platform Environments Comparison

| Feature | Local Development | Demo / Staging Deployment | Commercial Production |
| :--- | :--- | :--- | :--- |
| **Database** | Local MongoDB (`localhost:27017`) or Docker | MongoDB Atlas Free Tier (M0) | MongoDB Atlas Dedicated (M10+) |
| **SSL / HTTPS** | Plain HTTP | HTTPS mandatory (Let's Encrypt / Cloudflare) | HTTPS mandatory with HSTS |
| **Auth Cookies** | `SameSite=Lax`, `Secure=False` | `SameSite=None`, `Secure=True` | `SameSite=None`, `Secure=True` |
| **Commerce Data** | In-memory seeded demo store | Seeded demo store (`Northstar Goods`) | Live store connector (future) |
| **Ask AHONIX AI** | Emergent Cloud Sandbox / API key | Emergent Cloud Sandbox / API key | LLM Gateway / Anthropic Claude API |

---

## 2. Environment Variables Reference

### Backend Configuration (`backend/.env`)

| Variable | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `MONGO_URL` | **Yes** | `mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority` | Connection string for MongoDB database |
| `DB_NAME` | **Yes** | `ahonix_prod` | Target database name |
| `JWT_SECRET` | **Yes** | `e1d4... (64-char hex)` | Secret key for signing HS256 auth tokens |
| `CORS_ORIGINS` | **Yes** | `https://app.yourdomain.com,https://yourdomain.com` | Allowed frontend origins (comma-separated, no wildcards) |
| `FRONTEND_URL` | **Yes** | `https://app.yourdomain.com` | Public frontend URL for redirects |
| `APP_URL` | **Yes** | `https://app.yourdomain.com` | Used to detect HTTPS for cookie security flags |
| `ADMIN_EMAIL` | **Yes** | `alex@northstargoods.com` | Initial admin account email seeded on boot |
| `ADMIN_PASSWORD` | **Yes** | `Ahonix2026!` | Initial admin account password seeded on boot |
| `EMERGENT_LLM_KEY`| Optional | `sk-emergent-...` | API key for Ask AHONIX analyst streaming |
| `SHOPIFY_API_KEY` | Optional | `your_client_id` | Client ID from Shopify Partner App |
| `SHOPIFY_API_SECRET` | Optional | `your_client_secret` | Client Secret for HMAC signature verification |
| `SHOPIFY_SCOPES` | Optional | `read_products,read_orders` | Minimum read-only scopes requested from merchant |
| `SHOPIFY_API_VERSION` | Optional | `2026-07` | Official stable Shopify Admin API version |
| `SHOPIFY_REDIRECT_URI` | Optional | `{APP_URL}/api/integrations/shopify/callback` | Explicit redirect URI override if behind custom proxy |

> [!CAUTION]
> Generate a cryptographically secure `JWT_SECRET` for production using:
> ```bash
> openssl rand -hex 32
> ```

### Frontend Configuration (`frontend/.env`)

| Variable | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `REACT_APP_BACKEND_URL` | Optional | `https://api.yourdomain.com` | Target backend URL. Leave **blank** if served behind same reverse proxy |
| `WDS_SOCKET_PORT` | Optional | `3000` | Dev server HMR port (443 behind reverse proxy) |
| `ENABLE_HEALTH_CHECK` | Optional | `false` | Webpack build health plugin toggle |

---

## 3. Staging Deployment Guide (Single-Origin: https://staging.ahonix.com)

The staging environment is deployed at **`https://staging.ahonix.com`** using a single-origin architecture:
- **Frontend SPA**: Served at `/` with SPA client-side fallback for `/privacy`, `/terms`, `/login`, `/register`, `/app/*`, `/reset-password`.
- **FastAPI Backend**: Reverse-proxied via Nginx at `/api/*`.
- **Database**: Dedicated MongoDB Atlas staging database namespace (`ahonix_staging`).

```
https://staging.ahonix.com
        │
        ├── Frontend SPA (React / Nginx)  ──>  /
        │     • /privacy, /terms, /login, /register, /app/*, /reset-password
        │
        ├── FastAPI Backend               ──>  /api/*
        │     • /api/health
        │     • /api/auth/*
        │     • /api/integrations/*
        │     • /api/internal/cron/*
        │
        └── MongoDB Atlas Staging DB     ──>  ahonix_staging
```

### Staging Setup Steps

#### Step 1: Configure MongoDB Atlas Staging Database
1. In your MongoDB Atlas project, ensure the database name is `ahonix_staging` (isolated from production).
2. Create or verify a staging database user with `readWrite` permissions on `ahonix_staging`.
3. Add the staging server IP (or `0.0.0.0/0` if dynamic PaaS) to the Atlas IP Access List.

#### Step 2: Configure Staging Environment Variables
Copy the staging template and supply staging credentials:
```bash
cp backend/.env.staging.example backend/.env.staging
```
Set the required values in `backend/.env.staging`:
```ini
MONGO_URL=mongodb+srv://<staging_user>:<staging_password>@cluster.mongodb.net/ahonix_staging?retryWrites=true&w=majority&appName=AHONIX
DB_NAME=ahonix_staging
APP_URL=https://staging.ahonix.com
FRONTEND_URL=https://staging.ahonix.com
CORS_ORIGINS=https://staging.ahonix.com
JWT_SECRET=<generate-strong-64-char-hex>
ADMIN_EMAIL=staging-admin@ahonix.com
ADMIN_PASSWORD=<generate-strong-password>

SHOPIFY_API_KEY=<staging_client_id>
SHOPIFY_API_SECRET=<staging_client_secret>
SHOPIFY_API_VERSION=2026-07
SHOPIFY_SCOPES=read_products,read_orders
SHOPIFY_REDIRECT_URI=https://staging.ahonix.com/api/integrations/shopify/callback
SHOPIFY_SYNC_BATCH_SIZE=250
SHOPIFY_SYNC_MAX_PAGES=0

SMTP_HOST=smtp.staging-provider.com
SMTP_PORT=587
SMTP_USERNAME=<staging_smtp_user>
SMTP_PASSWORD=<staging_smtp_password>
EMAIL_FROM=AHONIX Staging <staging-security@ahonix.com>

META_APP_ID=<staging_meta_app_id>
META_APP_SECRET=<staging_meta_app_secret>
META_API_VERSION=v21.0
META_SCOPES=ads_read,read_insights
META_REDIRECT_URI=https://staging.ahonix.com/api/integrations/meta/callback

GOOGLE_ADS_CLIENT_ID=<staging_google_client_id>
GOOGLE_ADS_CLIENT_SECRET=<staging_google_client_secret>
GOOGLE_ADS_DEVELOPER_TOKEN=<staging_google_developer_token>
GOOGLE_ADS_API_VERSION=v19
GOOGLE_ADS_REDIRECT_URI=https://staging.ahonix.com/api/integrations/google-ads/callback

CRON_SECRET=<generate-strong-64-char-hex>
```

#### Step 3: Staging External Integration Callback Registration
Register the following exact URLs with external third-party provider portals for staging:

| Service | Setting Location | Exact Staging Callback / Ingress URL |
| :--- | :--- | :--- |
| **Shopify Partner App** | App Setup → Allowed redirection URL(s) | `https://staging.ahonix.com/api/integrations/shopify/callback` |
| **Shopify Webhooks** | Partner Dashboard / API Subscriptions | `https://staging.ahonix.com/api/integrations/shopify/webhooks` |
| **Meta for Developers** | Facebook Login → Valid OAuth Redirect URIs | `https://staging.ahonix.com/api/integrations/meta/callback` |
| **Google Cloud Console** | OAuth 2.0 Client → Authorized redirect URIs | `https://staging.ahonix.com/api/integrations/google-ads/callback` |

*(Note: These endpoints become live once the staging containers are booted behind TLS).*

#### Step 4: Staging Build & Launch via Docker Compose
Run the staging-specific Docker Compose setup:
```bash
# Build and launch staging containers
docker compose -f docker-compose.staging.yml up -d --build

# Verify container health and status
docker compose -f docker-compose.staging.yml ps
```

#### Step 5: Verify Staging Health Check
Test the live health check endpoint:
```bash
curl -i https://staging.ahonix.com/api/health
```
Expected HTTP 200 response:
```json
{
  "status": "ok",
  "db": true,
  "version": "2.0.0"
}
```

#### Step 6: Staging Rollback Procedure
If an issue is detected during staging testing:
```bash
# 1. Stop staging containers
docker compose -f docker-compose.staging.yml down

# 2. Checkout previous known-good git tag/commit
git checkout <previous-tag-or-commit>

# 3. Rebuild and start previous version
docker compose -f docker-compose.staging.yml up -d --build
```

---

## 4. MongoDB Atlas Setup (Production Database)

1. **Create an Atlas Account & Cluster**:
   - Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) and create a cluster (M0 free-tier for testing, M10+ for production).
2. **Configure Database User**:
   - Navigate to **Security** → **Database Access**.
   - Create a user (e.g. `ahonix_user`) with **Read and write to any database** (or scoped to `ahonix_prod`).
3. **Configure Network Access**:
   - Navigate to **Security** → **Network Access**.
   - Add the public IP address of your application server (or `0.0.0.0/0` if deploying to dynamic IP platforms like AWS ECS, Cloud Run, or Render).
4. **Obtain Connection String**:
   - Click **Connect** → **Drivers** (Python 3.11+).
   - Copy the SRV connection string:
     ```
     mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
     ```
   - Set this value as `MONGO_URL` in your backend environment.

---

## 5. Full-Stack Docker Deployment (Production)

### Using Docker Compose (Single Host / VPS)

The repository provides a complete [`docker-compose.yml`](file:///d:/AHONIX/docker-compose.yml):

```bash
# 1. Clone the repository
git clone <your-repo-url> /opt/ahonix
cd /opt/ahonix

# 2. Configure production backend environment
cat << 'EOF' > backend/.env
MONGO_URL=mongodb+srv://dbuser:StrongPassword@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
DB_NAME=ahonix_prod
CORS_ORIGINS=https://app.yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
APP_URL=https://app.yourdomain.com
JWT_SECRET=4f92bc3e7a1859d041c28479e0a1f5923b7c81d2e9f04a6b5c3e7a1859d041c2
ADMIN_EMAIL=alex@northstargoods.com
ADMIN_PASSWORD=StrongAdminPassword2026!
EOF

# 3. Build and launch containers
docker compose up -d --build

# 4. Check container health status
docker compose ps
```

---

## 6. Standalone Container Deployment

### Backend Container
```bash
cd backend
docker build -t ahonix-backend:latest .

docker run -d \
  --name ahonix-backend \
  -p 8000:8000 \
  --env-file .env \
  ahonix-backend:latest
```

### Frontend Container (Nginx Static Server)
```bash
cd frontend
docker build \
  --build-arg REACT_APP_BACKEND_URL=https://api.yourdomain.com \
  -t ahonix-frontend:latest .

docker run -d \
  --name ahonix-frontend \
  -p 80:80 \
  ahonix-frontend:latest
```

---

## 7. CORS & Cookie Networking (HTTPS Requirements)

In modern web browsers, cross-origin authentication with cookies requires strict adherence to browser security policies:

1. **HTTPS is Mandatory**:
   - In production (`APP_URL` contains HTTPS), AHONIX sets authentication cookies (`access_token`, `refresh_token`, `session_token`) with:
     - `Secure = True`
     - `SameSite = None`
     - `HttpOnly = True`
   - Browsers will silently **reject** `SameSite=None` cookies if the request is not sent over HTTPS.
2. **CORS Headers**:
   - The backend `CORS_ORIGINS` setting **must** match the exact protocol and domain of the frontend (e.g. `https://app.yourdomain.com`).
   - Wildcard origins (`*`) are explicitly blocked by the backend when credentials are enabled.
3. **Reverse Proxy Alternative (Recommended)**:
   - Route both frontend and backend through a single domain (e.g., frontend at `/` and backend API at `/api/`) via Cloudflare, Traefik, or Nginx. This eliminates cross-origin cookie complexity entirely.

---

## 8. Health Check & Deployment Monitoring

The backend exposes an unauthenticated health check endpoint:

```
GET /api/health
```

### Response Formats:

**Healthy State (HTTP 200)**:
```json
{
  "status": "ok",
  "db": true,
  "version": "2.0.0"
}
```

**Degraded State (HTTP 200 with db=false)**:
```json
{
  "status": "degraded",
  "db": false,
  "version": "2.0.0"
}
```

### Monitoring Integration:
- **Docker Compose**: Uses the built-in `HEALTHCHECK` directive in `backend/Dockerfile`.
- **AWS ECS / GCP Cloud Run / Kubernetes**: Point liveness and readiness probes to `/api/health` with `interval: 15s` and `timeout: 5s`.
- The database check utilizes a strict 2-second timeout so health probes will never hang during database network partitions.

---

## 9. Post-Deployment Verification Checklist

Once deployed, verify the system in order:

1. **Verify Health Endpoint**:
   ```bash
   curl -i https://api.yourdomain.com/api/health
   ```
   Ensure `"status": "ok"` and `"db": true`.
2. **Verify Admin Login**:
   - Navigate to `https://app.yourdomain.com/login`.
   - Enter your `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
   - Verify that you are redirected to `/app/overview` and the `access_token` cookie is stored.
3. **Verify Demo Workspace**:
   - Inspect the Overview dashboard KPIs ($339,007 revenue, 2,955 orders).
   - Check that navigation to `/app/profit`, `/app/sales`, and `/app/actions` loads data cleanly.
4. **Verify Action Center Sandbox**:
   - Navigate to `/app/actions`.
   - Click "Simulate Impact" on an action; verify that its stage transitions forward.
5. **Verify Ask AHONIX**:
   - Open the "Ask AHONIX" drawer from the top-right button.
   - Send a prompt (e.g., *"What should I focus on today?"*).
   - Verify streaming markdown analyst answer.
6. **Verify Shopify Integration (Phase 3.1)**:
   - Navigate to Settings → Integrations.
   - Enter a development store domain (e.g., `dev-store.myshopify.com`).
   - Click "Authorize on Shopify" to initiate the OAuth flow.
   - Upon return, verify the "Connected" green status badge and click "Sync Now".

---

## 10. Shopify Partner App Setup Guide

To connect real Shopify stores, you must create a Shopify Partner App:

1. **Create App in Shopify Partner Dashboard**:
   - Go to [Shopify Partners](https://partners.shopify.com) → **Apps** → **Create App** → **Create app manually**.
   - Set an App name (e.g., `AHONIX Commerce OS`).
2. **Configure App URLs**:
   - **App URL**: `https://app.yourdomain.com` (or your local ngrok URL for development)
   - **Allowed redirection URL(s)**:
     ```
     https://api.yourdomain.com/api/integrations/shopify/callback
     ```
     *(For local development, e.g.: `https://<tunnel-id>.ngrok-free.app/api/integrations/shopify/callback`)*
3. **Configure API Access Scopes**:
   - In App Setup → **Access scopes**, request:
     - `read_products`
     - `read_orders`
   - AHONIX strictly uses read-only scopes.
4. **Copy Credentials to Backend Environment**:
   - Copy **Client ID** → set as `SHOPIFY_API_KEY` in `backend/.env`.
   - Copy **Client Secret** → set as `SHOPIFY_API_SECRET` in `backend/.env`.
   - Ensure `SHOPIFY_API_VERSION=2026-07` is set (or left default).
5. **Testing with a Development Store**:
   - In Partner Dashboard, create a **Development Store** with test data.
   - Install your app on the development store to verify real OAuth and read-only sync!

---

## 11. Automated Marketing Synchronization (Internal Cron)

Phase 6.4 implements a secure internal endpoint to refresh Meta Ads and Google Ads performance insights across all connected merchant workspaces without requiring an in-process background worker or external task queue (Celery/Redis).

### Configuration (`backend/.env`)

| Variable | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `CRON_SECRET` | **Yes** | `d4e5f6... (64-char hex)` | Bearer secret required in `X-Cron-Secret` header |
| `CRON_MAX_WORKSPACES` | Optional | `50` | Maximum workspaces processed per cron invocation |

> [!CAUTION]
> Generate a strong random secret for `CRON_SECRET` using `openssl rand -hex 32`. Never expose this endpoint to public traffic without a valid `X-Cron-Secret` header. Always enforce HTTPS in production.

### Endpoint Details

- **Method**: `POST`
- **Path**: `/api/internal/cron/sync-marketing`
- **Headers**:
  ```http
  X-Cron-Secret: your_cron_secret_here
  Content-Type: application/json
  ```
- **Response**:
  ```json
  {
    "ok": true,
    "started_at": "2026-09-14T04:00:00.123456+00:00",
    "completed_at": "2026-09-14T04:00:15.654321+00:00",
    "workspaces_processed": 5,
    "platforms_succeeded": 9,
    "platforms_failed": 0,
    "reauth_required": 0
  }
  ```

### Example External Scheduler Configurations

#### A. Linux Crontab (Server-Local)
Run daily at 04:00 UTC:
```bash
0 4 * * * curl -s -X POST https://api.yourdomain.com/api/internal/cron/sync-marketing \
  -H "X-Cron-Secret: your_cron_secret_here" \
  >> /var/log/ahonix_marketing_cron.log 2>&1
```

#### B. AWS EventBridge / CloudWatch Scheduled Event
Trigger an AWS Lambda or HTTP API Destination pointing to `https://api.yourdomain.com/api/internal/cron/sync-marketing` with header `X-Cron-Secret: <SECRET>` every 6 hours or once daily at 04:00 UTC (`cron(0 4 * * ? *)`).

#### C. Google Cloud Scheduler
- **Target type**: HTTP
- **URL**: `https://api.yourdomain.com/api/internal/cron/sync-marketing`
- **HTTP method**: `POST`
- **HTTP headers**: `X-Cron-Secret: your_cron_secret_here`
- **Frequency**: `0 4 * * *` (Daily at 04:00 UTC)

---

> [!WARNING]
> **Ask AHONIX (`emergentintegrations` Dependency)**:
> The AI streaming analyst currently utilizes the `emergentintegrations` Python package to interface with Claude (`claude-sonnet-4-6`). This package is bundled within the Emergent platform environment and is not published on the public PyPI repository.
>
> - **In Emergent Environments**: Ask AHONIX functions fully with streaming responses.
> - **In External Independent Deployments**: The platform core (authentication, Overview, True Profit, Sales, Marketing, Action Center, Markets simulator) runs independently. The `backend/Dockerfile` builds cleanly by installing all standard dependencies. If `/api/ask` is invoked outside an Emergent environment without the wheel, the server returns an informative error message rather than crashing.

---

## 12. Troubleshooting & Common Pitfalls

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **CORS error in browser console** | `CORS_ORIGINS` does not match the frontend origin or includes a trailing slash | Update `CORS_ORIGINS` in `backend/.env` without trailing slashes (e.g. `https://app.yourdomain.com`) |
| **Login succeeds but immediate redirect back to /login** | Cookie dropped because frontend is HTTP while `APP_URL` is HTTPS, or cross-domain `SameSite` issue | Ensure both frontend and backend use valid SSL/HTTPS certificates in production |
| **Health endpoint returns `"db": false`** | MongoDB Atlas IP access list does not permit connection from application host | Add host IP to Atlas Network Access list (or `0.0.0.0/0`) |
| **HTTP 429 Too Many Requests** | Rate limiter triggered (e.g., >10 login attempts per minute from same IP) | Wait 60 seconds or verify client is not stuck in an infinite request loop |
| **Docker Compose frontend cannot reach backend** | `REACT_APP_BACKEND_URL` pointing to `localhost` inside browser | In browser, `localhost:8000` refers to the user's computer. Ensure port 8000 is mapped or use the Nginx reverse-proxy |
