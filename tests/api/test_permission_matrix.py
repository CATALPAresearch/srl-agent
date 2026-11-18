"""Role x endpoint permission matrix.

Every registered route appears in ENDPOINTS with the policy that should apply to it.
Expected outcomes: ALLOW (status is neither 401 nor 403), 401 (no/invalid identity),
403 (valid identity, insufficient role). A guard test fails when a route is added
without a matrix entry.

Roles: anonymous, student (standalone), lti_student (course A), teacher (course A),
admin (admin session, no identity token), unknown_role (signed token, role "superuser").
"""
import pytest

pytestmark = pytest.mark.usefixtures("isolated_db")

ALLOW, UNAUTHENTICATED, FORBIDDEN = "allow", 401, 403
ROLES = ["anonymous", "student", "lti_student", "teacher", "admin", "unknown_role"]

ROLE_IS_NOT_CHECKED = (
    "unknown roles are not rejected: any signed identity counts as a participant "
    "(defense in depth - the server itself only issues 'student'/'teacher')"
)
WRONG_STATUS_FOR_ROLE = "insufficient role answers 401 instead of 403 (admin_required/staff_required)"

# Policy name -> expected outcome per role.
POLICIES = {
    # reachable by anyone (static files, questionnaire definition, defaults, identity bootstrap)
    "public": dict.fromkeys(ROLES, ALLOW),
    # credential endpoints: called with invalid credentials, so everyone gets 401
    "credentials": dict.fromkeys(ROLES, UNAUTHENTICATED),
    # needs a participant identity; admins (no identity token) are rejected
    "participant": {"anonymous": UNAUTHENTICATED, "student": ALLOW, "lti_student": ALLOW,
                    "teacher": ALLOW, "admin": UNAUTHENTICATED, "unknown_role": FORBIDDEN},
    # participant data that admins may read for a given ?userid=
    "participant_or_admin_read": {"anonymous": UNAUTHENTICATED, "student": ALLOW, "lti_student": ALLOW,
                                  "teacher": ALLOW, "admin": ALLOW, "unknown_role": FORBIDDEN},
    # dashboard: admins and verified teachers
    "staff": {"anonymous": UNAUTHENTICATED, "student": FORBIDDEN, "lti_student": FORBIDDEN,
              "teacher": ALLOW, "admin": ALLOW, "unknown_role": FORBIDDEN},
    # course-wide raw export: admins only
    "admin": {"anonymous": UNAUTHENTICATED, "student": FORBIDDEN, "lti_student": FORBIDDEN,
              "teacher": FORBIDDEN, "admin": ALLOW, "unknown_role": FORBIDDEN},
}

TARGET = "?userid=matrix_target_user&client=web"
BODY = {"client": "web", "userid": "matrix_target_user", "language": "de", "message": "Hallo",
        "lang": "de", "responses": {"q1": 3}, "event": "tab_hidden", "path": "/",
        "action": "strategy_hovered", "traces": [], "password": "wrong-password"}

# (method, rule) -> (request path, policy)
ENDPOINTS = {
    ("GET", "/"): ("/", "public"),
    ("GET", "/health"): ("/health", "public"),
    ("GET", "/frontend/<path:filename>"): ("/frontend/app.js", "public"),
    ("GET", "/static/<path:filename>"): ("/static/does-not-exist.css", "public"),
    ("GET", "/static/lti/<path:filename>"): ("/static/lti/index.html", "public"),
    ("GET", "/static/favicon.ico"): ("/static/favicon.ico", "public"),
    ("GET", "/translations/<lang>"): ("/translations/de", "public"),
    ("GET", "/survey/<survey_id>"): ("/survey/srl-o", "public"),
    ("GET", "/user_language/"): ("/user_language/" + TARGET, "public"),
    ("GET", "/user_role/"): ("/user_role/", "public"),
    ("GET", "/admin/status"): ("/admin/status", "public"),
    ("POST", "/admin/logout"): ("/admin/logout", "public"),
    ("POST", "/session/identity"): ("/session/identity", "public"),
    ("POST", "/admin/login"): ("/admin/login", "credentials"),
    ("POST", "/lti/launch"): ("/lti/launch", "credentials"),
    ("GET", "/session/identity"): ("/session/identity", "participant"),
    ("POST", "/startConversation"): ("/startConversation", "participant"),
    ("POST", "/reply"): ("/reply", "participant"),
    ("POST", "/resetConversation"): ("/resetConversation", "participant"),
    ("PUT", "/user_language/"): ("/user_language/", "participant"),
    ("POST", "/survey/<survey_id>/submit"): ("/survey/srl-o/submit", "participant"),
    ("POST", "/log/interaction"): ("/log/interaction", "participant"),
    ("POST", "/log/mouse_traces"): ("/log/mouse_traces", "participant"),
    ("POST", "/log/page_view"): ("/log/page_view", "participant"),
    ("POST", "/log/tab_event"): ("/log/tab_event", "participant"),
    ("GET", "/conversation"): ("/conversation" + TARGET, "participant_or_admin_read"),
    ("GET", "/student/results"): ("/student/results" + TARGET, "participant_or_admin_read"),
    ("GET", "/student/interview_runs"): ("/student/interview_runs" + TARGET, "participant_or_admin_read"),
    ("GET", "/dashboard/stats"): ("/dashboard/stats", "staff"),
    ("GET", "/dashboard/courses"): ("/dashboard/courses", "staff"),
    ("GET", "/survey/<survey_id>/results"): ("/survey/srl-o/results", "admin"),
}

