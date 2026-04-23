import json
import os
import re
import time
import threading
from flask import jsonify, session
import logging

from . import db, app
from .actions import LogAction
from .llm import (
    get_llm_response,
    get_prompt,
    get_frequency_prompt,
    get_context_prompt,
    get_complete_prompt)
from .database.crud import (
    get_language,
    get_user,
    first_time_setup,
    get_contexts,
    get_context_by_id,
    get_strategy_translation_by_id,
    store_answer,
    set_current_context,
    set_context_completed,
    get_completed_contexts,
    update_current_conversation_step,
    update_current_turn,
    update_strategy_with_frequency,
    get_strategies_for_context,
    store_llm_answer,
    set_interview_complete,
    store_strategy,
    get_strategies,
    get_strategy_mentions_for_user,
    save_evaluation_for_strategy,
    update_most_recent_strategy_for_frequency,
    store_study_subject,
    archive_conversation,
    reset_user_run_state,
    get_active_run_started_at,
)
from .logging_utlis import log_action
from .steps import strategy_step, frequency_step, validate_strategies, intro_step

logger = logging.getLogger("InterviewAgent")
_SUMMARY_THREADS = set()
_STRATEGY_CODE_PATTERN = re.compile(r"\b\d{3}-\d{3}\b")
_STRATEGY_NAME_CACHE = {}


def _pending_summary_message(user):
    user_lang = get_language(user.language_id)
    if user_lang and user_lang.lang_code == "de":
        return (
            "Das Interview ist abgeschlossen. Bitte fülle jetzt den Fragebogen aus. "
            "Deine Zusammenfassung wird im Hintergrund erstellt."
        )
    return (
        "The interview is complete. Please fill out the survey now. "
        "Your summary is being generated in the background."
    )


def _is_pending_summary_message(text):
    if not text or not isinstance(text, str):
        return False

    normalized = text.strip().lower()
    return (
        "summary is being generated in the background" in normalized
        or "zusammenfassung wird im hintergrund erstellt" in normalized
        or "bitte fuelle jetzt den fragebogen aus" in normalized
        or "bitte fülle jetzt den fragebogen aus" in normalized
    )


def _summary_fallback_message(user):
    user_lang = get_language(user.language_id)
    if user_lang and user_lang.lang_code == "de":
        return (
            "Vielen Dank fuers Ausfuellen des Fragebogens. "
            "Die ausfuehrliche Zusammenfassung konnte gerade nicht automatisch erzeugt werden. "
            "Bitte oeffne die Ergebnisse, um deine Lernstrategien einzusehen."
        )
    return (
        "Thank you for completing the survey. "
        "The detailed summary could not be generated automatically just now. "
        "Please open the results to review your learning strategies."
    )


def _get_latest_complete_message(user):
    run_started_at = get_active_run_started_at(user)
    complete_msgs = []
    for response in user.llm_responses:
        if response.conversation_step != "complete":
            continue
        if run_started_at is not None and response.message_time < run_started_at:
            continue
        complete_msgs.append(response)
    if not complete_msgs:
        return None
    complete_msgs.sort(key=lambda r: (r.message_time, r.turn), reverse=True)
    return complete_msgs[0].message


def _replace_strategy_codes_with_names(user, text):
    if not text or not isinstance(text, str):
        return text

    def _sub(match):
        code = match.group(0)
        cache_key = (user.language_id, code)
        if cache_key in _STRATEGY_NAME_CACHE:
            return _STRATEGY_NAME_CACHE[cache_key]

        replacement = code
        try:
            strategy = get_strategy_translation_by_id(user, code)
            if strategy and strategy.name:
                replacement = strategy.name
        except Exception as e:
            logger.warning("Could not resolve strategy code %s: %s", code, e)

        _STRATEGY_NAME_CACHE[cache_key] = replacement
        return replacement

    return _STRATEGY_CODE_PATTERN.sub(_sub, text)


