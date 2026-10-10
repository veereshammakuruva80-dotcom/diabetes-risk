"""
AI-Based Diabetes Risk Prediction System
Member 2: Health Data Input Module — Service Layer

Responsible for parsing, validating, and persisting patient metabolic parameters.
Prepares validated feature dictionary adhering to the Scikit-Learn Random Forest Classifier interface.
"""

from typing import Dict, Any, Tuple, List, Optional
from db import query_one, query_all, execute_commit

# Explicit physiological validation boundaries aligned with ML training distribution
VALIDATION_LIMITS = {
    "pregnancies": {"min": 0, "max": 25, "type": int, "label": "Pregnancies"},
    "glucose": {"min": 40.0, "max": 500.0, "type": float, "label": "Plasma Glucose (mg/dL)"},
    "blood_pressure": {"min": 40.0, "max": 250.0, "type": float, "label": "Diastolic Blood Pressure (mm Hg)"},
    "skin_thickness": {"min": 0.0, "max": 100.0, "type": float, "label": "Triceps Skin Thickness (mm)"},
    "insulin": {"min": 0.0, "max": 900.0, "type": float, "label": "2-Hour Serum Insulin (µU/mL)"},
    "bmi": {"min": 10.0, "max": 70.0, "type": float, "label": "Body Mass Index (kg/m²)"},
    "diabetes_pedigree_function": {"min": 0.05, "max": 3.00, "type": float, "label": "Diabetes Pedigree Function"},
    "age": {"min": 1, "max": 120, "type": int, "label": "Age (years)"}
}

REQUIRED_FIELDS = ["glucose", "blood_pressure", "bmi", "diabetes_pedigree_function", "age"]


def validate_health_data(raw_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Dict[str, str]]:
    """
    Validate health input parameters according to clinically justified physiological limits.
    
    Returns:
        (is_valid: bool, sanitized_data: dict, errors: dict)
    """
    errors: Dict[str, str] = {}
    sanitized: Dict[str, Any] = {}

    if not isinstance(raw_data, dict):
        return False, {}, {"general": "Invalid data format received. Expected a key-value object."}

    # 1. Check required fields are present and not empty
    for field in REQUIRED_FIELDS:
        val = raw_data.get(field)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            label = VALIDATION_LIMITS[field]["label"]
            errors[field] = f"{label} is required."

    # 2. Parse and validate each parameter
    for field, limits in VALIDATION_LIMITS.items():
        val = raw_data.get(field)
        field_type = limits["type"]
        min_val = limits["min"]
        max_val = limits["max"]
        label = limits["label"]

        # Default optional parameters if empty
        if val is None or (isinstance(val, str) and val.strip() == ""):
            if field in ["pregnancies", "skin_thickness", "insulin"]:
                sanitized[field] = field_type(0)
                continue
            else:
                # Already captured in required fields check
                continue

        # Convert to numeric type
        try:
            cleaned_str = str(val).strip()
            num_val = field_type(cleaned_str)
        except (ValueError, TypeError):
            errors[field] = f"{label} must be a valid number."
            continue

        # Check range limits
        if num_val < min_val or num_val > max_val:
            errors[field] = f"{label} must be between {min_val} and {max_val}."
            continue

        sanitized[field] = num_val

    is_valid = len(errors) == 0
    return is_valid, sanitized, errors


def save_health_data(user_id: int, raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and save a health data record for an authenticated user.
    Prevents unauthorized or unvalidated data insertion into the database.
    """
    if not user_id or not isinstance(user_id, int):
        return {"success": False, "error": "Authentication required. Invalid user session.", "errors": {}}

    is_valid, sanitized, errors = validate_health_data(raw_data)

    if not is_valid:
        return {
            "success": False,
            "error": "Validation failed. Please correct the highlighted errors.",
            "errors": errors
        }

    insert_query = """
        INSERT INTO health_data (
            user_id, pregnancies, glucose, blood_pressure, 
            skin_thickness, insulin, bmi, diabetes_pedigree_function, age
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        user_id,
        sanitized["pregnancies"],
        sanitized["glucose"],
        sanitized["blood_pressure"],
        sanitized["skin_thickness"],
        sanitized["insulin"],
        sanitized["bmi"],
        sanitized["diabetes_pedigree_function"],
        sanitized["age"]
    )

    try:
        record_id = execute_commit(insert_query, params)
        sanitized["id"] = record_id
        sanitized["user_id"] = user_id
        return {
            "success": True,
            "record_id": record_id,
            "data": sanitized,
            "message": "Clinical health data recorded successfully."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Database persistence error: {str(e)}",
            "errors": {"db": "Failed to persist health records to database."}
        }


def get_user_health_records(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all health records for the authenticated user only.
    Enforces strict user isolation.
    """
    if not user_id:
        return []
    query = """
        SELECT id, user_id, pregnancies, glucose, blood_pressure, 
               skin_thickness, insulin, bmi, diabetes_pedigree_function, age, created_at
        FROM health_data
        WHERE user_id = %s
        ORDER BY created_at DESC
    """
    return query_all(query, (user_id,))


def get_user_latest_health_record(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the most recent health record for the authenticated user.
    """
    if not user_id:
        return None
    query = """
        SELECT id, user_id, pregnancies, glucose, blood_pressure, 
               skin_thickness, insulin, bmi, diabetes_pedigree_function, age, created_at
        FROM health_data
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    return query_one(query, (user_id,))
