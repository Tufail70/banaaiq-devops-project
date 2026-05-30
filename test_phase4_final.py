"""
Phase 4 Verification Tests — 25 tests
Run: python test_phase4_final.py
"""
import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
from datetime import date, datetime

os.environ.setdefault("DATABASE_URL", "sqlite:///test_phase4.db")
os.environ.setdefault("SECRET_KEY", "test-phase4-secret-key-2026")
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key"

sys.path.insert(0, os.path.dirname(__file__))

import app as flask_app
from app import app as application, db
from models import (
    BOQ, BOQActual, BOQPackage, EngineerPackage, InventoryItem,
    Project, ProjectAssignment, ROLE_PROJECT_MANAGER, ROLE_SITE_ENGINEER, User,
)

# ── Config overrides ────────────────────────────────────────────────────────
application.config["TESTING"] = True
application.config["WTF_CSRF_ENABLED"] = False
application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test_phase4.db"
application.config["SERVER_NAME"] = "localhost"
application.config["PREFERRED_URL_SCHEME"] = "http"

PASS = 0
FAIL = 0
_failures = []
MIGRATION_DB_PATH = Path(tempfile.gettempdir()) / f"banaaiq_phase4_migrations_{os.getpid()}.db"
MIGRATION_DB_PATH.unlink(missing_ok=True)


def ok(n, desc):
    global PASS
    PASS += 1
    print(f"  [PASS] {n:02d}. {desc}")


