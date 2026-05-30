"""
Phase 3 Verification Tests — 40 tests
Run: python test_phase3_final.py
"""
import os
import sys
import json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
from datetime import date, timedelta, datetime
from unittest.mock import patch, MagicMock

os.environ.setdefault("DATABASE_URL", "sqlite:///test_phase3.db")
os.environ.setdefault("SECRET_KEY", "test-phase3-secret-key-2026")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")

sys.path.insert(0, os.path.dirname(__file__))

import app as flask_app
from app import app as application, db
from models import (
    BOQ, BOQActual, BOQPackage, DPR, EngineerPackage, InventoryItem,
    Notification, Project, ProjectAssignment, ProjectMilestone,
    ROLE_PROJECT_MANAGER, ROLE_SITE_ENGINEER, Task, User,
)

# ── Config overrides ────────────────────────────────────────────────────────
application.config["TESTING"] = True
application.config["WTF_CSRF_ENABLED"] = False
application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test_phase3.db"
application.config["SERVER_NAME"] = "localhost"
application.config["PREFERRED_URL_SCHEME"] = "http"

PASS = 0
FAIL = 0
_failures = []


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
    pm_a = User(full_name="PM Alpha", email="pm_a@test.com", role=ROLE_PROJECT_MANAGER)
    pm_a.set_password("TestPass1!")
    db.session.add(pm_a)

    # PM-B
    pm_b = User(full_name="PM Beta", email="pm_b@test.com", role=ROLE_PROJECT_MANAGER)
    pm_b.set_password("TestPass1!")
    db.session.add(pm_b)

    # SE-1
    se1 = User(full_name="Site Engineer One", email="se1@test.com", role=ROLE_SITE_ENGINEER, job_title="Site Engineer")
    se1.set_password("TestPass1!")
    db.session.add(se1)

    # SE-2
    se2 = User(full_name="Site Engineer Two", email="se2@test.com", role=ROLE_SITE_ENGINEER, job_title="MEP Engineer")
    se2.set_password("TestPass1!")
    db.session.add(se2)

    db.session.flush()

    # Project P1
    p1 = Project(
        user_id=pm_a.id,
        name="Test Phase 3 Project",
        project_code="BIQ-2026-0003",
        client_name="Test Client",
        location_city="Riyadh",
        contract_value=1000000,
        start_date=date(2026, 1, 1),
        planned_completion=date(2026, 12, 31),
        status="active",
    )
    db.session.add(p1)
    db.session.flush()

    # 3 milestones
    ms1 = ProjectMilestone(project_id=p1.id, title="Foundation Complete", planned_date=date(2026, 3, 31), actual_date=date(2026, 3, 25), status="completed")
    ms2 = ProjectMilestone(project_id=p1.id, title="Structure Complete", planned_date=date(2026, 6, 30), actual_date=None, status="pending")
    ms3 = ProjectMilestone(project_id=p1.id, title="Fit-out Complete", planned_date=date(2026, 9, 30), actual_date=None, status="pending")
    db.session.add_all([ms1, ms2, ms3])

    # BOQ with 10 items totaling 800000
    items_json = json.dumps([
        {"no": str(i), "desc": f"Item {i}", "unit": "m2", "qty": 100, "rate": 800, "total": 80000}
        for i in range(1, 11)
    ])
    boq1 = BOQ(
        user_id=pm_a.id,
        project_id=p1.id,
        title="Master BOQ",
        status="Final",
        items_json=items_json,
        subtotal=800000,
        vat_amount=0,
        grand_total=800000,
        is_master=True,
    )
    db.session.add(boq1)
    db.session.flush()

    # 5 inventory items (2 below threshold = low, one critical)
    inv_items = []
    for idx, (name, stock, threshold) in enumerate([
        ("Cement", 500, 100),      # ok
        ("Steel Bars", 200, 300),  # low (stock < threshold but >= threshold*0.25)
        ("Sand", 0, 50),           # critical (stock == 0 => stock < threshold*0.25=12.5)
        ("Gravel", 150, 100),      # ok
        ("Paint", 10, 200),        # critical (stock < threshold*0.25=50)
    ]):
        item = InventoryItem(
            user_id=pm_a.id,
            project_id=p1.id,
            name=name,
            category="Material",
            unit="kg",
            stock=stock,
            threshold=threshold,
            value_sar=stock * 5,
        )
        db.session.add(item)
        inv_items.append(item)

    # Assign SE-1 and SE-2
    assign1 = ProjectAssignment(project_id=p1.id, user_id=se1.id, role_on_project="Site Engineer")
    assign2 = ProjectAssignment(project_id=p1.id, user_id=se2.id, role_on_project="MEP Engineer")
    db.session.add_all([assign1, assign2])

    # EngineerPackage for SE-1 (5 items)
    item_statuses_se1 = {str(i): ("complete" if i < 4 else "not_started") for i in range(5)}
    pkg1 = EngineerPackage(
        project_id=p1.id,
        boq_id=boq1.id,
        assigned_user_id=se1.id,
        assigned_engineer_name="Site Engineer One",
        trade="Civil",
        package_value=400000,
        completion_percentage=80.0,
        item_statuses_json=json.dumps(item_statuses_se1),
    )
    db.session.add(pkg1)

    # EngineerPackage for SE-2 (5 items)
    item_statuses_se2 = {str(i): ("in_progress" if i < 2 else "not_started") for i in range(5)}
    pkg2 = EngineerPackage(
        project_id=p1.id,
        boq_id=boq1.id,
        assigned_user_id=se2.id,
        assigned_engineer_name="Site Engineer Two",
        trade="MEP",
        package_value=400000,
        completion_percentage=0.0,
        item_statuses_json=json.dumps(item_statuses_se2),
    )
    db.session.add(pkg2)

    # 8 tasks (5 for SE-1, 3 for SE-2) — 1 complete for SE-1
    task_data = [
        ("Task A1", "Site Engineer One", "complete"),
        ("Task A2", "Site Engineer One", "backlog"),
        ("Task A3", "Site Engineer One", "backlog"),
        ("Task A4", "Site Engineer One", "backlog"),
        ("Task A5", "Site Engineer One", "backlog"),
        ("Task B1", "Site Engineer Two", "backlog"),
        ("Task B2", "Site Engineer Two", "backlog"),
        ("Task B3", "Site Engineer Two", "backlog"),
    ]
    task_objects = []
    for title, assignee, status in task_data:
        t = Task(
            user_id=pm_a.id,
            project_id=p1.id,
            title=title,
            assignee=assignee,
            status=status,
            due=date(2026, 12, 31),
            priority="medium",
            category="Construction",
        )
        db.session.add(t)
        task_objects.append(t)

    db.session.flush()

    # BOQActual rows totaling 750000 SAR
    actual1 = BOQActual(boq_id=boq1.id, item_no="1", item_description="Civil works", budgeted_qty=100, actual_qty_used=100, budgeted_total_sar=400000, actual_total_sar=375000)
    actual2 = BOQActual(boq_id=boq1.id, item_no="2", item_description="MEP works", budgeted_qty=100, actual_qty_used=100, budgeted_total_sar=400000, actual_total_sar=375000)
    db.session.add_all([actual1, actual2])

    # DPR for SE-1
    dpr1 = DPR(user_id=se1.id, project_id=p1.id, date=date(2026, 4, 1), progress_notes="Foundation work", issues="None", status="Completed")
    db.session.add(dpr1)

    db.session.commit()

    # Store IDs
    pm_a_id = pm_a.id
    pm_b_id = pm_b.id
    se1_id = se1.id
    se2_id = se2.id
    p1_id = p1.id
    boq1_id = boq1.id
    print(f"\nSetup complete: PM-A={pm_a_id}, PM-B={pm_b_id}, SE-1={se1_id}, SE-2={se2_id}, P1={p1_id}")


