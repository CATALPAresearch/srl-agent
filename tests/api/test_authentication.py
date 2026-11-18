"""Authentication (401) through the real auth path.

Participant identity: bearer token signed with SECRET_KEY (salt "srl-identity", max age
180 days). Admin: signed Flask session cookie after POST /admin/login. The tokens carry no
aud/iss claims; the salt plays that role, so "wrong audience" = token signed for another
purpose (other salt) with the same key.
"""
import datetime

import pytest
import time_machine
from flask.sessions import SecureCookieSessionInterface
from flask.testing import FlaskClient
from itsdangerous import URLSafeTimedSerializer

from app import app
from app.identity import issue_token

pytestmark = pytest.mark.usefixtures("isolated_db")

IDENTITY_ENDPOINT = "/session/identity"
STAFF_ENDPOINT = "/dashboard/stats"
ADMIN_ENDPOINT = "/survey/srl-o/results"
STUDENT = {"uid": "authn_student", "role": "student", "context_id": "0", "source": "standalone"}
TEACHER = {"uid": "course_a:authn_teacher", "role": "teacher", "context_id": "course_a", "source": "lti"}


@pytest.fixture
def plain_client(flask_app, client_as):  # client_as sets ADMIN_PASSWORD / DISABLE_LLM
    return FlaskClient(flask_app, use_cookies=True)


@pytest.fixture
def login(plain_client, admin_password):
    return lambda: plain_client.post("/admin/login", json={"password": admin_password})


def bearer(token):
    return {"Authorization": "Bearer " + token}


def admin_cookie(client):
    return client.get_cookie(app.config.get("SESSION_COOKIE_NAME", "session")).value


# --- participant token: 401 cases --------------------------------------------

def test_no_credentials_is_401(plain_client):
    assert plain_client.get(IDENTITY_ENDPOINT).status_code == 401


@pytest.mark.parametrize("header", [
    pytest.param("Bearer", id="scheme-only"),
    pytest.param("Bearer ", id="empty-token"),
    pytest.param("Basic dXNlcjpwYXNz", id="basic-scheme"),
    pytest.param("bearer " + "x" * 20, id="lowercase-scheme-garbage"),
    pytest.param("Bearer not.a.token", id="garbage-token"),
    pytest.param("Token " + "x" * 20, id="unknown-scheme"),
])
def test_malformed_authorization_header_is_401(plain_client, header):
    assert plain_client.get(IDENTITY_ENDPOINT, headers={"Authorization": header}).status_code == 401


def test_token_with_wrong_signature_is_401(plain_client):
    forged = URLSafeTimedSerializer("not-the-server-key", salt="srl-identity").dumps(TEACHER)

    assert plain_client.get(STAFF_ENDPOINT, headers=bearer(forged)).status_code == 401


def test_token_with_tampered_payload_is_401(plain_client):
    payload, timestamp, signature = issue_token(STUDENT).rsplit(".", 2)
    other_payload = issue_token(TEACHER).rsplit(".", 2)[0]

    assert plain_client.get(STAFF_ENDPOINT,
                            headers=bearer(f"{other_payload}.{timestamp}.{signature}")).status_code == 401


def test_token_for_other_purpose_is_401(plain_client):
    other_audience = URLSafeTimedSerializer(app.secret_key, salt="cookie-session").dumps(TEACHER)

    assert plain_client.get(STAFF_ENDPOINT, headers=bearer(other_audience)).status_code == 401


def test_session_cookie_used_as_bearer_token_is_401(plain_client, login):
    login()
    cookie_value = admin_cookie(plain_client)
    fresh = FlaskClient(app, use_cookies=False)

    assert fresh.get(IDENTITY_ENDPOINT, headers=bearer(cookie_value)).status_code == 401


def test_token_without_uid_is_401(plain_client):
    token = issue_token({"role": "teacher", "context_id": "course_a"})

    assert plain_client.get(STAFF_ENDPOINT, headers=bearer(token)).status_code == 401


def test_token_older_than_180_days_is_401(plain_client):
    with time_machine.travel(datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), tick=False):
        token = issue_token(STUDENT)

    with time_machine.travel(datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc), tick=False):
        response = plain_client.get(IDENTITY_ENDPOINT, headers=bearer(token))

    assert response.status_code == 401


def test_token_younger_than_180_days_is_accepted(plain_client):
    with time_machine.travel(datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), tick=False):
        token = issue_token(STUDENT)

    with time_machine.travel(datetime.datetime(2026, 6, 29, tzinfo=datetime.timezone.utc), tick=False):
        response = plain_client.get(IDENTITY_ENDPOINT, headers=bearer(token))

    assert response.status_code == 200


def test_valid_token_is_accepted(plain_client):
    response = plain_client.get(IDENTITY_ENDPOINT, headers=bearer(issue_token(STUDENT)))

    assert response.get_json() == {"userid": "authn_student", "role": "student"}


def test_identity_from_session_cookie_is_accepted(plain_client):
    issued = plain_client.post(IDENTITY_ENDPOINT).get_json()

    assert plain_client.get(IDENTITY_ENDPOINT).get_json()["userid"] == issued["userid"]


# --- 401 vs 403 ------------------------------------------------------------

def test_invalid_token_on_staff_endpoint_is_401_not_403(plain_client):
    assert plain_client.get(STAFF_ENDPOINT, headers=bearer("garbage")).status_code == 401


@pytest.mark.xfail(reason="valid identity with insufficient role answers 401 instead of 403", strict=True)
def test_valid_student_on_staff_endpoint_is_403(plain_client):
    assert plain_client.get(STAFF_ENDPOINT, headers=bearer(issue_token(STUDENT))).status_code == 403


