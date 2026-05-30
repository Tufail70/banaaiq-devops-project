"""Step 3 verification -- run with: python test_step3.py (from banaaiq/)"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("SECRET_KEY", "test-only-key")

from app import app
from models import db, User, Project, EngineerPackage, ROLE_PROJECT_MANAGER, ROLE_SITE_ENGINEER

# ---- test-mode overrides ------------------------------------------------
# TESTING=True  -> HTTPExceptions propagate through the test client properly
# WTF_CSRF_ENABLED=False -> lets us POST without a real CSRF token so that
#                  role_required is the first gate that fires.
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False
# -------------------------------------------------------------------------

CREATED_USER_IDS = []
CREATED_PROJECT_IDS = []

with app.app_context():
    def ensure_user(email, role, name):
        user = User.query.filter_by(email=email).first()
        if user:
            return user
        user = User(full_name=name, email=email, role=role, job_title=role.replace("_", " ").title())
        user.set_password("Test1234!")
        db.session.add(user)
        db.session.flush()
        CREATED_USER_IDS.append(user.id)
        return user

    def ensure_project(owner, code, name):
        project = Project.query.filter_by(project_code=code).first()
        if project:
            return project
        project = Project(user_id=owner.id, name=name, project_code=code, status="active", currency="SAR")
        db.session.add(project)
        db.session.flush()
        CREATED_PROJECT_IDS.append(project.id)
        return project

    pm_seed_1 = ensure_user("step3-pm1@example.com", ROLE_PROJECT_MANAGER, "Step3 PM One")
    pm_seed_2 = ensure_user("step3-pm2@example.com", ROLE_PROJECT_MANAGER, "Step3 PM Two")
    ensure_user("step3-se@example.com", ROLE_SITE_ENGINEER, "Step3 Site Engineer")
    ensure_project(pm_seed_1, "BIQ-STP3-001", "Step3 PM One Project")
    ensure_project(pm_seed_2, "BIQ-STP3-002", "Step3 PM Two Project")
    db.session.commit()

# ---- Phase 1: collect IDs inside a short-lived app context --------------
# IMPORTANT: All test client .get()/.post() calls must happen OUTSIDE any
# active app context. Flask's `g` object lives on the app context in Flask 3;
# if requests share the same outer app context they share the same `g` and
# Flask-Login's cached current_user leaks across requests.
with app.app_context():
    pm1 = User.query.filter_by(role="project_manager").first()
    pm2 = User.query.filter_by(role="project_manager").offset(1).first()
    se  = User.query.filter_by(role="site_engineer").first()
    pm1_project = Project.query.filter_by(user_id=pm1.id).first() if pm1 else None
    pm2_project = Project.query.filter_by(user_id=pm2.id).first() if pm2 else None

    # Capture plain IDs — no ORM objects cross the context boundary.
    pm1_id = pm1.id if pm1 else None
    pm2_id = pm2.id if pm2 else None
    se_id  = se.id  if se  else None
    pm1_email = pm1.email if pm1 else "NONE"
    pm2_email = pm2.email if pm2 else "NONE"
    se_email  = se.email  if se  else "NONE"
    pm1_project_id = pm1_project.id if pm1_project else None
    pm2_project_id = pm2_project.id if pm2_project else None

print(f"PM1: {pm1_email}  id={pm1_id}  project={pm1_project_id}")
print(f"PM2: {pm2_email}  id={pm2_id}  project={pm2_project_id}")
print(f"SE:  {se_email}  id={se_id}")
print()

# ---- Phase 2: test client calls (no outer app context active) -----------

results = []


def check(label, condition, actual):
    tag = "PASS" if condition else "FAIL"
    results.append((tag, label, actual))


def fresh_client_for(user_id):
    """New test client with a pre-seeded Flask-Login session for *user_id*."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return c


# 1. SE GET /projects/create -> 403
r = fresh_client_for(se_id).get("/projects/create")
check("1. SE GET /projects/create -> 403", r.status_code == 403, r.status_code)

# 2. SE POST /projects/create -> 403
# With WTF_CSRF_ENABLED=False the role gate fires first.
r = fresh_client_for(se_id).post("/projects/create", data={"name": "test"})
check("2. SE POST /projects/create -> 403", r.status_code == 403, r.status_code)

# 3. SE GET /portfolio -> 403
r = fresh_client_for(se_id).get("/portfolio")
check("3. SE GET /portfolio -> 403", r.status_code == 403, r.status_code)

# 4. PM GET /workspace -> 403
r = fresh_client_for(pm1_id).get("/workspace")
check("4. PM GET /workspace -> 403", r.status_code == 403, r.status_code)

# 5. SE GET /projects -> 200 (scoped list)
r = fresh_client_for(se_id).get("/projects")
check("5. SE GET /projects -> 200", r.status_code == 200, r.status_code)

# 6. SE GET /projects/<pm1_project> -> 403 (no EngineerPackage)
if pm1_project_id:
    r = fresh_client_for(se_id).get(f"/projects/{pm1_project_id}")
    check("6. SE GET /projects/<pm1_id> -> 403", r.status_code == 403, r.status_code)
else:
    results.append(("SKIP", "6. SE GET /projects/<pm1_id> -> 403", "no PM1 project"))

# 7. PM1 cannot view PM2's project
if pm2_project_id:
    r = fresh_client_for(pm1_id).get(f"/projects/{pm2_project_id}")
    check("7. PM1 GET /projects/<pm2_id> -> 403", r.status_code == 403, r.status_code)
else:
    results.append(("SKIP", "7. PM1 GET /projects/<pm2_id> -> 403", "no PM2 project"))

# 8. POST without CSRF token -> 400 (only meaningful when CSRF is enabled)
# Re-enable CSRF for this one check, then restore.
app.config["WTF_CSRF_ENABLED"] = True
c8 = fresh_client_for(pm1_id)
r = c8.post("/projects/create", data={"name": "csrftest"})
check("8. POST without CSRF -> 400", r.status_code == 400, r.status_code)
app.config["WTF_CSRF_ENABLED"] = False  # restore

# ---- Results ------------------------------------------------------------

SEP = "=" * 64
print(SEP)
print("STEP 3 VERIFICATION RESULTS")
print(SEP)
for status, label, actual in results:
    print(f"  [{status}] {label}  (got {actual})")
print(SEP)
all_ok = all(s in ("PASS", "SKIP") for s, _, _ in results)
print("OVERALL:", "ALL PASS" if all_ok else "FAILURES DETECTED")
print(SEP)

with app.app_context():
    for pid in CREATED_PROJECT_IDS:
        project = db.session.get(Project, pid)
        if project:
            db.session.delete(project)
    db.session.commit()
    for uid in CREATED_USER_IDS:
        user = db.session.get(User, uid)
        if user:
            db.session.delete(user)
    db.session.commit()
