"""
AI-Based Diabetes Risk Prediction System
Member 2: Health Data Input Module — Flask Blueprint & API Endpoints
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.decorators import login_required
from services.auth_service import get_user_by_id
from services.health_data_service import (
    validate_health_data,
    save_health_data,
    get_user_health_records,
    get_user_latest_health_record,
    VALIDATION_LIMITS
)

health_data_bp = Blueprint("health_data", __name__)


@health_data_bp.route("/health-data", methods=["GET", "POST"])
@login_required
def health_data_input():
    """
    Render and process the clinical health data collection form.
    Requires user authentication to associate clinical records.
    """
    user_id = session.get("user_id")
    user = get_user_by_id(user_id)

    # Initial form defaults from user profile
    form_data = {
        "pregnancies": "0",
        "glucose": "",
        "blood_pressure": "",
        "skin_thickness": "",
        "insulin": "",
        "bmi": "",
        "diabetes_pedigree_function": "",
        "age": str(user.get("age") or "") if user else ""
    }
    errors = {}

    if request.method == "POST":
        # Extract inputs from form submission
        raw_input = {
            "pregnancies": request.form.get("pregnancies", "").strip(),
            "glucose": request.form.get("glucose", "").strip(),
            "blood_pressure": request.form.get("blood_pressure", "").strip(),
            "skin_thickness": request.form.get("skin_thickness", "").strip(),
            "insulin": request.form.get("insulin", "").strip(),
            "bmi": request.form.get("bmi", "").strip(),
            "diabetes_pedigree_function": request.form.get("diabetes_pedigree_function", "").strip(),
            "age": request.form.get("age", "").strip()
        }
        form_data.update(raw_input)

        save_result = save_health_data(user_id, raw_input)

        if save_result["success"]:
            flash("Clinical health data successfully validated and recorded.", "success")
            return redirect(url_for("health_data.health_data_input"))
        else:
            errors = save_result.get("errors", {})
            flash(save_result.get("error", "Failed to submit health data. Please check inputs."), "danger")

    recent_records = get_user_health_records(user_id)

    return render_template(
        "health_data.html",
        form_data=form_data,
        errors=errors,
        limits=VALIDATION_LIMITS,
        user=user,
        records=recent_records
    )


# ====================================================================
# REST API Endpoints for Integration & ML Prediction Handoff
# ====================================================================

@health_data_bp.route("/api/health-data", methods=["POST"])
@login_required
def api_submit_health_data():
    """
    REST API: Validate and store health data for the authenticated user.
    """
    user_id = session.get("user_id")
    data = request.get_json() or {}

    result = save_health_data(user_id, data)
    status_code = 201 if result["success"] else 400
    return jsonify(result), status_code


@health_data_bp.route("/api/health-data", methods=["GET"])
@login_required
def api_get_health_records():
    """
    REST API: Retrieve all health records for authenticated user.
    Enforces strict user isolation.
    """
    user_id = session.get("user_id")
    records = get_user_health_records(user_id)
    # Format created_at to ISO string for JSON serialization
    serialized = []
    for r in records:
        r_dict = dict(r)
        if "created_at" in r_dict and r_dict["created_at"]:
            r_dict["created_at"] = str(r_dict["created_at"])
        serialized.append(r_dict)
    return jsonify({"success": True, "records": serialized}), 200


@health_data_bp.route("/api/health-data/latest", methods=["GET"])
@login_required
def api_get_latest_health_record():
    """
    REST API: Retrieve the most recent health parameters for the authenticated user.
    Provides the standardized feature interface for the ML prediction module (Member 3).
    """
    user_id = session.get("user_id")
    latest = get_user_latest_health_record(user_id)
    if not latest:
        return jsonify({
            "success": False,
            "error": "No health records found for the authenticated user."
        }), 404

    features = {
        "pregnancies": latest["pregnancies"],
        "glucose": latest["glucose"],
        "blood_pressure": latest["blood_pressure"],
        "skin_thickness": latest["skin_thickness"],
        "insulin": latest["insulin"],
        "bmi": latest["bmi"],
        "diabetes_pedigree_function": latest["diabetes_pedigree_function"],
        "age": latest["age"]
    }
    return jsonify({
        "success": True,
        "record_id": latest["id"],
        "features": features,
        "created_at": str(latest["created_at"]) if latest.get("created_at") else None
    }), 200
