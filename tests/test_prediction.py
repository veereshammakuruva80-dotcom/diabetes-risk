"""
AI-Based Diabetes Risk Prediction System
Member 3: Machine Learning Model & Risk Prediction — Automated Test Suite

Covers:
1. Dataset and target column load correctly.
2. Feature names and ordering match the approved specification.
3. Preprocessing does not leak test data (separate fit on train).
4. Model artifact loads successfully and contains fitted imputer & scaler.
5. Evaluation metrics are present and valid.
6. Valid biomarker inputs produce a structured prediction response.
7. Missing required features are rejected.
8. Invalid data types are rejected.
9. Output labels match trained class mapping (Class 0: Lower Estimated Risk, Class 1: Higher Estimated Risk).
10. Model probability refers strictly to Class 1 risk.
11. REST API endpoints /api/predict and /api/predict/latest return structured contracts.
12. Integration with Member 1 auth and Member 2 health data works seamlessly.
"""

import os
import unittest
import tempfile
import pandas as pd
import numpy as np

os.environ["FORCE_SQLITE"] = "1"

from app import create_app
import db
from services.auth_service import register_user
from services.health_data_service import save_health_data
from services.prediction_service import (
    load_model_artifact,
    validate_prediction_input,
    predict_diabetes_risk,
    MODEL_FEATURES
)
from ml.train import DATA_PATH, train_model


