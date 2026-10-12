import re
import json
import logging
from pydantic import BaseModel
from json.decoder import JSONDecodeError

from .database.crud import get_language_by_id, get_all_strategies
from .llm import get_llm_response
from .prompts import (
    get_strategy_analysis_prompt,
    get_format_strategy_prompt,
    get_intro_prompt,
    get_prompt,
)
from .models import User
from .rag import USE_RAG_STRATEGY, detect_strategies_rag

# Max. number of follow-up questions when a user answer contains no usable information
# (no study subject in the intro, no learning strategy in a context).
MAX_FOLLOWUPS = 3
OTHER_STRATEGY = "008-001"
_NO_STRATEGY = {"", "other", OTHER_STRATEGY}
_EMPTY_SUBJECT = {"", "null", "none", "unknown", "unbekannt", "n/a"}

logger = logging.getLogger('InterviewAgent')


def _user_only_conv(conv):
    """Return only user-role messages from a conversation list.

    Analysis prompts (recognise_strategy, intro_check) need to know what the USER
    said, not what the bot replied.
    """
    if not conv:
        return []
    return [m for m in conv if isinstance(m, dict) and m.get("role") == "user"]


def _n_user_answers(conv) -> int:
    return len(_user_only_conv(conv))


def _is_de(user: User) -> bool:
    lang = get_language_by_id(user.language_id)
    return bool(lang and lang.lang_code == "de")


class StepIntroFields(BaseModel):
    """BaseModel of the expected JSON structure of a LLM response regarding a study subject"""
    study_subject: str
    status: str
    comment: str


class StepStrategieStepperFields(BaseModel):
    """BaseModel of the expected JSON structure of a LLM response regarding an open ended question"""
    strategies: str
    status: str
    comment: str


# ---------------------------------------------------------------------------
# Intro: only asks for the study subject
# ---------------------------------------------------------------------------

def intro_step(user: User, prev_conversation: list[str]):
    """Returns (study_subject, status, comment). status: completed | in_progress | abandon."""
    intro_prompt = get_intro_prompt(user, MAX_FOLLOWUPS + 1)
    system_prompt = get_prompt(user, "system")

    json_output, json_valid = try_get_json_completion(5, 0.0, 0.2, intro_prompt + system_prompt,
                                                      expected_fields_model=StepIntroFields,
                                                      prev_conversation=_user_only_conv(prev_conversation),
                                                      user_prompt=None)
    subject = str(json_output.get("study_subject") or "").strip() if json_valid else ""
    if subject.lower() not in _EMPTY_SUBJECT:
        return subject, "completed", ""

    if _n_user_answers(prev_conversation) > MAX_FOLLOWUPS:
        return "unknown", "abandon", ""

    comment = json_output.get("comment") if json_valid else ""
    if not comment:
        comment = (
            "In welchem Fach möchtest du deinen Abschluss machen?"
            if _is_de(user)
            else "Which subject are you studying?"
        )
    return "", "in_progress", comment


# ---------------------------------------------------------------------------
# Strategy: identify learning strategies in the answers to the context question
# ---------------------------------------------------------------------------

def strategy_step(user: User, context: str, prev_conversation: list[str]):
    """
    Returns (strategies, status, comment).
      - completed:   >= 1 valid, deduplicated strategy ID detected → ask frequency for each
      - in_progress: nothing detected yet → one open follow-up question (comment)
      - abandon:     nothing detected after MAX_FOLLOWUPS follow-ups → strategies = [OTHER_STRATEGY]
    The decision is made here deterministically; the LLM's own 'status' field is ignored.
    """
    if USE_RAG_STRATEGY:
        raw = _detect_strategies_rag(user, context, prev_conversation)
    else:
        raw = _detect_strategies_llm(user, context, prev_conversation)

    detected = [s for s in dict.fromkeys(validate_strategies(raw)) if s not in _NO_STRATEGY]
    n_answers = _n_user_answers(prev_conversation)
    logger.info("strategy_step: raw=%s detected=%s user_answers=%d", raw, detected, n_answers)

    if detected:
        return detected, "completed", ""
    if n_answers > MAX_FOLLOWUPS:
        return [OTHER_STRATEGY], "abandon", ""
    return [], "in_progress", _strategy_conversational_comment(user, context, prev_conversation)


