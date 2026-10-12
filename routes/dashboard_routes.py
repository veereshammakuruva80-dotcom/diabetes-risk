"""
AI-Based Diabetes Risk Prediction System
Member 4: Dashboard, Recommendations & Prediction History Blueprint

Routes:
- GET /dashboard : Render dynamic health dashboard with empty state support
- GET /history : Render patient prediction history list
- GET /api/dashboard : REST API returning complete dashboard summary
- GET /api/history : REST API returning prediction records for authenticated user
"""

from flask import Blueprint, render_template, jsonify, session, request
from utils.decorators import login_required
from services.dashboard_service import (
    get_dashboard_summary,
    get_user_predictions,
    get_user_latest_prediction
)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_view():
    """
    Render Member 4 Clinical Health Dashboard.
    Dynamically presents latest risk estimation, biomarker metrics, trend chart data,
    and lifestyle recommendations.
    """
    user_id = session.get("user_id")
    summary = get_dashboard_summary(user_id)
    return render_template("dashboard.html", summary=summary)


@dashboard_bp.route("/history", methods=["GET"])
@login_required
def history_view():
    """
    Render Member 4 Prediction History page.
    Displays chronological risk assessments belonging exclusively to the authenticated user.
    """
    user_id = session.get("user_id")
    history_records = get_user_predictions(user_id)
    return render_template("history.html", records=history_records)


# ====================================================================
# REST API Endpoints
# ====================================================================

@dashboard_bp.route("/api/dashboard", methods=["GET"])
@login_required
def api_dashboard_summary():
    """
    REST API: Retrieve aggregated dashboard metrics, trend data, and recommendations.
    Strictly isolated to authenticated user session.
    """
    user_id = session.get("user_id")
    summary = get_dashboard_summary(user_id)
    # Serialize datetime instances for JSON
    if summary.get("success"):
        if summary.get("latest_prediction") and summary["latest_prediction"].get("created_at"):
            summary["latest_prediction"]["created_at"] = str(summary["latest_prediction"]["created_at"])
        if summary.get("latest_health_data") and summary["latest_health_data"].get("created_at"):
            summary["latest_health_data"]["created_at"] = str(summary["latest_health_data"]["created_at"])
        for r in summary.get("recent_history", []):
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])

    return jsonify(summary), 200


@dashboard_bp.route("/api/history", methods=["GET"])
@login_required
def api_prediction_history():
    """
    REST API: Retrieve all historical prediction records for the authenticated user.
    """
    user_id = session.get("user_id")
    records = get_user_predictions(user_id)
    serialized = []
    for r in records:
        r_dict = dict(r)
        if r_dict.get("created_at"):
            r_dict["created_at"] = str(r_dict["created_at"])
        serialized.append(r_dict)

    return jsonify({
        "success": True,
        "count": len(serialized),
        "records": serialized
    }), 200
