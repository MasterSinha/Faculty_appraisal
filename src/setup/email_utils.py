import os
import ssl
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)


def _make_conf() -> ConnectionConfig:
    """Build ConnectionConfig from current env vars each call so UI changes take effect immediately."""
    tls = os.getenv("MAIL_TLS", "true").lower() == "true"
    ssl_flag = os.getenv("MAIL_SSL", "false").lower() == "true"
    username = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER", "")
    password = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
    server = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT", "587"))
    
    return ConnectionConfig(
        MAIL_USERNAME=username,
        MAIL_PASSWORD=password,
        MAIL_FROM=os.getenv("MAIL_FROM", username or "noreply@example.com"),
        MAIL_PORT=port,
        MAIL_SERVER=server,
        MAIL_FROM_NAME="Faculty Appraisal System",
        MAIL_STARTTLS=tls,
        MAIL_SSL_TLS=ssl_flag,
        USE_CREDENTIALS=bool(username and password),
        VALIDATE_CERTS=True,
    )


def _email_configured() -> bool:
    username = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER")
    server = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST")
    relay = os.getenv("RESEND_API_KEY") or os.getenv("SENDGRID_API_KEY") or os.getenv("MAIL_HTTP_RELAY_URL")
    return bool((username and server) or relay)


def _send_sync_smtplib(recipients: list[str], subject: str, body_html: str) -> bool:
    """Fallback synchronous SMTP sender using Python's standard smtplib."""
    username = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER", "")
    password = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
    server   = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST", "smtp.gmail.com")
    port     = int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT", "587"))
    mail_from = os.getenv("MAIL_FROM") or username or "noreply@example.com"
    from_name = "Faculty Appraisal System"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{mail_from}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(body_html, "html"))

    try:
        if port == 465 or os.getenv("MAIL_SSL", "false").lower() == "true":
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP_SSL(server, port, context=ctx, timeout=15) as s:
                if username and password:
                    s.login(username, password)
                s.sendmail(mail_from, recipients, msg.as_string())
        else:
            with smtplib.SMTP(server, port, timeout=15) as s:
                s.ehlo()
                if os.getenv("MAIL_TLS", "true").lower() == "true":
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    s.starttls(context=ctx)
                    s.ehlo()
                if username and password:
                    s.login(username, password)
                s.sendmail(mail_from, recipients, msg.as_string())
        logger.info(f"Successfully sent email via fallback smtplib to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Fallback smtplib failed for {recipients}: {type(e).__name__}: {e}")
        return False


