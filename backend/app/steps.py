import re
import json
import logging
from pydantic import BaseModel
from json.decoder import JSONDecodeError

from .database.crud import get_language_by_id, get_all_strategies
from .llm import (
    get_llm_response,
    get_strategy_analysis_prompt,
    get_format_strategy_prompt,
    get_frequency_validate_prompt,
    get_format_frequency_prompt,
    get_intro_prompt,
    get_prompt
)
from .models import User
from .rag import USE_RAG_STRATEGY, detect_strategies_rag

ABANDON_AFTER_STEPS = 6
logger = logging.getLogger('InterviewAgent')


def _user_only_conv(conv):
    """Return only user-role messages from a conversation list.

    Analysis prompts (recognise_strategy, validate_frequency, intro_check) need
    to know what the USER said, not what the bot replied.  Passing bot messages
    into these calls creates a confusing role structure and causes the LLM to
    continue the chat instead of outputting JSON or a clean analysis.
    """
    if not conv:
        return []
    return [m for m in conv if isinstance(m, dict) and m.get("role") == "user"]


def _json_retry_comment(user: User, step_name: str):
    lang = get_language_by_id(user.language_id)
    is_de = bool(lang and lang.lang_code == "de")

    if step_name == "intro":
        return (
            "Ich konnte deine Antwort noch nicht eindeutig zuordnen. In welchem Fach möchtest du deinen Abschluss machen?"
            if is_de
            else "I could not map your answer clearly yet. Which subject are you studying?"
        )

    if step_name == "frequency":
        return (
            "Wie häufig nutzt du diese Strategie? Bitte antworte nur mit einer Zahl von 1 bis 4."
            if is_de
            else "How often do you use this strategy? Please reply with a number from 1 to 4."
        )

    return (
        "Danke. Kannst du bitte genauer beschreiben, welche Lernstrategie du in dieser Situation nutzt?"
        if is_de
        else "Thanks. Could you describe more clearly which learning strategy you use in this situation?"
    )


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

class StepFrequencyStepperFields(BaseModel):
  """BaseModel of the expected JSON structure of a LLM response regarding a question about a number/frequency"""
  frequency: str
  status: str
  comment: str




def intro_step(user: User, prev_conversation: list[str]):
    """
    The first of the three types of steps. In this step the interview starts with an introduction.
    """
    intro_prompt = get_intro_prompt(user, ABANDON_AFTER_STEPS)
    system_prompt = get_prompt(user, "system")

    json_output, json_valid = try_get_json_completion(5, 0.0, 0.2, intro_prompt + system_prompt,
                                                      expected_fields_model=StepIntroFields,
                                                      prev_conversation=_user_only_conv(prev_conversation),
                                                      user_prompt=None)
    if not json_valid:
        return "", "in_progress", _json_retry_comment(user, "intro")
    if json_output["study_subject"] == "" and len(prev_conversation) >= ABANDON_AFTER_STEPS:
        json_output["study_subject"] = ["unknown"]
        json_output["status"] = "abandon"
    return json_output["study_subject"], json_output["status"], json_output["comment"]





def strategy_step(user: User, context: str, prev_conversation: list[str]):
    """
    The second type of step aims to collect mentioned strategies.
    Two strategy detection methods are supported: Retrieval Augmented Generation and ChainOfThought
    """
    if USE_RAG_STRATEGY:
        return _strategy_step_rag(user, context, prev_conversation)
    return _strategy_step_llm(user, context, prev_conversation)


