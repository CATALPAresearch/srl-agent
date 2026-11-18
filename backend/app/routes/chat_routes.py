"""Chat / conversation routes: start, reply, reset, history."""
import json

import sqlalchemy as sa
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import datetime

from app import app, db
from ..core import start_conversation_core, reply_core, reset_conversation
from ..database.crud import get_user, get_language_by_id, get_active_run_started_at
from ..models import InterviewAnswer
from ..actions import LogAction
from ..logging_utlis import log_action
from ..identity import effective_user_id

chat_bp = Blueprint('chat', __name__)

# Limits for /reply (each reply triggers several LLM calls): protects the LLM budget against abuse.
MAX_MESSAGE_CHARS = 2000
MAX_MESSAGES_PER_MINUTE = 10
MAX_MESSAGES_PER_INTERVIEW = 50


def _reply_limit_error(user, user_message):
    """Return an error response if a limit is exceeded, else None. Codes are shown in the UI."""
    if len(user_message) > MAX_MESSAGE_CHARS:
        return jsonify({"error": "message_too_long", "limit": MAX_MESSAGE_CHARS}), 413
    if user is None:
        return None
    mine = sa.and_(InterviewAnswer.user_id == user.id, InterviewAnswer.user_client == user.client)
    last_minute = db.session.scalar(
        sa.select(sa.func.count()).select_from(InterviewAnswer).where(
            mine, InterviewAnswer.message_time >= sa.text("LOCALTIMESTAMP - interval '1 minute'"))
    )
    if last_minute >= MAX_MESSAGES_PER_MINUTE:
        resp = jsonify({"error": "rate_limited", "limit": MAX_MESSAGES_PER_MINUTE, "retry_after": 60})
        resp.headers["Retry-After"] = "60"
        return resp, 429
    run_query = sa.select(sa.func.count()).select_from(InterviewAnswer).where(mine)
    run_started_at = get_active_run_started_at(user)
    if run_started_at is not None:
        run_query = run_query.where(InterviewAnswer.message_time >= run_started_at)
    if db.session.scalar(run_query) >= MAX_MESSAGES_PER_INTERVIEW:
        return jsonify({"error": "interview_quota_reached", "limit": MAX_MESSAGES_PER_INTERVIEW}), 429
    return None


@chat_bp.route("/resetConversation", methods=["POST", "OPTIONS"])
@cross_origin()
def delete_message():
    userid = None
    client = None
    try:
        content = request.json or {}
        client = content.get("client")
        userid = effective_user_id()
        if not userid:
            return jsonify({"error": "no identity - call POST /session/identity first"}), 401
        if not client:
            return jsonify({"error": "client required"}), 400
        app.logger.info("Resetting conversation for user: %s - %s", userid, client)
        user = get_user(userid, client)
        if not user:
            return jsonify({"error": "User not found"}), 400
        success = reset_conversation(user)
        if success:
            return (
                "*** Conversation has been reset. "
                "A new conversation can be started from the StudyTest server. ***"
            ), 200
        return jsonify({"error": "Reset failed"}), 500
    except Exception as e:
        app.logger.error("Error on reset conversation: %s - Rolling back DB changes", e)
        db.session.rollback()
        with open("config/translations.json", "r", encoding="utf-8") as file:
            translations = json.load(file)
        user = get_user(userid, client) if userid and client else None
        if user:
            user_lang = get_language_by_id(user.language_id)
            return translations["translations"][user_lang.lang_code]["reply_error"], 200
        return translations["translations"]["en"]["create_error"], 500


@chat_bp.route("/startConversation", methods=['POST'])
@cross_origin()
def start_conversation_flask():
    """
    Post request format:
    {
        "language": "en" or "de",
        "client": "discord",
        "userid": Discord user ID
    }
    """
    language = None
    try:
        content = request.json or {}
        userid = effective_user_id()
        client = content.get("client")
        language = content.get("language")
        if not userid:
            return jsonify({"error": "no identity - call POST /session/identity first"}), 401
        if not client:
            return jsonify({"error": "client required"}), 400
        if not language:
            return jsonify({"error": "language required"}), 400
        app.logger.info(
            "Starting new conversation (%s) for user: %s - %s", language, userid, client
        )

        user = get_user(userid, client)
        log_action(
            LogAction.API_CALL_START,
            user=user,
            value={
                "endpoint": "/startConversation",
                "language": language,
                "client": client,
                "userid": userid,
            },
            http_status=200,
            turn=0,
            step="request_received",
            context="conversation_start",
            strategy="strategy_not_detected",
        )

        return start_conversation_core(language, client, userid)
    except Exception as e:
        app.logger.error("Error on start conversation: %s - Rolling back DB changes", e)
        db.session.rollback()
        log_action(
            LogAction.DB_ROLLBACK,
            value={"error": str(e)},
            http_status=500,
            step="exception_handled",
        )
        with open("config/translations.json", "r", encoding="utf-8") as file:
            translations = json.load(file)
        lang = language or "en"
        return translations["translations"].get(lang, translations["translations"]["en"])["create_error"], 500