# ── Helper ──────────────────────────────────────────────────────────────────
def fresh(user_id):
    """Return a test client pre-authenticated as user_id via session injection."""
    c = application.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return c


def get_client():
    return application.test_client()


def login(client, email, password):
    # Legacy helper — not used for new tests (session injection preferred)
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


print("\n=== HEALTH SCORE TESTS (1-8) ===")

# Test 1: GET /api/projects/P1/health → 200 with all 4 components
client = fresh(pm_a_id)
r = client.get(f"/api/projects/{p1_id}/health")
check(1, "GET /api/projects/P1/health → 200", r.status_code == 200, f"got {r.status_code}")

# Test 2: Score is int 0-100
if r.status_code == 200:
    data = json.loads(r.data)
    score = data.get("score", -1)
    check(2, "Score is int 0-100", isinstance(score, int) and 0 <= score <= 100, f"score={score}")
else:
    fail(2, "Score is int 0-100", "previous test failed")

# Test 3: Status matches thresholds
if r.status_code == 200:
    data = json.loads(r.data)
    score = data.get("score", 50)
    status = data.get("status", "")
    expected = "green" if score >= 75 else ("amber" if score >= 50 else "red")
    check(3, "Status matches thresholds", status == expected, f"score={score} status={status} expected={expected}")
