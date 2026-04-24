"""
Route integration tests.

These are integration tests that require a running PostgreSQL database
pre-seeded with languages, contexts, and strategies (same as the dev DB).

DISABLE_LLM=true is set here so no Ollama instance is needed for these
route tests.  The LLM stub returns a fixed German greeting which is
enough to exercise the full request/response cycle.
"""

import os
import json
import uuid
import pathlib
import sys
import pytest

# Must be set before any import of the Flask app so config.py + llm.py pick it up
os.environ["DISABLE_LLM"] = "true"

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid():
    """Return a fresh unique user-id string to avoid cross-test DB conflicts."""
    return "test_" + uuid.uuid4().hex[:10]


def _start(client, userid, client_name="pytest", lang="en"):
    """POST /startConversation and return the response."""
    return client.post(
        "/startConversation",
        json={"userid": userid, "client": client_name, "language": lang},
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Static routes
# ---------------------------------------------------------------------------

class TestStaticRoutes:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"html" in resp.data.lower()

    def test_favicon_served(self, client):
        resp = client.get("/static/favicon.ico")
        assert resp.status_code in (200, 404)  # 404 is acceptable if file absent in test env


# ---------------------------------------------------------------------------
# /startConversation
# ---------------------------------------------------------------------------

class TestStartConversation:
    def test_valid_english(self, client):
        uid = _uid()
        resp = _start(client, uid, lang="en")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "message" in body

    def test_valid_german(self, client):
        uid = _uid()
        resp = _start(client, uid, lang="de")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "message" in body

    def test_unsupported_language_returns_400(self, client):
        resp = client.post(
            "/startConversation",
            json={"userid": _uid(), "client": "pytest", "language": "xx"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_userid_returns_400(self, client):
        resp = client.post(
            "/startConversation",
            json={"client": "pytest", "language": "en"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_missing_client_returns_400(self, client):
        resp = client.post(
            "/startConversation",
            json={"userid": _uid(), "language": "en"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_idempotent_second_call_200(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        resp = _start(client, uid, lang="en")
        assert resp.status_code == 200

    def test_response_message_is_string(self, client):
        uid = _uid()
        body = _start(client, uid).get_json()
        assert isinstance(body["message"], str)
        assert len(body["message"]) > 0


# ---------------------------------------------------------------------------
# /reply
# ---------------------------------------------------------------------------

class TestReply:
    def test_reply_after_start_returns_message(self, client):
        uid = _uid()
        _start(client, uid)
        resp = client.post(
            "/reply",
            json={"userid": uid, "client": "pytest", "message": "Informatik"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert "message" in resp.get_json()

    def test_reply_unknown_user_returns_400(self, client):
        resp = client.post(
            "/reply",
            json={"userid": "no_such_user_xyz", "client": "pytest", "message": "hi"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_reply_missing_message_returns_400(self, client):
        uid = _uid()
        _start(client, uid)
        resp = client.post(
            "/reply",
            json={"userid": uid, "client": "pytest"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_reply_missing_userid_returns_400(self, client):
        resp = client.post(
            "/reply",
            json={"client": "pytest", "message": "hi"},
            content_type="application/json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /resetConversation
# ---------------------------------------------------------------------------

class TestResetConversation:
    def test_reset_existing_user(self, client):
        uid = _uid()
        _start(client, uid)
        resp = client.post(
            "/resetConversation",
            json={"userid": uid, "client": "pytest"},
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_reset_nonexistent_user_returns_400(self, client):
        resp = client.post(
            "/resetConversation",
            json={"userid": "no_such_user_xyz", "client": "pytest"},
            content_type="application/json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /conversation
# ---------------------------------------------------------------------------

class TestConversation:
    def test_empty_history_for_unknown_user(self, client):
        resp = client.get(
            "/conversation",
            query_string={"userid": "no_such_user_xyz", "client": "pytest"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["messages"] == []

    def test_missing_userid_returns_400(self, client):
        resp = client.get("/conversation", query_string={"client": "pytest"})
        assert resp.status_code == 400

    def test_missing_client_returns_400(self, client):
        resp = client.get("/conversation", query_string={"userid": "someone"})
        assert resp.status_code == 400

    def test_has_bot_message_after_start(self, client):
        uid = _uid()
        _start(client, uid)
        resp = client.get(
            "/conversation",
            query_string={"userid": uid, "client": "pytest"},
        )
        assert resp.status_code == 200
        messages = resp.get_json()["messages"]
        assert len(messages) >= 1
        authors = {m["author"] for m in messages}
        assert "bot" in authors

    def test_message_structure(self, client):
        uid = _uid()
        _start(client, uid)
        messages = client.get(
            "/conversation",
            query_string={"userid": uid, "client": "pytest"},
        ).get_json()["messages"]
        for msg in messages:
            assert "author" in msg
            assert "message" in msg
            assert "id" in msg

    def test_user_and_bot_messages_after_reply(self, client):
        uid = _uid()
        _start(client, uid)
        client.post(
            "/reply",
            json={"userid": uid, "client": "pytest", "message": "Mathematik"},
            content_type="application/json",
        )
        messages = client.get(
            "/conversation",
            query_string={"userid": uid, "client": "pytest"},
        ).get_json()["messages"]
        authors = {m["author"] for m in messages}
        assert "user" in authors
        assert "bot" in authors


# ---------------------------------------------------------------------------
# /log/tab_event
# ---------------------------------------------------------------------------

class TestLogTabEvent:
    def test_tab_hidden_event(self, client):
        resp = client.post(
            "/log/tab_event",
            json={"userid": _uid(), "client": "pytest", "event": "tab_hidden", "timestamp": 1700000000},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["event"] == "tab_hidden"

    def test_tab_visible_event(self, client):
        resp = client.post(
            "/log/tab_event",
            json={"userid": _uid(), "client": "pytest", "event": "tab_visible", "timestamp": 1700000000},
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_invalid_event_type_returns_400(self, client):
        resp = client.post(
            "/log/tab_event",
            json={"userid": _uid(), "client": "pytest", "event": "bogus_event", "timestamp": 1700000000},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unknown_user_still_logs(self, client):
        # Log endpoints should not require a known user in DB
        resp = client.post(
            "/log/tab_event",
            json={"userid": "no_such_user_xyz", "client": "pytest", "event": "tab_hidden", "timestamp": 1},
            content_type="application/json",
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /log/mouse_traces
# ---------------------------------------------------------------------------

class TestLogMouseTraces:
    def test_valid_traces(self, client):
        uid = _uid()
        resp = client.post(
            "/log/mouse_traces",
            json={
                "userid": uid, "client": "pytest", "session_id": "s1",
                "traces": [{"x": 10, "y": 20, "t": 100}, {"x": 15, "y": 25, "t": 200}],
            },
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_empty_traces_list(self, client):
        resp = client.post(
            "/log/mouse_traces",
            json={"userid": _uid(), "client": "pytest", "session_id": "s2", "traces": []},
            content_type="application/json",
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /user_language/
# ---------------------------------------------------------------------------

class TestUserLanguage:
    def test_default_language_is_de(self, client):
        resp = client.get("/user_language/")
        assert resp.status_code == 200
        assert resp.data.decode().strip() == "de"

    def test_known_user_returns_their_language(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        # language route reads from session, not DB — default applies without active LTI session
        resp = client.get("/user_language/")
        assert resp.status_code == 200
        assert resp.data.decode().strip() in ("de", "en")


# ---------------------------------------------------------------------------
# /user_role/
# ---------------------------------------------------------------------------

class TestUserRole:
    def test_default_role_is_student(self, client):
        resp = client.get("/user_role/")
        assert resp.status_code == 200
        assert resp.data.decode().strip() == "student"


# ---------------------------------------------------------------------------
# /dashboard/stats  and  /dashboard/courses
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_stats_returns_expected_keys(self, client):
        resp = client.get("/dashboard/stats")
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ("total_students", "total_completed", "avg_duration_minutes",
                    "avg_response_time_seconds", "weekly_activity", "response_time_by_step"):
            assert key in body, f"Missing key: {key}"

    def test_stats_with_date_filter(self, client):
        resp = client.get("/dashboard/stats?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200

    def test_stats_empty_date_range_returns_zeros(self, client):
        resp = client.get("/dashboard/stats?from=2000-01-01&to=2000-01-02")
        body = resp.get_json()
        assert body["total_students"] == 0
        assert body["total_completed"] == 0

    def test_courses_returns_list(self, client):
        resp = client.get("/dashboard/courses")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_courses_shape(self, client):
        body = client.get("/dashboard/courses").get_json()
        for entry in body:
            assert "id" in entry
            assert "name" in entry
            assert "students" in entry

    def test_courses_standalone_label(self, client):
        uid = _uid()
        _start(client, uid)  # creates user with context_id="0"
        body = client.get("/dashboard/courses").get_json()
        ids = [e["id"] for e in body]
        if "0" in ids:
            standalone = next(e for e in body if e["id"] == "0")
            assert "standalone" in standalone["name"].lower() or standalone["name"] != ""


# ---------------------------------------------------------------------------
# /protocols
# ---------------------------------------------------------------------------

class TestProtocols:
    _created = []  # track names to clean up

    def test_list_returns_list(self, client):
        resp = client.get("/protocols")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_list_contains_default(self, client):
        names = [p["name"] for p in client.get("/protocols").get_json()]
        assert "interview_default" in names

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get("/protocols/does_not_exist_xyz")
        assert resp.status_code == 404

    def test_create_and_retrieve(self, client):
        name = "pytest_proto_" + uuid.uuid4().hex[:6]
        self._created.append(name)
        payload = {"name": name, "protocol": {"categories": [], "note": "test"}}
        resp = client.post("/protocols", json=payload, content_type="application/json")
        assert resp.status_code == 201

        get_resp = client.get(f"/protocols/{name}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["note"] == "test"

    def test_create_missing_name_returns_400(self, client):
        resp = client.post(
            "/protocols",
            json={"protocol": {"categories": []}},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_create_missing_protocol_returns_400(self, client):
        resp = client.post(
            "/protocols",
            json={"name": "should_fail"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_create_duplicate_returns_409(self, client):
        name = "pytest_dup_" + uuid.uuid4().hex[:6]
        self._created.append(name)
        payload = {"name": name, "protocol": {}}
        client.post("/protocols", json=payload, content_type="application/json")
        resp = client.post("/protocols", json=payload, content_type="application/json")
        assert resp.status_code == 409

    def test_delete_default_returns_403(self, client):
        resp = client.delete("/protocols/interview_default")
        assert resp.status_code == 403

    def test_create_and_delete(self, client):
        name = "pytest_del_" + uuid.uuid4().hex[:6]
        client.post("/protocols", json={"name": name, "protocol": {}}, content_type="application/json")
        resp = client.delete(f"/protocols/{name}")
        assert resp.status_code == 200
        assert client.get(f"/protocols/{name}").status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/protocols/no_such_proto_xyz")
        assert resp.status_code == 404

    def test_update_protocol(self, client):
        name = "pytest_upd_" + uuid.uuid4().hex[:6]
        self._created.append(name)
        client.post("/protocols", json={"name": name, "protocol": {"v": 1}}, content_type="application/json")
        resp = client.put(f"/protocols/{name}", json={"v": 2}, content_type="application/json")
        assert resp.status_code == 200
        body = client.get(f"/protocols/{name}").get_json()
        assert body["v"] == 2

    def test_update_nonexistent_returns_404(self, client):
        resp = client.put(
            "/protocols/no_such_xyz",
            json={"x": 1},
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_export_returns_file(self, client):
        name = "pytest_exp_" + uuid.uuid4().hex[:6]
        self._created.append(name)
        client.post("/protocols", json={"name": name, "protocol": {"key": "val"}}, content_type="application/json")
        resp = client.get(f"/protocols/{name}/export")
        assert resp.status_code == 200
        assert b"val" in resp.data

    @pytest.fixture(autouse=True, scope="class")
    def cleanup(self, client):
        yield
        for name in self._created:
            client.delete(f"/protocols/{name}")
        self._created.clear()


# ---------------------------------------------------------------------------
# /survey/<survey_id>
# ---------------------------------------------------------------------------

class TestSurvey:
    def test_get_existing_survey_en(self, client):
        resp = client.get("/survey/srl-o?lang=en")
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body, (dict, list))

    def test_get_existing_survey_de(self, client):
        resp = client.get("/survey/srl-o?lang=de")
        assert resp.status_code == 200

    def test_get_nonexistent_survey_returns_404(self, client):
        resp = client.get("/survey/no_such_survey_xyz?lang=en")
        assert resp.status_code == 404

    def test_no_lang_falls_back_to_default(self, client):
        # Without lang param and without a valid user, should fall back to 'de'
        resp = client.get("/survey/srl-o")
        assert resp.status_code == 200

    def test_lang_from_user(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        resp = client.get(f"/survey/srl-o?userid={uid}&client=pytest")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /survey/<survey_id>/submit
# ---------------------------------------------------------------------------

class TestSurveySubmit:
    def test_submit_returns_201(self, client):
        resp = client.post(
            "/survey/srl-o/submit",
            json={
                "userid": _uid(),
                "client": "pytest",
                "language": "en",
                "responses": {"q1": 4, "q2": 3},
            },
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["status"] == "ok"
        assert "id" in body

    def test_submit_missing_userid_returns_500(self, client):
        resp = client.post(
            "/survey/srl-o/submit",
            json={"client": "pytest", "language": "en", "responses": {}},
            content_type="application/json",
        )
        assert resp.status_code in (400, 500)

    def test_submit_stores_responses(self, client):
        uid = _uid()
        client.post(
            "/survey/srl-o/submit",
            json={"userid": uid, "client": "pytest", "language": "en", "responses": {"oase_1": 5}},
            content_type="application/json",
        )
        # Verify via results endpoint
        resp = client.get(f"/student/results?userid={uid}&client=pytest")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["survey"] is not None
        assert body["survey"]["responses"]["oase_1"] == 5


# ---------------------------------------------------------------------------
# /student/results
# ---------------------------------------------------------------------------

class TestStudentResults:
    def test_missing_userid_returns_400(self, client):
        resp = client.get("/student/results?client=pytest")
        assert resp.status_code == 400

    def test_unknown_user_returns_200_with_empty_strategies(self, client):
        resp = client.get("/student/results?userid=no_such_user_xyz&client=pytest")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["strategies"] == []
        assert body["survey"] is None

    def test_known_user_returns_expected_keys(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        resp = client.get(f"/student/results?userid={uid}&client=pytest")
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ("strategies", "survey", "interview_completed",
                    "answers_count", "total_contexts", "radar_data"):
            assert key in body, f"Missing key: {key}"

    def test_radar_data_is_list(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        resp = client.get(f"/student/results?userid={uid}&client=pytest")
        body = resp.get_json()
        assert isinstance(body["radar_data"], list)

    def test_radar_data_item_shape(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        body = client.get(f"/student/results?userid={uid}&client=pytest").get_json()
        for item in body["radar_data"]:
            assert "id" in item
            assert "name" in item
            assert "frequency" in item
            assert "avg_frequency" in item

    def test_lang_override_accepted(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        resp = client.get(f"/student/results?userid={uid}&client=pytest&lang=de")
        assert resp.status_code == 200

    def test_completed_runs_initially_zero(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        body = client.get(f"/student/results?userid={uid}&client=pytest").get_json()
        assert body["completed_runs"] == 0


# ---------------------------------------------------------------------------
# /student/interview_runs
# ---------------------------------------------------------------------------

class TestStudentInterviewRuns:
    def test_missing_userid_returns_400(self, client):
        resp = client.get("/student/interview_runs?client=pytest")
        assert resp.status_code == 400

    def test_unknown_user_returns_200(self, client):
        resp = client.get("/student/interview_runs?userid=no_such_user_xyz&client=pytest")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["active_run"] is None
        assert body["archived_runs"] == []

    def test_known_user_has_active_run(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        resp = client.get(f"/student/interview_runs?userid={uid}&client=pytest")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["active_run"] is not None

    def test_active_run_shape(self, client):
        uid = _uid()
        _start(client, uid, lang="en")
        body = client.get(f"/student/interview_runs?userid={uid}&client=pytest").get_json()
        run = body["active_run"]
        for key in ("complete", "completed_contexts", "total_contexts"):
            assert key in run, f"Missing key in active_run: {key}"

    def test_response_includes_userid_and_client(self, client):
        uid = _uid()
        body = client.get(f"/student/interview_runs?userid={uid}&client=pytest").get_json()
        assert body["userid"] == uid
        assert body["client"] == "pytest"


# ---------------------------------------------------------------------------
# /log/page_view
# ---------------------------------------------------------------------------

class TestLogPageView:
    def test_valid_page_view_returns_200(self, client):
        resp = client.post(
            "/log/page_view",
            json={"userid": _uid(), "client": "pytest", "path": "/agent-chat", "timestamp": 1700000001},
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["path"] == "/agent-chat"

    def test_missing_path_returns_400(self, client):
        resp = client.post(
            "/log/page_view",
            json={"userid": _uid(), "client": "pytest", "timestamp": 1700000001},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unknown_user_still_logs(self, client):
        resp = client.post(
            "/log/page_view",
            json={"userid": "no_such_user_xyz", "client": "pytest", "path": "/results", "timestamp": 1},
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_page_name_accepted(self, client):
        resp = client.post(
            "/log/page_view",
            json={
                "userid": _uid(), "client": "pytest",
                "path": "/results", "page_name": "ResultsPage", "timestamp": 1,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /log/interaction
# ---------------------------------------------------------------------------

class TestLogInteraction:
    def test_valid_action_returns_200(self, client):
        resp = client.post(
            "/log/interaction",
            json={
                "userid": _uid(), "client": "pytest",
                "action": "strategy_hovered",
                "value": {"strategy": "001-001"},
                "timestamp": 1700000002,
            },
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["action"] == "strategy_hovered"

    def test_missing_action_returns_400(self, client):
        resp = client.post(
            "/log/interaction",
            json={"userid": _uid(), "client": "pytest", "value": {}},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unknown_action_returns_400(self, client):
        resp = client.post(
            "/log/interaction",
            json={"userid": _uid(), "client": "pytest", "action": "bogus_action_xyz"},
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_all_ui_actions_accepted(self, client):
        actions = [
            "strategy_hovered",
            "unmentioned_strategy_hovered",
            "dashboard_kpi_hovered",
            "dashboard_chart_toggled",
            "survey_item_answered",
        ]
        for action in actions:
            resp = client.post(
                "/log/interaction",
                json={"userid": _uid(), "client": "pytest", "action": action, "value": {}},
                content_type="application/json",
            )
            assert resp.status_code == 200, f"Failed for action: {action}"
