"""
AI-Based Diabetes Risk Prediction System
Member 2: Health Data Input Module — Automated Test Suite

Tests:
1. Health-data page loads correctly when authenticated.
2. Valid inputs are accepted.
3. Required fields cannot be submitted empty.
4. Invalid numeric values are rejected.
5. Out-of-range values are handled appropriately.
6. Backend validation rejects invalid requests.
7. Submission success and failure messages work.
8. Existing navigation and shared styling remain intact.
9. Existing authentication continues working.
10. Existing unrelated modules (Member 1 auth & profile) still work.
11. Records are stored correctly and user ownership/isolation is enforced.
12. Submitted field names and types match the agreed ML interface.
"""

import os
import unittest
import tempfile

os.environ["FORCE_SQLITE"] = "1"

from app import create_app
import db
from services.auth_service import register_user
from services.health_data_service import (
    validate_health_data,
    save_health_data,
    get_user_health_records,
    get_user_latest_health_record
)


class HealthDataModuleTestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        db.SQLITE_DB_PATH = self.db_path
        db.init_db()

        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-health-data-secret-key",
            "WTF_CSRF_ENABLED": False
        })
        self.client = self.app.test_client()

        # Register and login default test user
        reg_res = register_user(
            full_name="Dr. Alex Rivera",
            email="alex.rivera@clinic.org",
            password="StrongPassword123!",
            confirm_password="StrongPassword123!",
            age=35,
            gender="Male",
            phone="+1-555-0199"
        )
        self.user_id = reg_res["user_id"]

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except Exception:
            pass

    def _login(self):
        return self.client.post("/login", data={
            "email": "alex.rivera@clinic.org",
            "password": "StrongPassword123!"
        }, follow_redirects=True)

    # 1. Health-data page loads correctly when authenticated
    def test_01_health_data_page_loads_correctly(self):
        # Unauthenticated request redirects to login
        res_unauth = self.client.get("/health-data")
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn("/login", res_unauth.headers["Location"])

        # Authenticated request loads successfully
        self._login()
        res_auth = self.client.get("/health-data")
        self.assertEqual(res_auth.status_code, 200)
        self.assertIn(b"Clinical Health Data Input", res_auth.data)
        self.assertIn(b"Plasma Glucose (mg/dL)", res_auth.data)

    # 2. Valid inputs are accepted
    def test_02_valid_inputs_accepted(self):
        self._login()
        valid_payload = {
            "pregnancies": "2",
            "glucose": "120.5",
            "blood_pressure": "80",
            "skin_thickness": "25",
            "insulin": "110",
            "bmi": "26.4",
            "diabetes_pedigree_function": "0.45",
            "age": "35"
        }
        res = self.client.post("/health-data", data=valid_payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"successfully validated and recorded", res.data)

        # Check DB persistence
        records = get_user_health_records(self.user_id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["glucose"], 120.5)
        self.assertEqual(records[0]["bmi"], 26.4)

    # 3. Required fields cannot be submitted empty
    def test_03_required_fields_cannot_be_empty(self):
        self._login()
        # Missing glucose, blood_pressure, bmi, pedigree
        empty_payload = {
            "pregnancies": "",
            "glucose": "",
            "blood_pressure": "",
            "skin_thickness": "",
            "insulin": "",
            "bmi": "",
            "diabetes_pedigree_function": "",
            "age": ""
        }
        res = self.client.post("/health-data", data=empty_payload)
        self.assertEqual(res.status_code, 200)  # Re-rendered form with error alerts
        self.assertIn(b"is required", res.data)

        records = get_user_health_records(self.user_id)
        self.assertEqual(len(records), 0)

    # 4. Invalid numeric values are rejected
    def test_04_invalid_numeric_values_rejected(self):
        is_valid, _, errors = validate_health_data({
            "glucose": "not-a-number",
            "blood_pressure": "abc",
            "bmi": "twenty-five",
            "diabetes_pedigree_function": "high",
            "age": "forty"
        })
        self.assertFalse(is_valid)
        self.assertIn("glucose", errors)
        self.assertIn("must be a valid number", errors["glucose"])

    # 5. Out-of-range values are handled appropriately
    def test_05_out_of_range_values_rejected(self):
        # Glucose too low (< 40)
        v1, _, err1 = validate_health_data({"glucose": 15, "blood_pressure": 80, "bmi": 25, "diabetes_pedigree_function": 0.5, "age": 30})
        self.assertFalse(v1)
        self.assertIn("between 40.0 and 500.0", err1["glucose"])

        # Glucose too high (> 500)
        v2, _, err2 = validate_health_data({"glucose": 650, "blood_pressure": 80, "bmi": 25, "diabetes_pedigree_function": 0.5, "age": 30})
        self.assertFalse(v2)
        self.assertIn("between 40.0 and 500.0", err2["glucose"])

        # BMI too high (> 70)
        v3, _, err3 = validate_health_data({"glucose": 100, "blood_pressure": 80, "bmi": 88.5, "diabetes_pedigree_function": 0.5, "age": 30})
        self.assertFalse(v3)
        self.assertIn("between 10.0 and 70.0", err3["bmi"])

        # Age too high (> 120)
        v4, _, err4 = validate_health_data({"glucose": 100, "blood_pressure": 80, "bmi": 25, "diabetes_pedigree_function": 0.5, "age": 140})
        self.assertFalse(v4)
        self.assertIn("between 1 and 120", err4["age"])

    # 6. Backend validation rejects invalid requests (API)
    def test_06_backend_api_rejects_invalid_requests(self):
        self._login()
        # Missing required values
        res = self.client.post("/api/health-data", json={"glucose": 9999})
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("errors", json_data)

    # 7. Submission success and failure messages work
    def test_07_submission_success_and_failure_messages(self):
        self._login()
        # Success submission
        res_ok = self.client.post("/health-data", data={
            "glucose": "110",
            "blood_pressure": "75",
            "bmi": "24.5",
            "diabetes_pedigree_function": "0.38",
            "age": "29"
        }, follow_redirects=True)
        self.assertIn(b"Clinical health data successfully validated and recorded", res_ok.data)

        # Failure submission
        res_fail = self.client.post("/health-data", data={
            "glucose": "10",  # Out of range
            "blood_pressure": "75",
            "bmi": "24.5",
            "diabetes_pedigree_function": "0.38",
            "age": "29"
        })
        self.assertIn(b"Validation failed", res_fail.data)

    # 8. Existing navigation and shared styling remain unchanged
    def test_08_existing_navigation_and_shared_styles(self):
        self._login()
        res = self.client.get("/health-data")
        # Shared navbar elements preserved
        self.assertIn(b"GlucoGuard AI", res.data)
        self.assertIn(b"nav-home", res.data)
        self.assertIn(b"nav-profile", res.data)
        self.assertIn(b"nav-logout", res.data)
        self.assertIn(b"nav-health-data", res.data)

    # 9. Existing authentication continues working
    def test_09_existing_authentication_preserved(self):
        # Login works
        login_res = self.client.post("/login", data={
            "email": "alex.rivera@clinic.org",
            "password": "StrongPassword123!"
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # Logout works
        logout_res = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn(b"successfully logged out", logout_res.data)

    # 10. Existing unrelated modules (Member 1 profile) still work
    def test_10_member1_profile_module_unaffected(self):
        self._login()
        # View profile
        profile_res = self.client.get("/profile")
        self.assertEqual(profile_res.status_code, 200)
        self.assertIn(b"Dr. Alex Rivera", profile_res.data)

        # Edit profile
        edit_res = self.client.post("/profile", data={
            "full_name": "Dr. Alex Rivera Senior",
            "age": "36",
            "gender": "Male",
            "phone": "+1-555-0199"
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)
        self.assertIn(b"Profile updated successfully", edit_res.data)

    # 11. Records are stored correctly and user ownership/isolation is enforced
    def test_11_records_stored_with_strict_user_ownership(self):
        # Register User 2
        user2_reg = register_user(
            full_name="Patient User Two",
            email="user2@clinic.org",
            password="Password987!",
            confirm_password="Password987!",
            age=50
        )
        user2_id = user2_reg["user_id"]

        # Save record for User 1
        save_health_data(self.user_id, {
            "glucose": 105, "blood_pressure": 72, "bmi": 22.0,
            "diabetes_pedigree_function": 0.25, "age": 35
        })

        # Save record for User 2
        save_health_data(user2_id, {
            "glucose": 195, "blood_pressure": 90, "bmi": 34.2,
            "diabetes_pedigree_function": 0.85, "age": 50
        })

        # User 1 query: only sees their own records
        u1_records = get_user_health_records(self.user_id)
        self.assertEqual(len(u1_records), 1)
        self.assertEqual(u1_records[0]["glucose"], 105.0)

        # User 2 query: only sees their own records
        u2_records = get_user_health_records(user2_id)
        self.assertEqual(len(u2_records), 1)
        self.assertEqual(u2_records[0]["glucose"], 195.0)

    # 12. Submitted field names and types match the agreed ML interface
    def test_12_field_names_and_types_match_ml_interface(self):
        self._login()
        # Save record via API
        payload = {
            "pregnancies": 3,
            "glucose": 135.0,
            "blood_pressure": 82.0,
            "skin_thickness": 28.0,
            "insulin": 140.0,
            "bmi": 29.5,
            "diabetes_pedigree_function": 0.52,
            "age": 41
        }
        post_res = self.client.post("/api/health-data", json=payload)
        self.assertEqual(post_res.status_code, 201)

        # Retrieve standardized feature vector from /api/health-data/latest
        latest_res = self.client.get("/api/health-data/latest")
        self.assertEqual(latest_res.status_code, 200)
        data = latest_res.get_json()
        self.assertTrue(data["success"])

        features = data["features"]
        # Required ML model feature vector keys
        expected_keys = [
            "pregnancies", "glucose", "blood_pressure", "skin_thickness",
            "insulin", "bmi", "diabetes_pedigree_function", "age"
        ]
        for k in expected_keys:
            self.assertIn(k, features)

        # Check types
        self.assertIsInstance(features["pregnancies"], int)
        self.assertIsInstance(features["glucose"], float)
        self.assertIsInstance(features["blood_pressure"], float)
        self.assertIsInstance(features["skin_thickness"], float)
        self.assertIsInstance(features["insulin"], float)
        self.assertIsInstance(features["bmi"], float)
        self.assertIsInstance(features["diabetes_pedigree_function"], float)
        self.assertIsInstance(features["age"], int)


if __name__ == "__main__":
    unittest.main()
