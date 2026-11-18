"""
Security regression tests for the three access-control fixes:

1. LTI launches must carry a valid OAuth 1.0 signature (LTI 1.1).
2. Teachers only see their own course; course-wide data only for admins.
3. User data endpoints act on the server-issued identity, never on a userid
   sent by the client (no reading or writing other users' interviews).

Needs the test DB like test_routes.py.
"""

import os
import re
import time
import uuid

import pytest

os.environ["DISABLE_LLM"] = "true"

from app.lti import oauth_signature  # noqa: E402

CONSUMER_KEY = "pytest_key"
SHARED_SECRET = "pytest secret/&"
ADMIN_PASSWORD = "pytest-admin-secret"

# rolled back after each test: failed admin logins must not pile up (login throttling)
pytestmark = pytest.mark.usefixtures("isolated_db")


def _uid(prefix="sec"):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def fresh_client(flask_app, monkeypatch):
    monkeypatch.setenv("LTI_CONSUMER_KEY", CONSUMER_KEY)
    monkeypatch.setenv("LTI_SHARED_SECRET", SHARED_SECRET)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.delenv("LTI_LAUNCH_URL", raising=False)
    return flask_app.test_client()


# ===========================================================================
# 1. LTI launch signature
# ===========================================================================

def _launch_params(roles="Instructor", context_id=None, user_id=None, timestamp=None, nonce=None):
    return {
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "resource_link_id": "1",
        "context_id": context_id or _uid("course"),
        "context_title": "Kurs: Lernen & Lehren",
        "user_id": user_id or _uid("moodle"),
        "roles": roles,
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_nonce": nonce or uuid.uuid4().hex,
        "oauth_version": "1.0",
    }


def _sign(params, url="http://localhost/lti/launch", secret=SHARED_SECRET):
    signed = dict(params)
    signed["oauth_signature"] = oauth_signature("POST", url, list(params.items()), secret)
    return signed


def _token_from_page(html):
    match = re.search(r'"token": "([^"]+)"', html)
    assert match, "no token in LTI page"
    return match.group(1)


class TestOAuthSignature:
    def test_matches_oauthlib_reference(self):
        """Reference value computed with oauthlib (RFC 5849) for the same input."""
        params = [
            ("oauth_consumer_key", "moodle_key"), ("oauth_nonce", "fixed-nonce-123"),
            ("oauth_signature_method", "HMAC-SHA1"), ("oauth_timestamp", "1700000000"),
            ("oauth_version", "1.0"), ("lti_message_type", "basic-lti-launch-request"),
            ("lti_version", "LTI-1p0"), ("resource_link_id", "42"), ("user_id", "7"),
            ("context_id", "course 5"), ("context_title", "Lernen & Lehren: Ä/ö?"),
            ("roles", "Instructor,urn:lti:role:ims/lis/Learner"), ("v", "2"),
            ("oauth_signature", "is-excluded"),
        ]
        assert oauth_signature(
            "POST", "https://srl-agent.example.org/lti/launch", params, "s3cr3t/with spaces&"
        ) == "DeF0MU/pfT+hm/m+/kZFrBTktKI="


