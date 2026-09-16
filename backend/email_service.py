"""AHONIX Transactional Email Service.

Provides a production-grade provider abstraction for transactional email dispatch:
- Production: SMTP transport over TLS/SSL (configurable via standard SMTP_* environment variables).
- Development/Fallback: Safe simulated delivery (never logs raw reset tokens or credentials).

Security Principles:
- Zero credential or token leakage in logs (even in development mode).
- Email addresses are masked in log messages.
- Plaintext passwords and raw reset tokens are never written to disk or stdout.
- Fully asynchronous execution using background thread dispatch for blocking network I/O.
"""
import os
import smtplib
import ssl
import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger("ahonix.email")

DEFAULT_SMTP_PORT = 587
DEFAULT_EMAIL_FROM = "AHONIX Security <no-reply@ahonix.com>"

# In-memory development mailbox for testing/verification without leaking secrets to stdout
_dev_mailbox = []


def get_dev_mailbox():
    """Access development mailbox for automated testing."""
    return list(_dev_mailbox)


def clear_dev_mailbox():
    """Clear development mailbox."""
    _dev_mailbox.clear()


def mask_email(email: str) -> str:
    """Mask email address for privacy-safe logging (e.g., a***x@domain.com)."""
    if not email or "@" not in email:
        return "[redacted]"
    parts = email.split("@")
    user, domain = parts[0], parts[1]
    if len(user) <= 2:
        masked_user = user[0] + "*" if len(user) > 0 else "*"
    else:
        masked_user = user[0] + "*" * (len(user) - 2) + user[-1]
    return f"{masked_user}@{domain}"


def get_email_config() -> Dict[str, Any]:
    """Load and validate email configuration from environment variables."""
    raw_port = os.environ.get("SMTP_PORT", str(DEFAULT_SMTP_PORT)).strip()
    try:
        smtp_port = int(raw_port)
    except ValueError:
        smtp_port = DEFAULT_SMTP_PORT

    frontend_url = os.environ.get("FRONTEND_URL") or os.environ.get("APP_URL") or "http://localhost:3000"

    return {
        "resend_api_key": os.environ.get("RESEND_API_KEY", "").strip(),
        "smtp_host": os.environ.get("SMTP_HOST", "").strip(),
        "smtp_port": smtp_port,
        "smtp_username": os.environ.get("SMTP_USERNAME", "").strip(),
        "smtp_password": os.environ.get("SMTP_PASSWORD", "").strip(),
        "email_from": os.environ.get("EMAIL_FROM", "").strip() or DEFAULT_EMAIL_FROM,
        "frontend_url": frontend_url.rstrip("/"),
    }


def is_smtp_configured() -> bool:
    """Check if production SMTP transport credentials are configured."""
    cfg = get_email_config()
    return bool(cfg["smtp_host"])


def build_reset_password_html(reset_url: str, expiration_hours: int = 1) -> str:
    """Generate clean, responsive, dark-themed HTML email for password reset."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset your AHONIX password</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #08090E;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #F8FAFC;
    }}
    .wrapper {{
      width: 100%;
      background-color: #08090E;
      padding: 40px 15px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 540px;
      margin: 0 auto;
      background-color: #0F111A;
      border: 1px solid #1E2235;
      border-radius: 16px;
      overflow: hidden;
    }}
    .header {{
      padding: 32px 32px 24px;
      border-bottom: 1px solid #1E2235;
    }}
    .brand {{
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #10B981;
      text-transform: uppercase;
      text-decoration: none;
    }}
    .brand-sub {{
      font-size: 11px;
      color: #64748B;
      font-weight: 600;
      margin-top: 4px;
      letter-spacing: 0.5px;
    }}
    .content {{
      padding: 32px;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #F8FAFC;
      margin-top: 0;
      margin-bottom: 16px;
    }}
    p {{
      font-size: 14px;
      line-height: 1.6;
      color: #CBD5E1;
      margin: 0 0 20px;
    }}
    .button-wrap {{
      margin: 28px 0;
      text-align: center;
    }}
    .button {{
      display: inline-block;
      background-color: #10B981;
      color: #022C22 !important;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      padding: 14px 28px;
      border-radius: 10px;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.25);
    }}
    .fallback {{
      font-size: 12px;
      color: #64748B;
      word-break: break-all;
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #1E2235;
    }}
    .fallback a {{
      color: #10B981;
      text-decoration: underline;
    }}
    .notice {{
      background-color: #121420;
      border: 1px solid #1E2235;
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 12px;
      color: #94A3B8;
      margin-top: 24px;
    }}
    .footer {{
      padding: 24px 32px;
      border-top: 1px solid #1E2235;
      font-size: 11px;
      color: #475569;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="brand">AHONIX</div>
        <div class="brand-sub">THE AI COMMERCE OS</div>
      </div>
      <div class="content">
        <h1>Reset your password</h1>
        <p>
          We received a request to reset the password for your AHONIX merchant account.
          Click the button below to choose a new password:
        </p>
        <div class="button-wrap">
          <a href="{reset_url}" class="button" target="_blank" rel="noopener noreferrer">Reset Password</a>
        </div>
        <div class="notice">
          <strong>Security Notice:</strong> This password reset link is valid for {expiration_hours} hour.
          If you did not make this request, you can safely ignore this email. Your password will remain unchanged.
        </div>
        <div class="fallback">
          If the button above does not work, copy and paste this link into your browser:<br>
          <a href="{reset_url}" target="_blank" rel="noopener noreferrer">{reset_url}</a>
        </div>
      </div>
      <div class="footer">
        © 2026 AHONIX · The AI Commerce OS. All rights reserved.
      </div>
    </div>
  </div>
</body>
</html>"""