@chat_bp.route("/reply", methods=['POST'])
@cross_origin()
def reply():
    """
    Post request format:
    {
        "client": "discord",
        "userid": Discord user ID,
        "message": message
    }
    """
    client_id = None
    userid = None
    try:
        content = request.json or {}
        client_id = content.get("client")
        userid = effective_user_id()
        user_message = content.get("message")
        if not userid:
            return jsonify({"error": "no identity - call POST /session/identity first"}), 401
        if not client_id:
            return jsonify({"error": "client required"}), 400
        if not user_message or not isinstance(user_message, str):
            return jsonify({"error": "message required"}), 400
        limited = _reply_limit_error(get_user(userid, client_id), user_message)
        if limited:
            return limited

        llm_response, status = reply_core(client_id, userid, user_message)
        return llm_response, status

    except Exception as e:
        app.logger.error("Error on reply: %s - Rolling back DB changes", e)
        db.session.rollback()

        user = get_user(userid, client_id) if userid and client_id else None
        log_action(
            LogAction.DB_ROLLBACK,
            user=user,
            value={"error": str(e)},
            http_status=500,
            step="exception_handled",
        )

        with open("config/translations.json", "r", encoding="utf-8") as file:
            translations = json.load(file)

        if user:
            user_lang = get_language_by_id(user.language_id)
            return translations["translations"][user_lang.lang_code]["reply_error"], 200
        return translations["translations"]["en"]["create_error"], 500


@chat_bp.route("/conversation", methods=["GET"])
@cross_origin()
def get_conversation():
    """Return the full conversation history for a user, ordered chronologically.

    Query params: userid, client
    Response: { "messages": [{"author": "user"|"bot", "message": "...", "id": <int>}, ...] }
    """
    userid = effective_user_id(request.args.get("userid"), allow_admin_override=True)
    client = request.args.get("client")
    if not userid:
        return jsonify({"error": "no identity - call POST /session/identity first"}), 401
    if not client:
        return jsonify({"messages": []}), 400

    try:
        reset_ts = db.session.scalar(sa.text("""
            SELECT timestamp
            FROM activity_log
            WHERE user_id = :uid
              AND user_client = :client
              AND action = 'reset_conversation'
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"uid": userid, "client": client})

        boundary = None
        if reset_ts is not None:
            boundary = datetime.datetime.fromtimestamp(int(reset_ts))

        user_rows = db.session.execute(sa.text("""
            SELECT turn, message, message_time, 'user' AS author
            FROM interview_answer
            WHERE user_id = :uid AND user_client = :client
        """), {"uid": userid, "client": client}).fetchall()

        bot_rows = db.session.execute(sa.text("""
            SELECT turn, message, message_time, 'bot' AS author
            FROM llm_response
            WHERE user_id = :uid AND user_client = :client
        """), {"uid": userid, "client": client}).fetchall()

        all_rows = [
            {"turn": r[0], "message": r[1], "time": r[2], "author": r[3]}
            for r in (list(user_rows) + list(bot_rows))
        ]
        if boundary is not None:
            all_rows = [r for r in all_rows if r["time"] is not None and r["time"] >= boundary]
        # Sort by timestamp; within same turn put user message before bot reply
        all_rows.sort(key=lambda r: (r["time"], 0 if r["author"] == "user" else 1))

        messages = [
            {"author": r["author"], "message": r["message"], "id": i + 1}
            for i, r in enumerate(all_rows)
        ]
        return jsonify({"messages": messages}), 200

    except Exception as e:
        app.logger.error("Error fetching conversation: %s", e)
        db.session.rollback()
        return jsonify({"messages": []}), 500
