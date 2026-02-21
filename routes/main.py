from flask import Blueprint, render_template, request, jsonify, session, send_file, redirect, url_for
from flask_login import login_required, current_user
import logging
import os
import re
from datetime import datetime
from generator import generate_content
from export import to_txt, to_pdf, to_docx

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")

@main_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=current_user.username)

@main_bp.route("/generate_content", methods=["POST"])
@login_required
def generate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body."}), 400

    storyline = data.get("storyline", "").strip()
    genre = data.get("genre", "Cinematic Default")
    character_names = data.get("characterNames", "").strip()

    if not storyline:
        return jsonify({"error": "Please provide a story concept."}), 400
    if len(storyline) > 2000:
        return jsonify({"error": "Story concept must be under 2000 characters."}), 400

    try:
        result = generate_content(storyline, genre, character_names=character_names)
    except RuntimeError as exc:
        logger.error("Content generation failed: %s", exc)
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        logger.exception("Unexpected error during generation.")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

    session["generated"] = result
    return jsonify(result)

@main_bp.route("/download/<section>/<fmt>")
@login_required
def download(section, fmt):
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
    
    username = current_user.username
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
            buf = to_pdf(content, section, username=username)
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
