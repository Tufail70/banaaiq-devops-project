"""backfill_india_launch.py
--------------------------
One-shot backfill for India launch migrations 016-017.

Migration 016 already sets price_inr/price_inr_annual via SQL UPDATE,
but price_usd and default_currency need filling. Migration 017 sets
server_default on country/preferred_currency, but existing rows are NULL.

Safe to run multiple times — each update is conditional.

Usage:
    cd banaaiq
    python scripts/backfill_india_launch.py
"""
import logging
import os
import sys

# ── Bootstrap ────────────────────────────────────────────────────────────────
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("backfill")

from app import app, db
from models import Plan, User

def backfill():
    with app.app_context():
        # ── Plans ────────────────────────────────────────────────────────────
        log.info("--- Plan backfill ---")
        plans_updated = 0

        starter = Plan.query.filter_by(name="starter").first()
        if starter:
            if starter.price_inr is None:
                starter.price_inr = 1499
                log.info("  starter.price_inr set to 1499")
            if starter.price_inr_annual is None:
                starter.price_inr_annual = 14990
                log.info("  starter.price_inr_annual set to 14990")
            if starter.price_usd is None:
                starter.price_usd = 25
                log.info("  starter.price_usd set to 25")
            if starter.default_currency is None:
                starter.default_currency = "INR"
                log.info("  starter.default_currency set to INR")
            plans_updated += 1
        else:
            log.warning("  Plan 'starter' not found — skipping")

        pro = Plan.query.filter_by(name="professional").first()
        if pro:
            if pro.price_inr is None:
                pro.price_inr = 3999
                log.info("  professional.price_inr set to 3999")
            if pro.price_inr_annual is None:
                pro.price_inr_annual = 39990
                log.info("  professional.price_inr_annual set to 39990")
            if pro.price_usd is None:
                pro.price_usd = 65
                log.info("  professional.price_usd set to 65")
            if pro.default_currency is None:
                pro.default_currency = "INR"
                log.info("  professional.default_currency set to INR")
            plans_updated += 1
        else:
            log.warning("  Plan 'professional' not found — skipping")

        enterprise = Plan.query.filter_by(name="enterprise").first()
        if enterprise:
            if enterprise.default_currency is None:
                enterprise.default_currency = "INR"
                log.info("  enterprise.default_currency set to INR")
            # price_inr intentionally left NULL (custom pricing)
            plans_updated += 1
        else:
            log.warning("  Plan 'enterprise' not found — skipping")

        db.session.flush()
        log.info(f"  Plans processed: {plans_updated}")

        # Print final plan state
        for p in Plan.query.all():
            log.info(
                f"  [{p.name}] price_inr={p.price_inr} "
                f"price_inr_annual={p.price_inr_annual} "
                f"price_usd={p.price_usd} "
                f"default_currency={p.default_currency}"
            )

        # ── Users ────────────────────────────────────────────────────────────
        log.info("--- User backfill ---")
        null_country_count = User.query.filter(User.country.is_(None)).count()
        log.info(f"  Users with NULL country: {null_country_count}")

        if null_country_count > 0:
            updated = User.query.filter(User.country.is_(None)).update(
                {"country": "IN", "preferred_currency": "INR"},
                synchronize_session=False,
            )
            log.info(f"  Backfilled {updated} users → country='IN', preferred_currency='INR'")
        else:
            log.info("  All users already have country set — nothing to backfill")

        db.session.commit()
        log.info("--- Backfill complete ---")


if __name__ == "__main__":
    try:
        backfill()
        sys.exit(0)
    except Exception as exc:
        log.exception(f"Backfill failed: {exc}")
        sys.exit(1)
