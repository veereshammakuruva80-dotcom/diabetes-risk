"""
AI-Based Diabetes Risk Prediction System
Member 3: Prediction Routes & REST API Endpoints
"""

from flask import Blueprint, render_template, request, jsonify, flash, session, redirect, url_for
from utils.decorators import login_required
from services.health_data_service import get_user_latest_health_record
from services.prediction_service import predict_diabetes_risk, load_model_artifact
from services.dashboard_service import save_prediction_record

prediction_bp = Blueprint("prediction", __name__)


@prediction_bp.route("/predict", methods=["GET", "POST"])
@login_required
def predict_view():
    """
    Render diabetes prediction interface and process risk calculation requests.
    Pre-populates inputs from the patient's latest recorded health data if available.
    """
    user_id = session.get("user_id")
    latest_record = get_user_latest_health_record(user_id)

    # Default inputs from latest recorded health data, or defaults
    initial_inputs = {
        "pregnancies": str(latest_record.get("pregnancies", "0")) if latest_record else "0",
        "glucose": str(latest_record.get("glucose", "")) if latest_record else "",
        "blood_pressure": str(latest_record.get("blood_pressure", "")) if latest_record else "",
        "skin_thickness": str(latest_record.get("skin_thickness", "0")) if latest_record else "0",
        "insulin": str(latest_record.get("insulin", "0")) if latest_record else "0",
        "bmi": str(latest_record.get("bmi", "")) if latest_record else "",
        "diabetes_pedigree_function": str(latest_record.get("diabetes_pedigree_function", "")) if latest_record else "",
        "age": str(latest_record.get("age", "")) if latest_record else ""
    }

    result = None

    if request.method == "POST":
        input_data = {
            "pregnancies": request.form.get("pregnancies", "").strip(),
            "glucose": request.form.get("glucose", "").strip(),
            "blood_pressure": request.form.get("blood_pressure", "").strip(),
            "skin_thickness": request.form.get("skin_thickness", "").strip(),
            "insulin": request.form.get("insulin", "").strip(),
            "bmi": request.form.get("bmi", "").strip(),
            "diabetes_pedigree_function": request.form.get("diabetes_pedigree_function", "").strip(),
            "age": request.form.get("age", "").strip()
        }
        initial_inputs.update(input_data)

        prediction_result = predict_diabetes_risk(input_data)

        if prediction_result["success"]:
            result = prediction_result
            # Persist prediction result for Member 4 Dashboard and History
            save_prediction_record(
                user_id=user_id,
                prediction_result=prediction_result,
                health_data_id=latest_record.get("id") if latest_record else None,
                measurements=prediction_result["prediction"]["input_biomarkers"]
            )
            flash("AI Diabetes Risk Assessment generated successfully.", "success")
        else:
            flash(prediction_result.get("error", "Unable to generate prediction."), "danger")

    # If GET request and patient has existing health data, pre-run prediction
    elif latest_record and not result:
        pre_pred = predict_diabetes_risk(latest_record)
        if pre_pred["success"]:
            result = pre_pred

    return render_template(
        "predict.html",
        inputs=initial_inputs,
        result=result,
        has_health_record=bool(latest_record)
    )


# ====================================================================
# REST API Endpoints for ML Prediction Integration
# ====================================================================

@prediction_bp.route("/api/predict", methods=["POST"])
@login_required
def api_predict():
    """
    REST API: Calculate diabetes risk for provided biomarker payload.
    """
    data = request.get_json() or {}
    result = predict_diabetes_risk(data)
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@prediction_bp.route("/api/predict/latest", methods=["GET"])
@login_required
def api_predict_latest():
    """
    REST API: Execute risk prediction directly on the authenticated user's latest recorded health data.
    """
    user_id = session.get("user_id")
    latest = get_user_latest_health_record(user_id)
    if not latest:
        return jsonify({
            "success": False,
            "error": "No health records found for the authenticated user. Please submit health data first."
        }), 404

    result = predict_diabetes_risk(dict(latest))
    status_code = 200 if result["success"] else 400
    return jsonify(result), status_code


@prediction_bp.route("/api/model/info", methods=["GET"])
def api_model_info():
    """
    REST API: Retrieve metadata and metrics for the active Random Forest model.
    """
    try:
        artifact = load_model_artifact()
        return jsonify({
            "success": True,
            "model_type": "Random Forest Classifier",
            "features": artifact.get("features", []),
            "metrics": artifact.get("metrics", {}),
            "feature_importances": artifact.get("feature_importances", {}),
            "target_mapping": artifact.get("target_mapping", {})
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
