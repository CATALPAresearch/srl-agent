import json
import functools

from .config import get_interview_config_path
from .database.crud import get_language_by_id


@functools.lru_cache(maxsize=None)
def _load_prompts() -> dict:
    with open("config/prompts.json", "r", encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def _load_interview_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_prompt(user, prompt_name: str) -> str:
    prompts = _load_prompts()
    user_lang = get_language_by_id(user.language_id)
    return prompts[user_lang.lang_code][prompt_name]


def get_intro_prompt(user, limit: int) -> str:
    return get_prompt(user, "intro_check").replace("${limit}", str(limit))


def get_context_prompt(context: str, user) -> str:
    prompt = get_prompt(user, "context")
    return prompt.replace("${context}", context).replace("${subject}", user.study_subject)


def get_frequency_validate_prompt(user, strategy) -> str:
    prompt = get_prompt(user, "validate_frequency")
    return prompt.replace("${strategy_for_frequency}", str(strategy))


def get_frequency_prompt(user, context: str, strategy: str) -> str:
    prompt = get_prompt(user, "frequency")
    return prompt.replace("${strategy}", str(strategy)).replace("${context}", context)


def get_format_frequency_prompt(user, strategy, reasoning_response: str) -> str:
    prompt = get_prompt(user, "format_frequency")
    return prompt.replace(
        "${strategy_for_frequency}", str(strategy)).replace(
        "${reasoning_response}", reasoning_response)


def get_strategy_analysis_prompt(user) -> str:
    interview_context = _load_interview_config(get_interview_config_path())
    user_lang = get_language_by_id(user.language_id)
    strat_info = [cat["strategies"] for cat in interview_context[user_lang.lang_code]["categories"]]
    return get_prompt(user, "recognise_strategy").replace("${strat_info}", str(strat_info))


def get_format_strategy_prompt(user, reasoning_response: str, conv_length: int, context: str, limit: int) -> str:
    interview_context = _load_interview_config(get_interview_config_path())
    user_lang = get_language_by_id(user.language_id)
    strat_info = [cat["strategies"] for cat in interview_context[user_lang.lang_code]["categories"]]
    return get_prompt(user, "format_strategy").replace(
        "${reasoning_response}", reasoning_response).replace(
        "${strat_info}", str(strat_info)).replace(
        "${len(prev_conversation)}", str(conv_length)).replace(
        "${context}", context).replace(
        "${limit}", str(limit))


def get_complete_prompt(user, most_contexts_strat: str, const_strategy: str,
                        avg_freq, total_strat: int, const_strategies: list) -> str:
    interview_context = _load_interview_config(get_interview_config_path())
    user_lang = get_language_by_id(user.language_id)
    strat_info = interview_context[user_lang.lang_code]["categories"]
    return get_prompt(user, "interview_complete").replace(
        "${most_contexts}", most_contexts_strat).replace(
        "${const_strategy}", const_strategy).replace(
        "${avg_freq}", str(avg_freq)).replace(
        "${total_strat}", str(total_strat)).replace(
        "${const_strategies}", str(const_strategies)).replace(
        "${strategies}", str(strat_info))