def _detect_strategies_rag(user: User, context: str, prev_conversation: list) -> list[str]:
    """Detect strategies via pgvector embedding similarity."""
    user_messages = [m["content"] for m in _user_only_conv(prev_conversation)]
    if not user_messages:
        return []
    try:
        return detect_strategies_rag(user_messages, top_k=3)
    except Exception as e:
        logger.error("[RAG] Embedding retrieval failed: %s — falling back to LLM", e)
        return _detect_strategies_llm(user, context, prev_conversation)


def _detect_strategies_llm(user: User, context: str, prev_conversation: list) -> list[str]:
    """LLM chain-of-thought strategy detection. Returns raw strategy IDs (unvalidated)."""
    reasoning_response = get_llm_response(
        get_strategy_analysis_prompt(user),
        user_prompt=None, temperature=0.0,
        prev_conversation=_user_only_conv(prev_conversation)
    )
    format_strategy_prompt = get_format_strategy_prompt(
        user, reasoning_response, _n_user_answers(prev_conversation), context, MAX_FOLLOWUPS + 1
    )
    # No conversational system prompt here: its "never name strategies" rule conflicts
    # with outputting strategy IDs. The user's answers are passed as well so the format
    # call does not depend solely on how verbose the analysis was.
    json_output, json_valid = try_get_json_completion(5, 0.0, 0.2, format_strategy_prompt,
                                                      expected_fields_model=StepStrategieStepperFields,
                                                      prev_conversation=_user_only_conv(prev_conversation),
                                                      user_prompt=None)
    if not json_valid:
        return []
    raw = json_output.get("strategies") or []
    if isinstance(raw, str):
        raw = raw.split(",")
    return [str(s).strip() for s in raw if str(s).strip()]


def _strategy_conversational_comment(user: User, context: str, prev_conversation: list) -> str:
    """Open follow-up question when no strategy was detected yet."""
    system = get_prompt(user, "system")
    if _is_de(user):
        guide = (
            f"Gehe kurz auf die letzte Aussage des/der Gesprächspartner*in ein. "
            "Stelle dann genau eine kurze, offene Frage dazu, "
            f"was er/sie konkret im Kontext '{context}' tut, wenn er/sie lernt. "
            "WICHTIG: Nenne niemals Lernstrategien, Lernmethoden oder Strategiekategorien beim Namen, "
            "beschreibe sie nicht und deute sie nicht an — auch nicht als Beispiel. "
            "Stelle keine suggestiven oder führenden Fragen. "
            "Schreibe NUR deine eigene nächste Aussage oder Frage. Simuliere keinen Dialog."
        )
    else:
        guide = (
            f"Briefly acknowledge the student's last message. "
            "Then ask exactly one short, open-ended question about what the student concretely does "
            f"when studying in the context '{context}'. "
            "IMPORTANT: Never name, describe, or hint at any learning strategy, method, or category "
            "— not even as an example. "
            "Do not ask leading or suggestive questions. "
            "Write ONLY your next message. Do not simulate a dialogue."
        )
    return get_llm_response(
        system + "\n\n" + guide,
        user_prompt=None,
        temperature=0.3,
        prev_conversation=prev_conversation,
    )


# ---------------------------------------------------------------------------
# Frequency: parse the 1–4 rating deterministically (no LLM)
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    "eins": 1, "zwei": 2, "drei": 3, "vier": 4,
    "one": 1, "two": 2, "three": 3, "four": 4,
}
_NUMBER_PATTERN = re.compile(r"\b(\d+|" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)

_FREQ_HINT_DE = "Bitte antworte mit einer Zahl von 1 bis 4."
_FREQ_HINT_EN = "Please answer with a number from 1 to 4."


