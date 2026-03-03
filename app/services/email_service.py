import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import get_settings

log = structlog.get_logger()


async def send_email(to: str, subject: str, html: str) -> None:
    """Send a transactional email via SMTP. Silently skips when SMTP is not configured."""
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        log.warning("email.skipped", reason="SMTP not configured", to=to, subject=subject)
        return

    def _send():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, to, msg.as_string())

    try:
        await asyncio.to_thread(_send)
        log.info("email.sent", to=to, subject=subject)
    except Exception as exc:
        log.error("email.failed", to=to, subject=subject, error=str(exc))


# ── Templates ─────────────────────────────────────────────────────────────────

def registration_html(full_name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;color:#1a1a1a;">
  <h1 style="color:#6c3bdb;">Welcome to LitMusic, {full_name}!</h1>
  <p>Your account is ready. Start exploring premium loops and stem packs crafted for producers.</p>
  <a href="https://litmusic.app"
     style="display:inline-block;margin-top:8px;padding:12px 28px;background:#6c3bdb;
            color:#fff;border-radius:6px;text-decoration:none;font-weight:bold;">
    Browse Loops
  </a>
  <p style="margin-top:40px;color:#999;font-size:12px;">
    LitMusic &mdash; Professional Music Production Samples
  </p>
</body>
</html>"""


def purchase_html(full_name: str, product_title: str, product_type: str, amount: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:24px;color:#1a1a1a;">
  <h1 style="color:#6c3bdb;">Purchase Confirmed ✓</h1>
  <p>Hi {full_name}, thanks for your purchase on LitMusic!</p>
  <table style="width:100%;border-collapse:collapse;margin:20px 0;border-radius:8px;overflow:hidden;">
    <tr style="background:#f5f0ff;">
      <td style="padding:12px 16px;font-weight:bold;width:40%;">Item</td>
      <td style="padding:12px 16px;">{product_title}</td>
    </tr>
    <tr>
      <td style="padding:12px 16px;font-weight:bold;">Type</td>
      <td style="padding:12px 16px;">{product_type}</td>
    </tr>
    <tr style="background:#f5f0ff;">
      <td style="padding:12px 16px;font-weight:bold;">Amount Paid</td>
      <td style="padding:12px 16px;">${amount}</td>
    </tr>
  </table>
  <p>Your purchase is available in your library immediately.</p>
  <a href="https://litmusic.app/library"
     style="display:inline-block;margin-top:8px;padding:12px 28px;background:#6c3bdb;
            color:#fff;border-radius:6px;text-decoration:none;font-weight:bold;">
    Go to Library
  </a>
  <p style="margin-top:40px;color:#999;font-size:12px;">
    LitMusic &mdash; Professional Music Production Samples
  </p>
</body>
</html>"""
