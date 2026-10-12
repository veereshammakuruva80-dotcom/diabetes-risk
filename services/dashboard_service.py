"""
AI-Based Diabetes Risk Prediction System
Member 4: Health Dashboard, Recommendations & Prediction History Service

Features:
1. Dynamic Dashboard aggregation (User profile, latest risk prediction, biomarkers, trend metrics).
2. Transparent, rule-based General Health Recommendation Engine adhering to clinical disclaimers.
3. User-isolated Prediction History with chronological sorting.
4. Persistence of prediction events into the predictions table.
"""

from typing import Dict, Any, List, Optional
from db import query_one, query_all, execute_commit
from services.auth_service import get_user_by_id
from services.health_data_service import get_user_latest_health_record
from services.prediction_service import predict_diabetes_risk


def save_prediction_record(
    user_id: int,
    prediction_result: Dict[str, Any],
    health_data_id: Optional[int] = None,
    measurements: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """
    Persist an executed risk prediction for the authenticated user into the predictions table.
    Enforces user isolation and captures associated biomarkers if available.
    """
    if not user_id or not prediction_result.get("success"):
        return None

    pred_data = prediction_result.get("prediction", {})
    predicted_class = pred_data.get("predicted_class", 0)
    risk_label = pred_data.get("risk_label", "Lower Estimated Risk")
    risk_prob = pred_data.get("risk_probability", 0.0)
    risk_pct = pred_data.get("risk_percentage", 0.0)

    # Extract biomarker measurements
    meas = measurements or pred_data.get("input_biomarkers", {})
    glucose = meas.get("glucose")
    bmi = meas.get("bmi")
    blood_pressure = meas.get("blood_pressure")

    query = """
        INSERT INTO predictions (
            user_id, health_data_id, predicted_class, risk_label,
            risk_probability, risk_percentage, glucose, bmi, blood_pressure
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        user_id,
        health_data_id,
        predicted_class,
        risk_label,
        risk_prob,
        risk_pct,
        glucose,
        bmi,
        blood_pressure
    )

    try:
        record_id = execute_commit(query, params)
        return record_id
    except Exception as e:
        # Logging or silent return to avoid blocking caller
        return None


def get_user_predictions(user_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieve prediction history for the authenticated user only.
    Always sorted newest first (created_at DESC).
    """
    if not user_id:
        return []

    query = """
        SELECT id, user_id, health_data_id, predicted_class, risk_label,
               risk_probability, risk_percentage, glucose, bmi, blood_pressure, created_at
        FROM predictions
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
    """
    if limit and isinstance(limit, int) and limit > 0:
        query += f" LIMIT {limit}"

    return query_all(query, (user_id,))


def get_user_latest_prediction(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the most recent prediction record for the authenticated user.
    """
    if not user_id:
        return None

    query = """
        SELECT id, user_id, health_data_id, predicted_class, risk_label,
               risk_probability, risk_percentage, glucose, bmi, blood_pressure, created_at
        FROM predictions
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """
    return query_one(query, (user_id,))


def generate_health_recommendations(
    latest_prediction: Optional[Dict[str, Any]],
    health_measurements: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Rule-Based General Health Recommendation Engine.
    
    IMPORTANT:
    - Transparent rule-based clinical wellness guidance.
    - Not claimed to be AI-generated or diagnostic.
    - Does not prescribe medicines or alter dosages.
    - Handles missing or unmeasured data safely.
    """
    recommendations = []

    pred_class = None
    risk_pct = 0.0

    if latest_prediction:
        pred_class = latest_prediction.get("predicted_class")
        risk_pct = float(latest_prediction.get("risk_percentage") or 0.0)

    meas = health_measurements or {}
    glucose = meas.get("glucose")
    bmi = meas.get("bmi")
    bp = meas.get("blood_pressure")

    # 1. Primary Risk Stratification Recommendation
    if pred_class == 1 or risk_pct >= 50.0:
        recommendations.append({
            "category": "Risk Management & Medical Consultation",
            "icon": "🩺",
            "priority": "high",
            "title": "Professional Clinical Consultation Recommended",
            "description": (
                "Your statistical risk assessment indicates an elevated probability bracket. "
                "Consider discussing your results with a qualified healthcare professional or endocrinologist "
                "for clinical diagnostic testing (such as fasting plasma glucose or HbA1c)."
            ),
            "action": "Schedule Clinical Evaluation"
        })
    else:
        recommendations.append({
            "category": "Preventive Care",
            "icon": "🛡️",
            "priority": "normal",
            "title": "Maintain Baseline Glycemic Health",
            "description": (
                "Your latest indicators suggest a lower estimated diabetes risk profile. "
                "Continue routine preventative health checkups and monitor key metabolic markers periodically."
            ),
            "action": "Continue Annual Checkups"
        })

    # 2. Nutrition and Dietary Guidelines (Based on Glucose & Risk)
    if glucose is not None and float(glucose) >= 140.0:
        recommendations.append({
            "category": "Nutrition & Dietary Habits",
            "icon": "🥗",
            "priority": "high",
            "title": "Glycemic Load & Dietary Moderation",
            "description": (
                "Recorded glucose levels exceed normal fasting/postprandial thresholds. "
                "Prioritize whole grains, high-fiber vegetables, and lean proteins while minimizing "
                "refined carbohydrates, sugar-sweetened beverages, and ultra-processed snacks."
            ),
            "action": "Reduce Sugary Drinks & Simple Carbs"
        })
    elif glucose is not None and float(glucose) >= 100.0:
        recommendations.append({
            "category": "Nutrition & Dietary Habits",
            "icon": "🥗",
            "priority": "medium",
            "title": "Balanced Whole-Food Nutrition",
            "description": (
                "Blood glucose is within borderline/impaired fasting range. "
                "Adopt Mediterranean or DASH-style dietary patterns rich in legumes, leafy greens, "
                "nuts, and fiber to stabilize postprandial glucose surges."
            ),
            "action": "Opt for Low Glycemic Index Foods"
        })
    else:
        recommendations.append({
            "category": "Nutrition & Dietary Habits",
            "icon": "🥗",
            "priority": "low",
            "title": "Balanced Nutrition Guidance",
            "description": (
                "Maintain a balanced plate emphasizing seasonal vegetables, healthy unsaturated fats, "
                "adequate hydration with water, and controlled portions."
            ),
            "action": "Stay Hydrated with Plain Water"
        })

    # 3. Physical Activity & Exercise (Based on BMI & Risk)
    if bmi is not None and float(bmi) >= 30.0:
        recommendations.append({
            "category": "Physical Activity",
            "icon": "🏃",
            "priority": "high",
            "title": "Structured Low-Impact Aerobic Activity",
            "description": (
                "Clinical evidence highlights the metabolic benefit of 150+ minutes of moderate-intensity "
                "activity per week (e.g. brisk walking, cycling, or swimming). Even 10-minute post-meal walks "
                "significantly improve insulin sensitivity."
            ),
            "action": "Aim for 30 Min Moderate Activity 5x/Week"
        })
    elif bmi is not None and float(bmi) >= 25.0:
        recommendations.append({
            "category": "Physical Activity",
            "icon": "🏃",
            "priority": "medium",
            "title": "Consistent Daily Movement",
            "description": (
                "Regular aerobic exercise combined with mild resistance training assists in muscle glucose uptake "
                "and aids long-term healthy weight management."
            ),
            "action": "Break Up Prolonged Sitting"
        })
    else:
        recommendations.append({
            "category": "Physical Activity",
            "icon": "🏃",
            "priority": "low",
            "title": "Active Lifestyle Maintenance",
            "description": (
                "Engage in cardiovascular conditioning and flexibility exercises to promote ongoing metabolic and cardiovascular resilience."
            ),
            "action": "Maintain 7,000–10,000 Daily Steps"
        })

    # 4. Cardiovascular & Blood Pressure Monitoring
    if bp is not None and float(bp) >= 90.0:
        recommendations.append({
            "category": "Cardiovascular Health",
            "icon": "❤️",
            "priority": "high",
            "title": "Blood Pressure & Sodium Management",
            "description": (
                "Diastolic blood pressure reading indicates elevated cardiovascular resistance. "
                "Limit sodium intake, manage daily stress with relaxation techniques, and have blood pressure re-evaluated by a healthcare provider."
            ),
            "action": "Monitor Blood Pressure Weekly"
        })
    elif bp is not None and float(bp) >= 80.0:
        recommendations.append({
            "category": "Cardiovascular Health",
            "icon": "❤️",
            "priority": "medium",
            "title": "Heart-Healthy Habits",
            "description": (
                "Diastolic pressure is in the pre-hypertension bracket. Ensure adequate dietary potassium, magnesium, and restorative sleep."
            ),
            "action": "Practice Stress Reduction"
        })

    # 5. Weight Management Guidance (If BMI recorded)
    if bmi is not None and float(bmi) >= 25.0:
        recommendations.append({
            "category": "Weight Management",
            "icon": "⚖️",
            "priority": "medium",
            "title": "Sustainable Weight Loss Strategy",
            "description": (
                "A modest reduction of 5% to 7% of total body weight has been shown to reduce diabetes incidence "
                "by over 50% in prediabetic individuals (Diabetes Prevention Program clinical trials)."
            ),
            "action": "Target 5% Gradual Weight Reduction"
        })

    return recommendations


def get_dashboard_summary(user_id: int) -> Dict[str, Any]:
    """
    Construct the aggregated dashboard data object for the authenticated user.
    """
    user = get_user_by_id(user_id)
    if not user:
        return {"success": False, "error": "User not found"}

    # 1. Fetch latest recorded health data (Member 2)
    latest_health = get_user_latest_health_record(user_id)

    # 2. Fetch latest prediction (Member 4 / Member 3)
    latest_pred = get_user_latest_prediction(user_id)

    # Auto-generate prediction if health data exists but no prediction is stored yet
    if latest_health and not latest_pred:
        ml_res = predict_diabetes_risk(dict(latest_health))
        if ml_res.get("success"):
            pred_id = save_prediction_record(
                user_id=user_id,
                prediction_result=ml_res,
                health_data_id=latest_health.get("id"),
                measurements=dict(latest_health)
            )
            latest_pred = get_user_latest_prediction(user_id)

    # 3. Retrieve prediction history (up to last 10 records for trends)
    history_records = get_user_predictions(user_id, limit=10)

    # 4. Generate transparent rule-based health recommendations
    recommendations = generate_health_recommendations(latest_pred, latest_health)

    # 5. Prepare trend visualization data (chronological order for graph)
    trend_data = []
    for r in reversed(history_records):
        created_str = str(r["created_at"])[:10] if r.get("created_at") else "Recent"
        trend_data.append({
            "date": created_str,
            "risk_percentage": round(float(r.get("risk_percentage") or 0.0), 1),
            "glucose": r.get("glucose"),
            "bmi": r.get("bmi"),
            "risk_label": r.get("risk_label")
        })

    return {
        "success": True,
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "age": user.get("age"),
            "gender": user.get("gender")
        },
        "has_records": bool(latest_pred or latest_health),
        "latest_prediction": latest_pred,
        "latest_health_data": latest_health,
        "recent_history": history_records[:5],
        "total_predictions": len(history_records),
        "trend_data": trend_data,
        "recommendations": recommendations,
        "clinical_disclaimer": (
            "General health guidance provided for lifestyle and informational purposes only. "
            "These suggestions do NOT constitute a medical diagnosis, prescription, or clinical treatment plan. "
            "Always consult a qualified healthcare professional before altering medication or dietary regimens."
        )
    }
