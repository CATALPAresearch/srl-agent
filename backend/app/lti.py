"""LTI 1.1 tool provider: verified launch -> server-issued identity -> UI.

Every launch must carry a valid OAuth 1.0 HMAC-SHA1 signature made with the shared
secret configured in Moodle (LTI_CONSUMER_KEY / LTI_SHARED_SECRET). Without both
settings all launches are rejected.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import quote, urlsplit

from flask import Blueprint, Response, request, session
from sqlalchemy.exc import IntegrityError

from app import app, db
from .actions import LogAction
from .audit import audit
from .identity import issue_token
from .models import LtiNonce

_LTI_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'lti')
MAX_CLOCK_SKEW_SECONDS = 300

lti_bp = Blueprint("lti", __name__, url_prefix="/lti")

_INSTRUCTOR_ROLES = {
    "instructor", "teacher", "faculty", "staff", "administrator",
    "urn:lti:role:ims/lis/instructor",
    "urn:lti:role:ims/lis/teachingassistant",
    "urn:lti:instrole:ims/lis/instructor",
    "urn:lti:instrole:ims/lis/administrator",
}


def _normalize_role(raw_roles: str) -> str:
    """Map LTI 1.1 roles string to 'teacher' or 'student'."""
    for part in raw_roles.lower().split(","):
        if part.strip() in _INSTRUCTOR_ROLES:
            return "teacher"
    return "student"


def _enc(value) -> str:
    """RFC 3986 percent-encoding as required by OAuth 1.0."""
    return quote(str(value), safe="")


def _launch_url() -> str:
    """The URL Moodle signed: LTI_LAUNCH_URL, or the public URL seen by the reverse proxy."""
    configured = os.environ.get("LTI_LAUNCH_URL")
    if configured:
        parts = urlsplit(configured)
        return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path}"
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme).split(",")[0].strip().lower()
    host = request.host.lower()
    if (scheme, host.rsplit(":", 1)[-1]) in (("http", "80"), ("https", "443")):
        host = host.rsplit(":", 1)[0]
    return f"{scheme}://{host}{request.path}"


def oauth_signature(method: str, url: str, params: list, consumer_secret: str) -> str:
    """OAuth 1.0 HMAC-SHA1 signature (RFC 5849, section 3.4)."""
    pairs = sorted((_enc(k), _enc(v)) for k, v in params if k != "oauth_signature")
    normalized = "&".join(f"{k}={v}" for k, v in pairs)
    base_string = "&".join([method.upper(), _enc(url), _enc(normalized)])
    key = f"{_enc(consumer_secret)}&"
    digest = hmac.new(key.encode(), base_string.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _verify_launch():
    """Return None if the launch is authentic, otherwise a short reason."""
    consumer_key = os.environ.get("LTI_CONSUMER_KEY")
    consumer_secret = os.environ.get("LTI_SHARED_SECRET")
    if not consumer_key or not consumer_secret:
        return "LTI is not configured (LTI_CONSUMER_KEY / LTI_SHARED_SECRET)"

    form = request.form
    if form.get("oauth_signature_method") != "HMAC-SHA1":
        return "unsupported signature method"
    if form.get("oauth_version", "1.0") != "1.0":
        return "unsupported oauth version"
    if not hmac.compare_digest(form.get("oauth_consumer_key", ""), consumer_key):
        return "unknown consumer key"

    try:
        timestamp = int(form.get("oauth_timestamp", ""))
    except ValueError:
        return "invalid timestamp"
    now = int(time.time())
    if abs(now - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        return "timestamp outside the allowed window"

    params = list(request.form.items(multi=True)) + list(request.args.items(multi=True))
    expected = oauth_signature("POST", _launch_url(), params, consumer_secret)
    if not hmac.compare_digest(form.get("oauth_signature", ""), expected):
        return "invalid signature"

    nonce = form.get("oauth_nonce", "")
    if not nonce:
        return "missing nonce"
    LtiNonce.query.filter(LtiNonce.timestamp < now - 2 * MAX_CLOCK_SKEW_SECONDS).delete()
    db.session.add(LtiNonce(nonce=nonce[:255], consumer_key=consumer_key, timestamp=timestamp))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return "nonce already used (replay)"
    return None


def _render_ui(config: dict) -> Response:
    with open(os.path.join(_LTI_STATIC_DIR, 'index.html'), "r", encoding="utf-8") as f:
        html = f.read()
    # JSON inside <script>: escape "</" so the payload cannot close the tag
    payload = json.dumps(config).replace("</", "<\\/")
    html = html.replace("__SRL_CONFIG__", payload)
    return Response(html, mimetype="text/html")


@lti_bp.route("/launch", methods=["POST"])
def launch():
    reason = _verify_launch()
    if reason:
        app.logger.warning("Rejected LTI launch: %s", reason)
        audit(LogAction.AUDIT_LTI_LAUNCH_REJECTED, http_status=401, reason=reason,
              consumer_key=request.form.get("oauth_consumer_key"))
        return Response("LTI launch rejected: " + reason, status=401, mimetype="text/plain")

    p = request.form
    context_id = p.get("context_id")
    user_id = p.get("user_id")
    if not context_id or not user_id:
        return Response("LTI launch rejected: context_id and user_id required", status=400, mimetype="text/plain")

    identity = {
        "uid": f"{context_id}:{user_id}",
        "role": _normalize_role(p.get("roles", "")),
        "context_id": context_id,
        "context_title": p.get("context_title"),
        "source": "lti",
    }
    session["identity"] = identity
    audit(LogAction.AUDIT_LTI_LAUNCH, http_status=200, uid=identity["uid"], role=identity["role"],
          course=context_id)
    return _render_ui({
        "client": "lti",
        "userId": identity["uid"],
        "role": identity["role"],
        "token": issue_token(identity),
    })
