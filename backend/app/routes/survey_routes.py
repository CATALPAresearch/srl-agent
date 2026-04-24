"""Survey and student-results routes."""
import ast
import json
import os
import uuid

import sqlalchemy as sa
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from app import app, db
from ..config import get_interview_config_path
from ..core import trigger_summary_generation_if_needed
from ..database.crud import get_user, get_language_by_id
from ..models import (
    SurveyResponse, UserStrategy, StrategyTranslation, Language,
    ConversationState, Context, Archive,
)
from ._paths import CONFIG_DIR

survey_bp = Blueprint('survey', __name__)


def _load_user_archives(user_id: str, user_client: str) -> list:
    """Return archived conversations for a user as a list of (archive_id, payload) tuples."""
    rows = db.session.scalars(
        sa.select(Archive)
        .where(sa.text("archived_conversation::jsonb->>'user_id' = :uid"))
        .where(sa.text("archived_conversation::jsonb->>'user_client' = :client"))
        .params(uid=user_id, client=user_client)
        .order_by(Archive.id.desc())
    ).all()
    result = []
    for row in rows:
        try:
            payload = json.loads(row.archived_conversation)
        except Exception:
            try:
                payload = ast.literal_eval(row.archived_conversation)
            except Exception:
                payload = None
        if isinstance(payload, dict):
            result.append((row.id, payload))
    return result


@survey_bp.route("/survey/<survey_id>", methods=["GET"])
@cross_origin()
def get_survey(survey_id):
    """
    Return the survey definition JSON for the given survey_id.
    Query params:
        - lang: language code (en, de). If not provided, uses user's language_id.
        - userid: user ID (required if lang not provided)
        - client: client identifier (required if lang not provided)
    Default language: de
    """
    safe_name = os.path.basename(survey_id)  # prevent path traversal

    lang = request.args.get('lang')
    if not lang:
        userid = request.args.get('userid')
        client = request.args.get('client')
        if userid and client:
            user = get_user(userid, client)
            if user:
                user_lang = get_language_by_id(user.language_id)
                lang = user_lang.lang_code if user_lang else 'de'
            else:
                lang = 'de'
        else:
            lang = 'de'

    # Try language-specific file first, fall back to generic bilingual file
    path = os.path.join(CONFIG_DIR, f"survey_{safe_name}_{lang}.json")
    if not os.path.isfile(path):
        path = os.path.join(CONFIG_DIR, f"survey_{safe_name}.json")

    if not os.path.isfile(path):
        return jsonify({"error": "Survey not found"}), 404

    with open(path, "r", encoding="utf-8") as f:
        survey = json.load(f)
    return jsonify(survey), 200


@survey_bp.route("/survey/<survey_id>/submit", methods=["POST", "OPTIONS"])
@cross_origin()
def submit_survey(survey_id):
    """
    Store a completed survey.
    Expected JSON body:
    {
        "userid": "...",
        "client": "...",
        "language": "en",
        "responses": { "oase_1": 4, "oase_2": 5, ... }
    }
    """
    try:
        content = request.json
        user_id = content["userid"]
        client = content["client"]
        language = content.get("language", "en")
        responses = content["responses"]

        entry = SurveyResponse(
            id=str(uuid.uuid4()),
            survey_id=survey_id,
            user_id=user_id,
            user_client=client,
            language=language,
            responses=responses,
        )
        db.session.add(entry)
        db.session.commit()

        # Ensure summary generation is triggered for completed interviews,
        # even if the survey payload used a different client identifier.
        requested_user = get_user(user_id, client)
        resolved_client = client
        if requested_user is None:
            for candidate in ("web", "standalone"):
                candidate_user = get_user(user_id, candidate)
                if candidate_user is not None:
                    resolved_client = candidate
                    break

        summary_trigger = trigger_summary_generation_if_needed(user_id, resolved_client)

        app.logger.info("Survey %s submitted by user %s/%s", survey_id, user_id, client)
        return jsonify({
            "status": "ok",
            "id": entry.id,
            "summary_trigger": summary_trigger,
            "resolved_client": resolved_client,
        }), 201

    except Exception as e:
        app.logger.error("Error saving survey response: %s", e)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@survey_bp.route("/student/results", methods=["GET"])
