import os
import unittest
import tempfile
import sqlite3
from werkzeug.security import check_password_hash

# Ensure test uses an isolated SQLite database
os.environ["FORCE_SQLITE"] = "1"

from app import create_app
import db
from services.auth_service import (
    register_user,
    authenticate_user,
    get_user_by_id,
    get_user_by_email,
    update_user_profile
)


class AuthModuleTestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        db.SQLITE_DB_PATH = self.db_path
        db.init_db()

        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-12345",
            "WTF_CSRF_ENABLED": False
        })
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.close(self.db_fd)
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except Exception:
            pass

    # 1. Registration succeeds with valid information
    def test_01_registration_succeeds_with_valid_information(self):
        response = self.client.post("/register", data={
            "full_name": "Dr. Sarah Connor",
            "email": "sarah.connor@clinic.org",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "age": "38",
            "gender": "Female",
            "phone": "+1-555-0144"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account created successfully", response.data)

        user = get_user_by_email("sarah.connor@clinic.org")
        self.assertIsNotNone(user)
        self.assertEqual(user["full_name"], "Dr. Sarah Connor")
        self.assertEqual(user["age"], 38)
        self.assertEqual(user["gender"], "Female")

    # 2. Invalid registration data is rejected
    def test_02_invalid_registration_data_rejected(self):
        # A: Invalid email format
        res1 = self.client.post("/register", data={
            "full_name": "John Doe",
            "email": "not-an-email",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(res1.status_code, 400)
        self.assertIn(b"valid email address", res1.data)

        # B: Short password (< 8 chars)
        res2 = self.client.post("/register", data={
            "full_name": "John Doe",
            "email": "john@clinic.org",
            "password": "short",
            "confirm_password": "short"
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn(b"at least 8 characters", res2.data)

        # C: Mismatched passwords
        res3 = self.client.post("/register", data={
            "full_name": "John Doe",
            "email": "john@clinic.org",
            "password": "Password123!",
            "confirm_password": "DifferentPassword456!"
        })
        self.assertEqual(res3.status_code, 400)
        self.assertIn(b"Passwords do not match", res3.data)

        # D: Invalid age
        res4 = self.client.post("/register", data={
            "full_name": "John Doe",
            "email": "john@clinic.org",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "age": "999"
        })
        self.assertEqual(res4.status_code, 400)
        self.assertIn(b"Age must be between 1 and 120", res4.data)

    # 3. Duplicate emails are rejected
    def test_03_duplicate_email_rejected(self):
        # Register first time
        res1 = register_user(
            full_name="Alice Smith",
            email="alice@clinic.org",
            password="StrongPassword123!",
            confirm_password="StrongPassword123!"
        )
        self.assertTrue(res1["success"])

        # Attempt to register again with same email
        res2 = self.client.post("/register", data={
            "full_name": "Alice Duplicate",
            "email": "alice@clinic.org",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!"
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn(b"already exists", res2.data)

    # 4. Valid login succeeds
    def test_04_valid_login_succeeds(self):
        register_user(
            full_name="Robert Lang",
            email="robert@clinic.org",
            password="SecurePassWord789!",
            confirm_password="SecurePassWord789!"
        )

        response = self.client.post("/login", data={
            "email": "robert@clinic.org",
            "password": "SecurePassWord789!"
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back, Robert Lang", response.data)

        # Verify session is established
        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)
            self.assertEqual(sess["user_name"], "Robert Lang")
            self.assertEqual(sess["user_email"], "robert@clinic.org")

    # 5. Invalid login fails safely
    def test_05_invalid_login_fails_safely(self):
        register_user(
            full_name="Secure User",
            email="user@clinic.org",
            password="CorrectPassword123!",
            confirm_password="CorrectPassword123!"
        )

        # Wrong password
        res1 = self.client.post("/login", data={
            "email": "user@clinic.org",
            "password": "WrongPassword999!"
        })
        self.assertEqual(res1.status_code, 401)
        self.assertIn(b"Invalid email or password", res1.data)

        # Non-existent email (should give the exact same generic message)
        res2 = self.client.post("/login", data={
            "email": "does.not.exist@clinic.org",
            "password": "SomePassword123!"
        })
        self.assertEqual(res2.status_code, 401)
        self.assertIn(b"Invalid email or password", res2.data)

    # 6. Passwords are stored as hashes
    def test_06_passwords_stored_as_secure_hashes(self):
        plain_password = "SensitivePlainTextPass123!"
        register_user(
            full_name="Hash Check User",
            email="hashcheck@clinic.org",
            password=plain_password,
            confirm_password=plain_password
        )

        user = get_user_by_email("hashcheck@clinic.org")
        stored_hash = user["password_hash"]

        # Ensure plaintext password is NEVER stored
        self.assertNotIn(plain_password, stored_hash)
        self.assertNotEqual(plain_password, stored_hash)

        # Ensure it is a secure hash format and verifies correctly
        self.assertTrue(stored_hash.startswith("pbkdf2:sha256:") or stored_hash.startswith("scrypt:"))
        self.assertTrue(check_password_hash(stored_hash, plain_password))
        self.assertFalse(check_password_hash(stored_hash, "WrongPassword"))

    # 7. Logout ends the authenticated session
    def test_07_logout_ends_authenticated_session(self):
        register_user(
            full_name="Logout User",
            email="logout@clinic.org",
            password="Password1234!",
            confirm_password="Password1234!"
        )

        # Log in
        self.client.post("/login", data={
            "email": "logout@clinic.org",
            "password": "Password1234!"
        })

        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)

        # Log out
        res = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"successfully logged out", res.data)

        # Check session is completely cleared
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

        # Verify accessing profile after logout is rejected
        profile_res = self.client.get("/profile")
        self.assertEqual(profile_res.status_code, 302)
        self.assertIn("/login", profile_res.headers["Location"])

    # 8. Unauthorized profile access is rejected
    def test_08_unauthorized_profile_access_rejected(self):
        # Web route redirection
        response = self.client.get("/profile")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        # API endpoint 401 Unauthorized
        api_response = self.client.get("/api/profile")
        self.assertEqual(api_response.status_code, 401)
        data = api_response.get_json()
        self.assertFalse(data["authenticated"])

    # 9. Users cannot access another user's private profile
    def test_09_user_isolation_prevent_cross_account_access(self):
        # Create User A
        reg_a = register_user("User Alpha", "alpha@clinic.org", "PasswordAlpha123!", "PasswordAlpha123!", 30, "Male", "+1-555-0111")
        self.assertTrue(reg_a["success"], f"Registration A failed: {reg_a.get('error')}")
        id_a = reg_a["user_id"]

        # Create User B
        reg_b = register_user("User Beta", "beta@clinic.org", "PasswordBeta123!", "PasswordBeta123!", 45, "Female", "+1-555-0222")
        self.assertTrue(reg_b["success"], f"Registration B failed: {reg_b.get('error')}")
        id_b = reg_b["user_id"]

        # Log in as User A
        self.client.post("/login", data={"email": "alpha@clinic.org", "password": "PasswordAlpha123!"})

        # Profile view must return User A's data, strictly isolated from User B
        res_a = self.client.get("/profile")
        self.assertIn(b"User Alpha", res_a.data)
        self.assertNotIn(b"User Beta", res_a.data)

        # Profile edit form updates ONLY User A
        self.client.post("/profile", data={
            "full_name": "User Alpha Updated",
            "age": "32",
            "gender": "Male",
            "phone": "+1-555-1111"
        })

        user_a_updated = get_user_by_id(id_a)
        user_b_check = get_user_by_id(id_b)

        self.assertEqual(user_a_updated["full_name"], "User Alpha Updated")
        self.assertEqual(user_a_updated["age"], 32)

        # Ensure User B's record remains 100% untouched
        self.assertEqual(user_b_check["full_name"], "User Beta")
        self.assertEqual(user_b_check["age"], 45)

    # 10. Existing pages, navigation, and shared UI continue working
    def test_10_shared_pages_and_navigation_continue_working(self):
        # Landing page
        home_res = self.client.get("/")
        self.assertEqual(home_res.status_code, 200)
        self.assertIn(b"GlucoGuard AI", home_res.data)
        self.assertIn(b"Predictive AI for Early Diabetes Risk Detection", home_res.data)

        # Health check API
        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)
        health_data = health_res.get_json()
        self.assertEqual(health_data["status"], "healthy")
        self.assertEqual(health_data["member1_auth_profile"], "active")

        # Static assets accessible
        css_res = self.client.get("/static/css/style.css")
        self.assertEqual(css_res.status_code, 200)

        js_res = self.client.get("/static/js/main.js")
        self.assertEqual(js_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
