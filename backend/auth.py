"""Unified authentication: custom JWT (email/password) + Emergent Google OAuth.
Canonical user identifier is a UUID `user_id`. MongoDB `_id` is never exposed.
"""
import os
import re
import uuid
import logging
import secrets
from datetime import datetime, timezone, timedelta

from urllib.parse import quote_plus, urlencode
import bcrypt
import jwt
import httpx
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from rate_limit import make_rate_limiter, check_rate_limit
from email_service import send_password_reset_email, send_verification_email, mask_email

logger = logging.getLogger("ahonix.auth")

JWT_ALGORITHM = "HS256"
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

_db = None


def get_google_auth_config() -> dict:
    """Load Google OAuth configuration from environment variables."""
    app_url = os.environ.get("APP_URL", os.environ.get("BACKEND_URL", "http://localhost:8000")).rstrip("/")
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    client_id = os.environ.get("GOOGLE_CLIENT_ID", os.environ.get("GOOGLE_ADS_CLIENT_ID", "")).strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")).strip()
    redirect_uri = os.environ.get(
        "GOOGLE_AUTH_REDIRECT_URI",
        f"{app_url}/api/auth/google/callback"
    ).strip()

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "frontend_url": frontend_url,
    }



def init_auth(db):
    global _db
    _db = db


# --- password helpers --------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        logger.warning("JWT_SECRET environment variable is not set. Using dev fallback.")
        return "dev-insecure-jwt-secret-please-set-JWT_SECRET-in-production"
    return secret


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=60), "type": "access"}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _is_production() -> bool:
    """Detect production vs local dev for cookie secure flag."""
    url = os.environ.get("APP_URL", os.environ.get("FRONTEND_URL", "")).strip()
    if not url:
        return False
    return not any(h in url.lower() for h in ("localhost", "127.0.0.1", "0.0.0.0"))


def is_production_env() -> bool:
    """Check if current environment is production/staging."""
    env = os.environ.get("ENVIRONMENT", "").strip().lower()
    if env in ("test", "testing", "development", "local", "dev"):
        return False
    return bool(os.environ.get("RENDER") or env in ("production", "staging") or _is_production())


def _set_jwt_cookies(response: Response, access: str, refresh: str):
    secure = _is_production()
    samesite = "none" if secure else "lax"
    response.set_cookie("access_token", access, httponly=True, secure=secure,
                        samesite=samesite, max_age=3600, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=secure,
                        samesite=samesite, max_age=604800, path="/")


def _public_user(u: dict) -> dict:
    return {
        "user_id": u["user_id"], "email": u["email"], "name": u.get("name", ""),
        "picture": u.get("picture"), "auth_provider": u.get("auth_provider", "password"),
        "email_verified": u.get("email_verified", True),
        "onboarding_completed": u.get("onboarding_completed", False),
        "active_workspace_id": u.get("active_workspace_id"),
    }


