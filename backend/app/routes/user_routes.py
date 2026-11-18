"""User-info routes: language, role."""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from app import db
from ..database.crud import get_user, get_language_by_id, get_language
from ..identity import current_identity, effective_user_id

user_bp = Blueprint('user', __name__)


@user_bp.route("/user_language/", methods=["GET"])
@cross_origin()
def get_user_language():
    """
    Query params:
        "client": client identifier
        "userid": user ID
    """
    userid = effective_user_id()
    client = request.args.get('client')
    user = get_user(userid, client)
    if user:
        user_lang = get_language_by_id(user.language_id)
        return (user_lang.lang_code if user_lang else 'de'), 200
    return 'de', 200  # Default to German for new / standalone users


@user_bp.route("/user_language/", methods=["PUT"])
@cross_origin()
def set_user_language():
    """
    Persist the user's language selection.
    JSON body: { "userid": "...", "client": "...", "lang": "de"|"en" }
    """
    content = request.json or {}
    userid = effective_user_id()
    client = content.get("client")
    lang_code = content.get("lang")
    if not userid:
        return jsonify({"error": "no identity - call POST /session/identity first"}), 401
    if not client or not lang_code:
        return jsonify({"error": "client and lang required"}), 400
    user = get_user(userid, client)
    if not user:
        return jsonify({"error": "User not found"}), 404
    lang = get_language(lang_code)
    if not lang:
        return jsonify({"error": f"Unknown language: {lang_code}"}), 400
    user.language_id = lang.id
    db.session.commit()
    return jsonify({"status": "ok", "lang": lang_code}), 200


@user_bp.route("/translations/<lang>", methods=["GET"])
@cross_origin()
def get_translations(lang):
    """Return the translation strings for the given language (used by Discord bot)."""
    import json
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "translations.json")
    with open(os.path.abspath(path), "r", encoding="utf-8") as f:
        data = json.load(f)
    translations = data.get("translations", {})
    if lang not in translations:
        return jsonify({"error": f"Unknown language: {lang}"}), 400
    return jsonify(translations[lang]), 200


@user_bp.route("/user_role/", methods=["GET"])
@cross_origin()
def get_user_role():
    """
    Return the role ('student' or 'teacher') for the requesting user.
    Role from the server-issued identity (verified LTI launch) → default 'student'.
    """
    identity = current_identity() or {}
    role = identity.get("role", "student")
    return role, 200
