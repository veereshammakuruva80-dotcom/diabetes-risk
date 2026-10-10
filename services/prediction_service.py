"""
AI-Based Diabetes Risk Prediction System
Member 3: Prediction Service Layer

Loads serialized Random Forest model and preprocessing transformers.
Validates input biomarkers and generates structured risk estimates with probability scores.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "diabetes_rf_model.joblib"
)

# Standardized feature interface (strict ordering expected by the model)
MODEL_FEATURES = [
    "pregnancies",
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
    "diabetes_pedigree_function",
    "age"
]

_cached_artifact: Optional[Dict[str, Any]] = None


def load_model_artifact() -> Dict[str, Any]:
    """Load serialized model artifact with in-memory caching."""
    global _cached_artifact
    if _cached_artifact is not None:
        return _cached_artifact

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}. Please run training pipeline.")

    _cached_artifact = joblib.load(MODEL_PATH)
    return _cached_artifact


def validate_prediction_input(raw_input: Dict[str, Any]) -> Tuple[bool, Dict[str, float], Optional[str]]:
    """
    Validate that all 8 required features are present, numerical, and within reasonable limits.
    Returns: (is_valid, sanitized_dict, error_message)
    """
    if not isinstance(raw_input, dict):
        return False, {}, "Input data must be a JSON object or key-value dictionary."

    sanitized: Dict[str, float] = {}

    for feat in MODEL_FEATURES:
        val = raw_input.get(feat)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            # Default zero for optional/unmeasured clinical tests
            if feat in ["pregnancies", "skin_thickness", "insulin"]:
                sanitized[feat] = 0.0
                continue
            return False, {}, f"Missing required biomarker: '{feat}' is required for diabetes risk prediction."

        try:
            num = float(val)
        except (ValueError, TypeError):
            return False, {}, f"Invalid data type for '{feat}': must be a valid numeric value."

        if num < 0:
            return False, {}, f"Invalid negative value for '{feat}'."

        sanitized[feat] = num

    return True, sanitized, None


def predict_diabetes_risk(biomarkers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate structured diabetes risk prediction using trained Random Forest model.
    """
    # 1. Validate inputs
    is_valid, clean_data, err_msg = validate_prediction_input(biomarkers)
    if not is_valid:
        return {
            "success": False,
            "error": err_msg
        }

    # 2. Load model & transformers
    try:
        artifact = load_model_artifact()
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to load predictive model: {str(e)}"
        }

    model = artifact["model"]
    imputer = artifact["imputer"]
    scaler = artifact["scaler"]
    importances = artifact.get("feature_importances", {})

    # 3. Construct DataFrame matching model columns exactly
    df_input = pd.DataFrame([{
        "Pregnancies": clean_data["pregnancies"],
        "Glucose": clean_data["glucose"] if clean_data["glucose"] > 0 else np.nan,
        "BloodPressure": clean_data["blood_pressure"] if clean_data["blood_pressure"] > 0 else np.nan,
        "SkinThickness": clean_data["skin_thickness"] if clean_data["skin_thickness"] > 0 else np.nan,
        "Insulin": clean_data["insulin"] if clean_data["insulin"] > 0 else np.nan,
        "BMI": clean_data["bmi"] if clean_data["bmi"] > 0 else np.nan,
        "DiabetesPedigreeFunction": clean_data["diabetes_pedigree_function"],
        "Age": clean_data["age"]
    }])

    # 4. Apply training-fitted imputer and scaler
    try:
        imputed_array = imputer.transform(df_input)
        scaled_array = scaler.transform(imputed_array)

        # 5. Predict class and class probabilities
        pred_class = int(model.predict(scaled_array)[0])
        probabilities = model.predict_proba(scaled_array)[0]
        # Probability of Class 1 (Higher Estimated Risk)
        prob_high_risk = float(probabilities[1])
        prob_low_risk = float(probabilities[0])

    except Exception as e:
        return {
            "success": False,
            "error": f"Prediction inference error: {str(e)}"
        }

    risk_label = "Higher Estimated Risk" if pred_class == 1 else "Lower Estimated Risk"
    risk_percentage = round(prob_high_risk * 100, 1)

    # Top global feature importances for explainability
    sorted_importances = sorted(
        [{"feature": k, "importance_pct": round(v * 100, 1)} for k, v in importances.items()],
        key=lambda x: x["importance_pct"],
        reverse=True
    )

    return {
        "success": True,
        "prediction": {
            "predicted_class": pred_class,
            "risk_label": risk_label,
            "risk_probability": round(prob_high_risk, 4),
            "risk_percentage": risk_percentage,
            "confidence_lower_risk": round(prob_low_risk, 4),
            "top_contributing_factors": sorted_importances[:5],
            "input_biomarkers": clean_data
        },
        "model_metadata": {
            "algorithm": "Random Forest Classifier",
            "model_accuracy": artifact.get("metrics", {}).get("accuracy"),
            "model_roc_auc": artifact.get("metrics", {}).get("roc_auc")
        },
        "disclaimer": (
            "This assessment is an algorithmic risk estimation generated by machine learning "
            "for informational purposes only. It does NOT constitute medical diagnosis or advice."
        )
    }