class TestLtiLaunch:
    def test_valid_launch_returns_ui_with_identity_token(self, fresh_client):
        params = _launch_params(roles="Instructor")
        resp = fresh_client.post("/lti/launch", data=_sign(params))
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "__SRL_CONFIG__" not in html
        token = _token_from_page(html)
        ident = fresh_client.get("/session/identity", headers={"Authorization": f"Bearer {token}"}).get_json()
        assert ident == {"userid": f"{params['context_id']}:{params['user_id']}", "role": "teacher"}

    def test_unsigned_launch_is_rejected(self, fresh_client):
        """The attack from the report: a plain form POST claiming to be a teacher."""
        resp = fresh_client.post("/lti/launch", data={"roles": "Instructor", "user_id": "x", "context_id": "y"})
        assert resp.status_code == 401

    def test_wrong_secret_is_rejected(self, fresh_client):
        resp = fresh_client.post("/lti/launch", data=_sign(_launch_params(), secret="other-moodle"))
        assert resp.status_code == 401

    def test_tampered_role_is_rejected(self, fresh_client):
        signed = _sign(_launch_params(roles="Learner"))
        signed["roles"] = "Instructor"
        assert fresh_client.post("/lti/launch", data=signed).status_code == 401

    def test_unknown_consumer_key_is_rejected(self, fresh_client):
        params = _launch_params()
        params["oauth_consumer_key"] = "someone_else"
        assert fresh_client.post("/lti/launch", data=_sign(params)).status_code == 401

    def test_expired_timestamp_is_rejected(self, fresh_client):
        params = _launch_params(timestamp=int(time.time()) - 3600)
        assert fresh_client.post("/lti/launch", data=_sign(params)).status_code == 401

    def test_replayed_nonce_is_rejected(self, fresh_client):
        signed = _sign(_launch_params())
        assert fresh_client.post("/lti/launch", data=signed).status_code == 200
        assert fresh_client.post("/lti/launch", data=signed).status_code == 401

    def test_rejected_when_lti_not_configured(self, fresh_client, monkeypatch):
        monkeypatch.delenv("LTI_SHARED_SECRET")
        assert fresh_client.post("/lti/launch", data=_sign(_launch_params())).status_code == 401

    def test_signature_uses_public_url_behind_proxy(self, fresh_client):
        signed = _sign(_launch_params(), url="https://localhost/lti/launch")
        resp = fresh_client.post("/lti/launch", data=signed, headers={"X-Forwarded-Proto": "https"})
        assert resp.status_code == 200

    def test_configured_launch_url_is_used(self, fresh_client, monkeypatch):
        monkeypatch.setenv("LTI_LAUNCH_URL", "https://srl-agent.example.org/lti/launch")
        signed = _sign(_launch_params(), url="https://srl-agent.example.org/lti/launch")
        assert fresh_client.post("/lti/launch", data=signed).status_code == 200

    def test_query_parameters_are_signed(self, fresh_client):
        """Moodle's tool URL contains ?v=2; query parameters are part of the signature."""
        params = _launch_params()
        signed = _sign({**params, "v": "2"})
        signed.pop("v")
        assert fresh_client.post("/lti/launch?v=2", data=signed).status_code == 200
        assert fresh_client.post("/lti/launch?v=3", data=_sign(_launch_params())).status_code == 401


# ===========================================================================
# 2. Teachers only see their own course
# ===========================================================================

class TestCourseScoping:
    @pytest.fixture
    def two_courses(self, fresh_client, auth):
        """One student in course A, two in course B (created through the normal API)."""
        course_a, course_b = _uid("courseA"), _uid("courseB")
        for uid, course in [(_uid(), course_a), (_uid(), course_b), (_uid(), course_b)]:
            resp = fresh_client.post(
                "/startConversation",
                json={"client": "pytest", "language": "en"},
                headers=auth(uid, context_id=course),
            )
            assert resp.status_code == 200
        return course_a, course_b

    def test_teacher_sees_only_own_course_stats(self, fresh_client, auth, two_courses):
        course_a, course_b = two_courses
        teacher_a = auth(_uid("teacher"), role="teacher", context_id=course_a)
        stats = fresh_client.get("/dashboard/stats", headers=teacher_a).get_json()
        assert stats["total_students"] == 1

    def test_teacher_cannot_request_another_course(self, fresh_client, auth, two_courses):
        course_a, course_b = two_courses
        teacher_a = auth(_uid("teacher"), role="teacher", context_id=course_a)
        stats = fresh_client.get(f"/dashboard/stats?course_id={course_b}", headers=teacher_a).get_json()
        assert stats["total_students"] == 1  # still course A

    def test_teacher_course_list_contains_only_own_course(self, fresh_client, auth, two_courses):
        course_a, _ = two_courses
        teacher_a = auth(_uid("teacher"), role="teacher", context_id=course_a)
        courses = fresh_client.get("/dashboard/courses", headers=teacher_a).get_json()
        assert [c["id"] for c in courses] == [course_a]

    def test_admin_can_filter_any_course_and_see_all(self, fresh_client, two_courses):
        course_a, course_b = two_courses
        fresh_client.post("/admin/login", json={"password": ADMIN_PASSWORD})
        assert fresh_client.get(f"/dashboard/stats?course_id={course_b}").get_json()["total_students"] == 2
        all_courses = {c["id"] for c in fresh_client.get("/dashboard/courses").get_json()}
        assert {course_a, course_b} <= all_courses

    def test_teacher_via_verified_launch_is_scoped(self, fresh_client, two_courses):
        course_a, _ = two_courses
        resp = fresh_client.post("/lti/launch", data=_sign(_launch_params(context_id=course_a)))
        token = _token_from_page(resp.get_data(as_text=True))
        stats = fresh_client.get("/dashboard/stats", headers={"Authorization": f"Bearer {token}"}).get_json()
        assert stats["total_students"] == 1


