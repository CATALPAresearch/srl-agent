"""Privilege escalation via request payload.

Clients try to set their own role, user id, course or admin flag. The tests assert the
values the server actually stored or issued, not just the status code.
"""
import re
import time
import uuid

import pytest
import sqlalchemy as sa
from flask.testing import FlaskClient

from app.lti import oauth_signature

pytestmark = pytest.mark.usefixtures("isolated_db")

LTI_KEY = "authz_lti_key"
LTI_SECRET = "authz lti secret"
ESCALATION = {"role": "teacher", "is_admin": True, "context_id": "authz_course_victim",
              "userid": "authz_victim_user", "uid": "authz_victim_user", "source": "lti"}


@pytest.fixture
def lti_client(flask_app, client_as, monkeypatch):
    monkeypatch.setenv("LTI_CONSUMER_KEY", LTI_KEY)
    monkeypatch.setenv("LTI_SHARED_SECRET", LTI_SECRET)
    monkeypatch.delenv("LTI_LAUNCH_URL", raising=False)
    return FlaskClient(flask_app, use_cookies=True)


def signed_launch(roles):
    params = {
        "lti_message_type": "basic-lti-launch-request", "lti_version": "LTI-1p0", "resource_link_id": "1",
        "context_id": "authz_course_lti", "context_title": "Authz", "user_id": uuid.uuid4().hex,
        "roles": roles, "oauth_consumer_key": LTI_KEY, "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())), "oauth_nonce": uuid.uuid4().hex, "oauth_version": "1.0",
    }
    params["oauth_signature"] = oauth_signature("POST", "http://localhost/lti/launch",
                                                list(params.items()), LTI_SECRET)
    return params


def token_in(html):
    return re.search(r'"token": "([^"]+)"', html).group(1)


def stored_user(db, uid):
    return db.session.execute(sa.text("SELECT id, context_id FROM users WHERE id = :uid"), {"uid": uid}).first()


# --- identity endpoint -----------------------------------------------------

def test_new_identity_ignores_requested_role(client_as, make_user):
    client = client_as(make_user("anonymous"))

    issued = client.post("/session/identity", json=ESCALATION).get_json()

    assert issued["role"] == "student"


def test_new_identity_ignores_requested_userid(client_as, make_user):
    client = client_as(make_user("anonymous"))

    issued = client.post("/session/identity", json=ESCALATION).get_json()

    assert issued["userid"] != ESCALATION["userid"]


def test_new_identity_token_grants_no_dashboard_access(client_as, make_user):
    client = client_as(make_user("anonymous"))
    token = client.post("/session/identity", json=ESCALATION).get_json()["token"]

    response = client.get("/dashboard/stats", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code in (401, 403)


def test_refreshing_identity_keeps_student_role(client_as, make_user):
    student = make_user("student")
    client = client_as(student)

    issued = client.post("/session/identity", json=ESCALATION).get_json()

    assert (issued["userid"], issued["role"]) == (student.uid, "student")


# --- admin flag --------------------------------------------------------------

def test_admin_flag_in_login_payload_is_ignored(client_as, make_user):
    client = client_as(make_user("student"))

    client.post("/admin/login", json={"is_admin": True})

    assert client.get("/admin/status").get_json() == {"is_admin": False}


@pytest.mark.parametrize("password", [
    pytest.param(None, id="null"),
    pytest.param(True, id="boolean"),
    pytest.param(["x"], id="list"),
    pytest.param({"$ne": ""}, id="operator-object"),
    pytest.param("", id="empty-string"),
])
def test_non_string_or_empty_password_does_not_log_in(client_as, make_user, password):
    client = client_as(make_user("student"))

    client.post("/admin/login", json={"password": password})

    assert client.get("/admin/status").get_json() == {"is_admin": False}


def test_admin_flag_in_query_string_is_ignored(client_as, make_user):
    client = client_as(make_user("teacher"))

    response = client.get("/survey/srl-o/results?is_admin=true&admin=1")

    assert response.status_code in (401, 403)


# --- stored values -------------------------------------------------------------

def test_start_conversation_stores_user_under_caller_id(client_as, make_user, db):
    student = make_user("student")

    client_as(student).post("/startConversation", json={"client": "web", "language": "de", **ESCALATION})

    assert stored_user(db, ESCALATION["userid"]) is None


def test_start_conversation_stores_callers_course_not_requested_course(client_as, make_user, db):
    student = make_user("student")

    client_as(student).post("/startConversation", json={"client": "web", "language": "de", **ESCALATION})

    assert stored_user(db, student.uid).context_id == "0"


def test_survey_submission_is_stored_under_caller_id(client_as, make_user, db):
    student = make_user("student")

    client_as(student).post("/survey/srl-o/submit", json={
        "client": "web", "language": "de", "responses": {"q1": 2}, "user_id": ESCALATION["userid"], **ESCALATION})

    owners = db.session.execute(sa.text(
        "SELECT user_id FROM survey_responses WHERE user_id IN (:a, :b)"),
        {"a": student.uid, "b": ESCALATION["userid"]}).scalars().all()
    assert owners == [student.uid]


@pytest.mark.parametrize("action", [
    pytest.param("audit_admin_login", id="audit-action"),
    pytest.param("audit_access_denied", id="audit-denied"),
    pytest.param("interview_complete", id="server-side-action"),
])
def test_client_cannot_write_server_side_log_actions(client_as, make_user, db, action):
    count = sa.text("SELECT COUNT(*) FROM activity_log WHERE action = :a")
    before = db.session.execute(count, {"a": action}).scalar()

    response = client_as(make_user("student")).post("/log/interaction", json={"client": "web", "action": action})

    assert response.status_code == 400
    assert db.session.execute(count, {"a": action}).scalar() == before


# --- LTI role --------------------------------------------------------------------

def test_lti_learner_launch_issues_student_identity(lti_client):
    page = lti_client.post("/lti/launch", data=signed_launch("Learner")).get_data(as_text=True)

    identity = lti_client.get("/session/identity", headers={"Authorization": f"Bearer {token_in(page)}"})

    assert identity.get_json()["role"] == "student"


def test_lti_role_changed_after_signing_is_rejected(lti_client):
    params = signed_launch("Learner")
    params["roles"] = "Instructor"

    assert lti_client.post("/lti/launch", data=params).status_code == 401


def test_lti_custom_role_parameter_does_not_grant_teacher(lti_client):
    page = lti_client.post("/lti/launch", data=signed_launch("Learner,urn:custom:teacher-ish")).get_data(as_text=True)

    identity = lti_client.get("/session/identity", headers={"Authorization": f"Bearer {token_in(page)}"})

    assert identity.get_json()["role"] == "student"
