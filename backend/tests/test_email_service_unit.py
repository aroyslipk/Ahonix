"""Unit and Security Tests for Phase 6.2: Transactional Password Reset Email.

Coverage:
1. Email HTML and text template generation
2. Plain-text fallback
3. Reset URL generation
4. SMTP configuration parsing and validation
5. Development console fallback mode (safe simulation)
6. Production mode never logs raw tokens or URLs
7. Email send success (STARTTLS and SSL)
8. Email send failure resilience (SMTP error, timeout, network error)
9. Token invalidation on second request (only newest token valid)
10. Expired token rejection
11. Used token rejection
12. Per-email rate limiting (3 requests per 15 minutes)
13. Generic non-enumerating responses (existing, non-existing, oauth users)
14. Workspace and user isolation
15. Strict security and log sanitization assertion (zero secrets leaked)
"""
import sys
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from email_service import (
    get_email_config,
    is_smtp_configured,
    mask_email,
    build_reset_password_html,
    build_reset_password_text,
    send_password_reset_email,
    DEFAULT_SMTP_PORT,
    DEFAULT_EMAIL_FROM,
)
import auth
from auth import (
    forgot_password,
    reset_password,
    ForgotBody,
    ResetBody,
    verify_password,
    hash_password,
)
import rate_limit


def run_async(coro):
    """Helper to run async coroutines in synchronous pytest tests."""
    return asyncio.run(coro)


# --- Mock In-Memory Database for Auth Isolation -------------------------------

class MockCollection:
    def __init__(self, data=None):
        self.docs = list(data) if data else []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None

    async def insert_one(self, doc):
        stored = dict(doc)
        if "_id" not in stored:
            stored["_id"] = str(len(self.docs) + 1)
        self.docs.append(stored)
        return MagicMock(inserted_id=stored["_id"])

    async def update_one(self, query, update, upsert=False):
        for i, doc in enumerate(self.docs):
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    self.docs[i].update(update["$set"])
                return MagicMock(modified_count=1)
        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            self.docs.append(new_doc)
            return MagicMock(upserted_id="upserted")
        return MagicMock(modified_count=0)

    async def update_many(self, query, update):
        count = 0
        for i, doc in enumerate(self.docs):
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update:
                    self.docs[i].update(update["$set"])
                count += 1
        return MagicMock(modified_count=count)


class MockDatabase:
    def __init__(self):
        self.users = MockCollection()
        self.password_reset_tokens = MockCollection()
        self.user_sessions = MockCollection()


# --- Fixtures -----------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_rate_limits():
    """Clear in-memory rate limiting buckets between tests."""
    with rate_limit._lock:
        rate_limit._buckets.clear()
    yield
    with rate_limit._lock:
        rate_limit._buckets.clear()


@pytest.fixture
def mock_db():
    db = MockDatabase()
    # Seed a standard password user
    db.users.docs.append({
        "user_id": "user_12345",
        "email": "alex@northstargoods.com",
        "name": "Alex Rivera",
        "password_hash": hash_password("OldPassword123!"),
        "auth_provider": "password",
        "role": "admin",
        "active_workspace_id": "ws_northstar",
    })
    # Seed a secondary user for isolation tests
    db.users.docs.append({
        "user_id": "user_67890",
        "email": "sarah@othermerchant.com",
        "name": "Sarah Chen",
        "password_hash": hash_password("SarahSecret123!"),
        "auth_provider": "password",
        "role": "admin",
        "active_workspace_id": "ws_other",
    })
    # Seed an OAuth user (should not receive password resets)
    db.users.docs.append({
        "user_id": "user_oauth",
        "email": "google_user@northstargoods.com",
        "name": "OAuth User",
        "password_hash": "",
        "auth_provider": "google",
        "role": "member",
        "active_workspace_id": "ws_northstar",
    })
    auth.init_auth(db)
    return db


# ==============================================================================
# 1. Email Templates & Content Tests
# ==============================================================================

class TestEmailTemplates:
    def test_html_template_elements(self):
        reset_url = "https://app.ahonix.com/reset-password?token=secret_test_token_123"
        html = build_reset_password_html(reset_url, expiration_hours=1)

        # Branding
        assert "AHONIX" in html
        assert "THE AI COMMERCE OS" in html

        # Content & CTA
        assert "Reset your password" in html
        assert 'href="https://app.ahonix.com/reset-password?token=secret_test_token_123"' in html
        assert "Reset Password" in html

        # Expiration & Security notices
        assert "1 hour" in html
        assert "If you did not make this request, you can safely ignore this email" in html
        assert "Your password will remain unchanged" in html

        # Responsive styling & Plaintext fallback link
        assert "max-width: 540px" in html
        assert reset_url in html

    def test_text_template_elements(self):
        reset_url = "https://app.ahonix.com/reset-password?token=secret_test_token_123"
        text = build_reset_password_text(reset_url, expiration_hours=1)

        assert "AHONIX — The AI Commerce OS" in text
        assert "Reset Your Password" in text
        assert reset_url in text
        assert "valid for 1 hour" in text
        assert "safely ignore this email" in text


