"""
wipe_tasks_module.py
--------------------
Wipe all task-related data cleanly: task_logs, tasks, and task
notifications.  Safe to re-run (idempotent).

Usage:
    cd banaaiq
    python scripts/wipe_tasks_module.py
"""
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

from app import app, db  # noqa: E402
from models import Notification, Task, TaskLog  # noqa: E402

_WIPE_ORDER = [
    (TaskLog,  "task_logs"),
    (Task,     "tasks"),
]

with app.app_context():
    # ── Row counts before ─────────────────────────────────────────────────────
    print("\n=== ROW COUNTS BEFORE WIPE ===")
    for model, label in _WIPE_ORDER:
        try:
            count = model.query.count()
        except Exception:
            count = "N/A"
        print(f"  {label:<30} {count}")

    # Count task-linked notifications
    try:
        notif_count = Notification.query.filter(
            Notification.link.like("/dashboard/tasks/%")
        ).count()
    except Exception:
        notif_count = "N/A"
    print(f"  {'task notifications':<30} {notif_count}")
    print()

    # ── Confirmation ──────────────────────────────────────────────────────────
    print("About to delete ALL task data (task_logs, tasks, task notifications).")
    print("Type YES to proceed:")
    answer = input("> ").strip()
    if answer != "YES":
        print("Aborted — no data was changed.")
        sys.exit(0)
    print()

    # ── Wipe ─────────────────────────────────────────────────────────────────
    for model, label in _WIPE_ORDER:
        try:
            deleted = model.query.delete()
            db.session.flush()
            print(f"  Deleted {deleted:>6} rows from {label}")
        except Exception as exc:
            db.session.rollback()
            print(f"  ERROR deleting {label}: {exc}")
            sys.exit(1)

    # Orphan notifications
    try:
        notif_deleted = Notification.query.filter(
            Notification.link.like("/dashboard/tasks/%")
        ).delete(synchronize_session=False)
        db.session.flush()
        print(f"  Deleted {notif_deleted:>6} task notifications")
    except Exception as exc:
        db.session.rollback()
        print(f"  ERROR deleting task notifications: {exc}")
        sys.exit(1)

    db.session.commit()

    # ── Row counts after ──────────────────────────────────────────────────────
    print("\n=== ROW COUNTS AFTER WIPE ===")
    all_zero = True
    for model, label in _WIPE_ORDER:
        try:
            count = model.query.count()
        except Exception:
            count = "N/A"
        flag = "  <- NON-ZERO" if count != 0 else ""
        if count != 0:
            all_zero = False
        print(f"  {label:<30} {count}{flag}")

    try:
        notif_remaining = Notification.query.filter(
            Notification.link.like("/dashboard/tasks/%")
        ).count()
    except Exception:
        notif_remaining = "N/A"
    flag = "  <- NON-ZERO" if notif_remaining != 0 else ""
    if notif_remaining != 0:
        all_zero = False
    print(f"  {'task notifications':<30} {notif_remaining}{flag}")

    print()
    if all_zero:
        print("Task module data wiped. Ready for rebuild.")
    else:
        print("WARNING: some tables still have rows — check errors above.")