# ===========================================================================
# 3. Data endpoints are bound to the server-issued identity
# ===========================================================================

class TestIdentityBinding:
    @pytest.fixture
    def victim(self, fresh_client, auth):
        uid = _uid("victim")
        resp = fresh_client.post(
            "/startConversation", json={"client": "pytest", "language": "en"}, headers=auth(uid)
        )
        assert resp.status_code == 200
        return uid

    def test_cannot_read_another_users_conversation(self, fresh_client, auth, victim):
        attacker = auth(_uid("attacker"))
        resp = fresh_client.get(f"/conversation?userid={victim}&client=pytest", headers=attacker)
        assert resp.status_code == 200
        assert resp.get_json()["messages"] == []  # the attacker's own (empty) conversation

    def test_victim_reads_own_conversation(self, fresh_client, auth, victim):
        resp = fresh_client.get("/conversation?client=pytest", headers=auth(victim))
        assert len(resp.get_json()["messages"]) >= 1

    def test_cannot_read_another_users_results(self, fresh_client, auth, victim):
        attacker = auth(_uid("attacker"))
        body = fresh_client.get(f"/student/results?userid={victim}&client=pytest", headers=attacker).get_json()
        assert body["interview_completed"] is False and body["answers_count"] == 0

    def test_cannot_write_into_another_users_interview(self, fresh_client, auth, victim):
        attacker = auth(_uid("attacker"))
        fresh_client.post(
            "/reply", json={"userid": victim, "client": "pytest", "message": "hijack"}, headers=attacker
        )
        messages = fresh_client.get("/conversation?client=pytest", headers=auth(victim)).get_json()["messages"]
        assert all(m["message"] != "hijack" for m in messages)

    def test_cannot_reset_another_users_interview(self, fresh_client, auth, victim):
        attacker = auth(_uid("attacker"))
        fresh_client.post("/resetConversation", json={"userid": victim, "client": "pytest"}, headers=attacker)
        messages = fresh_client.get("/conversation?client=pytest", headers=auth(victim)).get_json()["messages"]
        assert len(messages) >= 1

    def test_no_identity_is_rejected(self, fresh_client, victim):
        assert fresh_client.get(f"/conversation?userid={victim}&client=pytest",
                                headers={"Authorization": "none"}).status_code == 401

    def test_tampered_token_is_rejected(self, fresh_client, auth, victim):
        token = auth(_uid("attacker"))["Authorization"]
        forged = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        assert fresh_client.get("/conversation?client=pytest",
                                headers={"Authorization": forged}).status_code == 401

    def test_admin_may_read_a_specific_user(self, fresh_client, victim):
        fresh_client.post("/admin/login", json={"password": ADMIN_PASSWORD})
        resp = fresh_client.get(f"/conversation?userid={victim}&client=pytest", headers={"Authorization": "none"})
        assert len(resp.get_json()["messages"]) >= 1