# ==============================================================================
# 2. Configuration & Email Masking Tests
# ==============================================================================

class TestEmailConfiguration:
    def test_get_email_config_defaults(self, monkeypatch):
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_PORT", raising=False)
        monkeypatch.delenv("SMTP_USERNAME", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        monkeypatch.delenv("EMAIL_FROM", raising=False)
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        monkeypatch.delenv("APP_URL", raising=False)

        cfg = get_email_config()
        assert cfg["smtp_host"] == ""
        assert cfg["smtp_port"] == DEFAULT_SMTP_PORT
        assert cfg["smtp_username"] == ""
        assert cfg["smtp_password"] == ""
        assert cfg["email_from"] == DEFAULT_EMAIL_FROM
        assert cfg["frontend_url"] == "http://localhost:3000"
        assert not is_smtp_configured()

    def test_get_email_config_custom(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.sendgrid.net")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USERNAME", "apikey")
        monkeypatch.setenv("SMTP_PASSWORD", "SG.testsecretkey123")
        monkeypatch.setenv("EMAIL_FROM", "security@mycustomdomain.com")
        monkeypatch.setenv("FRONTEND_URL", "https://app.mycustomdomain.com/")

        cfg = get_email_config()
        assert cfg["smtp_host"] == "smtp.sendgrid.net"
        assert cfg["smtp_port"] == 465
        assert cfg["smtp_username"] == "apikey"
        assert cfg["smtp_password"] == "SG.testsecretkey123"
        assert cfg["email_from"] == "security@mycustomdomain.com"
        assert cfg["frontend_url"] == "https://app.mycustomdomain.com"
        assert is_smtp_configured()

    def test_get_email_config_invalid_port_fallback(self, monkeypatch):
        monkeypatch.setenv("SMTP_PORT", "invalid_not_a_number")
        cfg = get_email_config()
        assert cfg["smtp_port"] == DEFAULT_SMTP_PORT

    def test_mask_email_formatting(self):
        assert mask_email("alex@northstargoods.com") == "a**x@northstargoods.com"
        assert mask_email("a@northstargoods.com") == "a*@northstargoods.com"
        assert mask_email("ab@northstargoods.com") == "a*@northstargoods.com"
        assert mask_email("user.name.123@domain.co.uk") == "u***********3@domain.co.uk"
        assert mask_email("invalid-email") == "[redacted]"
        assert mask_email("") == "[redacted]"


# ==============================================================================
# 3. Email Dispatch & Transport Tests
# ==============================================================================

class TestEmailDispatch:
    def test_development_fallback_simulation(self, monkeypatch, caplog):
        monkeypatch.delenv("SMTP_HOST", raising=False)
        caplog.set_level(logging.INFO)

        raw_token = "raw_secret_token_never_log_this_xyz999"
        success = run_async(send_password_reset_email("alex@northstargoods.com", raw_token))

        assert success is True
        # Verify log output records simulated delivery with masked email
        assert "development mode" in caplog.text
        assert "Simulated reset email delivery to a**x@northstargoods.com" in caplog.text
        # CRITICAL: verify secret token is NOT in the logs
        assert raw_token not in caplog.text
        assert f"token={raw_token}" not in caplog.text

    def test_production_smtp_starttls_success(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.sendgrid.net")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USERNAME", "apikey")
        monkeypatch.setenv("SMTP_PASSWORD", "SG.very_secret_pass")

        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", mock_smtp_class):
            success = run_async(
                send_password_reset_email(
                    "alex@northstargoods.com",
                    "secure_token_456",
                    frontend_url="https://app.ahonix.com",
                )
            )

        assert success is True
        mock_smtp_class.assert_called_once_with("smtp.sendgrid.net", 587, timeout=15)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("apikey", "SG.very_secret_pass")
        mock_smtp_instance.send_message.assert_called_once()

    def test_production_smtp_ssl_success(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USERNAME", "alex@northstargoods.com")
        monkeypatch.setenv("SMTP_PASSWORD", "app_password_secret")

        mock_ssl_instance = MagicMock()
        mock_ssl_class = MagicMock(return_value=mock_ssl_instance)
        mock_ssl_instance.__enter__ = MagicMock(return_value=mock_ssl_instance)
        mock_ssl_instance.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP_SSL", mock_ssl_class):
            success = run_async(send_password_reset_email("alex@northstargoods.com", "secure_token_789"))

        assert success is True
        mock_ssl_class.assert_called_once()
        mock_ssl_instance.login.assert_called_once_with("alex@northstargoods.com", "app_password_secret")
        mock_ssl_instance.send_message.assert_called_once()

    def test_smtp_failure_handling_does_not_crash(self, monkeypatch, caplog):
        monkeypatch.setenv("SMTP_HOST", "smtp.badhost.local")
        monkeypatch.setenv("SMTP_PORT", "587")
        caplog.set_level(logging.ERROR)

        with patch("smtplib.SMTP", side_effect=OSError("Connection refused")):
            success = run_async(send_password_reset_email("alex@northstargoods.com", "token_fail_test"))

        # Returns False safely, does not crash or raise unhandled exception
        assert success is False
        assert "Network error sending email" in caplog.text
        # Secrets should not be in the log
        assert "token_fail_test" not in caplog.text


# ==============================================================================
# 4. Password Reset Flow, Invalidation & Rate Limiting Tests
# ==============================================================================

class TestPasswordResetFlow:
    def test_forgot_password_generic_response_existing_user(self, mock_db):
        body = ForgotBody(email="alex@northstargoods.com")
        resp = run_async(forgot_password(body))
        assert resp == {"ok": True, "message": "If an account exists, a reset link has been sent."}

        # Verify a reset token document was created
        tokens = mock_db.password_reset_tokens.docs
        assert len(tokens) == 1
        assert tokens[0]["user_id"] == "user_12345"
        assert tokens[0]["used"] is False
        assert len(tokens[0]["token"]) > 20

    def test_forgot_password_generic_response_nonexistent_user(self, mock_db):
        body = ForgotBody(email="ghost_nonexistent@example.com")
        resp = run_async(forgot_password(body))
        assert resp == {"ok": True, "message": "If an account exists, a reset link has been sent."}

        # No token should be created for non-existent users
        assert len(mock_db.password_reset_tokens.docs) == 0

    def test_forgot_password_generic_response_oauth_user(self, mock_db):
        body = ForgotBody(email="google_user@northstargoods.com")
        resp = run_async(forgot_password(body))
        assert resp == {"ok": True, "message": "If an account exists, a reset link has been sent."}

        # No token should be created for OAuth users
        assert len(mock_db.password_reset_tokens.docs) == 0

    def test_token_invalidation_on_second_request(self, mock_db):
        body = ForgotBody(email="alex@northstargoods.com")

        # 1st request
        run_async(forgot_password(body))
        tokens_after_first = list(mock_db.password_reset_tokens.docs)
        assert len(tokens_after_first) == 1
        first_token = tokens_after_first[0]["token"]
        assert tokens_after_first[0]["used"] is False

        # 2nd request
        run_async(forgot_password(body))
        tokens_after_second = mock_db.password_reset_tokens.docs
        assert len(tokens_after_second) == 2

        # First token must now be marked as used/invalidated
        old_token_doc = next(t for t in tokens_after_second if t["token"] == first_token)
        assert old_token_doc["used"] is True
        assert old_token_doc.get("invalidated") is True

        # Second token must be active
        new_token_doc = next(t for t in tokens_after_second if t["token"] != first_token)
        second_token = new_token_doc["token"]
        assert new_token_doc["used"] is False

        # Attempting to use the first (invalidated) token must fail
        with pytest.raises(HTTPException) as exc_info:
            run_async(reset_password(ResetBody(token=first_token, password="BrandNewPassword123!")))
        assert exc_info.value.status_code == 400
        assert "Invalid or expired reset token" in exc_info.value.detail

        # Using the second (active) token must succeed
        success_resp = run_async(reset_password(ResetBody(token=second_token, password="BrandNewPassword123!")))
        assert success_resp == {"ok": True}

        # User's password should now be updated
        updated_user = run_async(mock_db.users.find_one({"email": "alex@northstargoods.com"}))
        assert verify_password("BrandNewPassword123!", updated_user["password_hash"])

    def test_rejection_of_expired_token(self, mock_db):
        # Insert an expired token
        past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        expired_token = "expired_token_test_1234567890abcdef"
        mock_db.password_reset_tokens.docs.append({
            "token": expired_token,
            "user_id": "user_12345",
            "expires_at": past_time,
            "used": False,
            "created_at": past_time,
        })

        with pytest.raises(HTTPException) as exc_info:
            run_async(reset_password(ResetBody(token=expired_token, password="NewPassword123!")))
        assert exc_info.value.status_code == 400
        assert "Reset token has expired" in exc_info.value.detail

    def test_rejection_of_already_used_token(self, mock_db):
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        used_token = "already_used_token_1234567890abcdef"
        mock_db.password_reset_tokens.docs.append({
            "token": used_token,
            "user_id": "user_12345",
            "expires_at": future_time,
            "used": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        with pytest.raises(HTTPException) as exc_info:
            run_async(reset_password(ResetBody(token=used_token, password="NewPassword123!")))
        assert exc_info.value.status_code == 400
        assert "Invalid or expired reset token" in exc_info.value.detail

    def test_rejection_of_malformed_token(self, mock_db):
        with pytest.raises(HTTPException) as exc_info:
            run_async(reset_password(ResetBody(token="!invalid$char*", password="NewPassword123!")))
        assert exc_info.value.status_code == 400
        assert "Invalid or expired reset token" in exc_info.value.detail

    def test_per_email_rate_limit(self, mock_db):
        email = "alex@northstargoods.com"
        body = ForgotBody(email=email)

        # First 3 requests must succeed within 15 minutes
        for i in range(3):
            resp = run_async(forgot_password(body))
            assert resp["ok"] is True

        # 4th request must be rejected with 429 Too Many Requests
        with pytest.raises(HTTPException) as exc_info:
            run_async(forgot_password(body))
        assert exc_info.value.status_code == 429
        assert "Too many requests" in exc_info.value.detail

        # A different email must not be blocked
        other_resp = run_async(forgot_password(ForgotBody(email="sarah@othermerchant.com")))
        assert other_resp["ok"] is True

    def test_user_isolation(self, mock_db):
        # Reset Alex's password
        run_async(forgot_password(ForgotBody(email="alex@northstargoods.com")))
        alex_token = mock_db.password_reset_tokens.docs[-1]["token"]

        run_async(reset_password(ResetBody(token=alex_token, password="AlexNewPassword123!")))

        # Check Alex's hash updated
        alex = run_async(mock_db.users.find_one({"email": "alex@northstargoods.com"}))
        assert verify_password("AlexNewPassword123!", alex["password_hash"])

        # Check Sarah's hash is completely unchanged
        sarah = run_async(mock_db.users.find_one({"email": "sarah@othermerchant.com"}))
        assert verify_password("SarahSecret123!", sarah["password_hash"])
        assert not verify_password("AlexNewPassword123!", sarah["password_hash"])

    def test_email_send_failure_resilience(self, mock_db, monkeypatch):
        # Mock send_password_reset_email to raise or fail
        with patch("auth.send_password_reset_email", side_effect=Exception("SMTP Connection Timeout")):
            resp = run_async(forgot_password(ForgotBody(email="alex@northstargoods.com")))

        # Must not crash or leak error to caller; returns generic response
        assert resp == {"ok": True, "message": "If an account exists, a reset link has been sent."}
        # Token is still generated so a reissue/retry flow functions properly
        assert len(mock_db.password_reset_tokens.docs) == 1


# ==============================================================================
# 5. Security & Log Sanitization Tests
# ==============================================================================

class TestSecurityAndLogSanitization:
    def test_zero_raw_secrets_in_logs_development(self, mock_db, caplog):
        caplog.set_level(logging.DEBUG)

        run_async(forgot_password(ForgotBody(email="alex@northstargoods.com")))
        created_token = mock_db.password_reset_tokens.docs[-1]["token"]

        all_logs = caplog.text
        # Assert raw token is NEVER logged
        assert created_token not in all_logs
        assert f"token={created_token}" not in all_logs
        # Assert raw reset URL is NEVER logged
        assert f"/reset-password?token={created_token}" not in all_logs
        # Assert full unmasked email is not logged
        assert "alex@northstargoods.com" not in all_logs
        # Assert masked email IS used
        assert "a**x@northstargoods.com" in all_logs

    def test_zero_raw_secrets_in_logs_production(self, mock_db, monkeypatch, caplog):
        monkeypatch.setenv("SMTP_HOST", "smtp.postmarkapp.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USERNAME", "postmark_api_user")
        monkeypatch.setenv("SMTP_PASSWORD", "super_secret_postmark_key_999")
        caplog.set_level(logging.DEBUG)

        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", return_value=mock_smtp):
            run_async(forgot_password(ForgotBody(email="alex@northstargoods.com")))

        created_token = mock_db.password_reset_tokens.docs[-1]["token"]
        all_logs = caplog.text

        # Zero credential or token leakage
        assert created_token not in all_logs
        assert "super_secret_postmark_key_999" not in all_logs
        assert f"/reset-password?token={created_token}" not in all_logs
        assert "alex@northstargoods.com" not in all_logs
