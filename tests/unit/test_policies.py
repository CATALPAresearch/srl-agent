"""Unit tests for the authorization policy functions (no HTTP round trip).

Each test builds a request context with real signed credentials and calls the policy
function directly: identity resolution, admin/teacher checks, user-id binding, course scope.
"""
import datetime

import pytest
import time_machine
from flask import session
from itsdangerous import URLSafeTimedSerializer

from app import app
from app.identity import (ADMIN_SESSION_SECONDS, current_identity, effective_user_id, end_admin_session,
                          is_admin, issue_token, start_admin_session)
from app.routes.admin_routes import is_teacher
from app.routes.dashboard_routes import _course_scope

pytestmark = pytest.mark.usefixtures("isolated_db")

STUDENT = {"uid": "unit_student", "role": "student", "context_id": "0", "source": "standalone"}
TEACHER = {"uid": "course_a:unit_teacher", "role": "teacher", "context_id": "course_a", "source": "lti"}


def bearer(claims):
    return {"Authorization": "Bearer " + issue_token(claims)}


# --- current_identity -------------------------------------------------------

def test_current_identity_is_none_without_credentials(flask_app):
    with app.test_request_context("/"):
        assert current_identity() is None


def test_current_identity_reads_signed_token(flask_app):
    with app.test_request_context("/", headers=bearer(STUDENT)):
        assert current_identity()["uid"] == "unit_student"


def test_current_identity_rejects_token_signed_with_other_key(flask_app):
    forged = URLSafeTimedSerializer("attacker-key", salt="srl-identity").dumps(TEACHER)
    with app.test_request_context("/", headers={"Authorization": "Bearer " + forged}):
        assert current_identity() is None


def test_current_identity_rejects_token_without_uid(flask_app):
    with app.test_request_context("/", headers=bearer({"role": "teacher", "context_id": "course_a"})):
        assert current_identity() is None


def test_current_identity_rejects_non_dict_payload(flask_app):
    with app.test_request_context("/", headers={"Authorization": "Bearer " + issue_token(["uid", "x"])}):
        assert current_identity() is None


def test_token_identity_takes_precedence_over_session_identity(flask_app):
    with app.test_request_context("/", headers=bearer(STUDENT)):
        session["identity"] = TEACHER
        assert current_identity()["uid"] == "unit_student"


# --- is_admin ---------------------------------------------------------------

def test_is_admin_false_without_session(flask_app):
    with app.test_request_context("/"):
        assert is_admin() is False


def test_is_admin_true_for_admin_session(flask_app):
    with app.test_request_context("/"):
        start_admin_session()
        assert is_admin() is True


def test_is_admin_false_for_admin_flag_without_server_side_session(flask_app):
    with app.test_request_context("/"):
        session["is_admin"] = True
        assert is_admin() is False


def test_is_admin_false_for_unknown_session_id(flask_app):
    with app.test_request_context("/"):
        session.update(is_admin=True, admin_sid="guessed-session-id")
        assert is_admin() is False


def test_is_admin_false_after_session_ended(flask_app):
    with app.test_request_context("/"):
        start_admin_session()
        stolen = dict(session)
        end_admin_session()
        session.update(stolen)
        assert is_admin() is False


def test_is_admin_false_after_session_lifetime(flask_app):
    with time_machine.travel(datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc), tick=False) as clock:
        with app.test_request_context("/"):
            start_admin_session()
            clock.shift(ADMIN_SESSION_SECONDS + 1)
            assert is_admin() is False


def test_new_admin_session_has_new_id(flask_app):
    with app.test_request_context("/"):
        start_admin_session()
        first = session["admin_sid"]
        start_admin_session()
        assert session["admin_sid"] != first


@pytest.mark.parametrize("value", [
    pytest.param("true", id="string-true"),
    pytest.param(1, id="int-1"),
    pytest.param("1", id="string-1"),
])
def test_is_admin_requires_boolean_true(flask_app, value):
    with app.test_request_context("/"):
        session["is_admin"] = value
        assert is_admin() is False


def test_teacher_token_does_not_make_admin(flask_app):
    with app.test_request_context("/", headers=bearer(TEACHER)):
        assert is_admin() is False


# --- is_teacher -------------------------------------------------------------

def test_is_teacher_true_for_teacher_with_course(flask_app):
    with app.test_request_context("/", headers=bearer(TEACHER)):
        assert is_teacher() is True


def test_is_teacher_false_for_student(flask_app):
    with app.test_request_context("/", headers=bearer(STUDENT)):
        assert is_teacher() is False


def test_is_teacher_false_for_teacher_without_course(flask_app):
    with app.test_request_context("/", headers=bearer({**TEACHER, "context_id": ""})):
        assert is_teacher() is False


def test_is_teacher_false_for_unknown_role(flask_app):
    with app.test_request_context("/", headers=bearer({**TEACHER, "role": "superuser"})):
        assert is_teacher() is False


def test_is_teacher_false_for_admin_session_without_identity(flask_app):
    with app.test_request_context("/"):
        start_admin_session()
        assert is_teacher() is False


# --- effective_user_id ------------------------------------------------------

def test_effective_user_id_none_without_identity(flask_app):
    with app.test_request_context("/"):
        assert effective_user_id("victim", allow_admin_override=True) is None


def test_effective_user_id_ignores_requested_id_for_student(flask_app):
    with app.test_request_context("/", headers=bearer(STUDENT)):
        assert effective_user_id("victim", allow_admin_override=True) == "unit_student"


def test_effective_user_id_ignores_requested_id_for_teacher(flask_app):
    with app.test_request_context("/", headers=bearer(TEACHER)):
        assert effective_user_id("victim", allow_admin_override=True) == "course_a:unit_teacher"


def test_effective_user_id_returns_requested_id_for_admin_override(flask_app):
    with app.test_request_context("/"):
        start_admin_session()
        assert effective_user_id("victim", allow_admin_override=True) == "victim"


def test_effective_user_id_ignores_requested_id_for_admin_without_override(flask_app):
    with app.test_request_context("/", headers=bearer(STUDENT)):
        start_admin_session()
        assert effective_user_id("victim") == "unit_student"


# --- _course_scope ----------------------------------------------------------

def test_course_scope_is_own_course_for_teacher(flask_app):
    with app.test_request_context("/?course_id=course_b", headers=bearer(TEACHER)):
        assert _course_scope() == "course_a"


def test_course_scope_follows_filter_for_admin(flask_app):
    with app.test_request_context("/?course_id=course_b"):
        start_admin_session()
        assert _course_scope() == "course_b"


def test_course_scope_is_all_courses_for_admin_without_filter(flask_app):
    with app.test_request_context("/"):
        start_admin_session()
        assert _course_scope() is None
