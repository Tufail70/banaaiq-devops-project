import os
import secrets as _secrets

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv()


def normalize_database_url(database_url):
    value = (database_url or "").strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql://", 1)
    return value


_flask_env = os.getenv("FLASK_ENV", "production").lower()
_database_url = os.getenv("DATABASE_URL")
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    if _flask_env == "development":
        _secret_key = _secrets.token_hex(32)
        print(
            "WARNING: SECRET_KEY not set. Using a random key — sessions will not "
            "persist across restarts. Set SECRET_KEY in your .env file."
        )
    else:
        raise RuntimeError(
            "CRITICAL: SECRET_KEY environment variable is not set. "
            "This is required in production to secure session cookies and CSRF tokens.\n"
            "Generate a key with: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "Then add SECRET_KEY=<value> to your .env file."
        )


def resolve_database_url():
    if _database_url:
        return normalize_database_url(_database_url)
    if _flask_env in {"development", "testing"}:
        return "sqlite:///banaaiq_dev.db"
    raise RuntimeError(
        "CRITICAL: DATABASE_URL environment variable is not set. "
        "Production must use an explicit database connection string."
    )


class Config:
    SECRET_KEY = _secret_key
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_MAX_RETRIES = 2
    DATABASE_URL = resolve_database_url()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "")

    SESSION_TYPE = "filesystem"
    DEBUG = os.getenv("FLASK_ENV", "production").lower() == "development"

    # Flask rejects any request body larger than this before it reaches the route handler.
    # Individual upload handlers also check per-file size (10 MB), but this is the hard cap
    # that prevents reading unbounded payloads into memory (DoS via large upload).
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # ── Cookie security ──────────────────────────────────────────────────────
    # Secure=True means cookies are only sent over HTTPS.
    # In development (HTTP) set FLASK_ENV=development to allow HTTP.
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _flask_env != "development"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True

    from datetime import timedelta as _td
    REMEMBER_COOKIE_DURATION = _td(days=30)
    # Regular session (without remember-me) — 12 hours of inactivity
    PERMANENT_SESSION_LIFETIME = _td(hours=12)
    # Invalidate session on IP/UA change (strong protection)
    SESSION_PROTECTION = "strong"


    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")
    SENTRY_ENVIRONMENT = os.getenv(
        "SENTRY_ENVIRONMENT",
        "development" if _flask_env != "production" else "production",
    )
    SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    # ── Email provider ────────────────────────────────────────────────────────
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "console")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@banaaiq.com")
    EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "BanaaIQ")

    # SMTP (generic)
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # SendGrid
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

    # AWS SES
    AWS_REGION = os.getenv("AWS_REGION", "me-south-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


    # ── Payment gateway ───────────────────────────────────────────────────────
    # Options: 'mock' (dev/test), 'razorpay' (India), 'stripe' (KSA — future)
    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "mock")

    # Razorpay (India)
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Stripe (future — KSA/Gulf)
    STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # ── India company / GST details ───────────────────────────────────────────
    COMPANY_GSTIN = os.getenv("COMPANY_GSTIN", "")           # 15-char GSTIN once registered
    COMPANY_LEGAL_NAME = os.getenv("COMPANY_LEGAL_NAME", "BanaaIQ Technologies")
    COMPANY_ADDRESS_LINE_1 = os.getenv("COMPANY_ADDRESS_LINE_1", "")
    COMPANY_ADDRESS_LINE_2 = os.getenv("COMPANY_ADDRESS_LINE_2", "")
    COMPANY_CITY = os.getenv("COMPANY_CITY", "")
    COMPANY_STATE = os.getenv("COMPANY_STATE", "")
    COMPANY_PIN = os.getenv("COMPANY_PIN", "")
    COMPANY_STATE_CODE = os.getenv("COMPANY_STATE_CODE", "")  # 2-digit GST state code


if not Config.OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY is not set. AI features will be unavailable until configured.")