def build_reset_password_text(reset_url: str, expiration_hours: int = 1) -> str:
    """Generate plain-text email for password reset."""
    return f"""AHONIX — The AI Commerce OS
Reset Your Password

We received a request to reset the password for your AHONIX account.

To choose a new password, visit the following link:
{reset_url}

Security Notice:
This link is valid for {expiration_hours} hour. If you did not request this password reset, you can safely ignore this email. Your password will remain unchanged.

---
© 2026 AHONIX · All rights reserved.
"""


def _send_smtp_sync(to_email: str, subject: str, html_content: str, text_content: str, cfg: Dict[str, Any]) -> bool:
    """Synchronous SMTP worker function intended to be executed in an asyncio thread."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["email_from"]
    msg["To"] = to_email

    part_text = MIMEText(text_content, "plain", "utf-8")
    part_html = MIMEText(html_content, "html", "utf-8")
    msg.attach(part_text)
    msg.attach(part_html)

    host = cfg["smtp_host"]
    port = cfg["smtp_port"]
    user = cfg["smtp_username"]
    password = cfg["smtp_password"]

    try:
        if port == 465:
            # SSL
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
        else:
            # STARTTLS
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
                if user and password:
                    server.login(user, password)
                server.send_message(msg)

        logger.info("Successfully dispatched transactional email to %s via SMTP (%s:%s)", mask_email(to_email), host, port)
        return True
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending email to %s (%s): %s", mask_email(to_email), type(e).__name__, str(e)[:200])
        return False
    except (OSError, TimeoutError) as e:
        logger.error("Network error sending email to %s (%s): %s", mask_email(to_email), type(e).__name__, str(e)[:200])
        return False
    except Exception as e:
        logger.error("Unexpected error sending email to %s (%s)", mask_email(to_email), type(e).__name__)
        return False


async def _dispatch_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
    cfg: Dict[str, Any],
) -> bool:
    """Unified email dispatcher supporting Resend HTTP API, SMTP, or safe dev fallback.
    
    CRITICAL: Never logs raw tokens or authorization headers.
    """
    # 1. Resend HTTP API (free transactional provider)
    if cfg.get("resend_api_key"):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {cfg['resend_api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": cfg["email_from"],
                        "to": [to_email],
                        "subject": subject,
                        "html": html_content,
                        "text": text_content,
                    },
                )
                if res.status_code in (200, 201):
                    logger.info("Dispatched email to %s via Resend API", mask_email(to_email))
                    return True
                else:
                    logger.error("Resend API error (%s): %s", res.status_code, res.text[:200])
                    return False
        except Exception as e:
            logger.error("Resend API request exception for %s: %s", mask_email(to_email), type(e).__name__)
            return False

    # 2. SMTP Transport
    if cfg.get("smtp_host"):
        try:
            return await asyncio.to_thread(_send_smtp_sync, to_email, subject, html_content, text_content, cfg)
        except Exception as e:
            logger.error("Async SMTP dispatch error for %s (%s)", mask_email(to_email), type(e).__name__)
            return False

    # 3. Development / Safe Fallback Mode
    _dev_mailbox.append({"to": to_email, "subject": subject})
    logger.info(
        "Email service in development mode (RESEND_API_KEY/SMTP_HOST not set). Simulated %sdelivery to %s. (Token omitted for security)",
        "reset email " if "reset" in subject.lower() else "",
        mask_email(to_email),
    )
    return True


def build_verify_email_html(verify_url: str, expiration_hours: int = 24) -> str:
    """Generate clean, responsive, dark-themed HTML email for email verification."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verify your AHONIX account</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #08090E;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #F8FAFC;
    }}
    .wrapper {{
      width: 100%;
      background-color: #08090E;
      padding: 40px 15px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 540px;
      margin: 0 auto;
      background-color: #0F111A;
      border: 1px solid #1E2235;
      border-radius: 16px;
      overflow: hidden;
    }}
    .header {{
      padding: 32px 32px 24px;
      border-bottom: 1px solid #1E2235;
    }}
    .brand {{
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.5px;
      color: #10B981;
      text-transform: uppercase;
      text-decoration: none;
    }}
    .brand-sub {{
      font-size: 11px;
      color: #64748B;
      font-weight: 600;
      margin-top: 4px;
      letter-spacing: 0.5px;
    }}
    .content {{
      padding: 32px;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #F8FAFC;
      margin-top: 0;
      margin-bottom: 16px;
    }}
    p {{
      font-size: 14px;
      line-height: 1.6;
      color: #CBD5E1;
      margin: 0 0 20px;
    }}
    .button-wrap {{
      margin: 28px 0;
      text-align: center;
    }}
    .button {{
      display: inline-block;
      background-color: #10B981;
      color: #022C22 !important;
      font-size: 14px;
      font-weight: 700;
      text-decoration: none;
      padding: 14px 28px;
      border-radius: 10px;
      box-shadow: 0 4px 14px rgba(16, 185, 129, 0.25);
    }}
    .fallback {{
      font-size: 12px;
      color: #64748B;
      word-break: break-all;
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #1E2235;
    }}
    .fallback a {{
      color: #10B981;
      text-decoration: underline;
    }}
    .notice {{
      background-color: #121420;
      border: 1px solid #1E2235;
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 12px;
      color: #94A3B8;
      margin-top: 24px;
    }}
    .footer {{
      padding: 24px 32px;
      border-top: 1px solid #1E2235;
      font-size: 11px;
      color: #475569;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="brand">AHONIX</div>
        <div class="brand-sub">THE AI COMMERCE OS</div>
      </div>
      <div class="content">
        <h1>Verify your email address</h1>
        <p>
          Welcome to AHONIX. Please confirm your email address to activate your account
          and begin turning commerce telemetry into deterministic profit.
        </p>
        <div class="button-wrap">
          <a href="{verify_url}" class="button" target="_blank" rel="noopener noreferrer">Verify Account</a>
        </div>
        <div class="notice">
          <strong>Security Notice:</strong> This verification link is valid for {expiration_hours} hours.
          If you did not create an AHONIX account, you can safely ignore this email.
        </div>
        <div class="fallback">
          If the button above does not work, copy and paste this link into your browser:<br>
          <a href="{verify_url}" target="_blank" rel="noopener noreferrer">{verify_url}</a>
        </div>
      </div>
      <div class="footer">
        © 2026 AHONIX · The AI Commerce OS. All rights reserved.
      </div>
    </div>
  </div>
</body>
</html>"""


def build_verify_email_text(verify_url: str, expiration_hours: int = 24) -> str:
    """Generate plain-text email for account verification."""
    return f"""AHONIX — The AI Commerce OS
Verify Your Email Address

Welcome to AHONIX. Please confirm your email address to activate your account:
{verify_url}

Security Notice:
This link is valid for {expiration_hours} hours. If you did not create an AHONIX account, you can safely ignore this message.

---
© 2026 AHONIX · All rights reserved.
"""


async def send_password_reset_email(to_email: str, reset_token: str, frontend_url: Optional[str] = None) -> bool:
    """Dispatch password reset email using configured transport (Resend, SMTP, or safe dev fallback).
    
    CRITICAL: Never logs raw reset tokens or reset URLs.
    """
    cfg = get_email_config()
    base_url = (frontend_url or cfg["frontend_url"]).rstrip("/")
    reset_url = f"{base_url}/reset-password?token={reset_token}"
    subject = "Reset your AHONIX password"

    html_content = build_reset_password_html(reset_url)
    text_content = build_reset_password_text(reset_url)

    return await _dispatch_email(to_email, subject, html_content, text_content, cfg)


async def send_verification_email(to_email: str, verify_token: str, frontend_url: Optional[str] = None) -> bool:
    """Dispatch account verification email using configured transport (Resend, SMTP, or safe dev fallback).
    
    CRITICAL: Never logs raw verification tokens or URLs.
    """
    cfg = get_email_config()
    base_url = (frontend_url or cfg["frontend_url"]).rstrip("/")
    verify_url = f"{base_url}/verify-email?token={verify_token}"
    subject = "Verify your AHONIX account"

    html_content = build_verify_email_html(verify_url)
    text_content = build_verify_email_text(verify_url)

    return await _dispatch_email(to_email, subject, html_content, text_content, cfg)