class TestStandaloneIdentity:
    def test_server_issues_identity(self, fresh_client):
        body = fresh_client.post("/session/identity").get_json()
        assert body["userid"].startswith("user_") and len(body["userid"]) > 20
        assert body["role"] == "student"
        again = fresh_client.get("/session/identity", headers={"Authorization": f"Bearer {body['token']}"})
        assert again.get_json()["userid"] == body["userid"]

    def test_standalone_identity_is_never_a_teacher(self, fresh_client):
        token = fresh_client.post("/session/identity").get_json()["token"]
        assert fresh_client.get("/dashboard/stats", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    def test_client_cannot_choose_its_userid(self, fresh_client):
        body = fresh_client.post(
            "/session/identity", json={"userid": "chosen_by_client"}, headers={"Authorization": "none"}
        ).get_json()
        assert body["userid"] != "chosen_by_client"


# ===========================================================================
# 4. Inventory: every endpoint not explicitly public rejects anonymous calls
# ===========================================================================

# (method, rule) pairs that are intentionally reachable without identity/admin.
PUBLIC_ENDPOINTS = {
    ("GET", "/"), ("GET", "/health"), ("GET", "/frontend/<path:filename>"),
    ("GET", "/static/lti/<path:filename>"), ("GET", "/static/favicon.ico"),
    ("GET", "/translations/<lang>"), ("GET", "/survey/<survey_id>"),  # questionnaire definition
    ("GET", "/user_language/"), ("GET", "/user_role/"),                # defaults only, no user data
    ("GET", "/admin/status"), ("POST", "/admin/logout"), ("POST", "/admin/login"),
    ("POST", "/session/identity"),                                     # issues an anonymous identity
    ("POST", "/lti/launch"),                                           # verified by OAuth signature
}


def _anonymous_requests(flask_app):
    for rule in flask_app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", "x", rule.rule)
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            yield method, rule.rule, path


class TestEndpointInventory:
    def test_public_list_is_up_to_date(self, flask_app):
        existing = {(m, r) for m, r, _ in _anonymous_requests(flask_app)}
        assert PUBLIC_ENDPOINTS <= existing, PUBLIC_ENDPOINTS - existing

    def test_every_non_public_endpoint_rejects_anonymous_calls(self, flask_app):
        from flask.testing import FlaskClient
        client = FlaskClient(flask_app, use_cookies=False)  # no identity, no admin session
        unprotected = []
        for method, rule, path in _anonymous_requests(flask_app):
            if (method, rule) in PUBLIC_ENDPOINTS:
                continue
            resp = client.open(path + "?userid=victim&client=web", method=method,
                               json={"userid": "victim", "client": "web"}, headers={"Authorization": "none"})
            if resp.status_code != 401:
                unprotected.append(f"{method} {rule} -> {resp.status_code}")
        assert not unprotected, "endpoints reachable without authentication:\n" + "\n".join(unprotected)


# ===========================================================================
# 5. Audit log
# ===========================================================================

def _audit_entries(action, since):
    from app.models import ActivityLog
    return [e for e in ActivityLog.query.filter(ActivityLog.action == action, ActivityLog.timestamp >= since).all()]


class TestAuditLog:
    def test_admin_login_and_failure_are_audited(self, fresh_client):
        since = int(time.time())
        fresh_client.post("/admin/login", json={"password": "wrong"})
        fresh_client.post("/admin/login", json={"password": ADMIN_PASSWORD})
        assert _audit_entries("audit_admin_login_failed", since)
        ok = _audit_entries("audit_admin_login", since)
        assert ok and ok[-1].user_id == "admin" and ok[-1].http_status == 200

    def test_admin_export_is_audited(self, fresh_client):
        since = int(time.time())
        fresh_client.post("/admin/login", json={"password": ADMIN_PASSWORD})
        fresh_client.get("/survey/oase/results")
        entries = _audit_entries("audit_admin_request", since)
        assert any(e.value["path"] == "/survey/oase/results" and e.value.get("survey_id") == "oase"
                   and e.http_status == 200 for e in entries)

    def test_denied_access_is_audited(self, fresh_client):
        since = int(time.time())
        fresh_client.get("/survey/oase/results")
        denied = _audit_entries("audit_access_denied", since)
        assert any(e.value["path"] == "/survey/oase/results" and e.http_status == 401 for e in denied)

    def test_dashboard_access_is_audited_with_course(self, fresh_client, auth):
        since = int(time.time())
        course = _uid("auditcourse")
        fresh_client.get("/dashboard/stats", headers=auth(_uid("teacher"), role="teacher", context_id=course))
        assert any(e.value.get("course") == course for e in _audit_entries("audit_dashboard_request", since))

    def test_admin_reading_user_data_is_audited(self, fresh_client):
        since = int(time.time())
        fresh_client.post("/admin/login", json={"password": ADMIN_PASSWORD})
        fresh_client.get("/conversation?userid=some_user&client=web", headers={"Authorization": "none"})
        assert any(e.value.get("target_user") == "some_user" for e in _audit_entries("audit_user_data_read", since))

    def test_lti_launches_are_audited(self, fresh_client):
        since = int(time.time())
        fresh_client.post("/lti/launch", data=_sign(_launch_params()))
        fresh_client.post("/lti/launch", data={"roles": "Instructor"})
        assert _audit_entries("audit_lti_launch", since)
        assert _audit_entries("audit_lti_launch_rejected", since)


class TestTelemetryEndpoints:
    @pytest.mark.parametrize("path", ["/log/tab_event", "/log/page_view", "/log/interaction", "/log/mouse_traces"])
    def test_anonymous_telemetry_is_rejected(self, fresh_client, path):
        resp = fresh_client.post(path, json={"event": "tab_hidden", "path": "/", "action": "strategy_hovered"},
                                 headers={"Authorization": "none"})
        assert resp.status_code == 401

    @pytest.mark.parametrize("action", ["audit_admin_login", "reset_conversation", "interview_complete"])
    def test_clients_cannot_log_server_side_actions(self, fresh_client, auth, action):
        resp = fresh_client.post("/log/interaction", json={"client": "web", "action": action},
                                 headers=auth(_uid()))
        assert resp.status_code == 400
