"""BanaaIQ unified mailer.

Providers: console (dev) | smtp | sendgrid | ses
Selected via EMAIL_PROVIDER env var (default: console).
"""
import logging
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

from flask import current_app

logger = logging.getLogger(__name__)


class MailError(Exception):
    """Raised when an email cannot be sent."""


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def retry_on_transient(max_attempts=3, base_delay=0.5):
    """Retry on transient network errors; do NOT retry auth/validation failures."""
    _NO_RETRY_KEYWORDS = ("auth", "invalid", "rejected", "550", "551", "552", "553")

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except MailError as exc:
                    last_error = exc
                    msg = str(exc).lower()
                    if any(kw in msg for kw in _NO_RETRY_KEYWORDS):
                        raise
                    if attempt < max_attempts - 1:
                        time.sleep(base_delay * (2 ** attempt))
            raise last_error
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@retry_on_transient(max_attempts=3, base_delay=0.5)
def send_email(to, subject, html_body, text_body=None, reply_to=None, headers=None):
    """Send an email via the configured provider.

    Parameters
    ----------
    to : str
        Recipient email address.
    subject : str
        Email subject line.
    html_body : str
        Full HTML email content.
    text_body : str | None
        Plain-text fallback; derived from html_body if omitted.
    reply_to : str | None
        Reply-To address.
    headers : dict | None
        Additional headers (ignored for SES/SendGrid).

    Returns
    -------
    bool
        True on success.

    Raises
    ------
    MailError
        On delivery failure.
    """
    provider = current_app.config.get("EMAIL_PROVIDER", "console")
    from_email = current_app.config.get("EMAIL_FROM", "no-reply@banaaiq.com")
    from_name = current_app.config.get("EMAIL_FROM_NAME", "BanaaIQ")

    if text_body is None:
        text_body = _html_to_text(html_body)

    dispatch = {
        "console": _send_console,
        "smtp": _send_smtp,
        "sendgrid": _send_sendgrid,
        "ses": _send_ses,
    }
    fn = dispatch.get(provider)
    if fn is None:
        raise MailError(f"Unknown EMAIL_PROVIDER: {provider!r}. Choose: console, smtp, sendgrid, ses")
    return fn(to, subject, html_body, text_body, from_email, from_name, reply_to)


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _send_console(to, subject, html, text, from_email, from_name, reply_to):
    """Dev mode — print to terminal."""
    sep = "=" * 60
    logger.info(sep)
    logger.info("[DEV EMAIL] To: %s", to)
    logger.info("[DEV EMAIL] From: %s <%s>", from_name, from_email)
    logger.info("[DEV EMAIL] Subject: %s", subject)
    if reply_to:
        logger.info("[DEV EMAIL] Reply-To: %s", reply_to)
    logger.info("[DEV EMAIL] --- Text Body ---")
    logger.info("%s", text[:2000])
    logger.info(sep)
    # Also print to stdout so flask dev server shows it prominently
    print(sep)
    print(f"[DEV EMAIL] To: {to}")
    print(f"[DEV EMAIL] Subject: {subject}")
    print(f"[DEV EMAIL] --- Text ---\n{text[:2000]}")
    print(sep)
    return True


def _send_smtp(to, subject, html, text, from_email, from_name, reply_to):
    cfg = current_app.config
    host = cfg.get("SMTP_HOST", "")
    if not host:
        raise MailError("SMTP_HOST is not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    port = int(cfg.get("SMTP_PORT", 587))
    use_tls = cfg.get("SMTP_USE_TLS", True)
    user = cfg.get("SMTP_USER", "")
    password = cfg.get("SMTP_PASSWORD", "")

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        logger.info("[SMTP] Sent to %s", to)
        return True
    except Exception as exc:
        logger.error("[SMTP] Failed to %s: %s", to, exc)
        raise MailError(f"SMTP send failed: {exc}") from exc


def _send_sendgrid(to, subject, html, text, from_email, from_name, reply_to):
    import requests as _requests
    api_key = current_app.config.get("SENDGRID_API_KEY", "")
    if not api_key:
        raise MailError("SENDGRID_API_KEY is not configured")

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": text},
            {"type": "text/html", "value": html},
        ],
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    try:
        resp = _requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if resp.status_code >= 400:
            raise MailError(f"SendGrid {resp.status_code}: {resp.text[:300]}")
        logger.info("[SendGrid] Sent to %s", to)
        return True
    except MailError:
        raise
    except Exception as exc:
        raise MailError(f"SendGrid network error: {exc}") from exc


def _send_ses(to, subject, html, text, from_email, from_name, reply_to):
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError as exc:
        raise MailError("boto3 is not installed — pip install boto3") from exc

    cfg = current_app.config
    client = boto3.client(
        "ses",
        region_name=cfg.get("AWS_REGION", "me-south-1"),
        aws_access_key_id=cfg.get("AWS_ACCESS_KEY_ID") or None,
        aws_secret_access_key=cfg.get("AWS_SECRET_ACCESS_KEY") or None,
    )

    params = {
        "Source": f"{from_name} <{from_email}>",
        "Destination": {"ToAddresses": [to]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text, "Charset": "UTF-8"},
                "Html": {"Data": html, "Charset": "UTF-8"},
            },
        },
    }
    if reply_to:
        params["ReplyToAddresses"] = [reply_to]

    try:
        client.send_email(**params)
        logger.info("[SES] Sent to %s", to)
        return True
    except ClientError as exc:
        raise MailError(f"AWS SES error: {exc}") from exc


# ---------------------------------------------------------------------------
# HTML → text helper
# ---------------------------------------------------------------------------

def _html_to_text(html_content):
    """Crude but functional HTML-to-plain-text conversion."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html_content, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    # Preserve line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