def _strategy_step_rag(user: User, context: str, prev_conversation: list[str]):
    """Detect strategies via pgvector embedding similarity."""
    logger.info("[RAG] Using embedding-based strategy detection")

    # Extract user messages from the conversation
    user_messages = [
        msg["content"] if isinstance(msg, dict) else str(msg)
        for msg in prev_conversation
        if (isinstance(msg, dict) and msg.get("role") == "user") or not isinstance(msg, dict)
    ]

    if not user_messages:
        return [], "in_progress", get_prompt(user, "system")

    try:
        strategies = detect_strategies_rag(user_messages, top_k=3)
    except Exception as e:
        logger.error("[RAG] Embedding retrieval failed: %s — falling back to LLM", e)
        return _strategy_step_llm(user, context, prev_conversation)

    # Build a conversational comment via a single LLM call
    system_prompt = get_prompt(user, "system")
    comment = get_llm_response(
        system_prompt
        + f"\nThe student mentioned these learning strategies: {strategies}."
        + f"\nContext: {context}."
        + "\nAcknowledge briefly which strategies you recognised and ask about details.",
        user_prompt=None,
        temperature=0.3,
        prev_conversation=prev_conversation,
    )

    status = "completed"
    if strategies in ([], ["008-001"]):
        status = "in_progress" if len(prev_conversation) < ABANDON_AFTER_STEPS else "abandon"
        if status == "abandon":
            strategies = ["other"]

    logger.info("[RAG] Detected strategies: %s  status: %s", strategies, status)
    return strategies, status, comment


def _strategy_conversational_comment(user: User, context: str, prev_conversation: list) -> str:
    """Generate a conversational follow-up that responds to the user's actual last message
    and steers toward describing their learning strategies in the current context.
    Used when no strategy was detected yet (in_progress) so that the agent doesn't repeat
    a static prompt but genuinely engages with what the user said.
    """
    lang = get_language_by_id(user.language_id)
    is_de = bool(lang and lang.lang_code == "de")
    system = get_prompt(user, "system")
    if is_de:
        guide = (
            f"Gehe kurz auf die letzte Aussage des/der Gesprächspartner*in ein. "
            f"Stelle dann genau eine kurze, offene Frage dazu, was er/sie konkret im Kontext '{context}' tut, wenn er/sie lernt. "
            "WICHTIG: Nenne niemals Lernstrategien, Lernmethoden oder Strategiekategorien beim Namen, "
            "beschreibe sie nicht und deute sie nicht an — auch nicht als Beispiel. "
            "Stelle keine suggestiven oder führenden Fragen. "
            "Schreibe NUR deine eigene nächste Aussage oder Frage. Simuliere keinen Dialog."
        )
    else:
        guide = (
            f"Briefly acknowledge the student's last message. "
            f"Then ask exactly one short, open-ended question about what the student concretely does when studying in the context '{context}'. "
            "IMPORTANT: Never name, describe, or hint at any learning strategy, method, or category — not even as an example. "
            "Do not ask leading or suggestive questions. "
            "Write ONLY your next message. Do not simulate a dialogue."
        )
    return get_llm_response(
        system + "\n\n" + guide,
        user_prompt=None,
        temperature=0.3,
        prev_conversation=prev_conversation,
    )


