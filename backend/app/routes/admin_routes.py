"""Admin login and access decorators.

The admin password is only ever checked server-side. A successful login creates a
server-side admin session (identity.start_admin_session); the signed session cookie only
carries its id, so logout revokes it for every copy of the cookie. Failed logins are
throttled per IP and globally. If ADMIN_PASSWORD is not set, admin login is disabled.
Teachers are identified by the server-issued identity (verified LTI launch).
"""
import hmac
import os
import time
from functools import wraps

import sqlalchemy as sa
from flask import Blueprint, jsonify, make_response, request

from app import db
from ..actions import LogAction
from ..audit import audit, client_ip
from ..identity import current_identity, end_admin_session, is_admin, start_admin_session
from ..logging_utlis import _hash_ip
from ..models import ActivityLog

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


# Brute-force protection for /admin/login, counted from the audit log (shared by all workers).
# The global limit also covers attackers spreading their guesses over many IP addresses;
# while it is reached, the admin has to wait too (at most LOGIN_WINDOW_SECONDS).
LOGIN_WINDOW_SECONDS = 15 * 60
MAX_FAILED_LOGINS_PER_IP = 5
MAX_FAILED_LOGINS_TOTAL = 50


def _login_throttled() -> bool:
    failed = sa.select(sa.func.count()).select_from(ActivityLog).where(
        ActivityLog.action == LogAction.AUDIT_ADMIN_LOGIN_FAILED.value,
        ActivityLog.timestamp >= int(time.time()) - LOGIN_WINDOW_SECONDS,
    )
    if db.session.scalar(failed) >= MAX_FAILED_LOGINS_TOTAL:
        return True
    ip = client_ip()
    return bool(ip) and db.session.scalar(failed.where(ActivityLog.ip_address == _hash_ip(ip))) \
        >= MAX_FAILED_LOGINS_PER_IP


@admin_bp.route("/admin/login", methods=["POST"])
def admin_login():
    if _login_throttled():  # checked before the password, so guesses stay unanswered
        audit(LogAction.AUDIT_ADMIN_LOGIN_THROTTLED, http_status=429)
        resp = jsonify({"is_admin": False, "error": "too_many_attempts", "retry_after": LOGIN_WINDOW_SECONDS})
        resp.headers["Retry-After"] = str(LOGIN_WINDOW_SECONDS)
        return resp, 429
    expected = os.environ.get("ADMIN_PASSWORD", "")
    given = (request.get_json(silent=True) or {}).get("password", "")
    if expected and isinstance(given, str) and hmac.compare_digest(given.encode(), expected.encode()):
        end_admin_session()  # no session fixation: always a fresh session id
        start_admin_session()
        audit(LogAction.AUDIT_ADMIN_LOGIN, http_status=200)
        return jsonify({"is_admin": True}), 200
    end_admin_session()
    audit(LogAction.AUDIT_ADMIN_LOGIN_FAILED, http_status=401, configured=bool(expected))
    return jsonify({"is_admin": False}), 401


@admin_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    if is_admin():
        audit(LogAction.AUDIT_ADMIN_LOGOUT, http_status=200)
    end_admin_session()
    return jsonify({"is_admin": False}), 200


@admin_bp.route("/admin/status", methods=["GET"])
def admin_status():
    return jsonify({"is_admin": is_admin()}), 200
