import os
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from dotenv import load_dotenv

load_dotenv()


import logging

logger = logging.getLogger(__name__)

def _make_conf() -> ConnectionConfig:
    """Build ConnectionConfig from current env vars each call so UI changes take effect immediately."""
    tls = os.getenv("MAIL_TLS", "true").lower() == "true"
    ssl = os.getenv("MAIL_SSL", "false").lower() == "true"
    username = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER", "")
    password = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
    server = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT", "587"))
    
    return ConnectionConfig(
        MAIL_USERNAME=username,
        MAIL_PASSWORD=password,
        MAIL_FROM=os.getenv("MAIL_FROM", "noreply@example.com"),
        MAIL_PORT=port,
        MAIL_SERVER=server,
        MAIL_FROM_NAME="Faculty Appraisal System",
        MAIL_STARTTLS=tls,
        MAIL_SSL_TLS=ssl,
        USE_CREDENTIALS=bool(username and password),
        VALIDATE_CERTS=True,
    )


def _email_configured() -> bool:
    username = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER")
    server = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST")
    return bool(username and server)


async def send_reset_email(email: str, reset_url: str):
    """Sends a password-reset email containing a one-time reset link."""
    # Always log the reset link so developers/admins on local VM can reset passwords even if SMTP is blocked/disabled
    logger.info(f"Generated password reset link for {email}: {reset_url}")
    print(f"\n========================================\nPASSWORD RESET LINK for {email}:\n{reset_url}\n========================================\n", flush=True)

    html = f"""
    <h3>Faculty Appraisal System — Password Reset</h3>
    <p>You requested a password reset. Click the link below to set a new password:</p>
    <a href="{reset_url}">{reset_url}</a>
    <br><br>
    <p>This link expires in 1 hour. If you did not request a reset, please ignore this email.</p>
    """

    message = MessageSchema(
        subject="Password Reset — Faculty Appraisal System",
        recipients=[email],
        body=html,
        subtype=MessageType.html,
    )

    if not _email_configured():
        logger.warning(f"SMTP is not configured in .env. Password reset link printed to console above.")
        return True

    fm = FastMail(_make_conf())
    try:
        await fm.send_message(message)
        logger.info(f"Password reset email successfully sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {str(e)}", exc_info=True)
        print(f"Failed to send reset email to {email}: {str(e)}")
        return False


async def send_announcement_emails(recipients: list[str], title: str, body: str, sent_by: str):
    """Broadcast an announcement email to all matching registered users."""
    if not recipients:
        return
    if not _email_configured():
        print("Email not configured — skipping announcement emails")
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

    <!-- ═══════════════════════════════════════════
         OUTER CARD  (600 px, white)
    ═══════════════════════════════════════════ -->
    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#ffffff;
                  border-radius:14px;overflow:hidden;
                  box-shadow:0 8px 40px rgba(15,23,42,0.14);">

      <!-- ── 1. Top stripe ── -->
      <tr>
        <td style="height:5px;background:#1e3a8a;font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <!-- ── 2. Header ── -->
      <tr>
        <td align="center" style="background:#1e3a8a;padding:32px 40px 28px;">

          <!-- University label -->
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

          <!-- System name -->
          <div style="color:#ffffff;font-size:26px;font-weight:800;
                      letter-spacing:-0.6px;line-height:1.15;margin-bottom:6px;">
            Faculty Appraisal System
          </div>
          <div style="color:#93c5fd;font-size:12px;font-weight:500;letter-spacing:0.3px;">
            Official Communication Portal
          </div>

        </td>
      </tr>

      <!-- ── 3. Gold accent line ── -->
      <tr>
        <td style="height:4px;background:#f59e0b;font-size:0;line-height:0;">&nbsp;</td>
      </tr>

      <!-- ── 4. Date / badge bar ── -->
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

      <!-- ── 5. Main content ── -->
      <tr>
        <td style="background:#ffffff;padding:36px 40px 30px;">

          <!-- "Announcement" micro-label -->
          <div style="color:#94a3b8;font-size:10px;font-weight:700;
                      letter-spacing:1.4px;text-transform:uppercase;margin-bottom:8px;">
            Announcement
          </div>

          <!-- Title -->
          <h1 style="margin:0 0 18px;color:#0f172a;font-size:24px;
                     font-weight:800;line-height:1.25;letter-spacing:-0.5px;">
            {title}
          </h1>

          <!-- Thin divider -->
          <div style="height:1px;background:#e2e8f0;margin-bottom:24px;"></div>

          <!-- Message body -->
          <div style="color:#334155;font-size:14.5px;line-height:1.85;
                      white-space:pre-line;margin-bottom:28px;">
{body}
          </div>

          <!-- Action note — left-border style -->
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

      <!-- ── 6. Footer ── -->
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

      <!-- ── 7. Bottom bar ── -->
      <tr>
        <td align="center" style="background:#0f172a;padding:12px 40px;">
          <span style="color:#475569;font-size:10px;letter-spacing:0.3px;">
            &copy; {year_str} Dr. D. Y. Patil International University
            &nbsp;&bull;&nbsp; All rights reserved
          </span>
        </td>
      </tr>

    </table>
    <!-- /OUTER CARD -->

    <!-- Below-card disclaimer -->
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

    fm = FastMail(_make_conf())
    for recipient in recipients:
        try:
            await fm.send_message(MessageSchema(
                subject=f"[Official Notice] {title} — DYP University Faculty Appraisal",
                recipients=[recipient],
                body=html,
                subtype=MessageType.html,
            ))
        except Exception as e:
            print(f"Announcement email failed for {recipient}: {e}")


async def send_verification_email(email: EmailStr, token: str):
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

    message = MessageSchema(
        subject="Email Verification - Faculty Appraisal System",
        recipients=[email],
        body=html,
        subtype=MessageType.html,
    )

    fm = FastMail(_make_conf())
    try:
        await fm.send_message(message)
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False
