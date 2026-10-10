import os
from datetime import timedelta
from flask import Flask, render_template, jsonify, request, session
from db import init_db
from routes.auth_routes import auth_bp

def create_app(test_config=None):
    """Application factory for Flask app."""
    app = Flask(__name__)

    # Session & Security Configuration
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "diabetes-risk-prediction-secure-session-key-dev"
    )
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    if test_config:
        app.config.update(test_config)

    # Initialize database tables
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            app.logger.error(f"Error during database initialization: {e}")

    # Register Blueprints
    app.register_blueprint(auth_bp)

    # Landing / Home Route
    @app.route("/")
    def index():
        return render_template("index.html")

    # API Health Check Endpoint
    @app.route("/api/health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "AI Diabetes Risk Prediction System",
            "member1_auth_profile": "active",
            "authenticated": "user_id" in session
        }), 200

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found", "status": 404}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error", "status": 500}), 500
        return render_template("500.html"), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