# Rows where the application deviates from the policy (suspected vulnerabilities).
KNOWN_DEVIATIONS = {}
for (_method, _rule), (_path, _policy) in ENDPOINTS.items():
    if POLICIES[_policy]["unknown_role"] == FORBIDDEN and _policy in ("participant", "participant_or_admin_read"):
        KNOWN_DEVIATIONS[(_method, _rule, "unknown_role")] = ROLE_IS_NOT_CHECKED
    if _policy in ("staff", "admin"):
        for _role, _outcome in POLICIES[_policy].items():
            if _outcome == FORBIDDEN:
                KNOWN_DEVIATIONS[(_method, _rule, _role)] = WRONG_STATUS_FOR_ROLE


def _matrix_params():
    for (method, rule), (path, policy) in sorted(ENDPOINTS.items(), key=lambda e: (e[0][1], e[0][0])):
        for role in ROLES:
            expected = POLICIES[policy][role]
            reason = KNOWN_DEVIATIONS.get((method, rule, role))
            marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
            yield pytest.param(method, path, role, expected, marks=marks,
                               id=f"{method} {rule} as {role} -> {expected}")


def _assert_outcome(status, expected):
    if expected == ALLOW:
        assert status not in (401, 403), f"denied with {status}"
    else:
        assert status == expected


@pytest.mark.parametrize("method, path, role, expected", list(_matrix_params()))
def test_role_endpoint_matrix(client_as, make_user, method, path, role, expected):
    client = client_as(make_user(role))

    response = client.open(path, method=method, json=BODY)

    _assert_outcome(response.status_code, expected)


def test_every_registered_route_is_in_the_matrix(flask_app):
    registered = {(method, rule.rule)
                  for rule in flask_app.url_map.iter_rules()
                  for method in rule.methods - {"HEAD", "OPTIONS"}}

    assert registered == set(ENDPOINTS), {
        "missing in matrix": sorted(registered - set(ENDPOINTS)),
        "stale in matrix": sorted(set(ENDPOINTS) - registered),
    }


# --- denied writes have no side effects --------------------------------------

DENIED_WRITES = [
    pytest.param("POST", "/startConversation", id="startConversation"),
    pytest.param("POST", "/reply", id="reply"),
    pytest.param("POST", "/resetConversation", id="resetConversation"),
    pytest.param("PUT", "/user_language/", id="user_language"),
    pytest.param("POST", "/survey/srl-o/submit", id="survey_submit"),
    pytest.param("POST", "/log/interaction", id="log_interaction"),
    pytest.param("POST", "/log/mouse_traces", id="log_mouse_traces"),
    pytest.param("POST", "/log/page_view", id="log_page_view"),
    pytest.param("POST", "/log/tab_event", id="log_tab_event"),
]


@pytest.mark.parametrize("method, path", DENIED_WRITES)
def test_anonymous_write_leaves_database_unchanged(client_as, make_user, db_snapshot, method, path):
    client = client_as(make_user("anonymous"))
    before = db_snapshot()

    response = client.open(path, method=method, json=BODY)

    assert response.status_code == 401
    assert db_snapshot() == before


@pytest.mark.parametrize("method, path", DENIED_WRITES)
def test_admin_session_without_identity_write_leaves_database_unchanged(
        client_as, make_user, db_snapshot, method, path):
    client = client_as(make_user("admin"))
    before = db_snapshot()

    response = client.open(path, method=method, json=BODY)

    assert response.status_code == 401
    assert db_snapshot() == before


def test_failed_admin_login_does_not_grant_admin(client_as, make_user):
    client = client_as(make_user("student"))

    client.post("/admin/login", json={"password": "wrong-password"})

    assert client.get("/admin/status").get_json() == {"is_admin": False}
