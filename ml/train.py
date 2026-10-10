"""
AI-Based Diabetes Risk Prediction System
Member 3: Machine Learning Model Training Pipeline

Dataset: NIDDK Pima Indians Diabetes Dataset (768 records, 8 features, 1 target)
Algorithm: Random Forest Classifier
Model Storage: Joblib serialization with fitted Imputer & Scaler
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix, classification_report
)

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diabetes.csv")
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "diabetes_rf_model.joblib")

FEATURE_NAMES = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
    "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"
]
TARGET_COL = "Outcome"

# Biological features where 0 represents missing/unmeasured data
ZERO_AS_MISSING = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


def train_model():
    """Execute stratified training and serialization of Random Forest classifier."""
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Training dataset not found at {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    X = df[FEATURE_NAMES].copy()
    y = df[TARGET_COL].copy()

    # Preprocessing: Mark biological zeros as NaN for imputation
    X[ZERO_AS_MISSING] = X[ZERO_AS_MISSING].replace(0, np.nan)

    # Stratified 80/20 train/test split (fixed seed for reproducibility)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # Median imputer fitted strictly on training data
    imputer = SimpleImputer(strategy="median")
    X_train_imputed = imputer.fit_transform(X_train)
    X_test_imputed = imputer.transform(X_test)

    # Standard scaler fitted strictly on training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_imputed)
    X_test_scaled = scaler.transform(X_test_imputed)

    # Random Forest Classifier
    rf = RandomForestClassifier(
        n_estimators=150,
        max_depth=6,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42
    )
    rf.fit(X_train_scaled, y_train)

    # Held-out test evaluation
    y_pred = rf.predict(X_test_scaled)
    y_proba = rf.predict_proba(X_test_scaled)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    prec = float(precision_score(y_test, y_pred))
    rec = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_proba))
    cm = confusion_matrix(y_test, y_pred).tolist()

    importances = {feat.lower(): float(imp) for feat, imp in zip(FEATURE_NAMES, rf.feature_importances_)}

    os.makedirs(MODEL_DIR, exist_ok=True)
    artifact = {
        "model": rf,
        "imputer": imputer,
        "scaler": scaler,
        "features": [f.lower() for f in FEATURE_NAMES],
        "feature_names_original": FEATURE_NAMES,
        "zero_missing_cols": ZERO_AS_MISSING,
        "feature_importances": importances,
        "metrics": {
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "roc_auc": roc_auc,
            "confusion_matrix": cm
        },
        "target_mapping": {
            0: "Lower Estimated Risk",
            1: "Higher Estimated Risk"
        }
    }
    joblib.dump(artifact, MODEL_PATH)

    print(f"Random Forest model successfully trained and saved to {MODEL_PATH}")
    print(f"Accuracy: {acc:.4f} | Recall: {rec:.4f} | Precision: {prec:.4f} | ROC-AUC: {roc_auc:.4f}")
    return artifact


if __name__ == "__main__":
    train_model()
