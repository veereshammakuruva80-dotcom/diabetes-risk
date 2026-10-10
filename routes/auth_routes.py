from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.decorators import login_required
from services.auth_service import (
    register_user,
    authenticate_user,
    get_user_by_id,
    update_user_profile
)
from urllib.parse import urlparse

auth_bp = Blueprint("auth", __name__)


def is_safe_redirect_url(target: str) -> bool:
    """Ensure redirect URL is local to avoid open-redirect vulnerabilities."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc or not test_url.netloc


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle new user registration."""
    if "user_id" in session:
        return redirect(url_for("auth.profile"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        age = request.form.get("age", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        phone = request.form.get("phone", "").strip() or None

        result = register_user(
            full_name=full_name,
            email=email,
            password=password,
            confirm_password=confirm_password,
            age=age,
            gender=gender,
            phone=phone
        )

        if result["success"]:
            flash(result["message"], "success")
            return redirect(url_for("auth.login"))
        else:
            flash(result["error"], "danger")
            return render_template(
                "register.html",
                full_name=full_name,
                email=email,
                age=age or "",
                gender=gender or "",
                phone=phone or ""
            ), 400

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user authentication and session establishment."""
    if "user_id" in session:
        return redirect(url_for("auth.profile"))

    next_page = request.args.get("next") or request.form.get("next")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        result = authenticate_user(email, password)

        if result["success"]:
            user = result["user"]
            session.clear()  # Prevent session fixation
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["user_email"] = user["email"]
            session.permanent = True

            flash(f"Welcome back, {user['full_name']}!", "success")

            if next_page and is_safe_redirect_url(next_page):
                return redirect(next_page)
            return redirect(url_for("auth.profile"))
        else:
            flash(result["error"], "danger")
            return render_template("login.html", email=email, next=next_page), 401

    return render_template("login.html", next=next_page)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Invalidate authenticated session."""
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Display and manage the authenticated user's profile."""
    user_id = session.get("user_id")
    user = get_user_by_id(user_id)

    if not user:
        session.clear()
        flash("User session expired. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        age = request.form.get("age", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        phone = request.form.get("phone", "").strip() or None

        update_result = update_user_profile(
            user_id=user_id,
            full_name=full_name,
            age=age,
            gender=gender,
            phone=phone
        )

        if update_result["success"]:
            session["user_name"] = full_name
            flash(update_result["message"], "success")
            # Refresh user details
            user = get_user_by_id(user_id)
        else:
            flash(update_result["error"], "danger")

    return render_template("profile.html", user=user)


# ==========================================
# REST API Endpoints for Integration & SPAs
# ==========================================

@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    """REST API: Register user."""
    data = request.get_json() or {}
    result = register_user(
        full_name=data.get("full_name", ""),
        email=data.get("email", ""),
        password=data.get("password", ""),
        confirm_password=data.get("confirm_password", ""),
        age=data.get("age"),
        gender=data.get("gender"),
        phone=data.get("phone")
    )
    status_code = 201 if result["success"] else 400
    return jsonify(result), status_code


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    """REST API: Login user and set session."""
    data = request.get_json() or {}
    result = authenticate_user(
        email=data.get("email", ""),
        password=data.get("password", "")
    )
    if result["success"]:
        user = result["user"]
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        session["user_email"] = user["email"]
        return jsonify({"success": True, "message": "Login successful", "user": user}), 200
    return jsonify(result), 401


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    """REST API: Logout."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"}), 200


@auth_bp.route("/api/profile", methods=["GET", "PUT"])
@login_required
def api_profile():
    """REST API: Get or update user profile."""
    user_id = session.get("user_id")

    if request.method == "GET":
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404
        safe_user = {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "age": user.get("age"),
            "gender": user.get("gender"),
            "phone": user.get("phone"),
            "created_at": str(user.get("created_at")) if user.get("created_at") else None
        }
        return jsonify({"success": True, "user": safe_user}), 200

    if request.method == "PUT":
        data = request.get_json() or {}
        result = update_user_profile(
            user_id=user_id,
            full_name=data.get("full_name", ""),
            age=data.get("age"),
            gender=data.get("gender"),
            phone=data.get("phone")
        )
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code
