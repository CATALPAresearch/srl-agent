"""Admin login: the password is only ever checked server-side.

The admin state lives in the signed Flask session cookie (SECRET_KEY), never in the
client. If ADMIN_PASSWORD is not set, admin login is disabled.
"""
import hmac
import os
from functools import wraps

from flask import Blueprint, jsonify, request, session

admin_bp = Blueprint('admin', __name__)


def is_admin() -> bool:
    return session.get("is_admin") is True


def admin_required(view):
    """Reject the request with 401 unless the session is logged in as admin."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({"error": "admin login required"}), 401
        return view(*args, **kwargs)
    return wrapper


@admin_bp.route("/admin/login", methods=["POST"])
def admin_login():
    expected = os.environ.get("ADMIN_PASSWORD", "")
    given = (request.get_json(silent=True) or {}).get("password", "")
    if expected and isinstance(given, str) and hmac.compare_digest(given.encode(), expected.encode()):
        session["is_admin"] = True
        return jsonify({"is_admin": True}), 200
    session.pop("is_admin", None)
    return jsonify({"is_admin": False}), 401


@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return jsonify({"is_admin": False}), 200


@admin_bp.route("/admin/status", methods=["GET"])
def admin_status():
    return jsonify({"is_admin": is_admin()}), 200
