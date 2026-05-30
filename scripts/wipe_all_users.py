"""
wipe_all_users.py
-----------------
Wipe ALL user data and related records for a clean testing slate.

Safe to re-run (idempotent).
Does NOT touch: plan, alembic_version.
Does NOT delete uploaded files on disk (they become orphaned but harmless).

Usage:
    cd banaaiq
    python scripts/wipe_all_users.py
"""
import os
import sys

# ── Bootstrap: add banaaiq/ to path and load .env ────────────────────────────
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
from models import (  # noqa: E402
    AIQueryLog,
    BOQ,
    BOQActual,
    BOQPackage,
    DPR,
    EngineerPackage,
    FeatureProject,
    InventoryAssignment,
    InventoryItem,
    Invoice,
    Notification,
    PaymentMethod,
    Project,
    ProjectAssignment,
    ProjectCounter,
    ProjectMilestone,
    StockRequest,
    Subscription,
    Task,
    TaskLog,
    UsageLog,
    User,
)

# Deletion order respects foreign-key dependencies (children before parents).
# Each entry: (Model class, human-readable label)
_WIPE_ORDER = [
    (TaskLog,             "task_logs"),
    (Task,                "tasks"),
    (UsageLog,            "usage_logs"),
    (InventoryAssignment, "inventory_assignments"),
    (StockRequest,        "stock_requests"),
    (InventoryItem,       "inventory_items"),
    (BOQActual,           "boq_actuals"),
    (BOQPackage,          "boq_packages"),
    (EngineerPackage,     "engineer_packages"),
    (BOQ,                 "boqs"),
    (ProjectAssignment,   "project_assignments"),
    (ProjectMilestone,    "project_milestone"),
    (DPR,                 "dprs"),
    (Project,             "projects"),
    (ProjectCounter,      "project_counters"),
    (Notification,        "notification"),
    (AIQueryLog,          "ai_query_log"),
    (Invoice,             "invoice"),
    (PaymentMethod,       "payment_method"),
    (Subscription,        "subscription"),
    (FeatureProject,      "feature_projects"),
    (User,                "users"),
]

with app.app_context():
    # ── Print BEFORE counts ───────────────────────────────────────────────────
    print("\n=== ROW COUNTS BEFORE WIPE ===")
    before_counts = {}
    for model, label in _WIPE_ORDER:
        try:
            count = model.query.count()
        except Exception:
            count = "N/A"
        before_counts[label] = count
        print(f"  {label:<30} {count}")
    print()

    # ── Confirmation prompt ───────────────────────────────────────────────────
    print("About to delete ALL users and ALL their data. Type YES to proceed:")
    answer = input("> ").strip()
    if answer != "YES":
        print("Aborted — no data was changed.")
        sys.exit(0)
    print()

    # ── Wipe in order ────────────────────────────────────────────────────────
    for model, label in _WIPE_ORDER:
        try:
            deleted = model.query.delete()
            db.session.flush()
            print(f"  Deleted {deleted:>6} rows from {label}")
        except Exception as exc:
            db.session.rollback()
            print(f"  ERROR deleting {label}: {exc}")
            sys.exit(1)

    db.session.commit()

    # ── Print AFTER counts ────────────────────────────────────────────────────
    print("\n=== ROW COUNTS AFTER WIPE ===")
    all_zero = True
    for model, label in _WIPE_ORDER:
        try:
            count = model.query.count()
        except Exception:
            count = "N/A"
        status = "" if count == 0 else "  ← NON-ZERO"
        if count != 0:
            all_zero = False
        print(f"  {label:<30} {count}{status}")

    print()
    if all_zero:
        print("All user data wiped. Ready for fresh testing.")
    else:
        print("WARNING: some tables still have rows — check errors above.")