async def _send_via_http_relay(recipients: list[str], subject: str, body_html: str) -> bool:
    """HTTPS API Relay sender (Resend / SendGrid / Custom HTTP Relay) for VMs where SMTP ports 25/465/587 are blocked."""
    resend_key   = os.getenv("RESEND_API_KEY")
    sendgrid_key = os.getenv("SENDGRID_API_KEY")
    relay_url    = os.getenv("MAIL_HTTP_RELAY_URL")
    mail_from    = os.getenv("MAIL_FROM") or os.getenv("MAIL_USERNAME") or "noreply@example.com"

    async with httpx.AsyncClient(timeout=15.0) as client:
        if resend_key:
            try:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    json={"from": mail_from, "to": recipients, "subject": subject, "html": body_html}
                )
                if resp.status_code in (200, 201):
                    logger.info(f"Successfully sent email via Resend API to {recipients}")
                    return True
                else:
                    logger.error(f"Resend API error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.error(f"Resend HTTP request failed: {e}")

        if sendgrid_key:
            try:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {sendgrid_key}"},
                    json={
                        "personalizations": [{"to": [{"email": r} for r in recipients]}],
                        "from": {"email": mail_from},
                        "subject": subject,
                        "content": [{"type": "text/html", "value": body_html}]
                    }
                )
                if resp.status_code in (200, 202):
                    logger.info(f"Successfully sent email via SendGrid API to {recipients}")
                    return True
                else:
                    logger.error(f"SendGrid API error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.error(f"SendGrid HTTP request failed: {e}")

        if relay_url:
            try:
                resp = await client.post(
                    relay_url,
                    json={"from": mail_from, "to": recipients, "subject": subject, "html": body_html}
                )
                if resp.status_code < 400:
                    logger.info(f"Successfully sent email via HTTP Relay to {recipients}")
                    return True
            except Exception as e:
                logger.error(f"HTTP Relay request failed: {e}")

    return False


async def dispatch_email(recipients: list[str], subject: str, body_html: str) -> bool:
    """Bulletproof multi-channel email dispatcher."""
    # 1. Try HTTPS API Relay first if configured (bypasses all VM SMTP port blocks)
    if os.getenv("RESEND_API_KEY") or os.getenv("SENDGRID_API_KEY") or os.getenv("MAIL_HTTP_RELAY_URL"):
        if await _send_via_http_relay(recipients, subject, body_html):
            return True

    if not _email_configured():
        logger.warning("No email transport (SMTP or HTTP Relay) configured in .env.")
        return False

    # 2. Try primary fastapi-mail (aiosmtplib)
    try:
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=body_html,
            subtype=MessageType.html,
        )
        fm = FastMail(_make_conf())
        await fm.send_message(message)
        logger.info(f"Email successfully sent via fastapi-mail to {recipients}")
        return True
    except Exception as e:
        logger.warning(f"fastapi-mail failed to send to {recipients} ({type(e).__name__}: {e}). Trying fallback smtplib...")

    # 3. Fallback to standard Python smtplib in thread pool
    return await asyncio.to_thread(_send_sync_smtplib, recipients, subject, body_html)


async def send_reset_email(email: str, reset_url: str) -> bool:
    """Sends a password-reset email containing a one-time reset link."""
    logger.info(f"Generated password reset link for {email}: {reset_url}")
    print(f"\n========================================\nPASSWORD RESET LINK for {email}:\n{reset_url}\n========================================\n", flush=True)

    html = f"""
    <h3>Faculty Appraisal System — Password Reset</h3>
    <p>You requested a password reset. Click the link below to set a new password:</p>
    <a href="{reset_url}">{reset_url}</a>
    <br><br>
    <p>This link expires in 1 hour. If you did not request a reset, please ignore this email.</p>
    """

    return await dispatch_email([email], "Password Reset — Faculty Appraisal System", html)