@pytest.mark.xfail(reason="valid identity with insufficient role answers 401 instead of 403", strict=True)
def test_valid_teacher_on_admin_endpoint_is_403(plain_client):
    assert plain_client.get(ADMIN_ENDPOINT, headers=bearer(issue_token(TEACHER))).status_code == 403


# --- admin session ---------------------------------------------------------

def test_wrong_admin_password_is_401(plain_client):
    assert plain_client.post("/admin/login", json={"password": "wrong"}).status_code == 401


def test_admin_login_is_disabled_without_configured_password(plain_client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD")

    assert plain_client.post("/admin/login", json={"password": ""}).status_code == 401


def test_admin_cookie_signed_with_other_key_is_401(plain_client):
    forged = SecureCookieSessionInterface().get_signing_serializer(
        type("FakeApp", (), {"secret_key": "attacker-key", "config": app.config})()
    ).dumps({"is_admin": True})
    plain_client.set_cookie(app.config.get("SESSION_COOKIE_NAME", "session"), forged)

    assert plain_client.get(ADMIN_ENDPOINT).status_code == 401


def test_admin_session_is_accepted(plain_client, login):
    login()

    assert plain_client.get(ADMIN_ENDPOINT).status_code == 200


def test_admin_session_older_than_session_lifetime_is_401(plain_client, login):
    with time_machine.travel(datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc), tick=False):
        login()

    with time_machine.travel(datetime.datetime(2026, 2, 2, tzinfo=datetime.timezone.utc), tick=False):
        response = plain_client.get(ADMIN_ENDPOINT)

    assert response.status_code == 401


def test_logout_ends_admin_session(plain_client, login):
    login()

    plain_client.post("/admin/logout")

    assert plain_client.get(ADMIN_ENDPOINT).status_code == 401


def test_admin_cookie_replayed_after_logout_is_401(plain_client, login):
    login()
    stolen = admin_cookie(plain_client)
    plain_client.post("/admin/logout")
    attacker = FlaskClient(app, use_cookies=True)
    attacker.set_cookie(app.config.get("SESSION_COOKIE_NAME", "session"), stolen)

    assert attacker.get(ADMIN_ENDPOINT).status_code == 401


def test_admin_login_is_throttled_after_repeated_failures(plain_client):
    statuses = [plain_client.post("/admin/login", json={"password": f"guess-{i}"}).status_code
                for i in range(20)]

    assert 429 in statuses


# --- admin login throttling ----------------------------------------------------

def failed_logins(client, count, ip="198.51.100.7"):
    for i in range(count):
        client.post("/admin/login", json={"password": f"guess-{i}"}, headers={"X-Real-IP": ip})


def test_correct_password_is_refused_after_five_failures_from_same_ip(plain_client, admin_password):
    failed_logins(plain_client, 5)

    response = plain_client.post("/admin/login", json={"password": admin_password},
                                 headers={"X-Real-IP": "198.51.100.7"})

    assert response.status_code == 429


def test_throttled_login_grants_no_admin_session(plain_client, admin_password):
    failed_logins(plain_client, 5)

    plain_client.post("/admin/login", json={"password": admin_password}, headers={"X-Real-IP": "198.51.100.7"})

    assert plain_client.get("/admin/status").get_json() == {"is_admin": False}


def test_throttled_login_announces_retry_after(plain_client):
    failed_logins(plain_client, 6)

    response = plain_client.post("/admin/login", json={"password": "x"}, headers={"X-Real-IP": "198.51.100.7"})

    assert response.headers["Retry-After"] == "900"


def test_four_failures_do_not_block_the_admin(plain_client, admin_password):
    failed_logins(plain_client, 4)

    response = plain_client.post("/admin/login", json={"password": admin_password},
                                 headers={"X-Real-IP": "198.51.100.7"})

    assert response.status_code == 200


def test_failures_from_other_ip_do_not_block_the_admin(plain_client, admin_password):
    failed_logins(plain_client, 5, ip="203.0.113.9")

    response = plain_client.post("/admin/login", json={"password": admin_password},
                                 headers={"X-Real-IP": "198.51.100.7"})

    assert response.status_code == 200


def test_distributed_guessing_hits_global_limit(plain_client):
    for i in range(50):
        failed_logins(plain_client, 1, ip=f"10.0.{i // 250}.{i % 250}")

    response = plain_client.post("/admin/login", json={"password": "x"}, headers={"X-Real-IP": "10.9.9.9"})

    assert response.status_code == 429


def test_throttle_ends_after_fifteen_minutes(plain_client, admin_password):
    with time_machine.travel(datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc), tick=False) as clock:
        failed_logins(plain_client, 5)
        clock.shift(15 * 60 + 1)
        response = plain_client.post("/admin/login", json={"password": admin_password},
                                     headers={"X-Real-IP": "198.51.100.7"})

    assert response.status_code == 200


# --- admin session lifetime ------------------------------------------------------

def test_admin_session_ends_after_eight_hours(plain_client, login):
    with time_machine.travel(datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc), tick=False) as clock:
        login()
        clock.shift(8 * 60 * 60 + 1)
        response = plain_client.get(ADMIN_ENDPOINT)

    assert response.status_code == 401


def test_failed_login_ends_existing_admin_session(plain_client, login):
    login()

    plain_client.post("/admin/login", json={"password": "wrong"})

    assert plain_client.get(ADMIN_ENDPOINT).status_code == 401
