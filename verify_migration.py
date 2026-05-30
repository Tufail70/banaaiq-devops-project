from app import app
from models import BOQ, DPR, InventoryItem, Task, TaskLog, User


TABLE_CHECKS = [
    ("User", User),
    ("DPR", DPR),
    ("BOQ", BOQ),
    ("InventoryItem", InventoryItem),
    ("Task", Task),
    ("TaskActivityLog", TaskLog),
]


def main():
    overall_success = True
    print("BanaaIQ PostgreSQL migration verification")
    print("-" * 44)

    with app.app_context():
        for label, model in TABLE_CHECKS:
            try:
                record_count = model.query.count()
                print(f"[PASS] {label}: {record_count} records")
            except Exception as exc:
                overall_success = False
                print(f"[FAIL] {label}: {exc}")

    print("-" * 44)
    print("RESULT: PASS" if overall_success else "RESULT: FAIL")
    return 0 if overall_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
