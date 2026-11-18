"""
Shared pytest fixtures for strategy-detection tests.

These are **integration tests** that require:
  • a running PostgreSQL database (same as the dev DB)
  • a running Ollama instance with ``nomic-embed-text`` (for RAG tests)
  • a running Ollama instance with ``phi3:latest``    (for LLM tests)

Usage
-----
    cd backend
    poetry run pytest ../tests/ -v              # all tests
    poetry run pytest ../tests/ -v -k rag       # RAG tests only
    poetry run pytest ../tests/ -v -k llm       # LLM tests only
    poetry run pytest ../tests/ -v --timeout=0  # no timeout (for slow LLM tests)
"""

import os
import sys
import csv
import json
import pathlib
import uuid

import pytest
import sqlalchemy as sa

# Ensure backend/ is importable
BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from urllib.parse import parse_qs, urlsplit          # noqa: E402

from flask.testing import FlaskClient                # noqa: E402

from app import app, db as _db                       # noqa: E402
from app.identity import issue_token                 # noqa: E402
from app.rag import seed_strategy_embeddings          # noqa: E402


def identity_headers(uid, role="student", context_id="0"):
    """Authorization header with a server-issued identity token, as the frontend sends it."""
    token = issue_token({"uid": uid, "role": role, "context_id": context_id, "source": "test"})
    return {"Authorization": f"Bearer {token}"}