def _spawn_summary_generation(user_id, client):
    key = f"{user_id}:{client}"
    if key in _SUMMARY_THREADS:
        return
    _SUMMARY_THREADS.add(key)

    def _worker():
        try:
            with app.app_context():
                user = get_user(user_id, client)
                if user is None or not user.conversation_state:
                    return

                latest_complete = _get_latest_complete_message(user)
                if latest_complete and not _is_pending_summary_message(latest_complete):
                    # Real summary already present for this run – nothing to do.
                    return

                llm_message = sign_off_interview(user)
                llm_message = _replace_strategy_codes_with_names(user, llm_message)
                turn = update_current_turn(user)
                store_llm_answer(
                    user,
                    llm_message,
                    None,
                    user.conversation_state.strategy_for_frequency,
                    turn,
                    "complete",
                )
                db.session.commit()
                logger.info("Background summary generated for %s/%s", user_id, client)
        except Exception as e:
            logger.error("Background summary generation failed for %s/%s: %s", user_id, client, e)
            try:
                with app.app_context():
                    user = get_user(user_id, client)
                    if user is None or not user.conversation_state:
                        return
                    latest_complete = _get_latest_complete_message(user)
                    if latest_complete and not _is_pending_summary_message(latest_complete):
                        return

                    fallback = _replace_strategy_codes_with_names(user, _summary_fallback_message(user))
                    turn = update_current_turn(user)
                    store_llm_answer(
                        user,
                        fallback,
                        None,
                        user.conversation_state.strategy_for_frequency,
                        turn,
                        "complete",
                    )
                    db.session.commit()
                    logger.info("Stored fallback summary for %s/%s", user_id, client)
            except Exception as fallback_err:
                logger.error(
                    "Failed to store fallback summary for %s/%s: %s",
                    user_id,
                    client,
                    fallback_err,
                )
        finally:
            _SUMMARY_THREADS.discard(key)

    threading.Thread(target=_worker, daemon=True, name=f"summary-{user_id[:8]}").start()


def trigger_summary_generation_if_needed(user_id, client):
    """Ensure summary generation is queued for a completed interview run."""
    user = get_user(user_id, client)
    if user is None or not user.conversation_state:
        return {"queued": False, "reason": "user_not_found"}

    if not user.conversation_state.interview_completed:
        return {"queued": False, "reason": "interview_not_completed"}

    latest_complete = _get_latest_complete_message(user)
    if latest_complete and not _is_pending_summary_message(latest_complete):
        return {"queued": False, "reason": "summary_already_present"}

    _spawn_summary_generation(user.id, user.client)
    return {"queued": True, "reason": "summary_requested"}


def start_conversation_core(language, client, userid) -> tuple[str, int]:
    """
    Post request format:
    {
        "language": "en" or "de",
        "client": "discord",
        "userid": Discord user ID
    }
    Returns: tuple[message, status code]
    """
    try:
        with open("config/translations.json", "r", encoding="utf-8") as file:
            translations = json.load(file)

        if not get_language(language):
            msg = translations["language_not_supported_message"]

            log_action(
                LogAction.LANGUAGE_NOT_SUPPORTED,
                value={"language": language},
                http_status=400,
                step="language_validation"
            )

            return msg, 400

        user = get_user(userid, client)

        if user is None:
            lti_context_id = session.get("lti_context") or "0"
            lti_context_title = session.get("lti_context_title")
            created_user = first_time_setup(userid, client, language,
                                            context_id=lti_context_id,
                                            context_title=lti_context_title)
            if created_user is None:
                log_action(
                    LogAction.USER_NOT_FOUND,
                    value={"userid": userid, "client": client},
                    http_status=500,
                    step="user_creation_failed",
                    context="conversation_start"
                )

                return "An error occurred, please try to restart the conversation", 500
            user = created_user

            log_action(
                LogAction.USER_CREATED,
                user=user,
                value={"language": language, "client": client},
                http_status=201,
                turn=0,
                step="user_created",
                context="conversation_start",
                strategy="strategy_not_detected"
            )
        elif user.conversation_state and user.conversation_state.interview_completed:
            # Completed runs should not be resumed. Archive and reset to a fresh run state.
            reset_conversation(user)

            # Keep the same user identity; only reset active run state.
            user.context_id = session.get("lti_context") or user.context_id or "0"
            user.context_title = session.get("lti_context_title") or user.context_title
            reset_user_run_state(user)

            log_action(
                LogAction.USER_CREATED,
                user=user,
                value={
                    "language": language,
                    "client": client,
                    "restart_after_completion": True,
                },
                http_status=201,
                turn=0,
                step="user_recreated_after_completion",
                context="conversation_start",
                strategy="strategy_not_detected"
            )

        logger.info("Created new user (%s): %s - %s", language, user.id, user.client)

        log_action(
            LogAction.START_CONVERSATION,
            user=user,
            value={"language": language, "client": client},
            turn=0,
            step="intro",
            http_status=200,
            context="conversation_start",
            strategy="strategy_not_detected"
        )

        system_prompt = get_prompt(user, "system")
        intro_prompt = get_prompt(user, "intro")
        update_current_conversation_step(user, "intro")

        try:
            llm_message = get_llm_response(system_prompt + " " + intro_prompt, None, 0.1)
        except Exception as e:
            logger.error("Initial LLM call failed in start_conversation_core: %s", e)
            llm_message = (
                "Hallo! Lass uns mit dem Interview beginnen. "
                "In welchem Fach möchtest du einen Abschluss machen?"
                if language == "de"
                else "Hello! Let's begin the interview. What subject are you studying?"
            )

        llm_message = _replace_strategy_codes_with_names(user, llm_message)

        turn = update_current_turn(user)
        store_llm_answer(user, llm_message, None, None, turn, step="intro")
        log_action(
            LogAction.REPLY_LLM,
            user=user,
            value={"message": llm_message},
            turn=turn,
            step="intro",
            context="conversation_start",
            strategy="strategy_not_detected",
            http_status=200
        )

        return jsonify({"message": llm_message}), 200
    except Exception as e:
        logger.error("Unhandled error in start_conversation_core: %s", e)
        log_action(
            LogAction.ERROR_OCCURRED,
            user=user if 'user' in locals() else None,
            value={"error": str(e)},
            http_status=500,
            step="start_conversation",
            context="conversation_start",
            strategy="strategy_not_detected",
        )
        fallback = translations["translations"].get(language, translations["translations"]["en"])["create_error"]
        return fallback, 500