def _strategy_step_llm(user: User, context: str, prev_conversation: list[str]):
    """Original LLM chain-of-thought strategy detection."""
    logger.debug("Retrieving contexts")
    from .config import get_interview_config_path
    with open(get_interview_config_path(), "r", encoding="utf-8") as file:
        interview_context = json.load(file)
    user_lang = get_language_by_id(user.language_id)
    strat_info = []
    for category in interview_context[user_lang.lang_code]["categories"]:
        strat_info.append(category["strategies"])

    logger.debug("Retrieving prompt")
    strategy_analysis_prompt = get_strategy_analysis_prompt(user)
    logger.debug("Retrieving reasoning response")
    reasoning_response = get_llm_response(
        strategy_analysis_prompt,
        user_prompt=None, temperature=0.0,
        prev_conversation=_user_only_conv(prev_conversation)
        )
    logger.debug("Retrieving prompt")
    format_strategy_prompt = get_format_strategy_prompt(user, reasoning_response, len(prev_conversation), context,
                                                        ABANDON_AFTER_STEPS)
    system_prompt = get_prompt(user, "system")
    logger.debug("Retrieving JSON")
    # Format call: reasoning_response already embedded in prompt – no conversation needed.
    # Do NOT append the conversational system_prompt here: its "never name strategies" rule
    # conflicts with this call's task of outputting strategy IDs in JSON.
    json_output, json_valid = try_get_json_completion(5, 0.0, 0.2, format_strategy_prompt,
                                                      expected_fields_model=StepStrategieStepperFields,
                                                      prev_conversation=[],
                                                      user_prompt=None)
    if not json_valid:
        # JSON could not be parsed at all – generate a contextual reply instead of a
        # static fallback so the agent can respond to what the user actually said.
        comment = _strategy_conversational_comment(user, context, prev_conversation)
        return [], "in_progress", comment

    # Normalize: LLM sometimes returns strategies as a string instead of a list.
    strategies_raw = json_output.get("strategies", [])
    if isinstance(strategies_raw, str):
        strategies_raw = [s.strip() for s in strategies_raw.split(",") if s.strip()] if strategies_raw else []
    json_output["strategies"] = strategies_raw

    if json_output["strategies"] not in ([], ["other"]):
        json_output["status"] = "completed"

    if json_output["strategies"] in ([], ["other"]) and len(prev_conversation) >= ABANDON_AFTER_STEPS:
        json_output["strategies"] = ["other"]
        json_output["status"] = "abandon"

    # For in_progress turns the format call used prev_conversation=[] so its comment
    # is context-blind. Generate a proper conversational response instead so the agent
    # can react to the user's last message (e.g. clarifying questions).
    if json_output["status"] == "in_progress":
        comment = _strategy_conversational_comment(user, context, prev_conversation)
    else:
        comment = json_output["comment"]

    return json_output["strategies"], json_output["status"], comment




def frequency_step(user: User, prev_conversation: list[str], conversation_for_strategy_in_context: list[str]):
    """
    Third type of step aim at collecting information about how often a strategy is applyed by the user. 
    The use should respond with a number between 1 and 4.
    """
    logger.debug("Retrieving strategy")
    strategy_for_frequency = user.conversation_state.strategy_for_frequency

    logger.debug("Retrieving prompt")
    frequency_validate_prompt = get_frequency_validate_prompt(user, strategy_for_frequency)
    system_prompt = get_prompt(user, "system")
    logger.debug("Retrieving reasoning response")
    reasoning_response = get_llm_response(
        frequency_validate_prompt + system_prompt,
        user_prompt=None,
        temperature=0.0,
        # Use the full context conversation (user messages only) so the reasoning
        # call can actually see the number the user typed (e.g. "3").
        # conversation_for_strategy_in_context is NOT used here because it is
        # passed with a positional-arg bug that makes it always empty.
        prev_conversation=_user_only_conv(prev_conversation)
        )
    logger.debug("Retrieving prompt")
    format_frequency_prompt = get_format_frequency_prompt(user, strategy_for_frequency, reasoning_response)
    logger.debug("Retrieving JSON")
    # Format call: reasoning_response already embedded in prompt – no conversation needed.
    # Do NOT append the conversational system_prompt here: its behavioral rules conflict with
    # the task of outputting a numeric frequency rating in JSON.
    json_output, json_valid = try_get_json_completion(5, 0.0, 0.2, format_frequency_prompt,
                                                      expected_fields_model=StepFrequencyStepperFields,
                                                      prev_conversation=[],
                                                      user_prompt=None
                                                      )
    if not json_valid:
        return [], 0, "in_progress", _json_retry_comment(user, "frequency")
    if json_output["status"] == "in_progress" and len(prev_conversation) > (ABANDON_AFTER_STEPS * 2):
        json_output["status"] = "abandon"
        json_output["frequency"] = 0
    return strategy_for_frequency, json_output["frequency"], json_output["status"], json_output["comment"]



def validate_strategies(user_strategies):
    """Util function that compares the detected strategies from the user input with expert curated list of strategies"""
    all_strategies = get_all_strategies()
    valid_strategies = []
    for strategy in user_strategies:
        if strategy in all_strategies:
            valid_strategies.append(strategy)
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
    """xxx"""
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
            for field in expected_fields:
                if field not in json_output:
                    json_output[field] = ""
            # If the LLM put its conversational reply outside the JSON block, use it as comment fallback
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
