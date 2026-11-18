"""Researcher / teacher dashboard routes.

Access: admins see all courses (optional ?course_id= filter). Teachers (verified LTI
launch) are always restricted to the course from their server-issued identity; any
course_id they send is ignored.
"""
import sqlalchemy as sa
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from app import app, db
from ..identity import current_identity, is_admin
from ..models import (
    User, ConversationState, SurveyResponse, Language,
)
from .admin_routes import staff_required

dashboard_bp = Blueprint('dashboard', __name__)

_EMPTY_STATS = {
    "total_students": 0, "total_completed": 0,
    "avg_duration_minutes": 0, "var_duration_minutes": 0,
    "std_duration_minutes": 0, "avg_response_time_seconds": 0,
    "survey_count": 0, "reattempts": 0,
    "avg_turns_completed": 0, "avg_turns_incomplete": 0,
    "dropoff_distribution": [], "strategy_distribution": [],
    "language_distribution": [], "avg_messages_per_interview": 0,
    "completion_funnel": [], "weekly_activity": [],
    "response_time_by_step": [], "total_messages": 0,
    "survey_avg_scores": [], "last_activity": None, "avg_response_gap_seconds": 0,
}


def _course_scope():
    """The course the caller may see: None = all courses (admins only)."""
    if is_admin():
        return request.args.get("course_id") or None
    return str(current_identity()["context_id"])