# --- current user resolver ---------------------------------------------------
async def get_current_user(request: Request) -> dict:
    # 1) JWT access token (cookie or bearer)
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization", "")
    bearer = auth_header[7:] if auth_header.startswith("Bearer ") else None

    if token:
        try:
            payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await _db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
                if user:
                    return user
        except jwt.PyJWTError:
            pass

    # 2) Emergent session token (cookie or bearer)
    session_token = request.cookies.get("session_token") or bearer
    if session_token:
        sess = await _db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if sess:
            expires_at = sess["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at >= datetime.now(timezone.utc):
                user = await _db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
                if user:
                    return user

    # 3) bearer that is actually a JWT
    if bearer:
        try:
            payload = jwt.decode(bearer, _secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await _db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
                if user:
                    return user
        except jwt.PyJWTError:
            pass

    raise HTTPException(status_code=401, detail="Not authenticated")


# --- request models ----------------------------------------------------------
class RegisterBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str = Field(..., min_length=10, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)


class VerifyEmailBody(BaseModel):
    token: str = Field(..., min_length=10, max_length=100)


class ResendVerificationBody(BaseModel):
    email: EmailStr


# --- rate limiters (per-IP) --------------------------------------------------
login_limiter = make_rate_limiter(max_calls=10, window_seconds=60, scope="login")
register_limiter = make_rate_limiter(max_calls=5, window_seconds=60, scope="register")
forgot_limiter = make_rate_limiter(max_calls=3, window_seconds=60, scope="forgot")
resend_limiter = make_rate_limiter(max_calls=3, window_seconds=60, scope="resend_verify")

router = APIRouter(prefix="/api/auth")


@router.post("/register")
async def register(body: RegisterBody, response: Response, _rl=Depends(register_limiter)):
    email = body.email.lower().strip()
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if await _db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    doc = {
        "user_id": user_id, "email": email, "name": body.name.strip() or email.split("@")[0],
        "password_hash": hash_password(body.password), "auth_provider": "password",
        "email_verified": False,
        "onboarding_completed": False, "active_workspace_id": None,
        "created_at": now_iso,
    }
    await _db.users.insert_one(doc)

    # Generate fresh cryptographically secure verification token (24-hour expiration)
    verify_token = secrets.token_urlsafe(32)
    expires_at_iso = (now + timedelta(hours=24)).isoformat()
    if _db is not None:
        await _db.email_verification_tokens.insert_one({
            "token": verify_token,
            "user_id": user_id,
            "email": email,
            "expires_at": expires_at_iso,
            "used": False,
            "created_at": now_iso,
        })

    # Dispatch transactional verification email (never leaks token in logs)
    try:
        await send_verification_email(to_email=email, verify_token=verify_token)
    except Exception as e:
        logger.error("Failed to dispatch verification email to %s: %s", mask_email(email), type(e).__name__)

    dev_token = verify_token if not is_production_env() else None

    # Note: Unverified users do not receive session cookies upon registration.
    return {
        "ok": True,
        "requires_verification": True,
        "message": "Verification email sent. Please check your inbox to activate your account.",
        "email": email,
        "dev_token": dev_token,
        **_public_user(doc),
    }


@router.post("/verify-email")
async def verify_email(body: VerifyEmailBody, response: Response):
    """Validate verification token, mark account verified, and authenticate user."""
    token = body.token.strip()
    if not re.match(r'^[A-Za-z0-9_-]{10,100}$', token):
        raise HTTPException(status_code=400, detail="Invalid verification token.")

    rec = await _db.email_verification_tokens.find_one({"token": token}) if _db is not None else None
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or already used verification token.")

    expires_str = rec.get("expires_at")
    if expires_str:
        try:
            exp_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")
        except Exception:
            pass

    user = await _db.users.find_one({"user_id": rec["user_id"]}) if _db is not None else None
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    now_iso = datetime.now(timezone.utc).isoformat()
    if _db is not None:
        await _db.email_verification_tokens.update_one(
            {"token": token},
            {"$set": {"used": True, "verified_at": now_iso}}
        )
        await _db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"email_verified": True}}
        )
    user["email_verified"] = True

    # Authenticate and set session cookies immediately on verification
    _set_jwt_cookies(response, create_access_token(user["user_id"], user["email"]),
                     create_refresh_token(user["user_id"]))

    return {
        "ok": True,
        "message": "Account successfully verified! You are now signed in.",
        "user": _public_user(user),
    }


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationBody, _rl=Depends(resend_limiter)):
    """Resend email verification link with per-email rate limiting."""
    email = body.email.lower().strip()
    check_rate_limit(f"resend_verify:{email}", max_calls=3, window_seconds=900)

    user = await _db.users.find_one({"email": email}) if _db is not None else None
    dev_token = None

    if user and user.get("auth_provider") == "password" and user.get("email_verified") is False:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at_iso = (now + timedelta(hours=24)).isoformat()

        if _db is not None:
            await _db.email_verification_tokens.update_many(
                {"user_id": user["user_id"], "used": False},
                {"$set": {"used": True, "invalidated": True, "invalidated_at": now_iso}}
            )

            token = secrets.token_urlsafe(32)
            await _db.email_verification_tokens.insert_one({
                "token": token,
                "user_id": user["user_id"],
                "email": email,
                "expires_at": expires_at_iso,
                "used": False,
                "created_at": now_iso,
            })

            try:
                await send_verification_email(to_email=email, verify_token=token)
            except Exception as e:
                logger.error("Failed to resend verification email to %s: %s", mask_email(email), type(e).__name__)

            if not is_production_env():
                dev_token = token

    return {
        "ok": True,
        "message": "If an unverified account exists, a fresh verification link has been sent.",
        "dev_token": dev_token,
    }


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response, _rl=Depends(login_limiter)):
    email = body.email.lower().strip()
    ident = f"{request.client.host if request.client else 'x'}:{email}"
    attempt = await _db.login_attempts.find_one({"identifier": ident}) if _db is not None else None
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")

    user = await _db.users.find_one({"email": email}) if _db is not None else None
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        if _db is not None:
            await _db.login_attempts.update_one(
                {"identifier": ident},
                {"$inc": {"count": 1},
                 "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
                upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Guard: check email verification status for password accounts
    if user.get("auth_provider") == "password" and user.get("email_verified") is False:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Please verify your email before logging in, or click Resend Verification.",
            headers={"X-Account-Status": "unverified"}
        )

    if _db is not None:
        await _db.login_attempts.delete_one({"identifier": ident})
    _set_jwt_cookies(response, create_access_token(user["user_id"], email),
                     create_refresh_token(user["user_id"]))
    return _public_user(user)


@router.get("/google/status")
async def google_auth_status():
    """Check if Google OAuth is configured on this server."""
    cfg = get_google_auth_config()
    return {"configured": bool(cfg["client_id"])}


@router.get("/google/login")
async def google_login(request: Request, redirect: str = "/app/overview"):
    """Initiate direct Google OAuth 2.0 flow for login/signup."""
    cfg = get_google_auth_config()
    frontend_url = cfg["frontend_url"]
    if not cfg["client_id"]:
        logger.warning("Google OAuth login requested but GOOGLE_CLIENT_ID is not configured.")
        error_msg = "Google OAuth is not configured on this server (GOOGLE_CLIENT_ID missing in Render). Please sign in with email and password."
        
        # Check if browser navigation vs API/test client
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(
                url=f"{frontend_url}/login?error={quote_plus(error_msg)}",
                status_code=302
            )
        raise HTTPException(status_code=503, detail=error_msg)

    state = secrets.token_urlsafe(32)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(seconds=900)

    # Safe redirect destination guard
    safe_redirect = redirect if redirect.startswith("/") else "/app/overview"

    if _db is not None:
        await _db.google_auth_states.replace_one(
            {"state": state},
            {
                "state": state,
                "redirect": safe_redirect,
                "created_at": now_utc.isoformat(),
                "expires_at": expires_at.isoformat(),
            },
            upsert=True,
        )

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": state,
        "prompt": "select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth 2.0 callback, exchange code, upsert user, create session, and redirect."""
    cfg = get_google_auth_config()
    frontend_url = cfg["frontend_url"]

    params = dict(request.query_params)
    error = params.get("error")
    if error:
        logger.warning("Google OAuth consent cancelled or error: %s", error)
        return RedirectResponse(url=f"{frontend_url}/login?error={quote_plus(error)}")

    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        logger.warning("Google OAuth callback missing code or state")
        return RedirectResponse(url=f"{frontend_url}/login?error=missing_parameters")

    target_path = "/app/overview"
    if _db is not None:
        state_doc = await _db.google_auth_states.find_one({"state": state})
        if not state_doc:
            logger.warning("Google OAuth invalid or expired CSRF state: %s", state)
            return RedirectResponse(url=f"{frontend_url}/login?error=invalid_state")
        target_path = state_doc.get("redirect") or "/app/overview"
        await _db.google_auth_states.delete_one({"state": state})

    # Exchange authorization code for tokens
    async with httpx.AsyncClient(timeout=15) as cx:
        token_res = await cx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "redirect_uri": cfg["redirect_uri"],
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_res.status_code != 200:
        logger.error("Google OAuth token exchange failed (%s): %s", token_res.status_code, token_res.text)
        return RedirectResponse(url=f"{frontend_url}/login?error=token_exchange_failed")

    token_data = token_res.json()
    google_access_token = token_data.get("access_token")
    if not google_access_token:
        return RedirectResponse(url=f"{frontend_url}/login?error=no_access_token")

    # Fetch user profile from OpenID userinfo
    async with httpx.AsyncClient(timeout=15) as cx:
        userinfo_res = await cx.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {google_access_token}"},
        )

    if userinfo_res.status_code != 200:
        logger.error("Failed to fetch Google user profile (%s)", userinfo_res.status_code)
        return RedirectResponse(url=f"{frontend_url}/login?error=userinfo_failed")

    profile = userinfo_res.json()
    email = (profile.get("email") or "").lower().strip()
    if not email:
        return RedirectResponse(url=f"{frontend_url}/login?error=email_not_provided")

    name = profile.get("name") or profile.get("given_name") or email.split("@")[0]
    picture = profile.get("picture")

    now_utc = datetime.now(timezone.utc)
    user = await _db.users.find_one({"email": email}) if _db is not None else None
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "auth_provider": "google",
            "onboarding_completed": False,
            "active_workspace_id": None,
            "created_at": now_utc.isoformat(),
        }
        if _db is not None:
            await _db.users.insert_one(user)
        logger.info("Created new Google OAuth user %s (%s)", user_id, mask_email(email))
    else:
        update_fields = {}
        if picture and user.get("picture") != picture:
            update_fields["picture"] = picture
        if not user.get("name") and name:
            update_fields["name"] = name
        if update_fields and _db is not None:
            await _db.users.update_one({"email": email}, {"$set": update_fields})
        logger.info("Google OAuth login for existing user %s (%s)", user["user_id"], mask_email(email))

    access_token = create_access_token(user["user_id"], email)
    refresh_token = create_refresh_token(user["user_id"])
    session_token = secrets.token_urlsafe(32)

    if _db is not None:
        await _db.user_sessions.update_one(
            {"session_token": session_token},
            {
                "$set": {
                    "user_id": user["user_id"],
                    "session_token": session_token,
                    "email": email,
                    "expires_at": (now_utc + timedelta(days=7)).isoformat(),
                    "created_at": now_utc.isoformat(),
                }
            },
            upsert=True,
        )

    dest = target_path if target_path.startswith("/") else f"/{target_path}"
    redirect_url = f"{frontend_url}{dest}#session_id={session_token}"

    redir = RedirectResponse(url=redirect_url, status_code=302)
    _set_jwt_cookies(redir, access_token, refresh_token)
    redir.set_cookie(
        "session_token",
        session_token,
        httponly=True,
        secure=_is_production(),
        samesite="none" if _is_production() else "lax",
        max_age=604800,
        path="/",
    )
    return redir