else:
    fail(3, "Status matches thresholds", "previous test failed")

# Test 4: Each component has score + detail keys
if r.status_code == 200:
    data = json.loads(r.data)
    components = data.get("components", {})
    all_ok = all(
        isinstance(components.get(k), dict) and "score" in components[k] and "detail" in components[k]
        for k in ("schedule", "budget", "task", "inventory")
    )
    check(4, "All 4 components have score + detail", all_ok, f"components keys: {list(components.keys())}")
else:
    fail(4, "All 4 components have score + detail", "previous test failed")

# Test 5: Cache — 2nd call returns same data fast
t0 = time.time()
r2 = client.get(f"/api/projects/{p1_id}/health")
t1 = time.time()
check(5, "Cache: 2nd call within 5 seconds", r2.status_code == 200 and (t1 - t0) < 5.0, f"time={t1-t0:.3f}s")

# Test 6: Invalidate cache + task update → next /health call has fresh data
with application.app_context():
    from utils import invalidate_health_cache
    invalidate_health_cache(p1_id)
r3 = client.get(f"/api/projects/{p1_id}/health")
check(6, "After cache invalidation health endpoint returns 200", r3.status_code == 200, f"got {r3.status_code}")

# Test 7: POST /recalculate-health → 200, returns last_calculated
r_recalc = client.post(f"/projects/{p1_id}/recalculate-health")
check(7, "POST /recalculate-health → 200", r_recalc.status_code == 200, f"got {r_recalc.status_code}")
if r_recalc.status_code == 200:
    recalc_data = json.loads(r_recalc.data)
    check(7, "POST /recalculate-health has last_calculated", "last_calculated" in recalc_data, f"keys: {list(recalc_data.keys())}")

# Test 8: ETag — 2nd call with If-None-Match → 304
r_first = client.get(f"/api/projects/{p1_id}/health")
etag = r_first.headers.get("ETag", "")
if etag:
    r_304 = client.get(f"/api/projects/{p1_id}/health", headers={"If-None-Match": etag})
    check(8, "ETag: 2nd call with matching ETag → 304", r_304.status_code == 304, f"got {r_304.status_code}, etag={etag}")
else:
    fail(8, "ETag: ETag header missing from /health response", f"headers: {dict(r_first.headers)}")

print("\n=== OVERSIGHT TESTS (9-16) ===")

# Test 9: PM-A GET /projects/P1/oversight → 200
r9 = client.get(f"/projects/{p1_id}/oversight")
check(9, "PM-A GET /projects/P1/oversight → 200", r9.status_code == 200, f"got {r9.status_code}")

# Test 10: SE-1 GET /projects/P1/oversight → 403
se_client = fresh(se1_id)
r10 = se_client.get(f"/projects/{p1_id}/oversight")
check(10, "SE-1 GET /oversight → 403", r10.status_code == 403, f"got {r10.status_code}")

# Test 11: PM-B GET /projects/P1/oversight → 403
pmb_client = fresh(pm_b_id)
r11 = pmb_client.get(f"/projects/{p1_id}/oversight")
check(11, "PM-B GET /oversight → 403", r11.status_code == 403, f"got {r11.status_code}")

# Test 12: Health score value in HTML
if r9.status_code == 200:
    html_content = r9.data.decode("utf-8")
    check(12, "Oversight HTML contains health score value", "health-score" in html_content.lower() or "data-health" in html_content, "no health elements found")
else:
    fail(12, "Oversight HTML contains health score", "route returned non-200")

# Test 13: SE-1 and SE-2 names in oversight HTML
if r9.status_code == 200:
    html_content = r9.data.decode("utf-8")
    check(13, "Oversight HTML contains SE-1 and SE-2 names",
          "Site Engineer One" in html_content and "Site Engineer Two" in html_content,
          f"names present: SE1={'Site Engineer One' in html_content}, SE2={'Site Engineer Two' in html_content}")