def _int_arg(name):
    value = request.args.get(name)
    return int(value) if value not in (None, "") else None


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
@cross_origin()
@staff_required
def get_dashboard_stats():
    """Aggregated statistics for the dashboards.
    Optional query params: date_from, date_to (Unix timestamps), course_id (admins only)
    """
    try:
        course = _course_scope()
        date_from = _int_arg("date_from")
        date_to = _int_arg("date_to")

        # interview_answer date window, used by message-based statistics
        ia_date = ""
        params = {}
        if date_from is not None:
            ia_date += " AND message_time >= to_timestamp(:date_from)"
            params["date_from"] = date_from
        if date_to is not None:
            ia_date += " AND message_time <= to_timestamp(:date_to)"
            params["date_to"] = date_to

        # users in scope (course + date window); every statistic below is limited to them
        scope_sql = "SELECT id FROM users WHERE 1=1"
        if course is not None:
            scope_sql += " AND context_id = :course"
            params["course"] = course
        if ia_date:
            scope_sql += f" AND id IN (SELECT DISTINCT user_id FROM interview_answer WHERE 1=1 {ia_date})"
        ids = [r[0] for r in db.session.execute(sa.text(scope_sql), params).fetchall()]
        if not ids:
            return jsonify(_EMPTY_STATS), 200
        p = {**params, "ids": ids}
        in_scope = "user_id = ANY(:ids)"

        def scalar(sql):
            return db.session.execute(sa.text(sql), p).scalar()

        def rows(sql):
            return db.session.execute(sa.text(sql), p).fetchall()

        # 1. Total unique students
        total_students = len(set(ids))

        # 2. Completed interviews
        total_completed = scalar(f"""
            SELECT COUNT(*) FROM state WHERE interview_completed = true AND {in_scope}
        """) or 0

        # 3. Avg interview duration + variance + std deviation
        duration_result = rows(f"""
            SELECT
                AVG(EXTRACT(epoch FROM last_time) - EXTRACT(epoch FROM first_time)),
                VARIANCE(EXTRACT(epoch FROM last_time) - EXTRACT(epoch FROM first_time)),
                STDDEV(EXTRACT(epoch FROM last_time) - EXTRACT(epoch FROM first_time))
            FROM (
                SELECT user_id, MIN(message_time) as first_time, MAX(message_time) as last_time
                FROM interview_answer
                WHERE {in_scope} {ia_date}
                GROUP BY user_id
            ) t
        """)[0]
        avg_duration_minutes = round(float(duration_result[0]) / 60, 1) if duration_result[0] else 0
        var_duration_minutes = round(float(duration_result[1]) / 3600, 1) if duration_result[1] else 0
        std_duration_minutes = round(float(duration_result[2]) / 60, 1) if duration_result[2] else 0

        # 4. Avg LLM response time (REPLY_LLM.timestamp - REPLY_USER.timestamp, same turn)
        try:
            result = scalar("""
                SELECT AVG(llm.timestamp - usr.timestamp)
                FROM activity_log llm
                JOIN activity_log usr
                  ON llm.user_id = usr.user_id
                 AND llm.turn    = usr.turn
                WHERE llm.action = 'reply_llm'
                  AND usr.action = 'reply_user'
                  AND llm.timestamp > usr.timestamp
                  AND llm.user_id = ANY(:ids)
            """)
            avg_response_time = round(float(result), 1) if result else 0
        except Exception:
            db.session.rollback()
            avg_response_time = 0

        # 5. Survey responses count + avg scores per question
        try:
            survey_rows = db.session.query(SurveyResponse).filter(SurveyResponse.user_id.in_(ids)).all()
            survey_count = len(survey_rows)
            survey_avg_scores_map: dict[str, list] = {}
            for row in survey_rows:
                if row.responses:
                    for key, val in row.responses.items():
                        if isinstance(val, (int, float)):
                            survey_avg_scores_map.setdefault(key, []).append(val)
            survey_avg_scores = [
                {"question": k, "avg": round(sum(v) / len(v), 2)}
                for k, v in survey_avg_scores_map.items()
            ]
        except Exception:
            db.session.rollback()
            survey_count = 0
            survey_avg_scores = []

        # 6. Drop-off analysis
        dropoff_rows = db.session.query(
            ConversationState.current_conversation_step,
            sa.func.count(ConversationState.id).label("count")
        ).filter(
            ConversationState.interview_completed.is_(False),
            ConversationState.user_id.in_(ids),
        ).group_by(ConversationState.current_conversation_step).all()
        dropoff_distribution = [
            {"step": row.current_conversation_step or "not_started", "count": row.count}
            for row in dropoff_rows
        ]

        # 7. Strategy distribution with English names
        strategy_rows = rows("""
            SELECT us.strategy, COUNT(*) as count,
                COALESCE(
                    (SELECT st2.name FROM strategy_translation st2
                     JOIN languages l2 ON l2.id = st2.language_id
                     WHERE st2.strategy = us.strategy AND l2.lang_code = 'en'
                     LIMIT 1),
                    (SELECT st3.name FROM strategy_translation st3
                     JOIN languages l3 ON l3.id = st3.language_id
                     WHERE st3.strategy = us.strategy AND l3.lang_code = 'de'
                     LIMIT 1),
                    us.strategy
                ) as strategy_name
            FROM user_strategy us
            WHERE us.user_id = ANY(:ids)
            GROUP BY us.strategy
            ORDER BY count DESC
        """)
        strategy_distribution = [
            {"strategy": row[0], "name": row[2], "count": row[1]}
            for row in strategy_rows
        ]

        # 8. Re-attempts
        reattempt_rows = scalar(f"""
            SELECT COUNT(*) FROM (
                SELECT user_id FROM state WHERE {in_scope}
                GROUP BY user_id HAVING COUNT(*) > 1
            ) t
        """) or 0

        # 9. Avg turns completed vs incomplete
        avg_turns_completed = db.session.query(
            sa.func.avg(ConversationState.current_turn)
        ).filter(
            ConversationState.interview_completed.is_(True),
            ConversationState.user_id.in_(ids),
        ).scalar()
        avg_turns_completed = round(float(avg_turns_completed), 1) if avg_turns_completed else 0

        avg_turns_incomplete = db.session.query(
            sa.func.avg(ConversationState.current_turn)
        ).filter(
            ConversationState.interview_completed.is_(False),
            ConversationState.user_id.in_(ids),
        ).scalar()
        avg_turns_incomplete = round(float(avg_turns_incomplete), 1) if avg_turns_incomplete else 0

        # 10. Language distribution
        lang_rows = db.session.query(
            Language.lang_code,
            sa.func.count(User.id).label("count")
        ).join(Language, User.language_id == Language.id).filter(
            User.id.in_(ids)
        ).group_by(Language.lang_code).all()
        language_distribution = [
            {"language": row.lang_code, "count": row.count}
            for row in lang_rows
        ]

        # 11. Avg messages per interview
        avg_messages = scalar(f"""
            SELECT AVG(msg_count) FROM (
                SELECT user_id, COUNT(*) as msg_count
                FROM interview_answer WHERE {in_scope} {ia_date}
                GROUP BY user_id
            ) t
        """)
        avg_messages = round(float(avg_messages), 1) if avg_messages else 0

        # 12. Total messages sent
        total_messages = scalar(f"""
            SELECT COUNT(*) FROM interview_answer WHERE {in_scope} {ia_date}
        """) or 0

        # 13. Completion funnel
        funnel = []
        for step in ['intro', 'strategy', 'frequency', 'complete']:
            count = db.session.execute(sa.text(f"""
                SELECT COUNT(DISTINCT user_id) FROM interview_answer
                WHERE conversation_step = :step AND {in_scope} {ia_date}
            """), {**p, "step": step}).scalar() or 0
            funnel.append({"step": step, "count": count})

        # 14. Weekly activity
        weekly_rows = rows(f"""
            SELECT
                DATE_TRUNC('week', message_time) as week,
                COUNT(*) as messages,
                COUNT(DISTINCT user_id) as users
            FROM interview_answer
            WHERE {in_scope} {ia_date}
            GROUP BY DATE_TRUNC('week', message_time)
            ORDER BY week
        """)
        weekly_activity = [
            {"week": str(row[0])[:10] if row[0] else "", "messages": row[1], "users": row[2]}
            for row in weekly_rows
        ]

        # 15. Avg response time by step (REPLY_LLM - REPLY_USER on same user+turn)
        try:
            step_response = rows("""
                SELECT llm.step, AVG(llm.timestamp - usr.timestamp) as avg_time
                FROM activity_log llm
                JOIN activity_log usr
                  ON llm.user_id = usr.user_id
                 AND llm.turn    = usr.turn
                WHERE llm.action = 'reply_llm'
                  AND usr.action = 'reply_user'
                  AND llm.timestamp > usr.timestamp
                  AND llm.user_id = ANY(:ids)
                GROUP BY llm.step
            """)
            response_time_by_step = [
                {"step": row[0], "avg_seconds": round(float(row[1]), 1) if row[1] else 0}
                for row in step_response
            ]
        except Exception:
            db.session.rollback()
            response_time_by_step = []

        # 16. Last activity
        last_activity = scalar(f"""
            SELECT MAX(message_time) FROM interview_answer WHERE {in_scope} {ia_date}
        """)
        last_activity_str = last_activity.strftime("%Y-%m-%d %H:%M") if last_activity else None

        # 17. Avg time between student responses (thinking time proxy)
        try:
            gap_result = scalar(f"""
                SELECT AVG(gap_seconds) FROM (
                    SELECT
                        EXTRACT(epoch FROM message_time - LAG(message_time)
                            OVER (PARTITION BY user_id ORDER BY message_time)) as gap_seconds
                    FROM interview_answer
                    WHERE {in_scope} {ia_date}
                ) t
                WHERE gap_seconds > 0 AND gap_seconds < 3600
            """)
            avg_response_gap = round(float(gap_result), 1) if gap_result else 0
        except Exception:
            db.session.rollback()
            avg_response_gap = 0

        return jsonify({
            "total_students": total_students,
            "total_completed": total_completed,
            "avg_duration_minutes": avg_duration_minutes,
            "var_duration_minutes": var_duration_minutes,
            "std_duration_minutes": std_duration_minutes,
            "avg_response_time_seconds": avg_response_time,
            "survey_count": survey_count,
            "survey_avg_scores": survey_avg_scores,
            "reattempts": int(reattempt_rows),
            "avg_turns_completed": avg_turns_completed,
            "avg_turns_incomplete": avg_turns_incomplete,
            "dropoff_distribution": dropoff_distribution,
            "strategy_distribution": strategy_distribution,
            "language_distribution": language_distribution,
            "avg_messages_per_interview": avg_messages,
            "total_messages": total_messages,
            "completion_funnel": funnel,
            "weekly_activity": weekly_activity,
            "response_time_by_step": response_time_by_step,
            "last_activity": last_activity_str,
            "avg_response_gap_seconds": avg_response_gap,
        }), 200

    except ValueError:
        return jsonify({"error": "date_from/date_to must be Unix timestamps"}), 400
    except Exception as e:
        app.logger.error("Error fetching dashboard stats: %s", e)
        db.session.rollback()
        return jsonify({"error": "Could not load dashboard statistics"}), 500


@dashboard_bp.route("/dashboard/courses", methods=["GET"])
@cross_origin()
@staff_required
def get_dashboard_courses():
    """Courses from LTI context data: all for admins, only their own for teachers."""
    try:
        sql = """
            SELECT context_id, context_title, COUNT(*) as students
            FROM users
            WHERE context_id IS NOT NULL {course_filter}
            GROUP BY context_id, context_title
            ORDER BY students DESC
        """
        params = {}
        course_filter = ""
        if not is_admin():
            course_filter = "AND context_id = :course"
            params["course"] = str(current_identity()["context_id"])
        rows = db.session.execute(sa.text(sql.format(course_filter=course_filter)), params).fetchall()
        return jsonify([
            {"id": r[0], "name": r[1] or ("No course (standalone)" if r[0] == "0" else r[0]), "students": r[2]}
            for r in rows
        ]), 200
    except Exception:
        db.session.rollback()
        return jsonify([]), 200