@cross_origin()
def get_student_results():
    """
    Return interview strategies and survey responses for a single student.
    Query params: userid, client, lang (optional UI language override for radar_data)
    """
    userid = request.args.get("userid")
    client = request.args.get("client", "standalone")
    ui_lang = request.args.get("lang")   # optional language override for radar labels
    if not userid:
        return jsonify({"error": "userid required"}), 400

    user_archives = [payload for _, payload in _load_user_archives(userid, client)]

    user = get_user(userid, client)
    if not user:
        completed_runs = sum(
            1 for item in user_archives if bool((item.get("state") or {}).get("complete"))
        )
        last_progress_done = 0
        last_progress_total = 0
        if user_archives:
            latest_state = (user_archives[0].get("state") or {})
            last_progress_done = int(latest_state.get("completed_contexts") or 0)
            last_progress_total = int(latest_state.get("total_contexts") or 0)

        return jsonify({
            "strategies": [],
            "survey": None,
            "interview_completed": False,
            "answers_count": 0,
            "total_contexts": 0,
            "completed_runs": completed_runs,
            "last_progress_done": last_progress_done,
            "last_progress_total": last_progress_total,
        }), 200

    user_lang = get_language_by_id(user.language_id)
    lang_id = user_lang.id if user_lang else None

    # --- Strategies mentioned by this user ---
    rows = db.session.execute(
        db.select(UserStrategy, StrategyTranslation)
        .outerjoin(
            StrategyTranslation,
            (StrategyTranslation.strategy == UserStrategy.strategy) &
            (StrategyTranslation.language_id == lang_id)
        )
        .where(UserStrategy.user_id == userid)
        .where(UserStrategy.user_client == client)
    ).all()

    strategies = []
    seen = set()
    for us, st in rows:
        if us.strategy not in seen:
            seen.add(us.strategy)
            strategies.append({
                "id": us.strategy,
                "name": st.name if st else us.strategy,
                "description": st.description if st else "",
                "frequency": us.frequency,
            })

    # --- Latest survey response ---
    survey_row = (
        SurveyResponse.query
        .filter_by(user_id=userid, user_client=client)
        .order_by(SurveyResponse.submitted_at.desc())
        .first()
    )
    survey = None
    if survey_row:
        survey = {
            "survey_id": survey_row.survey_id,
            "language": survey_row.language,
            "submitted_at": survey_row.submitted_at.isoformat() if survey_row.submitted_at else None,
            "responses": survey_row.responses,
        }

    # --- Interview completion status ---
    state = ConversationState.query.filter_by(
        user_id=userid, user_client=client
    ).first()
    interview_completed = bool(state and state.interview_completed)

    # --- Progress: completed contexts vs total contexts ---
    answers_count = len(state.completed_contexts) if state else 0
    total_contexts = (
        db.session.query(Context).filter(Context.language_id == lang_id).count()
        if lang_id else 0
    )

    # --- Archive stats for repeated interview runs ---
    completed_runs = sum(
        1
        for item in user_archives
        if bool((item.get("state") or {}).get("complete"))
    )
    if interview_completed:
        completed_runs += 1

    # Prefer active run progress if user is currently in an interview.
    # Otherwise show the most recent archived run progress.
    current_done = answers_count
    current_total = total_contexts
    if state and (current_done > 0 or state.interview_completed):
        last_progress_done = current_done
        last_progress_total = current_total
    elif user_archives:
        latest = user_archives[0]
        latest_state = latest.get("state") or {}
        last_progress_done = int(latest_state.get("completed_contexts") or 0)
        last_progress_total = int(total_contexts or latest_state.get("total_contexts") or 0)
    else:
        last_progress_done = 0
        last_progress_total = int(total_contexts or 0)

    # --- Radar chart data: all 17 strategies with max frequency ---
    with open(os.path.join(CONFIG_DIR, "strategy_code_map.json"), "r", encoding="utf-8") as _f:
        code_map = json.load(_f)

    # Determine which language to use for radar labels (UI lang override takes precedence).
    radar_lang_code = ui_lang if ui_lang else (user_lang.lang_code if user_lang else "en")

    # Build strategy_lookup from StrategyTranslation (language-aware name + description).
    # Resolve the lang_id for the radar language.
    radar_lang_obj = db.session.execute(
        sa.select(Language).where(Language.lang_code == radar_lang_code)
    ).scalar_one_or_none()
    radar_lang_id = radar_lang_obj.id if radar_lang_obj else lang_id

    _translations = db.session.execute(
        sa.select(StrategyTranslation).where(StrategyTranslation.language_id == radar_lang_id)
    ).scalars().all() if radar_lang_id else []
    if not _translations:
        _en_lang = db.session.execute(
            sa.select(Language).where(Language.lang_code == "en")
        ).scalar_one_or_none()
        if _en_lang:
            _translations = db.session.execute(
                sa.select(StrategyTranslation).where(StrategyTranslation.language_id == _en_lang.id)
            ).scalars().all()
    strategy_lookup = {
        t.strategy: {"name": t.name, "description": t.description}
        for t in _translations
    }

    # Load definitions from interview JSON (keyed by strategy code + language).
    _interview_json_path = get_interview_config_path()
    try:
        with open(_interview_json_path, "r", encoding="utf-8") as _f:
            _interview_data = json.load(_f)
        _lang_section = _interview_data.get(radar_lang_code) or _interview_data.get("en", {})
        definition_lookup = {
            s["id"]: s.get("definition", "")
            for cat in _lang_section.get("categories", [])
            for s in cat.get("strategies", [])
        }
    except Exception:
        definition_lookup = {}

    # Build frequency map: strategy_id → max frequency across contexts
    freq_map = {}
    for us, _st in rows:
        if us.frequency and int(us.frequency) > 0:
            freq_map[us.strategy] = max(freq_map.get(us.strategy, 0), int(us.frequency))

    # --- Course average: avg frequency per strategy ---
    completed_count = db.session.scalar(
        sa.select(sa.func.count())
        .select_from(ConversationState)
        .where(ConversationState.user_client == client)
        .where(ConversationState.interview_completed == True)
    ) or 1  # avoid divide-by-zero

    peer_rows = db.session.execute(
        sa.text("""
            SELECT strategy, ROUND(SUM(max_freq)::numeric / :count, 2) AS avg_frequency
            FROM (
                SELECT us.user_id, us.strategy, MAX(us.frequency) AS max_freq
                FROM user_strategy us
                JOIN state cs ON cs.user_id = us.user_id AND cs.user_client = us.user_client
                WHERE us.user_client = :client
                  AND cs.interview_completed = true
                  AND us.frequency > 0
                GROUP BY us.user_id, us.strategy
            ) sub
            GROUP BY strategy
        """),
        {"client": client, "count": completed_count},
    ).all()
    avg_map = {r.strategy: float(r.avg_frequency) for r in peer_rows}

    radar_data = []
    for code, sid in code_map.items():
        if code == "008-001":   # skip "other"
            continue
        info = strategy_lookup.get(code, {})
        radar_data.append({
            "id": code,
            "code": code,
            "name": info.get("name", sid),
            "description": info.get("description", ""),
            "definition": definition_lookup.get(code, ""),
            "frequency": freq_map.get(code, 0),
            "avg_frequency": avg_map.get(code, 0),
        })

    return jsonify({
        "strategies": strategies,
        "survey": survey,
        "interview_completed": interview_completed,
        "answers_count": answers_count,
        "total_contexts": total_contexts,
        "completed_runs": completed_runs,
        "last_progress_done": last_progress_done,
        "last_progress_total": last_progress_total,
        "radar_data": radar_data,
    }), 200