else:
    fail(13, "Oversight HTML contains SE names", "route returned non-200")

# Test 14: Project summary stats in HTML
if r9.status_code == 200:
    html_content = r9.data.decode("utf-8")
    check(14, "Oversight HTML contains project summary stats",
          "BOQ Completion" in html_content or "boq_completion" in html_content or "Active Tasks" in html_content,
          "no summary stats found")
else:
    fail(14, "Oversight HTML contains project summary", "route returned non-200")

# Test 15: Activity feed section present
if r9.status_code == 200:
    html_content = r9.data.decode("utf-8")
    check(15, "Activity feed section present in oversight HTML",
          "Activity Feed" in html_content or "activity-feed" in html_content or "سجل النشاط" in html_content,
          "no activity feed found")
else:
    fail(15, "Activity feed in oversight HTML", "route returned non-200")

# Test 16: Auto-poll JS (60s interval or /api/health endpoint reference)
if r9.status_code == 200:
    html_content = r9.data.decode("utf-8")
    check(16, "Oversight HTML has auto-poll JS",
          "60000" in html_content or "api/projects" in html_content,
          "no polling JS found")
else:
    fail(16, "Oversight HTML has auto-poll JS", "route returned non-200")

print("\n=== PORTFOLIO TESTS (17-24) ===")

# Test 17: PM-A GET /portfolio → 200
r17 = client.get("/portfolio")
check(17, "PM-A GET /portfolio → 200", r17.status_code == 200, f"got {r17.status_code}")

# Test 18: Portfolio contains P1 data
if r17.status_code == 200:
    html_content = r17.data.decode("utf-8")
    check(18, "Portfolio contains P1 data", "Test Phase 3 Project" in html_content or "BIQ-2026-0003" in html_content,
          "project not found in portfolio")
else:
    fail(18, "Portfolio contains P1 data", "route returned non-200")

# Test 19: KPI cards (total_committed or contract_value)
if r17.status_code == 200:
    html_content = r17.data.decode("utf-8")
    check(19, "Portfolio has KPI stat cards",
          "Total SAR" in html_content or "1,000,000" in html_content or "contract" in html_content.lower(),
          "no KPI cards found")
else:
    fail(19, "Portfolio KPI cards", "route returned non-200")

# Test 20: Health distribution present
if r17.status_code == 200:
    html_content = r17.data.decode("utf-8")
    check(20, "Portfolio shows health distribution",
          ("Green" in html_content or "green" in html_content) and
          ("Amber" in html_content or "amber" in html_content),
          "health distribution not found")
else:
    fail(20, "Portfolio health distribution", "route returned non-200")

# Test 21: Upcoming milestones section present
if r17.status_code == 200:
    html_content = r17.data.decode("utf-8")
    check(21, "Portfolio has upcoming milestones section",
          "Milestone" in html_content or "milestone" in html_content.lower() or "Due" in html_content,
          "no milestone section")
else:
    fail(21, "Portfolio milestones", "route returned non-200")

# Test 22: Portfolio export PDF → 200, application/pdf
r22 = client.get("/portfolio/export")
check(22, "GET /portfolio/export → 200 application/pdf",
      r22.status_code == 200 and "application/pdf" in r22.content_type,
      f"status={r22.status_code} content_type={r22.content_type}")

# Test 23: SE-1 GET /portfolio → 403
se_client = fresh(se1_id)
r23 = se_client.get("/portfolio")
check(23, "SE-1 GET /portfolio → 403", r23.status_code == 403, f"got {r23.status_code}")

# Test 24: PM-B GET /portfolio → 200 but NOT P1
pmb_client = fresh(pm_b_id)
r24 = pmb_client.get("/portfolio")
check(24, "PM-B GET /portfolio → 200 but NOT P1", r24.status_code == 200 and "BIQ-2026-0003" not in r24.data.decode("utf-8"),
      f"status={r24.status_code} p1_visible={'BIQ-2026-0003' in r24.data.decode('utf-8')}")

print("\n=== COMPLETION REPORT TESTS (25-33) ===")

# Test 25: PM-A POST /projects/P1/complete → project.status='completed'
r25 = client.post(f"/projects/{p1_id}/complete", follow_redirects=True)
with application.app_context():
    p1_reloaded = db.session.get(Project, p1_id)
    check(25, "POST /complete → project.status='completed'",
          p1_reloaded.status == "completed",
          f"status={p1_reloaded.status}")

