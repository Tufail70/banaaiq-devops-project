import os
import sys
import unittest
from datetime import date

os.environ.setdefault("SECRET_KEY", "test-production-flow-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_production_flows.db")
os.environ.setdefault("OPENAI_API_KEY", "")

sys.path.insert(0, os.path.dirname(__file__))

from app import app, db, _make_reset_token, _verify_reset_token, seed_plans
from models import BOQ, BOQActual, DPR, FeatureProject, Project, User


class ProductionFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["RATELIMIT_ENABLED"] = False
        with app.app_context():
            db.drop_all()
            db.create_all()
            seed_plans()

    def setUp(self):
        with app.app_context():
            BOQActual.query.delete()
            DPR.query.delete()
            BOQ.query.delete()
            FeatureProject.query.delete()
            Project.query.delete()
            User.query.delete()
            db.session.commit()

    def make_user(self, email="pm@test.local", role="project_manager"):
        user = User(full_name="Test Manager", email=email, company="TestCo", role=role)
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()
        return user

    def login(self, client, email="pm@test.local"):
        return client.post(
            "/auth/login",
            data={
                "form_type": "login",
                "login-email": email,
                "login-password": "Password123!",
            },
            follow_redirects=False,
        )

    def test_login_logout_and_protected_cache_headers(self):
        with app.app_context():
            self.make_user()

        client = app.test_client()
        response = self.login(client)
        self.assertEqual(response.status_code, 302)

        dashboard = client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("no-store", dashboard.headers.get("Cache-Control", ""))

        logout_get = client.get("/auth/logout")
        self.assertEqual(logout_get.status_code, 405)

        logout_post = client.post("/auth/logout", follow_redirects=False)
        self.assertEqual(logout_post.status_code, 302)
        self.assertIn("no-store", logout_post.headers.get("Cache-Control", ""))

        protected = client.get("/dashboard", follow_redirects=False)
        self.assertEqual(protected.status_code, 302)
        self.assertIn("/auth/login", protected.headers.get("Location", ""))

    def test_reset_token_is_single_use_after_password_change(self):
        with app.app_context():
            user = self.make_user()
            token = _make_reset_token(user)
            self.assertEqual(_verify_reset_token(token).id, user.id)
            user.set_password("NewPassword123!")
            db.session.commit()
            self.assertIsNone(_verify_reset_token(token))

    def test_api_unauthenticated_response_is_json_401(self):
        response = app.test_client().get("/api/tasks/assignees")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        self.assertFalse(response.get_json()["success"])

    def test_dpr_submit_does_not_crash_when_no_boq_notation(self):
        with app.app_context():
            user = self.make_user()
            project = Project(user_id=user.id, name="Tower A", project_code="BIQ-2026-TST")
            db.session.add(project)
            db.session.commit()
            user_id = user.id
            project_id = project.id

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        response = client.post(
            "/dashboard/dpr/submit",
            data={
                "project_id": str(project_id),
                "report_date": "2026-05-12",
                "progress_notes": "Completed blockwork inspection on level 2.",
                "weather": "Clear",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_manual_boq_actual_endpoint_records_progress(self):
        with app.app_context():
            user = self.make_user()
            project = Project(user_id=user.id, name="Tower A", project_code="BIQ-2026-TST")
            db.session.add(project)
            db.session.flush()
            boq = BOQ(
                user_id=user.id,
                project_id=project.id,
                title="Tower BOQ",
                items=[
                    {"no": "1.1", "description": "Concrete", "unit": "m3", "qty": 100, "rate": 250, "total": 25000}
                ],
            )
            db.session.add(boq)
            db.session.commit()
            user_id = user.id
            boq_id = boq.id

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

        response = client.post(
            "/boq/manual-actual",
            json={"boq_id": boq_id, "item_no": "1.1", "actual_qty": 12.5},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        with app.app_context():
            self.assertEqual(BOQActual.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
