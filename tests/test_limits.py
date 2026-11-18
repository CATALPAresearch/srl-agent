"""
Abuse limits for /reply (every reply costs several LLM calls) and protection of LLM credentials.

Needs the test DB like test_routes.py.
"""

import os
import uuid

import pytest

os.environ["DISABLE_LLM"] = "true"

from app.llm import bearer_headers, safe_to_send_secret  # noqa: E402
from app.routes import chat_routes  # noqa: E402


@pytest.fixture
def user(flask_app, auth):
    """A started interview; returns a function that sends one reply as this user."""
    uid = f"limit_{uuid.uuid4().hex[:10]}"
    client = flask_app.test_client()
    headers = auth(uid)
    assert client.post("/startConversation", json={"client": "pytest", "language": "en"},
                       headers=headers).status_code == 200

    def reply(message="Ich lerne mit Karteikarten."):
        return client.post("/reply", json={"client": "pytest", "message": message}, headers=headers)
    return reply


class TestReplyLimits:
    def test_message_length_limit(self, user):
        assert user("x" * 2000).status_code == 200
        resp = user("x" * 2001)
        assert resp.status_code == 413
        assert resp.get_json() == {"error": "message_too_long", "limit": 2000}

    def test_rate_limit_per_minute(self, user, monkeypatch):
        monkeypatch.setattr(chat_routes, "MAX_MESSAGES_PER_MINUTE", 3)
        assert [user().status_code for _ in range(3)] == [200, 200, 200]
        resp = user()
        assert resp.status_code == 429
        assert resp.get_json()["error"] == "rate_limited"
        assert resp.headers["Retry-After"] == "60"

    def test_default_rate_limit_is_ten_per_minute(self, user):
        assert all(user().status_code == 200 for _ in range(10))
        assert user().get_json()["error"] == "rate_limited"

    def test_quota_per_interview(self, user, monkeypatch):
        monkeypatch.setattr(chat_routes, "MAX_MESSAGES_PER_MINUTE", 1000)
        monkeypatch.setattr(chat_routes, "MAX_MESSAGES_PER_INTERVIEW", 4)
        assert all(user().status_code == 200 for _ in range(4))
        resp = user()
        assert resp.status_code == 429
        assert resp.get_json() == {"error": "interview_quota_reached", "limit": 4}

    def test_default_quota_is_fifty(self):
        assert chat_routes.MAX_MESSAGES_PER_INTERVIEW == 50

    def test_limits_are_per_user(self, user, flask_app, auth, monkeypatch):
        monkeypatch.setattr(chat_routes, "MAX_MESSAGES_PER_MINUTE", 2)
        user(), user()
        assert user().status_code == 429
        other = flask_app.test_client()
        headers = auth(f"limit_{uuid.uuid4().hex[:10]}")
        other.post("/startConversation", json={"client": "pytest", "language": "en"}, headers=headers)
        assert other.post("/reply", json={"client": "pytest", "message": "hi"}, headers=headers).status_code == 200

    def test_rejected_messages_are_not_stored(self, user, monkeypatch):
        monkeypatch.setattr(chat_routes, "MAX_MESSAGES_PER_MINUTE", 1)
        user("first")
        user("second (rejected)")
        monkeypatch.setattr(chat_routes, "MAX_MESSAGES_PER_MINUTE", 1000)
        assert user("third").status_code == 200  # the rejected one did not count


class TestCredentialTransport:
    @pytest.mark.parametrize("url", [
        "https://ki-connect.example.org/api/v1", "http://localhost:11434", "http://127.0.0.1:8080/v1",
        "http://ollama:11434",  # Docker-internal service name
    ])
    def test_safe_urls(self, url):
        assert safe_to_send_secret(url)
        assert bearer_headers("secret", url) == {"Authorization": "Bearer secret"}

    @pytest.mark.parametrize("url", ["http://ki-connect.example.org/api/v1", "ftp://x.org", "", None])
    def test_key_is_never_sent_unencrypted_to_remote_hosts(self, url):
        assert not safe_to_send_secret(url)
        assert bearer_headers("secret", url) == {}

    def test_no_header_without_token(self):
        assert bearer_headers("", "https://x.org") == {}