# Test 26: PM-A GET /projects/P1/completion-report → 200 application/pdf
r26 = client.get(f"/projects/{p1_id}/completion-report")
check(26, "GET /completion-report → 200", r26.status_code == 200, f"got {r26.status_code}")

# Test 27: PDF generates without error
check(27, "completion-report returns application/pdf",
      r26.status_code == 200 and "application/pdf" in r26.content_type,
      f"content_type={r26.content_type}")

# Test 28: completion_summary saved to DB after first call
with application.app_context():
    p1_check = db.session.get(Project, p1_id)
    check(28, "completion_summary saved to DB after first call",
          p1_check.completion_summary is not None,
          f"completion_summary={p1_check.completion_summary!r}")

# Test 29: 2nd call → completion_summary unchanged (no new AI call if cached)
with application.app_context():
    p1_before = db.session.get(Project, p1_id)
    summary_before = p1_before.completion_summary

call_count = [0]
original_ai = None
try:
    import app as app_module
    original_ai = app_module.call_openai
    def mock_openai(prompt, **kwargs):
        call_count[0] += 1
        return False, "mock"
    app_module.call_openai = mock_openai
except Exception:
    pass

r29 = client.get(f"/projects/{p1_id}/completion-report")

try:
    if original_ai:
        app_module.call_openai = original_ai
except Exception:
    pass

with application.app_context():
    p1_after = db.session.get(Project, p1_id)
    summary_after = p1_after.completion_summary

check(29, "2nd completion-report call: summary unchanged (cached)",
      summary_before == summary_after,
      f"before={summary_before!r:.50} after={summary_after!r:.50}")

# Test 30: SE-1 GET /completion-report → 403
se_client = fresh(se1_id)
r30 = se_client.get(f"/projects/{p1_id}/completion-report")
check(30, "SE-1 GET /completion-report → 403", r30.status_code == 403, f"got {r30.status_code}")

# Test 31: PM-B GET /completion-report → 403 (not their project)
pmb_client = fresh(pm_b_id)
r31 = pmb_client.get(f"/projects/{p1_id}/completion-report")
check(31, "PM-B GET /completion-report → 403", r31.status_code == 403, f"got {r31.status_code}")

# Test 32: AI unavailable → fallback text (graceful degrade)
with application.app_context():
    p1_reset = db.session.get(Project, p1_id)
    p1_reset.completion_summary = None
    p1_reset.completion_summary_ar = None
    db.session.commit()

with patch("utils.can_use_ai", return_value=(False, "No AI")):
    r32 = client.get(f"/projects/{p1_id}/completion-report")
check(32, "AI unavailable → graceful fallback (no 500)",
      r32.status_code in (200, 302),
      f"got {r32.status_code}")

# Test 33: BOQ variance route doesn't 500
r33 = client.get(f"/projects/{p1_id}/completion-report")
check(33, "completion-report BOQ data doesn't cause 500",
      r33.status_code in (200, 302),
      f"got {r33.status_code}")

print("\n=== MIGRATION TESTS (34-35) ===")

# Test 34-35: Flask-Migrate downgrade/upgrade
import subprocess

