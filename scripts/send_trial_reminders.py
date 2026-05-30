"""send_trial_reminders.py
------------------------
Daily cron job — send trial-ending reminder emails to users whose
free trial is expiring in approximately 3 days or 1 day.

Reminder flags on Subscription prevent duplicate sends:
  reminder_3d_sent  — set True after the 3-day email is sent
  reminder_1d_sent  — set True after the 1-day email is sent

Exit codes:
  0 — completed without errors
  1 — unrecoverable setup/DB error
  2 — completed but ≥1 email send failed (see stderr for details)

Usage:
    cd banaaiq
    python scripts/send_trial_reminders.py

Cron example (daily at 07:00 UTC):
    0 7 * * * /path/to/venv/bin/python /path/to/banaaiq/scripts/send_trial_reminders.py >> /var/log/banaaiq/trial_reminders.log 2>&1
"""
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# ── Bootstrap: add banaaiq/ to sys.path and load .env ────────────────────────
_BANAAIQ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BANAAIQ_DIR)

_env_path = os.path.join(_BANAAIQ_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

from app import app, db  # noqa: E402
from flask import render_template  # noqa: E402
from mailer import MailError, send_email  # noqa: E402
from models import Subscription  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("trial_reminders")

# ---------------------------------------------------------------------------
# Time window constants
#
# We use a ±12-hour window around each target to tolerate cron drift and
# DST shifts while still preventing double-sending (the DB flag guards that).
# ---------------------------------------------------------------------------

_NOW_UTC = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC to match DB

_3D_WINDOW_START = _NOW_UTC + timedelta(days=2, hours=12)   # 2.5 days from now
_3D_WINDOW_END   = _NOW_UTC + timedelta(days=3, hours=12)   # 3.5 days from now

_1D_WINDOW_START = _NOW_UTC + timedelta(hours=12)            # 0.5 days from now
_1D_WINDOW_END   = _NOW_UTC + timedelta(days=1, hours=12)    # 1.5 days from now


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _send_trial_reminder(sub, template, subject):
    """Render template and send; raises MailError on failure."""
    user = sub.user
    html = render_template(template, user=user, subscription=sub)
    send_email(to=user.email, subject=subject, html_body=html)


def run():
    errors = 0

    with app.app_context():
        # ── 3-day reminders ──────────────────────────────────────────────────
        subs_3d = (
            Subscription.query
            .filter(
                Subscription.status == "trialing",
                Subscription.trial_end >= _3D_WINDOW_START,
                Subscription.trial_end <  _3D_WINDOW_END,
                Subscription.reminder_3d_sent == False,  # noqa: E712
            )
            .all()
        )

        logger.info("3-day window: %s — %s | candidates: %d",
                    _3D_WINDOW_START.strftime("%Y-%m-%d %H:%M"),
                    _3D_WINDOW_END.strftime("%Y-%m-%d %H:%M"),
                    len(subs_3d))

        for sub in subs_3d:
            try:
                _send_trial_reminder(
                    sub,
                    "emails/trial_ending_3d.html",
                    "Your BanaaIQ trial ends in 3 days",
                )
                sub.reminder_3d_sent = True
                db.session.commit()
                logger.info("3d reminder sent → %s (sub#%d)", sub.user.email, sub.id)
            except MailError as exc:
                db.session.rollback()
                logger.error("3d reminder FAILED → %s (sub#%d): %s",
                             sub.user.email, sub.id, exc)
                errors += 1
            except Exception as exc:
                db.session.rollback()
                logger.exception("Unexpected error for sub#%d: %s", sub.id, exc)
                errors += 1

        # ── 1-day reminders ──────────────────────────────────────────────────
        subs_1d = (
            Subscription.query
            .filter(
                Subscription.status == "trialing",
                Subscription.trial_end >= _1D_WINDOW_START,
                Subscription.trial_end <  _1D_WINDOW_END,
                Subscription.reminder_1d_sent == False,  # noqa: E712
            )
            .all()
        )

        logger.info("1-day window: %s — %s | candidates: %d",
                    _1D_WINDOW_START.strftime("%Y-%m-%d %H:%M"),
                    _1D_WINDOW_END.strftime("%Y-%m-%d %H:%M"),
                    len(subs_1d))

        for sub in subs_1d:
            try:
                _send_trial_reminder(
                    sub,
                    "emails/trial_ending_1d.html",
                    "Last chance — your BanaaIQ trial ends tomorrow",
                )
                sub.reminder_1d_sent = True
                db.session.commit()
                logger.info("1d reminder sent → %s (sub#%d)", sub.user.email, sub.id)
            except MailError as exc:
                db.session.rollback()
                logger.error("1d reminder FAILED → %s (sub#%d): %s",
                             sub.user.email, sub.id, exc)
                errors += 1
            except Exception as exc:
                db.session.rollback()
                logger.exception("Unexpected error for sub#%d: %s", sub.id, exc)
                errors += 1

        total_sent = len(subs_3d) + len(subs_1d) - errors
        logger.info("Done. sent=%d errors=%d", total_sent, errors)

    return errors


if __name__ == "__main__":
    sys.exit(2 if run() else 0)
