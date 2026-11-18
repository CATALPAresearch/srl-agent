"""Security audit log.

Writes privileged and security-relevant events to activity_log (action "audit_*") and to
the application log (picked up by Loki). Query: SELECT * FROM activity_log
WHERE action LIKE 'audit_%' ORDER BY timestamp DESC;
"""
import time
import uuid

from flask import has_request_context, request

from app import app, db
from .actions import LogAction
from .identity import current_identity, is_admin
from .logging_utlis import _hash_ip
from .models import ActivityLog


def client_ip():
    # The API is only reachable through nginx, which sets X-Real-IP to the real client address.
    return request.headers.get("X-Real-IP") or request.remote_addr


def audit(action: LogAction, http_status=None, **details):
    """Record a security event. Never raises: auditing must not break the request."""
    try:
        identity = current_identity() if has_request_context() else None
        admin = is_admin() if has_request_context() else False
        actor = "admin" if admin else (identity["uid"] if identity else None)
        value = {"admin": admin, "role": identity.get("role") if identity else None, **details}
        if has_request_context():
            value.update(method=request.method, path=request.path)
            ip = client_ip()
            user_agent = request.headers.get("User-Agent")
        else:
            ip, user_agent = None, None

        db.session.add(ActivityLog(
            id=str(uuid.uuid4()),
            timestamp=int(time.time()),
            user_id=actor,
            user_client="audit",
            action=action.value,
            value=value,
            user_agent=user_agent,
            ip_address=_hash_ip(ip) if ip else None,
            http_status=http_status,
        ))
        db.session.commit()
        app.logger.info("AUDIT %s actor=%s status=%s %s", action.value, actor, http_status, value)
    except Exception as e:
        db.session.rollback()
        app.logger.error("AUDIT logging failed for %s: %s", action, e)
