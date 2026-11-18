"""Server-issued user identity.

The user id is never taken from the request body or query string. It comes from an
identity the server issued itself - after a verified LTI launch, or as an anonymous
standalone identity - and is sent back by the client as a signed bearer token
(Authorization header). The token is signed with SECRET_KEY, so it cannot be forged
or modified. A token is used instead of the session cookie because browsers block
third-party cookies inside the Moodle iframe.

Identity: {"uid", "role" ("student"|"teacher"), "context_id", "context_title", "source"}
"""
import hashlib
import secrets
import time

from flask import request, session
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import app, db
from .models import AdminSession

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 180  # standalone users keep their interview for a semester
ADMIN_SESSION_SECONDS = 60 * 60 * 8  # admin sessions end after a working day, logout ends them at once


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(app.secret_key, salt="srl-identity")


def issue_token(identity: dict) -> str:
    return _serializer().dumps(identity)


def _identity_from_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        data = _serializer().loads(header[len("Bearer "):], max_age=TOKEN_MAX_AGE_SECONDS)
    except BadSignature:
        return None
    return data if isinstance(data, dict) and data.get("uid") else None


def current_identity():
    """The caller's identity (token first, then session cookie) or None."""
    return _identity_from_token() or session.get("identity")


def new_standalone_identity() -> dict:
    return {
        "uid": "user_" + secrets.token_hex(16),
        "role": "student",
        "context_id": "0",
        "context_title": None,
        "source": "standalone",
    }


def _admin_session_key(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def start_admin_session() -> None:
    """Mark the caller's session as admin, backed by a server-side row that logout can delete."""
    now = int(time.time())
    db.session.query(AdminSession).filter(AdminSession.expires_at <= now).delete()  # housekeeping
    session_id = secrets.token_urlsafe(32)
    db.session.add(AdminSession(token_hash=_admin_session_key(session_id), created_at=now,
                                expires_at=now + ADMIN_SESSION_SECONDS))
    db.session.commit()
    session["is_admin"] = True
    session["admin_sid"] = session_id


def end_admin_session() -> None:
    """Revoke the caller's admin session server-side (a copied cookie stops working too)."""
    session_id = session.pop("admin_sid", None)
    session.pop("is_admin", None)
    if isinstance(session_id, str):
        db.session.query(AdminSession).filter(
            AdminSession.token_hash == _admin_session_key(session_id)).delete()
        db.session.commit()


def is_admin() -> bool:
    """True only for a signed session cookie whose admin session still exists server-side."""
    session_id = session.get("admin_sid")
    if session.get("is_admin") is not True or not isinstance(session_id, str):
        return False
    admin_session = db.session.get(AdminSession, _admin_session_key(session_id))
    return admin_session is not None and admin_session.expires_at > int(time.time())


def effective_user_id(requested=None, allow_admin_override=False):
    """The user id a request may act on: always the caller's own id.

    Admins may read another user's data by passing it explicitly (allow_admin_override).
    Returns None if the caller has no identity.
    """
    if allow_admin_override and requested and is_admin():
        from .actions import LogAction  # local import: audit depends on this module
        from .audit import audit
        audit(LogAction.AUDIT_USER_DATA_READ, target_user=requested)
        return requested
    identity = current_identity()
    return identity["uid"] if identity else None
