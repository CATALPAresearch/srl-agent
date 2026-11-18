"""
Admin authentication: the admin password is checked server-side only and must
never be shipped to the browser.

Uses the Flask test client (needs the test DB like test_routes.py).
"""

import pytest

PASSWORD = "pytest-admin-secret"
PROTECTED = [
    ("get", "/protocols"),
    ("get", "/protocols/interview_default"),
    ("post", "/protocols"),
    ("put", "/protocols/interview_default"),
    ("delete", "/protocols/some_protocol"),
    ("get", "/protocols/interview_default/export"),
    ("post", "/protocols/import"),
    ("get", "/survey/oase/results"),
]


@pytest.fixture
def fresh_client(flask_app, monkeypatch):
    """A client with its own cookie jar, so admin sessions never leak between tests."""
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    return flask_app.test_client()


class TestAdminLogin:
    def test_status_defaults_to_not_admin(self, fresh_client):
        assert fresh_client.get("/admin/status").get_json() == {"is_admin": False}

    def test_wrong_password_is_rejected(self, fresh_client):
        resp = fresh_client.post("/admin/login", json={"password": "wrong"})
        assert resp.status_code == 401
        assert fresh_client.get("/admin/status").get_json()["is_admin"] is False

    def test_missing_or_invalid_payload_is_rejected(self, fresh_client):
        assert fresh_client.post("/admin/login").status_code == 401
        assert fresh_client.post("/admin/login", json={"password": None}).status_code == 401
        assert fresh_client.post("/admin/login", json={"password": ["x"]}).status_code == 401

    def test_old_hardcoded_default_does_not_work(self, fresh_client):
        assert fresh_client.post("/admin/login", json={"password": "admin"}).status_code == 401

    def test_login_status_logout(self, fresh_client):
        resp = fresh_client.post("/admin/login", json={"password": PASSWORD})
        assert resp.status_code == 200
        assert fresh_client.get("/admin/status").get_json()["is_admin"] is True

        assert fresh_client.post("/admin/logout").status_code == 200
        assert fresh_client.get("/admin/status").get_json()["is_admin"] is False

    def test_login_disabled_without_configured_password(self, flask_app, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "")
        client = flask_app.test_client()
        assert client.post("/admin/login", json={"password": ""}).status_code == 401
        monkeypatch.delenv("ADMIN_PASSWORD")
        assert client.post("/admin/login", json={"password": "admin"}).status_code == 401


class TestProtectedEndpoints:
    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_requires_admin(self, fresh_client, method, path):
        resp = getattr(fresh_client, method)(path, json={})
        assert resp.status_code == 401

    def test_accessible_after_login(self, fresh_client):
        fresh_client.post("/admin/login", json={"password": PASSWORD})
        assert fresh_client.get("/protocols").status_code == 200
        assert fresh_client.get("/survey/oase/results").status_code == 200


class TestDashboardAccess:
    """Aggregated course data: admins or teachers (LTI role in the signed session) only."""

    PATHS = ["/dashboard/stats", "/dashboard/courses"]

    @pytest.mark.parametrize("path", PATHS)
    def test_anonymous_is_rejected(self, fresh_client, path):
        assert fresh_client.get(path).status_code == 401

    @pytest.mark.parametrize("path", PATHS)
    def test_lti_student_is_rejected(self, fresh_client, path):
        with fresh_client.session_transaction() as s:
            s["lti_role"] = "student"
        assert fresh_client.get(path).status_code == 401

    @pytest.mark.parametrize("path", PATHS)
    def test_lti_teacher_is_allowed(self, fresh_client, path):
        with fresh_client.session_transaction() as s:
            s["lti_role"] = "teacher"
        assert fresh_client.get(path).status_code == 200

    @pytest.mark.parametrize("path", PATHS)
    def test_admin_is_allowed(self, fresh_client, path):
        fresh_client.post("/admin/login", json={"password": PASSWORD})
        assert fresh_client.get(path).status_code == 200

    def test_forged_client_flag_has_no_effect(self, fresh_client):
        """The reported attack: setting srl_admin_session in the browser grants nothing."""
        fresh_client.set_cookie("srl_admin_session", "1")
        assert fresh_client.get("/dashboard/stats").status_code == 401
        assert fresh_client.get("/protocols").status_code == 401


class TestPasswordNotExposed:
    def test_index_page_does_not_contain_password(self, fresh_client):
        resp = fresh_client.get("/")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert PASSWORD not in body
        assert "SRL_ADMIN_PASSWORD" not in body