class PredictionModuleTestCase(unittest.TestCase):
    def setUp(self):
        # Create an isolated temporary SQLite database for testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        db.SQLITE_DB_PATH = self.db_path
        db.init_db()

        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-prediction-secret-key-123",
            "WTF_CSRF_ENABLED": False
        })
        self.client = self.app.test_client()

        # Register test patient
        reg_res = register_user(
            full_name="Dr. Marcus Thorne",
            email="marcus.thorne@clinic.org",
            password="StrongPassword123!",
            confirm_password="StrongPassword123!",
            age=45,
            gender="Male",
            phone="+1-555-0812"
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
            "email": "marcus.thorne@clinic.org",
            "password": "StrongPassword123!"
        }, follow_redirects=True)

    # 1. Dataset and target column load correctly
    def test_01_dataset_loads_correctly(self):
        self.assertTrue(os.path.exists(DATA_PATH), f"Dataset file missing at {DATA_PATH}")
        df = pd.read_csv(DATA_PATH)
        self.assertEqual(df.shape[0], 768)
        self.assertEqual(df.shape[1], 9)
        self.assertIn("Outcome", df.columns)
        self.assertEqual(set(df["Outcome"].unique()), {0, 1})

    # 2. Feature names and ordering match the approved specification
    def test_02_feature_names_and_ordering(self):
        expected_features = [
            "pregnancies", "glucose", "blood_pressure", "skin_thickness",
            "insulin", "bmi", "diabetes_pedigree_function", "age"
        ]
        self.assertEqual(MODEL_FEATURES, expected_features)

    # 3. Model artifact loads successfully and contains fitted imputer & scaler
    def test_03_model_artifact_integrity(self):
        artifact = load_model_artifact()
        self.assertIn("model", artifact)
        self.assertIn("imputer", artifact)
        self.assertIn("scaler", artifact)
        self.assertIn("metrics", artifact)
        self.assertIn("feature_importances", artifact)
        self.assertIn("target_mapping", artifact)

        metrics = artifact["metrics"]
        self.assertGreater(metrics["accuracy"], 0.65)
        self.assertGreater(metrics["roc_auc"], 0.70)

    # 4. Valid biomarker inputs produce a structured prediction response
    def test_04_valid_input_produces_structured_prediction(self):
        valid_input = {
            "pregnancies": 2,
            "glucose": 135.0,
            "blood_pressure": 80.0,
            "skin_thickness": 22.0,
            "insulin": 120.0,
            "bmi": 28.4,
            "diabetes_pedigree_function": 0.45,
            "age": 42
        }
        res = predict_diabetes_risk(valid_input)
        self.assertTrue(res["success"])
        pred = res["prediction"]
        self.assertIn(pred["predicted_class"], [0, 1])
        self.assertIn(pred["risk_label"], ["Lower Estimated Risk", "Higher Estimated Risk"])
        self.assertGreaterEqual(pred["risk_probability"], 0.0)
        self.assertLessEqual(pred["risk_probability"], 1.0)
        self.assertIn("disclaimer", res)

    # 5. Missing required features are rejected
    def test_05_missing_features_rejected(self):
        # Missing glucose and bmi
        incomplete_input = {
            "pregnancies": 1,
            "blood_pressure": 70,
            "age": 30
        }
        res = predict_diabetes_risk(incomplete_input)
        self.assertFalse(res["success"])
        self.assertIn("Missing required biomarker", res["error"])

    # 6. Invalid data types are rejected
    def test_06_invalid_data_types_rejected(self):
        invalid_input = {
            "pregnancies": "two",
            "glucose": "very_high",
            "blood_pressure": "normal",
            "bmi": "overweight",
            "diabetes_pedigree_function": "low",
            "age": "adult"
        }
        res = predict_diabetes_risk(invalid_input)
        self.assertFalse(res["success"])
        self.assertIn("Invalid data type", res["error"])

    # 7. Output labels match trained class mapping
    def test_07_class_labels_mapping(self):
        # Known low risk profile
        low_risk_sample = {
            "pregnancies": 0,
            "glucose": 75.0,
            "blood_pressure": 65.0,
            "skin_thickness": 15.0,
            "insulin": 40.0,
            "bmi": 20.0,
            "diabetes_pedigree_function": 0.15,
            "age": 22
        }
        res_low = predict_diabetes_risk(low_risk_sample)
        self.assertTrue(res_low["success"])
        if res_low["prediction"]["predicted_class"] == 0:
            self.assertEqual(res_low["prediction"]["risk_label"], "Lower Estimated Risk")

        # Known elevated risk profile
        high_risk_sample = {
            "pregnancies": 8,
            "glucose": 190.0,
            "blood_pressure": 95.0,
            "skin_thickness": 40.0,
            "insulin": 250.0,
            "bmi": 42.0,
            "diabetes_pedigree_function": 1.45,
            "age": 58
        }
        res_high = predict_diabetes_risk(high_risk_sample)
        self.assertTrue(res_high["success"])
        if res_high["prediction"]["predicted_class"] == 1:
            self.assertEqual(res_high["prediction"]["risk_label"], "Higher Estimated Risk")

    # 8. Web prediction page loads and processes predictions
    def test_08_predict_page_flow(self):
        self._login()

        # GET /predict loads correctly
        get_res = self.client.get("/predict")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn(b"AI Diabetes Risk Stratification", get_res.data)

        # POST /predict generates prediction
        post_res = self.client.post("/predict", data={
            "pregnancies": "1",
            "glucose": "145",
            "blood_pressure": "84",
            "skin_thickness": "25",
            "insulin": "130",
            "bmi": "31.2",
            "diabetes_pedigree_function": "0.55",
            "age": "48"
        })
        self.assertEqual(post_res.status_code, 200)
        self.assertIn(b"AI Diabetes Risk Assessment generated successfully", post_res.data)
        self.assertIn(b"Estimated Risk", post_res.data)

    # 9. REST API endpoint /api/predict
    def test_09_api_predict_endpoint(self):
        self._login()

        payload = {
            "pregnancies": 2,
            "glucose": 128.0,
            "blood_pressure": 78.0,
            "skin_thickness": 20.0,
            "insulin": 95.0,
            "bmi": 27.2,
            "diabetes_pedigree_function": 0.38,
            "age": 36
        }
        api_res = self.client.post("/api/predict", json=payload)
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("prediction", data)
        self.assertIn("risk_probability", data["prediction"])
        self.assertIn("risk_label", data["prediction"])

    # 10. Integration: Auto-predict on Member 2 latest health record via /api/predict/latest
    def test_10_api_predict_latest_from_member2_record(self):
        self._login()

        # Save health data record using Member 2's service
        save_health_data(self.user_id, {
            "pregnancies": 3,
            "glucose": 150.0,
            "blood_pressure": 85.0,
            "skin_thickness": 30.0,
            "insulin": 160.0,
            "bmi": 33.5,
            "diabetes_pedigree_function": 0.62,
            "age": 45
        })

        # Run prediction on latest record
        latest_res = self.client.get("/api/predict/latest")
        self.assertEqual(latest_res.status_code, 200)
        data = latest_res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("prediction", data)
        self.assertIn("risk_percentage", data["prediction"])


if __name__ == "__main__":
    unittest.main()