@survey_bp.route("/student/interview_runs", methods=["GET"])
@cross_origin()
def get_student_interview_runs():
    """Return interview run metadata (active run + archived runs) for one student."""
    userid = request.args.get("userid")
    client = request.args.get("client", "standalone")
    if not userid:
        return jsonify({"error": "userid required"}), 400

    archive_rows = _load_user_archives(userid, client)
    archived_runs = []
    for archive_id, payload in archive_rows:
        state = payload.get("state") or {}
        archived_runs.append({
            "archive_id": archive_id,
            "archived_at": payload.get("archived_at"),
            "complete": bool(state.get("complete")),
            "completed_contexts": int(state.get("completed_contexts") or 0),
            "total_contexts": int(state.get("total_contexts") or 0),
            "message_count": len(payload.get("messages") or []),
        })

    user = get_user(userid, client)
    active_run = None
    if user and user.conversation_state:
        state = user.conversation_state
        user_lang = get_language_by_id(user.language_id)
        total_contexts = (
            db.session.query(Context).filter(Context.language_id == user_lang.id).count()
            if user_lang else 0
        )
        completed_contexts = len(state.completed_contexts or [])

        last_start_ts = db.session.scalar(sa.text("""
            SELECT timestamp
            FROM activity_log
            WHERE user_id = :uid
              AND user_client = :client
              AND action = 'start_conversation'
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"uid": userid, "client": client})

        active_run = {
            "started_at": int(last_start_ts) if last_start_ts is not None else None,
            "complete": bool(state.interview_completed),
            "current_step": state.current_conversation_step,
            "current_turn": int(state.current_turn or 0),
            "completed_contexts": int(completed_contexts),
            "total_contexts": int(total_contexts),
        }

    completed_runs = sum(1 for r in archived_runs if r["complete"]) + (
        1 if active_run and active_run["complete"] else 0
    )

    return jsonify({
        "userid": userid,
        "client": client,
        "completed_runs": completed_runs,
        "active_run": active_run,
        "archived_runs": archived_runs,
    }), 200


@survey_bp.route("/survey/<survey_id>/results", methods=["GET"])
@cross_origin()
def get_survey_results(survey_id):
    """Return all responses for a given survey (admin/research endpoint)."""
    rows = SurveyResponse.query.filter_by(survey_id=survey_id).all()
    results = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_client": r.user_client,
            "language": r.language,
            "responses": r.responses,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        }
        for r in rows
    ]
    return jsonify(results), 200