async def send_announcement_emails(recipients: list[str], title: str, body: str, sent_by: str):
    """Broadcast an announcement email to all matching registered users."""
    if not recipients:
        return

    from datetime import datetime
    now       = datetime.now()
    date_str  = now.strftime("%d %B %Y")
    year_str  = now.strftime("%Y")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#dde3ed;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#dde3ed;padding:40px 16px;">
  <tr><td align="center">

    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#ffffff;
                  border-radius:14px;overflow:hidden;
                  box-shadow:0 8px 40px rgba(15,23,42,0.14);">

      <tr>
        <td style="height:5px;background:#1e3a8a;font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <tr>
        <td align="center" style="background:#1e3a8a;padding:32px 40px 28px;">
          <div style="margin-bottom:14px;">
            <span style="display:inline-block;
                         background:rgba(255,255,255,0.09);
                         border:1px solid rgba(255,255,255,0.20);
                         border-radius:4px;padding:5px 16px;">
              <span style="color:#bfdbfe;font-size:9px;font-weight:700;
                           letter-spacing:1.6px;text-transform:uppercase;">
                Dr. D. Y. Patil International University, Pune
              </span>
            </span>
          </div>

          <div style="color:#ffffff;font-size:26px;font-weight:800;
                      letter-spacing:-0.6px;line-height:1.15;margin-bottom:6px;">
            Faculty Appraisal System
          </div>
          <div style="color:#93c5fd;font-size:12px;font-weight:500;letter-spacing:0.3px;">
            Official Communication Portal
          </div>
        </td>
      </tr>

      <tr>
        <td style="height:4px;background:#f59e0b;font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <tr>
        <td style="background:#f8fafc;padding:11px 40px;border-bottom:1px solid #e2e8f0;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="color:#64748b;font-size:11px;font-weight:600;">
                {date_str}
              </td>
              <td align="right">
                <span style="display:inline-block;
                             background:#dbeafe;color:#1e40af;
                             font-size:9px;font-weight:800;
                             letter-spacing:1.2px;text-transform:uppercase;
                             padding:4px 12px;border-radius:4px;
                             border:1px solid #bfdbfe;">
                  Official Notice
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <tr>
        <td style="background:#ffffff;padding:36px 40px 30px;">
          <div style="color:#94a3b8;font-size:10px;font-weight:700;
                      letter-spacing:1.4px;text-transform:uppercase;margin-bottom:8px;">
            Announcement
          </div>

          <h1 style="margin:0 0 18px;color:#0f172a;font-size:24px;
                     font-weight:800;line-height:1.25;letter-spacing:-0.5px;">
            {title}
          </h1>

          <div style="height:1px;background:#e2e8f0;margin-bottom:24px;"></div>

          <div style="color:#334155;font-size:14.5px;line-height:1.85;
                      white-space:pre-line;margin-bottom:28px;">
{body}
          </div>

          <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;">
            <tr>
              <td style="border-left:3px solid #2563eb;
                         background:#f0f7ff;border-radius:0 7px 7px 0;
                         padding:14px 18px;">
                <div style="color:#1e40af;font-size:12.5px;line-height:1.65;">
                  <strong>Please Note:</strong>&nbsp; This is an official communication
                  from the Faculty Appraisal System at Dr. D. Y. Patil International
                  University. Please read carefully and take any required action promptly.
                </div>
              </td>
            </tr>
          </table>

        </td>
      </tr>

      <tr>
        <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:22px 40px;">
          <div style="color:#1e293b;font-size:12px;font-weight:700;margin-bottom:3px;">
            Dr. D. Y. Patil International University, Pune
          </div>
          <div style="color:#64748b;font-size:11px;line-height:1.6;margin-bottom:14px;">
            Faculty Appraisal System &nbsp;&bull;&nbsp;
            Confidential &nbsp;&bull;&nbsp; For Internal Use Only
          </div>

          <div style="height:1px;background:#e2e8f0;margin-bottom:14px;"></div>

          <div style="color:#94a3b8;font-size:10.5px;line-height:1.75;">
            This email was sent by&nbsp;<strong style="color:#64748b;">{sent_by}</strong>
            &nbsp;via the Faculty Appraisal System.<br>
            This is an automated notification &mdash; please do not reply to this email.
          </div>
        </td>
      </tr>

      <tr>
        <td align="center" style="background:#0f172a;padding:12px 40px;">
          <span style="color:#475569;font-size:10px;letter-spacing:0.3px;">
            &copy; {year_str} Dr. D. Y. Patil International University
            &nbsp;&bull;&nbsp; All rights reserved
          </span>
        </td>
      </tr>

    </table>

    <div style="color:#94a3b8;font-size:10px;text-align:center;
                margin-top:18px;max-width:440px;
                margin-left:auto;margin-right:auto;line-height:1.65;">
      If you received this email in error, please disregard it and notify
      your system administrator. Do not share this message externally.
    </div>

  </td></tr>
</table>

</body>
</html>"""

    for recipient in recipients:
        await dispatch_email([recipient], f"[Official Notice] {title} — DYP University Faculty Appraisal", html)


async def send_verification_email(email: EmailStr, token: str) -> bool:
    """Sends a verification email with a link to the verify endpoint."""
    app_url = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")

    if app_url.endswith(".run.app.a.run.app"):
        app_url = app_url.replace(".run.app.a.run.app", ".a.run.app")

    verify_url = f"{app_url}/api/v1/auth/verify-email?token={token}"

    html = f"""
    <h3>Welcome to the Faculty Appraisal System</h3>
    <p>Please verify your email address by clicking the link below:</p>
    <a href="{verify_url}">Verify Email Address</a>
    <br><br>
    <p>If you did not create an account, please ignore this email.</p>
    """

    return await dispatch_email([email], "Email Verification - Faculty Appraisal System", html)
