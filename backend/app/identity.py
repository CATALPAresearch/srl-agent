"""Server-issued user identity.

The user id is never taken from the request body or query string. It comes from an
identity the server issued itself - after a verified LTI launch, or as an anonymous
standalone identity - and is sent back by the client as a signed bearer token
(Authorization header). The token is signed with SECRET_KEY, so it cannot be forged
or modified. A token is used instead of the session cookie because browsers block
third-party cookies inside the Moodle iframe.

Identity: {"uid", "role" ("student"|"teacher"), "context_id", "context_title", "source"}
"""
import secrets

from flask import request, session
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app import app

TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 180  # standalone users keep their interview for a semester


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


def is_admin() -> bool:
    return session.get("is_admin") is True


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
