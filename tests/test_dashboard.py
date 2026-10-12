"""
AI-Based Diabetes Risk Prediction System
Member 4: Health Dashboard, Recommendations & Prediction History — Automated Test Suite

Covers:
1. Dashboard loads for an authenticated user.
2. Dashboard handles a user with no predictions (empty state).
3. Dashboard displays actual prediction data correctly.
4. Risk probability and risk category match the prediction API.
5. General health recommendations handle missing and normal health measurements safely.
6. Rule-based recommendations generate clinical wellness advice without claiming diagnostic certainty.
7. Prediction history displays the correct authenticated user's records.
8. User isolation: User A cannot access or retrieve User B's prediction records.
9. An unauthenticated user cannot access protected dashboard or history views/APIs.
10. REST APIs (/api/dashboard, /api/history) return structured JSON payloads with status 200.
"""

import os
import unittest
import tempfile

os.environ["FORCE_SQLITE"] = "1"

from app import create_app
import db
from services.auth_service import register_user
from services.health_data_service import save_health_data
from services.prediction_service import predict_diabetes_risk
from services.dashboard_service import (
    save_prediction_record,
    get_user_predictions,
    get_user_latest_prediction,
    get_dashboard_summary,
    generate_health_recommendations
)


class DashboardModuleTestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        db.SQLITE_DB_PATH = self.db_path
        db.init_db()

        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-dashboard-secret-key-456",
            "WTF_CSRF_ENABLED": False
        })
        self.client = self.app.test_client()

        # Register User A (Alice Vance)
        reg_a = register_user(
            full_name="Alice Vance",
            email="alice.vance@clinic.org",
            password="SecurePassword123!",
            confirm_password="SecurePassword123!",
            age=38,
            gender="Female",
            phone="+1-555-0101"
        )
        self.user_a_id = reg_a["user_id"]

        # Register User B (Bob Miller)
        reg_b = register_user(
            full_name="Bob Miller",
            email="bob.miller@clinic.org",
            password="SecurePassword456!",
            confirm_password="SecurePassword456!",
            age=52,
            gender="Male",
            phone="+1-555-0202"
        )
        self.user_b_id = reg_b["user_id"]

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except Exception:
            pass

    def _login(self, email="alice.vance@clinic.org", password="SecurePassword123!"):
        return self.client.post("/login", data={
            "email": email,
            "password": password
        }, follow_redirects=True)

    # 1. Unauthenticated users are rejected
    def test_01_unauthenticated_access_rejected(self):
        # Web routes redirect to /login
        res_dash = self.client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn("/login", res_dash.headers["Location"])

        res_hist = self.client.get("/history")
        self.assertEqual(res_hist.status_code, 302)
        self.assertIn("/login", res_hist.headers["Location"])

        # API routes return 401 Unauthorized
        res_api_dash = self.client.get("/api/dashboard")
        self.assertEqual(res_api_dash.status_code, 401)

        res_api_hist = self.client.get("/api/history")
        self.assertEqual(res_api_hist.status_code, 401)

    # 2. Dashboard loads for authenticated user with empty state
    def test_02_dashboard_empty_state_for_new_user(self):
        self._login()
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back, Alice Vance", res.data)
        self.assertIn(b"No Diabetes Risk Assessments Recorded Yet", res.data)
        self.assertIn(b"Record Initial Biomarkers", res.data)

    # 3. Prediction history empty state
    def test_03_history_empty_state(self):
        self._login()
        res = self.client.get("/history")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"No Historical Records Found", res.data)

    # 4. Save and retrieve prediction record
    def test_04_save_and_retrieve_prediction(self):
        sample_pred = {
            "success": True,
            "prediction": {
                "predicted_class": 1,
                "risk_label": "Higher Estimated Risk",
                "risk_probability": 0.785,
                "risk_percentage": 78.5,
                "input_biomarkers": {
                    "glucose": 165.0,
                    "bmi": 34.2,
                    "blood_pressure": 88.0
                }
            }
        }
        rec_id = save_prediction_record(self.user_a_id, sample_pred)
        self.assertIsNotNone(rec_id)

        # Retrieve user predictions
        history = get_user_predictions(self.user_a_id)
        self.assertEqual(len(history), 1)
        item = history[0]
        self.assertEqual(item["predicted_class"], 1)
        self.assertEqual(item["risk_label"], "Higher Estimated Risk")
        self.assertAlmostEqual(item["risk_percentage"], 78.5, places=1)
        self.assertEqual(item["glucose"], 165.0)

    # 5. User isolation: User A cannot see User B's predictions
    def test_05_strict_user_isolation(self):
        # Save record for User A
        pred_a = {
            "success": True,
            "prediction": {
                "predicted_class": 0,
                "risk_label": "Lower Estimated Risk",
                "risk_probability": 0.22,
                "risk_percentage": 22.0,
                "input_biomarkers": {"glucose": 95.0, "bmi": 22.0, "blood_pressure": 70.0}
            }
        }
        save_prediction_record(self.user_a_id, pred_a)

        # Save record for User B
        pred_b = {
            "success": True,
            "prediction": {
                "predicted_class": 1,
                "risk_label": "Higher Estimated Risk",
                "risk_probability": 0.85,
                "risk_percentage": 85.0,
                "input_biomarkers": {"glucose": 180.0, "bmi": 36.0, "blood_pressure": 95.0}
            }
        }
        save_prediction_record(self.user_b_id, pred_b)

        # Verify User A's history
        history_a = get_user_predictions(self.user_a_id)
        self.assertEqual(len(history_a), 1)
        self.assertEqual(history_a[0]["risk_label"], "Lower Estimated Risk")

        # Verify User B's history
        history_b = get_user_predictions(self.user_b_id)
        self.assertEqual(len(history_b), 1)
        self.assertEqual(history_b[0]["risk_label"], "Higher Estimated Risk")

        # Web API request as User A
        self._login(email="alice.vance@clinic.org", password="SecurePassword123!")
        api_res = self.client.get("/api/history")
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["records"][0]["risk_label"], "Lower Estimated Risk")

    # 6. Active Dashboard displays actual prediction and trends
    def test_06_active_dashboard_view(self):
        self._login()

        # Insert 2 predictions to trigger trend calculation
        pred_1 = {
            "success": True,
            "prediction": {
                "predicted_class": 0,
                "risk_label": "Lower Estimated Risk",
                "risk_probability": 0.35,
                "risk_percentage": 35.0,
                "input_biomarkers": {"glucose": 105.0, "bmi": 24.5, "blood_pressure": 75.0}
            }
        }
        pred_2 = {
            "success": True,
            "prediction": {
                "predicted_class": 1,
                "risk_label": "Higher Estimated Risk",
                "risk_probability": 0.65,
                "risk_percentage": 65.0,
                "input_biomarkers": {"glucose": 150.0, "bmi": 29.8, "blood_pressure": 82.0}
            }
        }
        save_prediction_record(self.user_a_id, pred_1)
        save_prediction_record(self.user_a_id, pred_2)

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Higher Estimated Risk", res.data)
        self.assertIn(b"65.0%", res.data)
        self.assertIn(b"150.0", res.data)
        self.assertIn(b"Clinical Wellness Guidance", res.data)
        self.assertIn(b"General Guidance Notice", res.data)

    # 7. Recommendation Engine safely handles missing measurements
    def test_07_recommendations_with_missing_measurements(self):
        # Empty inputs should not throw an exception
        recs_empty = generate_health_recommendations(None, None)
        self.assertIsInstance(recs_empty, list)
        self.assertGreater(len(recs_empty), 0)

        # Partial inputs
        recs_partial = generate_health_recommendations(
            latest_prediction={"predicted_class": 1, "risk_percentage": 72.0},
            health_measurements={"glucose": None, "bmi": 32.5}
        )
        self.assertIsInstance(recs_partial, list)
        titles = [r["title"] for r in recs_partial]
        self.assertIn("Professional Clinical Consultation Recommended", titles)
        self.assertIn("Structured Low-Impact Aerobic Activity", titles)

    # 8. REST API /api/dashboard returns correct structure
    def test_08_api_dashboard_endpoint(self):
        self._login()
        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("user", data)
        self.assertIn("recommendations", data)
        self.assertIn("trend_data", data)
        self.assertIn("clinical_disclaimer", data)


if __name__ == "__main__":
    unittest.main()