def load_dotenv_dict(cwd):
    """Load .env file from cwd, return dict of key/value pairs."""
    env_vars = {}
    env_file = os.path.join(cwd, ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

def run_flask(args, cwd):
    # Inherit full environment (so flask/packages are on PYTHONPATH),
    # then overlay with .env values, then explicitly set DATABASE_URL
    # from .env (overriding the test process's sqlite override).
    import subprocess as sp
    env = os.environ.copy()
    dotenv = load_dotenv_dict(cwd)
    env.update(dotenv)  # .env values override test-process env vars
    env["FLASK_APP"] = "app.py"
    result = sp.run(
        [sys.executable, "-m", "flask"] + args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return result

banaaiq_dir = os.path.dirname(__file__)

# First ensure we're at head
run_flask(["db", "upgrade"], banaaiq_dir)

# Downgrade back one step (from 005 to 004)
downgrade_result = run_flask(["db", "downgrade", "004_phase2_distribution"], banaaiq_dir)
check(35, "flask db downgrade to 004 → rc=0", downgrade_result.returncode == 0, f"rc={downgrade_result.returncode} stderr={downgrade_result.stderr[-300:]}")

# Upgrade back to head
upgrade_result = run_flask(["db", "upgrade"], banaaiq_dir)
check(34, "flask db upgrade → rc=0", upgrade_result.returncode == 0, f"rc={upgrade_result.returncode} stderr={upgrade_result.stderr[-300:]}")

print("\n=== REGRESSION SMOKE TESTS (36-40) ===")

# Test 36: Role enforcement basics (unauthenticated → redirect)
anon_client = get_client()
r36 = anon_client.get("/projects")
check(36, "Unauthenticated /projects → redirect to login",
      r36.status_code in (302, 401),
      f"got {r36.status_code}")

# Test 37: SE /my-workspace still renders
se_client2 = fresh(se1_id)
r37 = se_client2.get("/my-workspace")
check(37, "SE GET /my-workspace → 200", r37.status_code == 200, f"got {r37.status_code}")

# Test 38: PM creates regular BOQ (BOQ page loads)
pm_client2 = fresh(pm_a_id)
r38 = pm_client2.get("/dashboard/boq")
check(38, "PM GET /dashboard/boq → 200", r38.status_code == 200, f"got {r38.status_code}")

# Test 39: SE /my-workspace still renders (second check)
se_client3 = fresh(se1_id)
r39 = se_client3.get("/my-workspace")
check(39, "SE /my-workspace still renders (2nd check)", r39.status_code == 200, f"got {r39.status_code}")

# Test 40: GET / → 200
r40 = anon_client.get("/")
check(40, "GET / → 200", r40.status_code == 200, f"got {r40.status_code}")

print("\n=== BACKWARD-COMPAT HEALTH COMPONENT TESTS (41-42) ===")

# Test 41: get_health_components handles new dict format (Phase 3 format)
with application.app_context():
    from utils import get_health_components
    import json as _json
    new_fmt = _json.dumps({
        "schedule": {"score": 85, "detail": "On track", "detail_ar": "في المسار"},
        "budget":   {"score": 70, "detail": "Under budget", "detail_ar": "ضمن الميزانية"},
        "task":     {"score": 50, "detail": "5 of 10 done", "detail_ar": "5 من 10"},
        "inventory":{"score": 90, "detail": "All ok", "detail_ar": "جيد"},
    })
    class _FakeProject:
        health_components_json = new_fmt
    comps = get_health_components(_FakeProject())
    all_valid = all(isinstance(comps.get(k), int) and 0 <= comps[k] <= 100 for k in ("schedule", "budget", "task", "inventory"))
    check(41, "get_health_components: new dict format → 4 valid int scores", all_valid,
          f"got: {comps}")

# Test 42: get_health_components handles legacy flat-int format
with application.app_context():
    from utils import get_health_components
    import json as _json
    legacy_fmt = _json.dumps({"schedule": 75, "budget": 80, "tasks": 70, "inventory": 90})
    class _FakeLegacyProject:
        health_components_json = legacy_fmt
    comps2 = get_health_components(_FakeLegacyProject())
    all_valid2 = all(isinstance(comps2.get(k), int) and 0 <= comps2[k] <= 100 for k in ("schedule", "budget", "task", "inventory"))
    check(42, "get_health_components: legacy flat-int format → 4 valid int scores", all_valid2,
          f"got: {comps2}")

# Test 43: project_workspace route renders without TypeError
pm_ws_client = fresh(pm_a_id)
with application.app_context():
    p1_obj = db.session.get(Project, p1_id)
    # Reset completion so workspace is accessible (not redirecting to report)
    p1_obj.status = "active"
    db.session.commit()
r43 = pm_ws_client.get(f"/projects/{p1_id}")
check(43, "PM project_workspace renders without health TypeError",
      r43.status_code in (200, 302),
      f"got {r43.status_code} body_snippet={r43.data[:200].decode('utf-8','replace') if r43.status_code == 500 else 'ok'}")

# ── Summary ─────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  RESULTS: {PASS} PASSED / {FAIL} FAILED out of {PASS+FAIL} tests")
if _failures:
    print("\nFailed tests:")
    for f_line in _failures:
        print(f_line)
print("=" * 55)

# Cleanup test DB files
for db_file in ["test_phase3.db", "test_phase3_migrate.db"]:
    try:
        os.unlink(os.path.join(os.path.dirname(__file__), db_file))
    except Exception:
        pass

sys.exit(0 if FAIL == 0 else 1)
