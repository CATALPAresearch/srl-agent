"""Admin login and access decorators.

The admin password is only ever checked server-side; the admin state lives in the
signed Flask session cookie (SECRET_KEY). If ADMIN_PASSWORD is not set, admin login
is disabled. Teachers are identified by the server-issued identity (verified LTI launch).
"""
import hmac
import os
from functools import wraps

from flask import Blueprint, jsonify, make_response, request, session

from ..actions import LogAction
from ..audit import audit
from ..identity import current_identity, is_admin

admin_bp = Blueprint('admin', __name__)


def is_teacher() -> bool:
    identity = current_identity()
    return bool(identity and identity.get("role") == "teacher" and identity.get("context_id"))


def _status(result):
    return make_response(result).status_code


def admin_required(view):
    """Reject the request with 401 unless the session is logged in as admin. Audited."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin():
            audit(LogAction.AUDIT_ACCESS_DENIED, http_status=401, required="admin")
            return jsonify({"error": "admin login required"}), 401
        result = view(*args, **kwargs)
        audit(LogAction.AUDIT_ADMIN_REQUEST, http_status=_status(result), args=dict(request.args), **kwargs)
        return result
    return wrapper


def staff_required(view):
    """Admins, or teachers from a verified LTI launch (scoped to their course by the view). Audited."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not (is_admin() or is_teacher()):
            audit(LogAction.AUDIT_ACCESS_DENIED, http_status=401, required="admin or teacher")
            return jsonify({"error": "admin or teacher login required"}), 401
        result = view(*args, **kwargs)
        identity = current_identity() or {}
        course = request.args.get("course_id") if is_admin() else identity.get("context_id")
        audit(LogAction.AUDIT_DASHBOARD_REQUEST, http_status=_status(result), course=course, args=dict(request.args))
        return result
    return wrapper


@admin_bp.route("/admin/login", methods=["POST"])
def admin_login():
    expected = os.environ.get("ADMIN_PASSWORD", "")
    given = (request.get_json(silent=True) or {}).get("password", "")
    if expected and isinstance(given, str) and hmac.compare_digest(given.encode(), expected.encode()):
        session["is_admin"] = True
        audit(LogAction.AUDIT_ADMIN_LOGIN, http_status=200)
        return jsonify({"is_admin": True}), 200
    session.pop("is_admin", None)
    audit(LogAction.AUDIT_ADMIN_LOGIN_FAILED, http_status=401, configured=bool(expected))
    return jsonify({"is_admin": False}), 401


@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    if is_admin():
        audit(LogAction.AUDIT_ADMIN_LOGOUT, http_status=200)
    session.pop("is_admin", None)
    return jsonify({"is_admin": False}), 200


@admin_bp.route("/admin/status", methods=["GET"])
def admin_status():
    return jsonify({"is_admin": is_admin()}), 200
