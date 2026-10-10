from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify

def login_required(f):
    """
    Decorator to protect routes requiring authentication.
    Redirects unauthenticated web requests to /login and returns 401 for API calls.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "Authentication required. Please log in to proceed.",
                    "authenticated": False
                }), 401
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function