def parse_frequency(text: str):
    """Return the FIRST number in the text (digit or number word) if it is 1–4, else None.
    '3', 'drei', '3-4', '3 bis 4', 'eins bis zwei' → 3, 3, 3, 3, 1."""
    match = _NUMBER_PATTERN.search(text or "")
    if not match:
        return None
    token = match.group(1).lower()
    value = _NUMBER_WORDS.get(token) or int(token)
    return value if 1 <= value <= 4 else None


def _repeat_frequency_question(user: User, prev_conversation: list) -> str:
    hint = _FREQ_HINT_DE if _is_de(user) else _FREQ_HINT_EN
    last_question = next(
        (m["content"] for m in reversed(prev_conversation or [])
         if isinstance(m, dict) and m.get("role") == "assistant"),
        "",
    )
    for prefix in (_FREQ_HINT_DE, _FREQ_HINT_EN):
        if last_question.startswith(prefix):
            last_question = last_question[len(prefix):].strip()
    return f"{hint} {last_question}".strip()


def frequency_step(user: User, prev_conversation: list):
    """
    Returns (strategy, frequency, status, comment).
    Valid rating → completed. Otherwise the same question is repeated (in_progress).
    """
    strategy = user.conversation_state.strategy_for_frequency
    user_msgs = _user_only_conv(prev_conversation)
    last_answer = user_msgs[-1]["content"] if user_msgs else ""
    frequency = parse_frequency(last_answer)
    logger.info("frequency_step: strategy=%s answer=%r → %s", strategy, last_answer, frequency)

    if frequency is not None:
        return strategy, frequency, "completed", ""
    return strategy, 0, "in_progress", _repeat_frequency_question(user, prev_conversation)


def validate_strategies(user_strategies):
    """Util function that compares the detected strategies from the user input with expert curated list of strategies"""
    all_strategies = get_all_strategies()
    valid_strategies = []
    for strategy in user_strategies:
        if strategy in all_strategies:
            valid_strategies.append(strategy)
        else:
            logger.warning(
                "validate_strategies: strategy '%s' not found in Strategy table (not stored). "
                "Available IDs (first 10): %s",
                strategy, all_strategies[:10],
            )
    logger.info(
        "validate_strategies: input=%s  valid=%s  db_count=%d",
        user_strategies, valid_strategies, len(all_strategies),
    )
    return valid_strategies


def try_get_json_completion(
        num_attempts,
        start_temp,
        temp_increase,
        system_prompt,
        expected_fields_model,
        prev_conversation=None,
        user_prompt=None
):
    """Call the LLM until it returns parseable JSON. Returns (dict, True) or (raw_text, False)."""
    if prev_conversation is None:
        prev_conversation = []
    expected_fields = list(expected_fields_model.model_fields.keys())
    attempts = num_attempts
    temperature = start_temp
    llm_message_raw = ""
    while attempts > 0:
        try:
            logger.info("@ steps, try_get_json_completion:: call get_llm_response")
            llm_message_raw = get_llm_response(
                system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                prev_conversation=prev_conversation,
                expected_fields_model=expected_fields_model
            )
            regex = r"{[\s\S]+}"
            logger.info("@ steps, try_get_json_completion:: LLM response: " + llm_message_raw)
            json_string = re.search(regex, llm_message_raw).group()
            json_output = json.loads(json_string)
            # Merge fields across all levels: LLM sometimes splits fields between the
            # top-level and a nested status key, e.g.:
            #   {"complete": {"strategies": [...]}, "status": "completed", "comment": "..."}
            merged = dict(json_output)
            for value in json_output.values():
                if isinstance(value, dict):
                    for f in expected_fields:
                        if merged.get(f) in ("", None, [], {}) and value.get(f) not in ("", None, [], {}):
                            merged[f] = value[f]
            json_output = merged
            for field in expected_fields:
                if field not in json_output:
                    json_output[field] = ""
            if not json_output.get("comment"):
                outside_text = llm_message_raw.replace(json_string, "").strip()
                if outside_text:
                    json_output["comment"] = outside_text
            logger.info("JSON is valid")
            return json_output, True
        except (AttributeError, JSONDecodeError):
            logger.info("Invalid JSON, trying again")
            attempts -= 1
            temperature += temp_increase

    logger.info("JSON invalid")
    return llm_message_raw, False