def reply_core(client, userid, user_message) -> tuple[str, int]:
    """
    Post request format:
    {
        "client": "discord",
        "userid": Discord user ID
        "user_message": message
    }
    """
    logger.info('Started reply_core')

    llm_message = ''
    user = None
    current_context = None
    turn = 0

    try:
        user = get_user(userid, client)
        if user is None:
            log_action(
                LogAction.USER_NOT_FOUND,
                value={"userid": userid, "client": client},
                http_status=500,
                step="user_not_found",
                context="conversation_could_not_start"
            )

            return "User not found. Start a conversation first.", 400

        # Retrieve current context
        current_context_id = user.conversation_state.current_context

        if current_context_id:
            current_context = get_context_by_id(current_context_id)
        else:
            current_context = None

        turn = update_current_turn(user)

        conversation_step = user.conversation_state.current_conversation_step
        logger.info('......................')
        logger.info('conversation step: ' + str(conversation_step))
        current_strategy = user.conversation_state.strategy_for_frequency

        log_action(
            LogAction.REPLY_USER,
            user=user,
            value={"message": user_message},
            context=current_context.context if current_context else "user first response",
            strategy=current_strategy if current_strategy else "strategy_not_detected",
            turn=turn,
            step=user.conversation_state.current_conversation_step if user.conversation_state else None,
            http_status=200
        )

        user_answer_db = store_answer(user, current_context_id, current_strategy, user_message, turn, conversation_step)

        conversation_for_current_context = retrieve_full_conversation(user, current_context_id)

        logger.info(user_message)

        if user.conversation_state.interview_completed:
            llm_message = _get_latest_complete_message(user) or _pending_summary_message(user)
            llm_message = _replace_strategy_codes_with_names(user, llm_message)
            return jsonify({"message": llm_message, "complete": True}), 200

        logger.info("Replying to user: %s - %s. Step: %s", user.id, user.client, conversation_step)

        match conversation_step:
            case "intro":
                logger.info('@intro step, Entered intro step')
                study_subject, status, comment = intro_step(user, conversation_for_current_context)
                logger.info('@intro step, got subject')
                logger.info(study_subject)
                logger.info('@intro status: %s',status)

                if status in ("completed", "complete", "abandon", "in_progress"):
                    store_study_subject(user, study_subject)
                    contexts = set(get_contexts(user.language_id))
                    if get_completed_contexts(user) is not None:
                        completed_contexts = set(get_completed_contexts(user))
                        remaining_contexts = contexts.difference(completed_contexts)
                    else:
                        remaining_contexts = contexts
                    current_context = list(remaining_contexts)[0]

                    set_current_context(user, current_context)

                    system_prompt = get_prompt(user, "system")
                    context_prompt = get_context_prompt(current_context.context, user)
                    update_current_conversation_step(user, "strategy")

                    llm_message = get_llm_response(context_prompt + "  " + system_prompt, None, 0.1)

                    log_action(
                        LogAction.REPLY_LLM,
                        user=user,
                        value={"message": llm_message},
                        turn=turn,
                        step=conversation_step,
                        context=current_context.context,
                        strategy=user.conversation_state.strategy_for_frequency if user.conversation_state.strategy_for_frequency else "strategy_not_detected",
                        http_status=200
                    )

                    logger.info('@intro step, second llm call ')
                    logger.info(llm_message)

            case "strategy":
                strategies_mentioned, status, llm_message = strategy_step(user, str(current_context.context),
                                                                          conversation_for_current_context)
                if status in ("completed", "complete", "abandon"):
                    update_current_conversation_step(user, "frequency")
                    valid_strategies = validate_strategies(strategies_mentioned)

                    for mentioned_strategy in valid_strategies:
                        store_strategy(user, user_answer_db, current_context.id, mentioned_strategy)
                        if mentioned_strategy == "008-001":
                            update_strategy_with_frequency(user, current_context.id, mentioned_strategy, 0)
                    llm_message, current_context = ask_about_frequency(user, current_context)

                    log_action(
                        LogAction.REPLY_LLM,
                        user=user,
                        value={"message": llm_message},
                        turn=turn,
                        step=conversation_step,
                        context=current_context.context if current_context else None,
                        strategy=user.conversation_state.strategy_for_frequency if user.conversation_state.strategy_for_frequency else "strategy_not_detected",
                        http_status=200
                    )
                else:
                    log_action(
                        LogAction.REPLY_LLM,
                        user=user,
                        value={"message": llm_message},
                        turn=turn,
                        step="strategy",
                        context=current_context.context if current_context else None,
                        strategy=user.conversation_state.strategy_for_frequency,
                        http_status=200
                    )

            case "frequency":
                conversation_for_strategy_in_context = retrieve_full_conversation(
                    user,
                    user.conversation_state.current_context,
                    user.conversation_state.strategy_for_frequency
                )

                strategy_rated, rated_frequency, status, llm_message = frequency_step(
                    user,
                    conversation_for_current_context,
                    conversation_for_strategy_in_context
                )

                if status in ("completed", "abandon"):
                    # Store user's answer(s)
                    update_strategy_with_frequency(user, current_context_id, strategy_rated,
                                                   rated_frequency)
                    # check if further strategies need to be checked for frequency
                    llm_message, current_context = ask_about_frequency(user, current_context)

                log_action(
                    LogAction.REPLY_LLM,
                    user=user,
                    value={"message": llm_message},
                    turn=turn,
                    step=conversation_step,
                    context=current_context.context if current_context else None,
                    strategy=strategy_rated,
                    http_status=200
                )

            case _:
                pass

        llm_message = _replace_strategy_codes_with_names(user, llm_message)

        store_llm_answer(user, llm_message, current_context,
                         user.conversation_state.strategy_for_frequency, turn,
                         user.conversation_state.current_conversation_step
                         )
        return jsonify({
            "message": llm_message,
            "complete": bool(user.conversation_state.interview_completed),
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error("Error in reply_core: %s", e)

        log_action(
            LogAction.DB_ROLLBACK,
            user=user,
            value={"error": str(e)},
            http_status=500,
            step="exception_handled",
            turn=turn,
            context=current_context.context if current_context else None,
            strategy=user.conversation_state.strategy_for_frequency if user else None
        )
        # Avoid hard frontend failure (Axios 500) and keep conversation usable.
        fallback_text = (
            "Entschuldigung, ich hatte gerade ein internes Problem. "
            "Kannst du die letzte Antwort bitte noch einmal kurz formulieren?"
        )
        try:
            if user and user.language_id:
                lang = get_language_by_id(user.language_id)
                if lang and lang.lang_code == "en":
                    fallback_text = (
                        "Sorry, I had an internal issue just now. "
                        "Could you briefly repeat your last answer?"
                    )
        except Exception:
            pass

        return jsonify({
            "message": fallback_text,
            "complete": bool(user.conversation_state.interview_completed) if user and user.conversation_state else False,
            "degraded": True,
        }), 200


def set_current_context_complete(user, current_context):
    # Set context completed and move to next context
    contexts = set(get_contexts(user.language_id))
    set_context_completed(user, current_context)
    completed_contexts = set(get_completed_contexts(user))
    remaining_contexts = contexts.difference(completed_contexts)
    if remaining_contexts == set():
        set_interview_complete(user)
        return None

    next_context = list(remaining_contexts)[0]
    set_current_context(user, next_context)
    return next_context


def retrieve_full_conversation(user, context_id=None, step=None, strategy_id=None):
    # Use a list of (turn, role_order, message) tuples to avoid collisions when
    # both a user answer and a bot reply share the same turn number.
    # role_order=0 → user (spoke first), role_order=1 → assistant (replied second).
    run_started_at = get_active_run_started_at(user)
    entries = []
    for response in user.llm_responses:
        if context_id is None or response.context == context_id:
            if step is None or response.conversation_step == step:
                if strategy_id is None or response.strategy == strategy_id:
                    if run_started_at is not None and response.message_time < run_started_at:
                        continue
                    entries.append((response.turn, 1, {"role": "assistant", "content": response.message}))
    for response in user.interview_answers:
        if context_id is None or response.context == context_id:
            if step is None or response.conversation_step == step:
                if strategy_id is None or response.strategy == strategy_id:
                    if run_started_at is not None and response.message_time < run_started_at:
                        continue
                    entries.append((response.turn, 0, {"role": "user", "content": response.message}))

    entries.sort(key=lambda e: (e[0], e[1]))
    return [msg for _, _, msg in entries]


def ask_about_frequency(user, current_context):
    # retrieve all interview answers for current context
    answers = get_strategies_for_context(user, current_context.id)
    system_prompt = get_prompt(user, "system")

    def list_filter(a):
        if a.frequency is None and a.strategy != "008-001":
            return True
        else:
            return False

    answers_without_frequency = list(filter(list_filter, answers))
    if len(answers_without_frequency):
        for answer in answers_without_frequency:
            context = get_context_by_id(answer.context)
            strategy = get_strategy_translation_by_id(user, answer.strategy)
            logger.info("Asking about frequency for strategy: %s", strategy.name)
            frequency_prompt = get_frequency_prompt(user, context.context, strategy.name)
            update_current_conversation_step(user, "frequency")
            update_most_recent_strategy_for_frequency(user, strategy)
            conversation_so_far = retrieve_full_conversation(user, context.id, "strategy")
            llm_message = get_llm_response(frequency_prompt + " " + system_prompt,
                                                  prev_conversation=_user_only_conv(conversation_so_far))
            new_context = current_context
            break
    # if all answers have frequency, move to next context
    else:
        llm_message, new_context = move_to_next_context(user, current_context)
    return llm_message, new_context


def _generate_summary_now(user):
    """Generate the interview summary synchronously.

    Called directly from move_to_next_context so the summary is ready
    in the same DB transaction as the interview completion – no background
    thread, no race conditions, no server-restart-kills-thread issues.
    """
    try:
        llm_message = sign_off_interview(user)
        llm_message = _replace_strategy_codes_with_names(user, llm_message)
        logger.info("Summary generated synchronously for %s/%s", user.id, user.client)
        return llm_message
    except Exception as e:
        logger.error("Synchronous summary generation failed for %s/%s: %s", user.id, user.client, e)
        return _replace_strategy_codes_with_names(user, _summary_fallback_message(user))


def move_to_next_context(user, current_context):
    next_context = set_current_context_complete(user, current_context)
    conversation_so_far = retrieve_full_conversation(user)
    system_prompt = get_prompt(user, "system")

    # Optional test-only short-circuit: stop after N completed contexts.
    # Disabled by default; enable with TEST_STOP_AFTER_CONTEXTS=1 (or 2, ...).
    stop_after_contexts = int(os.getenv("TEST_STOP_AFTER_CONTEXTS", "0") or "0")
    completed_contexts = get_completed_contexts(user) or []
    if stop_after_contexts > 0 and len(completed_contexts) >= stop_after_contexts:
        set_interview_complete(user)
        update_current_conversation_step(user, "complete")
        llm_message = _generate_summary_now(user)
        return llm_message, None

    if next_context:
        logger.info("Moving on to context: %s", next_context.context)
        prompt = get_context_prompt(next_context.context, user)
        update_current_conversation_step(user, "strategy")
        llm_message = get_llm_response(prompt + system_prompt,
                                              prev_conversation=_user_only_conv(conversation_so_far))
    else:
        update_current_conversation_step(user, "complete")
        llm_message = _generate_summary_now(user)

    return llm_message, next_context


def sign_off_interview(user):
    summary = evaluate(user)
    return summary


def evaluate(user):
    evaluations = []
    strategy_scores = {}
    for strategy_translation in get_strategies(user.language_id):
        strategy_scores[strategy_translation.strategy] = {"contexts": []}
        mentions = get_strategy_mentions_for_user(user, strategy_translation)
        SU = 0
        SF = 0
        SC = 0
        if mentions:
            SU = (len(mentions) != 0)
            SF = len(mentions)
            for mention in mentions:
                SC += mention.frequency
                strategy_scores[strategy_translation.strategy]["contexts"].append(mention.context)
        evaluation = save_evaluation_for_strategy(user, strategy_translation, SU, SF, SC)
        strategy_scores[strategy_translation.strategy]["SU"] = SU
        strategy_scores[strategy_translation.strategy]["SF"] = SF
        strategy_scores[strategy_translation.strategy]["SC"] = SC
        if SF != 0:
            strategy_scores[strategy_translation.strategy]["RC"] = SC / SF
        else:
            strategy_scores[strategy_translation.strategy]["RC"] = 0
        evaluations.append(evaluation)
    summary = generate_summary(user, strategy_scores)
    return summary


def generate_summary(user, strategy_scores):
    most_contexts = list(sorted(strategy_scores.items(), key=lambda item: len(item[1]["contexts"]), reverse=True))
    most_consistently = list(sorted(strategy_scores.items(), key=lambda item: item[1]["RC"], reverse=True))
    strategies_used = list({strategy: item for strategy, item in strategy_scores.items() if len(item["contexts"]) > 0})
    consistently_used = list({strategy: item for strategy, item in strategy_scores.items() if item["RC"] > 2.5})

    most_contexts_strat = get_strategy_translation_by_id(user, most_contexts[0][0]).description
    const_strategy = get_strategy_translation_by_id(user, most_consistently[0][0]).description
    avg_freq = most_consistently[0][1]["RC"]
    total_strat = len(strategies_used)
    const_strategies = []
    for strat in consistently_used:
        const_strategies.append(get_strategy_translation_by_id(user, strat).description)
    full_conversation = retrieve_full_conversation(user)
    # Use only user messages as conversation context for the summary LLM call.
    # With interleaved user+bot history the list can end on an assistant message,
    # which confuses the model into producing dialogue instead of a summary.
    user_only_conv = [m for m in full_conversation if isinstance(m, dict) and m.get("role") == "user"]
    system_prompt = get_prompt(user, "system")
    prompt = get_complete_prompt(user, most_contexts_strat, const_strategy, avg_freq, total_strat, const_strategies)
    llm_message = get_llm_response(prompt + " " + system_prompt, prev_conversation=user_only_conv)
    return llm_message


def reset_conversation(user):
    try:
        user_id = user.id if user else None
        user_client = user.client if user else None

        log_action(
            LogAction.RESET_CONVERSATION,
            user=user,
            value={"status": "started"},
            http_status=200,
            step="complete",
            context= "delete conversation",
            strategy= "no strategy"
        )

        conversation = retrieve_full_conversation(user)
        state = user.conversation_state

        completed_contexts = get_completed_contexts(user) or []
        total_contexts = len(get_contexts(user.language_id) or [])
        archive = {
            "user_id": user.id,
            "user_client": user.client,
            "archived_at": int(time.time()),
            "messages": conversation,
            "state": {
                "complete": state.interview_completed,
                "current_context": state.current_context,
                "step": state.current_conversation_step,
                "completed_contexts": len(completed_contexts),
                "total_contexts": total_contexts,
            },
        }

        success = archive_conversation(user, archive)

        if success:
            log_action(
                LogAction.CONVERSATION_ARCHIVED,
                value={
                    "user_id": user_id,
                    "user_client": user_client,
                    "archived_messages": len(conversation),
                },
                http_status=200,
                step="complete",
                context="conversation archived",
                strategy="no strategy"
            )
        else:
            log_action(
                LogAction.ERROR_OCCURRED,
                user=user,
                value={"reason": "archive_failed"},
                http_status=500
            )

        return success

    except Exception as e:
        log_action(
            LogAction.ERROR_OCCURRED,
            value={
                "user_id": user_id if 'user_id' in locals() else None,
                "user_client": user_client if 'user_client' in locals() else None,
                "error": str(e),
            },
            http_status=500
        )
        raise