@router.post("/session")
async def google_session(request: Request, response: Response):
    """Exchange OAuth session_id for a persistent session.
    Checks internal user_sessions first, falls back to Emergent session proxy.
    """
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        body = await request.json()
        session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    # 1) Check local database user_sessions (AHONIX OAuth session)
    if _db is not None:
        sess = await _db.user_sessions.find_one({"session_token": session_id}, {"_id": 0})
        if sess:
            expires_at = sess.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at >= datetime.now(timezone.utc):
                user = await _db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
                if user:
                    _set_jwt_cookies(
                        response,
                        create_access_token(user["user_id"], user["email"]),
                        create_refresh_token(user["user_id"]),
                    )
                    response.set_cookie(
                        "session_token",
                        session_id,
                        httponly=True,
                        secure=_is_production(),
                        samesite="none" if _is_production() else "lax",
                        max_age=604800,
                        path="/",
                    )
                    return _public_user(user)

    # 2) Fallback to Emergent OAuth proxy for legacy preview environments
    async with httpx.AsyncClient(timeout=15) as cx:
        r = await cx.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = r.json()
    email = data["email"].lower().strip()

    user = await _db.users.find_one({"email": email})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id, "email": email, "name": data.get("name", ""),
            "picture": data.get("picture"), "auth_provider": "google",
            "onboarding_completed": False, "active_workspace_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await _db.users.insert_one(user)
    else:
        await _db.users.update_one({"email": email},
                                   {"$set": {"picture": data.get("picture", user.get("picture"))}})

    session_token = data["session_token"]
    await _db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {"user_id": user["user_id"], "session_token": session_token,
                  "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                  "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    secure = _is_production()
    samesite = "none" if secure else "lax"
    response.set_cookie("session_token", session_token, httponly=True, secure=secure,
                        samesite=samesite, max_age=604800, path="/")
    return _public_user(user)



@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _public_user(user)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(rt, _secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await _db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    secure = _is_production()
    samesite = "none" if secure else "lax"
    response.set_cookie("access_token", create_access_token(user["user_id"], user["email"]),
                        httponly=True, secure=secure, samesite=samesite, max_age=3600, path="/")
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response):
    st = request.cookies.get("session_token")
    if st and _db is not None:
        try:
            await _db.user_sessions.delete_one({"session_token": st})
        except Exception as e:
            logger.warning("Could not delete session on logout (%s)", type(e).__name__)
    secure = _is_production()
    samesite = "none" if secure else "lax"
    response.delete_cookie("access_token", path="/", secure=secure, samesite=samesite)
    response.delete_cookie("refresh_token", path="/", secure=secure, samesite=samesite)
    response.delete_cookie("session_token", path="/", secure=secure, samesite=samesite)
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(body: ForgotBody, _rl=Depends(forgot_limiter)):
    email = body.email.lower().strip()

    # Enforce per-email rate limit: maximum 3 requests per 15 minutes (900 seconds)
    check_rate_limit(f"forgot_email:{email}", max_calls=3, window_seconds=900)

    user = await _db.users.find_one({"email": email})
    # Always return generic ok response to prevent account enumeration
    if user and user.get("auth_provider") == "password":
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at_iso = (now + timedelta(hours=1)).isoformat()

        # Invalidate previous unused reset tokens for this user
        await _db.password_reset_tokens.update_many(
            {"user_id": user["user_id"], "used": False},
            {"$set": {"used": True, "invalidated": True, "invalidated_at": now_iso}},
        )

        # Generate fresh cryptographically secure reset token
        token = secrets.token_urlsafe(32)
        await _db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "expires_at": expires_at_iso,
            "used": False,
            "created_at": now_iso,
        })

        # Dispatch transactional reset email (safely catches exceptions, never leaks token in logs)
        try:
            await send_password_reset_email(to_email=email, reset_token=token)
        except Exception as e:
            logger.error("Failed to dispatch password reset email to %s: %s", mask_email(email), type(e).__name__)

    return {"ok": True, "message": "If an account exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetBody):
    # Validate token format before DB lookup
    if not re.match(r'^[A-Za-z0-9_-]{10,100}$', body.token):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    rec = await _db.password_reset_tokens.find_one({"token": body.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    if datetime.fromisoformat(rec["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired.")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    await _db.users.update_one({"user_id": rec["user_id"]},
                               {"$set": {"password_hash": hash_password(body.password)}})
    await _db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"ok": True}


async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await _db.users.find_one({"email": admin_email})
    if existing is None:
        await _db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}", "email": admin_email,
            "name": "Alex Rivera", "password_hash": hash_password(admin_password),
            "auth_provider": "password", "role": "admin",
            "onboarding_completed": False, "active_workspace_id": None,
            "created_at": datetime.now(timezone.utc).isoformat()})
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await _db.users.update_one({"email": admin_email},
                                   {"$set": {"password_hash": hash_password(admin_password)}})