def fail(n, desc, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  [FAIL] {n:02d}. {desc}" + (f" | {detail}" if detail else "")
    print(msg)
    _failures.append(msg)


def check(n, desc, condition, detail=""):
    if condition:
        ok(n, desc)
    else:
        fail(n, desc, detail)


# ── Setup ───────────────────────────────────────────────────────────────────
with application.app_context():
    db.drop_all()
    db.create_all()

    # PM-A
    pm_a = User(full_name="PM Alpha", email="pm_a_p4@test.com", role=ROLE_PROJECT_MANAGER)
    pm_a.set_password("TestPass1!")
    db.session.add(pm_a)

    # PM-B
    pm_b = User(full_name="PM Beta", email="pm_b_p4@test.com", role=ROLE_PROJECT_MANAGER)
    pm_b.set_password("TestPass1!")
    db.session.add(pm_b)

    # SE-1 (job_title = MEP Engineer)
    se1 = User(full_name="SE MEP One", email="se1_p4@test.com", role=ROLE_SITE_ENGINEER, job_title="MEP Engineer")
    se1.set_password("TestPass1!")
    db.session.add(se1)

    db.session.flush()

    # Project P1 owned by PM-A
    p1 = Project(
        user_id=pm_a.id,
        name="Phase4 Test Project",
        project_code="BIQ-2026-P4",
        client_name="Test Client",
        location_city="Riyadh",
        contract_value=2000000,
        start_date=date(2026, 1, 1),
        planned_completion=date(2026, 12, 31),
        status="active",
    )
    db.session.add(p1)
    db.session.flush()

    # BOQ for P1
    items_json = json.dumps([
        {"no": str(i), "desc": f"Item {i}", "unit": "m2", "qty": 100, "rate": 500, "total": 50000}
        for i in range(1, 6)
    ])
    boq1 = BOQ(
        user_id=pm_a.id,
        project_id=p1.id,
        title="Master BOQ Phase4",
        status="Final",
        items_json=items_json,
        grand_total=250000,
        is_master=True,
    )
    db.session.add(boq1)
    db.session.flush()

    # 3 BOQPackages
    pkg_items = json.dumps([
        {"no": "1", "desc": "Foundation", "unit": "m2", "qty": 100, "rate": 500, "total": 50000}
    ])
    boq_pkg1 = BOQPackage(
        boq_id=boq1.id,
        package_name="SE-1 Civil Package",
        package_type="civil",
        assigned_engineer_name="SE MEP One",
        assigned_engineer_email="se1_p4@test.com",
        items_json=pkg_items,
        grand_total_sar=50000,
    )
    boq_pkg2 = BOQPackage(
        boq_id=boq1.id,
        package_name="SE-1 MEP Package",
        package_type="mep",
        assigned_engineer_name="SE MEP One",
        assigned_engineer_email="se1_p4@test.com",
        items_json=pkg_items,
        grand_total_sar=50000,
    )
    boq_pkg3 = BOQPackage(
        boq_id=boq1.id,
        package_name="Other Package",
        package_type="civil",
        assigned_engineer_name="Another Engineer",
        assigned_engineer_email="other@test.com",
        items_json=pkg_items,
        grand_total_sar=50000,
    )
    db.session.add_all([boq_pkg1, boq_pkg2, boq_pkg3])

    # EngineerPackage for SE-1
    ep1 = EngineerPackage(
        project_id=p1.id,
        boq_id=boq1.id,
        assigned_user_id=se1.id,
        assigned_engineer_name="SE MEP One",
        trade="MEP",
        package_value=100000,
        completion_percentage=0.0,
    )
    db.session.add(ep1)

    db.session.commit()

    pm_a_id = pm_a.id
    pm_b_id = pm_b.id
    se1_id = se1.id
    p1_id = p1.id
    boq1_id = boq1.id
    boq_pkg1_id = boq_pkg1.id
    boq_pkg2_id = boq_pkg2.id
    boq_pkg3_id = boq_pkg3.id
    print(f"\nSetup complete: PM-A={pm_a_id}, PM-B={pm_b_id}, SE-1={se1_id}, P1={p1_id}")
    print(f"  BOQ-PKG1 (SE-1's civil)={boq_pkg1_id}, BOQ-PKG3 (other)={boq_pkg3_id}")


# ── Helper ──────────────────────────────────────────────────────────────────
def fresh(user_id):
    """Return a test client pre-authenticated as user_id via session injection."""
    c = application.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return c


# ══════════════════════════════════════════════════════════════════════════════
# 500 BUG FIX TESTS (1-3)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== 500 BUG FIX TESTS (1-3) ===")

# Test 1: PM-A GET /boq/package/<SE-1's package_id> → 200 (PM can view)
client = fresh(pm_a_id)
r = client.get(f"/boq/package/{boq_pkg1_id}")
check(1, f"PM-A GET /boq/package/{boq_pkg1_id} → 200", r.status_code == 200,
      f"got {r.status_code}")

# Test 2: SE-1 GET /boq/package/<own_package_id> → 200
client = fresh(se1_id)
r = client.get(f"/boq/package/{boq_pkg2_id}")
check(2, f"SE-1 GET /boq/package/{boq_pkg2_id} (own) → 200", r.status_code == 200,
      f"got {r.status_code}")

# Test 3: PM-B GET /boq/package/<PM-A's package_id> → 403 or 404
client = fresh(pm_b_id)
r = client.get(f"/boq/package/{boq_pkg1_id}")
check(3, f"PM-B GET /boq/package/{boq_pkg1_id} (PM-A's) → 403/404",
      r.status_code in (403, 404), f"got {r.status_code}")

# ══════════════════════════════════════════════════════════════════════════════
# ROLE VISIBILITY TESTS (4-8)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== ROLE VISIBILITY TESTS (4-8) ===")

# Test 4: PM sidebar: GET /dashboard → HTML does NOT contain translator link
client = fresh(pm_a_id)
r = client.get("/dashboard")
html = r.data.decode("utf-8", errors="replace")
# The translator link should be wrapped in site_engineer check so PM should not see nav-translator
check(4, "PM GET /dashboard → translator link not shown to PM",
      "nav-translator" not in html or
      (r.status_code == 200 and "nav-translator" not in html),
      f"status={r.status_code}, has nav-translator={'nav-translator' in html}")

# Test 5: SE sidebar: GET /dashboard → HTML contains translator link
client = fresh(se1_id)
r = client.get("/dashboard")
html_se = r.data.decode("utf-8", errors="replace")
check(5, "SE GET /dashboard → translator link shown",
      r.status_code == 200 and "nav-translator" in html_se,
      f"status={r.status_code}")

# Test 6: PM GET /dashboard/translator → 403
client = fresh(pm_a_id)
r = client.get("/dashboard/translator")
check(6, "PM GET /dashboard/translator → 403", r.status_code == 403,
      f"got {r.status_code}")

# Test 7: PM GET /dashboard/tutorials → 403
client = fresh(pm_a_id)
r = client.get("/dashboard/tutorials")
check(7, "PM GET /dashboard/tutorials → 403", r.status_code == 403,
      f"got {r.status_code}")

# Test 8: SE GET /dashboard/translator → 200 (or redirect, not 403)
client = fresh(se1_id)
r = client.get("/dashboard/translator")
check(8, "SE GET /dashboard/translator → 200 (not 403)",
      r.status_code in (200, 302), f"got {r.status_code}")

# ══════════════════════════════════════════════════════════════════════════════
# BOQ CREATION TESTS (9-13)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== BOQ CREATION TESTS (9-13) ===")

# Test 9: PM GET /dashboard/boq → "Generate from Description" present in HTML
client = fresh(pm_a_id)
r = client.get("/dashboard/boq")
html_pm_boq = r.data.decode("utf-8", errors="replace")
check(9, "PM GET /dashboard/boq → 'Generate from Description' present",
      r.status_code == 200 and "Generate from Description" in html_pm_boq,
      f"status={r.status_code}")

# Test 10: SE GET /dashboard/boq → "Upload & Analyze by Role" present in HTML
client = fresh(se1_id)
r = client.get("/dashboard/boq")
html_se_boq = r.data.decode("utf-8", errors="replace")
check(10, "SE GET /dashboard/boq → 'Upload & Analyze by Role' present",
      r.status_code == 200 and ("Upload" in html_se_boq and "Analyze" in html_se_boq),
      f"status={r.status_code}, Upload present={'Upload' in html_se_boq}")

# Test 11: SE POST /boq/generate-from-description → 403
client = fresh(se1_id)
r = client.post("/boq/generate-from-description", data={"description": "test"})
check(11, "SE POST /boq/generate-from-description → 403",
      r.status_code == 403, f"got {r.status_code}")

# Test 12: SE GET /dashboard/boq/new → 403
client = fresh(se1_id)
r = client.get("/dashboard/boq/new")
check(12, "SE GET /dashboard/boq/new → 403", r.status_code == 403,
      f"got {r.status_code}")

# Test 13: PM GET /dashboard/boq/upload → 403 (SE-only route)
client = fresh(pm_a_id)
r = client.get("/dashboard/boq/upload")
check(13, "PM GET /dashboard/boq/upload → 403",
      r.status_code == 403, f"got {r.status_code}")

# ══════════════════════════════════════════════════════════════════════════════
# MASTER INVENTORY TESTS (14-18)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== MASTER INVENTORY TESTS (14-18) ===")

# Test 14: PM GET /dashboard/inventory/generate → 200
client = fresh(pm_a_id)
r = client.get("/dashboard/inventory/generate")
check(14, "PM GET /dashboard/inventory/generate → 200",
      r.status_code == 200, f"got {r.status_code}")

# Test 15: PM POST /dashboard/inventory/generate with description + project_id
#          → preview mode (generated items in response), mocked AI
mock_items = [
    {
        "name": "Portland Cement",
        "name_ar": "إسمنت بورتلاند",
        "category": "Concrete",
        "unit": "bag",
        "recommended_stock": 500,
        "threshold": 100,
        "value_sar": 18.50,
        "supplier_hint": "Saudi Cement Co.",
        "notes": "Standard 50kg bags",
    },
    {
        "name": "Steel Rebar",
        "name_ar": "حديد تسليح",
        "category": "Steel",
        "unit": "ton",
        "recommended_stock": 50,
        "threshold": 10,
        "value_sar": 2800.0,
        "supplier_hint": "Hadeed Steel",
        "notes": "Fy500 grade",
    },
]

with application.test_request_context():
    pass  # ensure context

from unittest.mock import patch, MagicMock

def mock_openai_inventory(*args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(mock_items)
    return mock_resp

client = fresh(pm_a_id)
with patch("openai.OpenAI") as MockOpenAI:
    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock()
    mock_instance.chat.completions.create.return_value.choices = [MagicMock()]
    mock_instance.chat.completions.create.return_value.choices[0].message.content = json.dumps(mock_items)
    MockOpenAI.return_value = mock_instance
    r = client.post(
        "/dashboard/inventory/generate",
        data={
            "project_id": str(p1_id),
            "project_description": "3-floor villa in Riyadh with marble finishing and MEP works",
            "project_type": "Residential",
            "floor_area_sqm": "400",
        }
    )
html_preview = r.data.decode("utf-8", errors="replace")
check(15, "PM POST /dashboard/inventory/generate → preview (200 with items)",
      r.status_code == 200 and ("Portland Cement" in html_preview or "Save All" in html_preview),
      f"status={r.status_code}, Save All={'Save All' in html_preview}")

# Test 16: SE POST /dashboard/inventory/generate → 403
client = fresh(se1_id)
r = client.post(
    "/dashboard/inventory/generate",
    data={"project_description": "test", "project_type": "Residential"},
)
check(16, "SE POST /dashboard/inventory/generate → 403",
      r.status_code == 403, f"got {r.status_code}")

# Test 17: PM saves generated items (confirm=1) → InventoryItem rows created with source='ai_generated_master'
with application.app_context():
    count_before = InventoryItem.query.filter_by(
        user_id=pm_a_id, source="ai_generated_master"
    ).count()

client = fresh(pm_a_id)
with patch("openai.OpenAI") as MockOpenAI:
    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock()
    mock_instance.chat.completions.create.return_value.choices = [MagicMock()]
    mock_instance.chat.completions.create.return_value.choices[0].message.content = json.dumps(mock_items)
    MockOpenAI.return_value = mock_instance
    r = client.post(
        "/dashboard/inventory/generate",
        data={
            "project_id": str(p1_id),
            "project_description": "3-floor villa in Riyadh with marble finishing",
            "project_type": "Residential",
            "floor_area_sqm": "400",
            "confirm": "1",
        },
        follow_redirects=False,
    )

with application.app_context():
    count_after = InventoryItem.query.filter_by(
        user_id=pm_a_id, source="ai_generated_master"
    ).count()

check(17, "PM confirm=1 → InventoryItem rows with source='ai_generated_master' saved",
      r.status_code in (200, 302) and count_after > count_before,
      f"status={r.status_code}, before={count_before}, after={count_after}")

# Test 18: InventoryItem.source field exists in DB
with application.app_context():
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(db.engine)
    cols = {c["name"] for c in insp.get_columns("inventory_items")}
    check(18, "InventoryItem.source column exists in DB",
          "source" in cols, f"cols={cols}")

# ══════════════════════════════════════════════════════════════════════════════
# MIGRATION TESTS (19-20)
# ══════════════════════════════════════════════════════════════════════════════
print("\n=== MIGRATION TESTS (19-20) ===")

def run_flask(cmd):
    """Run a flask db command from the banaaiq directory against an isolated SQLite DB."""
    cwd = os.path.dirname(__file__)
    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"
    env["DATABASE_URL"] = f"sqlite:///{MIGRATION_DB_PATH.as_posix()}"
    env["OPENAI_API_KEY"] = "sk-test-fake-key"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "flask"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


rc, out, err = run_flask(["db", "upgrade"])
check(19, "flask db upgrade → rc=0",
      rc == 0, f"rc={rc} stderr={err[:200]}")

rc2, out2, err2 = run_flask(["db", "downgrade", "005_phase3_completion_summary"])
if rc2 == 0:
    rc3, out3, err3 = run_flask(["db", "upgrade"])
    check(20, "flask db downgrade 005 → 0 then upgrade back → 0",
          rc3 == 0, f"downgrade rc={rc2}, upgrade back rc={rc3}")
else:
    check(20, "flask db downgrade 005 → rc=0", False,
          f"rc={rc2} err={err2[:200]}")

# ══════════════════════════════════════════════════════════════════════════════
# REGRESSION TESTS (21-25)
# ══════════════════════════════════════════════════════════════════════════════
try:
    MIGRATION_DB_PATH.unlink(missing_ok=True)
except OSError:
    pass

print("\n=== REGRESSION TESTS (21-25) ===")

# Test 21: Phase 3 test_phase3_final.py still passes
test3_path = os.path.join(os.path.dirname(__file__), "test_phase3_final.py")
if os.path.exists(test3_path):
    try:
        result = subprocess.run(
            [sys.executable, test3_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.path.dirname(__file__),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout = result.stdout + result.stderr
        # Look for FAIL count
        import re
        m = re.search(r"FAILED:\s*(\d+)", stdout)
        phase3_fails = int(m.group(1)) if m else -1
        check(21, "Phase 3 tests still pass (0 failures)",
              result.returncode == 0 or phase3_fails == 0,
              f"rc={result.returncode} phase3_fails={phase3_fails}")
    except Exception as e:
        fail(21, "Phase 3 tests still pass", str(e))
else:
    fail(21, "Phase 3 tests still pass", "test_phase3_final.py not found")

# Test 22: PM GET /projects → 200
client = fresh(pm_a_id)
r = client.get("/projects")
check(22, "PM GET /projects → 200", r.status_code == 200, f"got {r.status_code}")

# Test 23: SE GET /my-workspace → 200
client = fresh(se1_id)
r = client.get("/my-workspace")
check(23, "SE GET /my-workspace → 200",
      r.status_code in (200, 302), f"got {r.status_code}")

# Test 24: PM GET /portfolio → 200
client = fresh(pm_a_id)
r = client.get("/portfolio")
check(24, "PM GET /portfolio → 200", r.status_code in (200, 302),
      f"got {r.status_code}")

# Test 25: GET / → 200 (public landing)
c = application.test_client()
r = c.get("/")
check(25, "GET / → 200", r.status_code == 200, f"got {r.status_code}")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"PASSED: {PASS}  FAILED: {FAIL}  TOTAL: {PASS + FAIL}")
if _failures:
    print("\nFailed tests:")
    for f_msg in _failures:
        print(f_msg)

if PASS == 25 and FAIL == 0:
    print("\nAll 25 tests passed!")
    sys.exit(0)
else:
    sys.exit(1)
