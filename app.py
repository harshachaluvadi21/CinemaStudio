"""
app.py — Flask application entry point for Coffee-with-Cinema.

Configures the app, registers blueprints, sets up CSRF protection, and
defines the main routes: dashboard, content generation, and file download.
"""

import os
import logging
from datetime import timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    send_file,
    flash,
)
from flask_wtf.csrf import CSRFProtect

from generator import generate_content
from export import to_txt, to_pdf, to_docx

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App Factory ──────────────────────────────────────────────────────────────

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)

    # Core config
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
        WTF_CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    )

    if test_config:
        app.config.update(test_config)

    # CSRF protection
    csrf = CSRFProtect(app)
    
    # Initialize Flask-Session
    from flask_session import Session
    app.config["SESSION_TYPE"] = "filesystem"
    Session(app)

    # Initialize CORS
    from flask_cors import CORS
    CORS(app)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def login_required(f):
        """Decorator that redirects unauthenticated users to the landing page."""
        from functools import wraps

        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("username"):
                return redirect(url_for("index"))
            return f(*args, **kwargs)

        return decorated

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        if session.get("username"):
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/set_name", methods=["POST"])
    def set_name():
        """Handle name submission from the landing page modal."""
        data = request.get_json(silent=True)
        if not data or "username" not in data:
            return jsonify({"error": "Name is required."}), 400
        
        username = data["username"].strip()
        if not username:
             return jsonify({"error": "Name cannot be empty."}), 400
             
        session.clear()
        session["username"] = username
        session.permanent = True
        return jsonify({"success": True})

    @app.route("/logout")
    def logout():
        """Log the user out and clear the session."""
        session.clear()
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", username=session.get("username"))

    @app.route("/generate_content", methods=["POST"])
    @login_required
    def generate():
        """
        Accept a JSON body {"storyline": "..."} and return AI-generated content.

        Returns:
            JSON: {"screenplay": ..., "characters": ..., "sound": ...}
                  or {"error": "..."} with HTTP 400/500.
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid request body."}), 400

        storyline = data.get("storyline", "").strip()
        if not storyline:
            return jsonify({"error": "Please provide a story concept."}), 400
        if len(storyline) > 2000:
            return jsonify({"error": "Story concept must be under 2000 characters."}), 400

        # Store in session for download use
        try:
            result = generate_content(storyline)
        except RuntimeError as exc:
            logger.error("Content generation failed: %s", exc)
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:
            logger.exception("Unexpected error during generation.")
            return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

        # Cache generated content in session for download endpoints
        session["generated"] = result
        return jsonify(result)

    @app.route("/download/<section>/<fmt>")
    @login_required
    def download(section, fmt):
        """
        Stream a file download for the given section and format.

        URL params:
            section: 'screenplay' | 'characters' | 'sound'
            fmt:     'txt' | 'pdf' | 'docx'
        """
        valid_sections = {"screenplay", "characters", "sound"}
        valid_formats = {"txt", "pdf", "docx"}

        if section not in valid_sections or fmt not in valid_formats:
            return jsonify({"error": "Invalid section or format."}), 400

        generated = session.get("generated")
        if not generated or section not in generated:
            return jsonify({"error": "No generated content found. Please generate content first."}), 404

        content = generated[section]

        mime_map = {
            "txt": "text/plain",
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        import re
        from datetime import datetime

        # Create a safe filename: (Username)_(Section)_YYYYMMDD.(ext)
        username = session.get("username", "User")
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', username)
        timestamp = datetime.now().strftime("%Y%m%d")
        
        base_name = f"{safe_name}_{section.title()}_{timestamp}"
        
        filename_map = {
            "txt": f"{base_name}.txt",
            "pdf": f"{base_name}.pdf",
            "docx": f"{base_name}.docx",
        }

        try:
            if fmt == "txt":
                buf = to_txt(content, section)
            elif fmt == "pdf":
                buf = to_pdf(content, section)
            else:
                buf = to_docx(content, section)
        except Exception as exc:
            logger.exception("Export failed for section=%s fmt=%s", section, fmt)
            return jsonify({"error": "Export failed. Please try again."}), 500

        return send_file(
            buf,
            mimetype=mime_map[fmt],
            as_attachment=True,
            download_name=filename_map[fmt],
        )

    # ── Error Handlers ────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({"error": "Not found."}), 404
        return render_template("login.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        # Check if it's a timeout
        if "Read timed out" in str(e):
            return jsonify({
                "error": "The AI is taking too long to respond. Please try again or check if Ollama is running."
            }), 504
        return jsonify({"error": "Internal server error."}), 500

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "Request too large."}), 413

    return app


# ─── Entry Point ──────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
