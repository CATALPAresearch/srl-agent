"""Object-level authorization (IDOR / BOLA).

Convention of this API: a userid in the request is ignored for participants; every
request acts on the caller's own identity. Accessing another user's object therefore
does not answer 403/404 - it answers with the caller's own (usually empty) data and
must neither reveal nor change the other user's data. Admins may read a user explicitly.
"""
import pytest
import sqlalchemy as sa

pytestmark = pytest.mark.usefixtures("isolated_db")

OWNER_MESSAGE = "Ich schreibe Zusammenfassungen."  # sent by the owned_interview fixture


@pytest.fixture
def owner(make_user, owned_interview):
    return owned_interview(make_user("lti_student", course="authz_course_a"))


@pytest.fixture
def attacker(client_as, make_user):
    return client_as(make_user("student"))


def answers_of(db, uid):
    return db.session.execute(sa.text(
        "SELECT message FROM interview_answer WHERE user_id = :uid ORDER BY message_time"), {"uid": uid}
    ).scalars().all()


def language_of(db, uid):
    return db.session.execute(sa.text(
        "SELECT l.lang_code FROM users u JOIN languages l ON l.id = u.language_id WHERE u.id = :uid"),
        {"uid": uid}).scalar()


def survey_count_of(db, uid):
    return db.session.execute(sa.text(
        "SELECT COUNT(*) FROM survey_responses WHERE user_id = :uid"), {"uid": uid}).scalar()


def activity_count_of(db, uid):
    return db.session.execute(sa.text(
        "SELECT COUNT(*) FROM activity_log WHERE user_id = :uid AND action NOT LIKE 'audit_%'"),
        {"uid": uid}).scalar()


# --- read ------------------------------------------------------------------

def test_attacker_cannot_read_owners_conversation(owner, attacker):
    response = attacker.get(f"/conversation?userid={owner.uid}&client=web")

    assert OWNER_MESSAGE not in response.get_data(as_text=True)


def test_attacker_reading_owners_conversation_gets_own_empty_history(owner, attacker):
    response = attacker.get(f"/conversation?userid={owner.uid}&client=web")

    assert response.get_json() == {"messages": []}


def test_owner_reads_own_conversation(owner, client_as):
    response = client_as(owner).get("/conversation?client=web")

    assert OWNER_MESSAGE in response.get_data(as_text=True)


def test_attacker_cannot_read_owners_results(owner, attacker):
    body = attacker.get(f"/student/results?userid={owner.uid}&client=web").get_json()

    assert body["answers_count"] == 0


def test_attacker_cannot_read_owners_interview_runs(owner, attacker):
    body = attacker.get(f"/student/interview_runs?userid={owner.uid}&client=web").get_json()

    assert body["active_run"] is None


def test_teacher_cannot_read_student_conversation_by_userid(owner, client_as, make_user):
    teacher = client_as(make_user("teacher", course="authz_course_a"))

    response = teacher.get(f"/conversation?userid={owner.uid}&client=web")

    assert OWNER_MESSAGE not in response.get_data(as_text=True)


def test_admin_can_read_owners_conversation_explicitly(owner, client_as, make_user):
    admin = client_as(make_user("admin"))

    response = admin.get(f"/conversation?userid={owner.uid}&client=web")

    assert OWNER_MESSAGE in response.get_data(as_text=True)


# --- update ----------------------------------------------------------------

def test_attacker_reply_does_not_reach_owners_interview(owner, attacker, db):
    attacker.post("/reply", json={"userid": owner.uid, "client": "web", "message": "hijack"})

    assert answers_of(db, owner.uid) == [OWNER_MESSAGE]


def test_attacker_cannot_change_owners_language(owner, attacker, db):
    attacker.put("/user_language/", json={"userid": owner.uid, "client": "web", "lang": "en"})

    assert language_of(db, owner.uid) == "de"


def test_attacker_survey_submission_is_not_stored_for_owner(owner, attacker, db):
    attacker.post("/survey/srl-o/submit",
                  json={"userid": owner.uid, "client": "web", "language": "de", "responses": {"q1": 1}})

    assert survey_count_of(db, owner.uid) == 1


def test_attacker_telemetry_is_not_logged_for_owner(owner, attacker, db):
    before = activity_count_of(db, owner.uid)

    attacker.post("/log/page_view", json={"userid": owner.uid, "client": "web", "path": "/"})

    assert activity_count_of(db, owner.uid) == before


# --- delete ----------------------------------------------------------------

def test_attacker_cannot_reset_owners_interview(owner, attacker, db):
    attacker.post("/resetConversation", json={"userid": owner.uid, "client": "web"})

    assert answers_of(db, owner.uid) == [OWNER_MESSAGE]


def test_attacker_reset_leaves_owners_conversation_visible(owner, attacker, client_as):
    attacker.post("/resetConversation", json={"userid": owner.uid, "client": "web"})

    assert OWNER_MESSAGE in client_as(owner).get("/conversation?client=web").get_data(as_text=True)


# --- lists -----------------------------------------------------------------

@pytest.fixture
def two_courses(make_user, owned_interview):
    owned_interview(make_user("lti_student", course="authz_course_a"))
    owned_interview(make_user("lti_student", course="authz_course_b"))
    owned_interview(make_user("lti_student", course="authz_course_b"))


def test_teacher_course_list_contains_only_own_course(two_courses, client_as, make_user):
    teacher = client_as(make_user("teacher", course="authz_course_a"))

    courses = teacher.get("/dashboard/courses").get_json()

    assert [c["id"] for c in courses] == ["authz_course_a"]


def test_teacher_stats_count_only_own_course(two_courses, client_as, make_user):
    teacher = client_as(make_user("teacher", course="authz_course_a"))

    stats = teacher.get("/dashboard/stats").get_json()

    assert stats["total_students"] == 1


def test_teacher_cannot_switch_course_via_filter(two_courses, client_as, make_user):
    teacher = client_as(make_user("teacher", course="authz_course_a"))

    stats = teacher.get("/dashboard/stats?course_id=authz_course_b").get_json()

    assert stats["total_students"] == 1


def test_teacher_of_empty_course_sees_no_students(two_courses, client_as, make_user):
    teacher = client_as(make_user("teacher", course="authz_course_empty"))

    stats = teacher.get("/dashboard/stats").get_json()

    assert stats["total_students"] == 0


def test_admin_course_filter_selects_that_course(two_courses, client_as, make_user):
    admin = client_as(make_user("admin"))

    stats = admin.get("/dashboard/stats?course_id=authz_course_b").get_json()

    assert stats["total_students"] == 2