class IdentityClient(FlaskClient):
    """Test client that acts as the user named in the request.

    The server takes the user id only from the identity token, never from the request.
    Tests that send a "userid" (JSON body or query string) therefore get a matching
    token, exactly like the real frontend. Tests that set Authorization themselves
    (e.g. to check that one user cannot act as another) are left untouched.
    """

    def open(self, *args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        if "Authorization" not in headers:
            uid = None
            body = kwargs.get("json")
            if isinstance(body, dict):
                uid = body.get("userid")
            query = kwargs.get("query_string")
            if not uid and isinstance(query, dict):
                uid = query.get("userid")
            if not uid and args and isinstance(args[0], str):
                uid = (parse_qs(urlsplit(args[0]).query).get("userid") or [None])[0]
            if uid:
                headers.update(identity_headers(uid))
                kwargs["headers"] = headers
        return super().open(*args, **kwargs)


app.test_client_class = IdentityClient


@pytest.fixture
def auth():
    """identity_headers(uid, role="student", context_id="0") -> Authorization header."""
    return identity_headers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def flask_app():
    """Create the Flask application and push an app context for the entire
    test session.  Seeds RAG embeddings only when USE_RAG_STRATEGY=true."""
    app.config["TESTING"] = True
    with app.app_context():
        _db.create_all()
        if os.getenv("USE_RAG_STRATEGY", "false").lower() == "true":
            seed_strategy_embeddings()
        yield app


@pytest.fixture(scope="session")
def db(flask_app):
    """Return the SQLAlchemy db instance (already inside an app context)."""
    return _db


@pytest.fixture(scope="session")
def client(flask_app):
    """Return a Flask test client for the entire test session."""
    return flask_app.test_client()


# ---------------------------------------------------------------------------
# Authorization test suite (tests/unit, tests/api)
#
# Identity in this app: a bearer token signed with SECRET_KEY (app/identity.py) for
# students/teachers, the signed Flask session cookie for admins (POST /admin/login).
# Convention for foreign objects: a userid sent by the client is ignored, every
# request acts on the caller's own identity (no 403/404 for other users' objects).
# ---------------------------------------------------------------------------

AUTHZ_ADMIN_PASSWORD = "authz-test-admin-password"


@pytest.fixture
def admin_password():
    """The ADMIN_PASSWORD that client_as configures for the test."""
    return AUTHZ_ADMIN_PASSWORD


@pytest.fixture
def isolated_db(flask_app):
    """Run the test inside an outer transaction that is rolled back afterwards.

    The app commits on its own (request teardown, logging); with
    join_transaction_mode="create_savepoint" those commits only release savepoints.
    """
    engines = _db.engines
    engine = engines[None]
    factory_kw = _db.session.session_factory.kw
    original_kw = dict(factory_kw)
    connection = engine.connect()
    outer = connection.begin()
    _db.session.remove()
    engines[None] = connection
    _db.session.configure(join_transaction_mode="create_savepoint")
    # Start without failed admin logins (login throttling). Only inside the rolled-back
    # transaction - the real audit log is never changed.
    _db.session.execute(sa.text("DELETE FROM activity_log WHERE action = 'audit_admin_login_failed'"))
    _db.session.commit()
    try:
        yield
    finally:
        _db.session.remove()
        engines[None] = engine
        factory_kw.clear()
        factory_kw.update(original_kw)
        outer.rollback()
        connection.close()


class AuthzUser:
    """A test actor. `token_claims` is None for actors without identity token."""

    def __init__(self, name, token_claims=None, admin=False):
        self.name = name
        self.token_claims = token_claims
        self.admin = admin

    @property
    def uid(self):
        return self.token_claims["uid"] if self.token_claims else None

    def __repr__(self):
        return f"<{self.name}>"


def _uid(prefix):
    return f"authz_{prefix}_{uuid.uuid4().hex[:10]}"


@pytest.fixture
def make_user():
    """Factory per role: student (standalone), lti_student, teacher, admin, anonymous,
    unknown_role. Teachers/LTI students belong to a course (context_id)."""
    def factory(role, course="authz_course_a"):
        if role == "anonymous":
            return AuthzUser("anonymous")
        if role == "admin":
            return AuthzUser("admin", admin=True)
        if role == "student":
            return AuthzUser("student", {"uid": _uid("student"), "role": "student",
                                         "context_id": "0", "source": "standalone"})
        if role == "lti_student":
            return AuthzUser("lti_student", {"uid": f"{course}:{_uid('s')}", "role": "student",
                                             "context_id": course, "source": "lti"})
        if role == "teacher":
            return AuthzUser("teacher", {"uid": f"{course}:{_uid('t')}", "role": "teacher",
                                         "context_id": course, "source": "lti"})
        if role == "unknown_role":
            return AuthzUser("unknown_role", {"uid": _uid("x"), "role": "superuser",
                                              "context_id": course, "source": "lti"})
        raise ValueError(role)
    return factory


@pytest.fixture
def client_as(flask_app, monkeypatch):
    """client_as(user) -> test client acting as `user` through the real auth path:
    a signed identity token (test SECRET_KEY) and/or a real admin login."""
    from flask.testing import FlaskClient as PlainClient  # no auto-identity magic

    monkeypatch.setenv("ADMIN_PASSWORD", AUTHZ_ADMIN_PASSWORD)
    monkeypatch.setenv("DISABLE_LLM", "true")

    def make(user):
        c = PlainClient(flask_app, use_cookies=True)
        if user.token_claims:
            c.environ_base["HTTP_AUTHORIZATION"] = "Bearer " + issue_token(user.token_claims)
        if user.admin:
            assert c.post("/admin/login", json={"password": AUTHZ_ADMIN_PASSWORD}).status_code == 200
        return c
    return make


@pytest.fixture
def owned_interview(client_as):
    """Give a user real owned data: a started interview, one answer, a survey response."""
    def create(user):
        c = client_as(user)
        assert c.post("/startConversation", json={"client": "web", "language": "de"}).status_code == 200
        assert c.post("/reply", json={"client": "web", "message": "Ich schreibe Zusammenfassungen."}).status_code == 200
        assert c.post("/survey/srl-o/submit",
                      json={"client": "web", "language": "de", "responses": {"q1": 4}}).status_code == 201
        return user
    return create


AUTHZ_TABLES = ["users", "state", "interview_answer", "llm_response", "user_strategy",
                "survey_responses", "archive", "mouse_traces", "lti_nonce"]


@pytest.fixture
def db_snapshot(flask_app):
    """db_snapshot() -> row counts of all user-data tables (activity_log without audit rows)."""
    def snapshot():
        counts = {t: _db.session.execute(sa.text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in AUTHZ_TABLES}
        counts["activity_log (non-audit)"] = _db.session.execute(
            sa.text("SELECT COUNT(*) FROM activity_log WHERE action NOT LIKE 'audit_%'")).scalar()
        return counts
    return snapshot


# ---------------------------------------------------------------------------
# Eval dataset loader
# ---------------------------------------------------------------------------

_EVAL_CSV = pathlib.Path(__file__).resolve().parent / "strategy_eval.csv"
_CODE_MAP = BACKEND_DIR / "config" / "strategy_code_map.json"


def _load_code_map() -> dict[str, str]:
    with open(_CODE_MAP, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_eval_conversations() -> list[dict]:
    """
    Parse strategy_eval.csv into per-participant conversation windows.

    For every row that has a ``gold_strategy`` label we collect the
    preceding conversation turns (same participant) as context and bundle
    them into a test case dict::

        {
            "participant": "P1",
            "conversation": ["msg1", "msg2", ...],
            "gold_strategy": "004-002",
            "gold_strategy_id": "organization",
        }

    To keep the test suite feasible we use the **last 6 messages** leading
    up to (and including) the labeled row as the conversation window — the
    same window size that ``detect_strategies_rag()`` uses.
    """
    code_map = _load_code_map()

    conversations: dict[str, list[str]] = {}   # participant → cumulative msgs
    cases: list[dict] = []

    with open(_EVAL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            participant = row["participant"].strip()
            message = row["message"].strip()
            gold = row["gold_strategy"].strip()

            conversations.setdefault(participant, []).append(message)

            if gold and gold != "nan":
                window = conversations[participant][-6:]
                cases.append({
                    "participant": participant,
                    "conversation": list(window),
                    "gold_strategy": gold,
                    "gold_strategy_id": code_map.get(gold, gold),
                })

    return cases


# Cache so parametrize can access it at collection time
EVAL_CASES = _load_eval_conversations()


def short_id(case: dict) -> str:
    """Short pytest ID like ``P1-004-002[3]``."""
    return f"{case['participant']}-{case['gold_strategy']}"
