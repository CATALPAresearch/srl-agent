import json
import os
import requests
import time
import logging

from ollama import Client

from .database.crud import get_language_by_id

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL = os.getenv("MODEL")
try:
    OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
except ValueError:
    OLLAMA_NUM_PREDICT = 256
try:
    OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
except ValueError:
    OLLAMA_NUM_CTX = 2048
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "https://huggingface.co/")
# https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_TOKEN = os.getenv("EMBEDDING_TOKEN", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2
logger = logging.getLogger('InterviewAgent')
_OPENAI_MODEL_CACHE = None


def _extract_openai_content(data):
    """Extract text content from OpenAI-compatible chat completion responses."""
    try:
        message = data.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Some providers return structured content blocks.
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if isinstance(block.get("text"), str):
                        text_parts.append(block["text"])
                    elif block.get("type") == "text" and isinstance(block.get("content"), str):
                        text_parts.append(block["content"])
            return "\n".join([p for p in text_parts if p])
    except Exception as e:
        logger.warning("Could not parse OpenAI-compatible response content: %s", e)
    return ""


def _resolve_openai_model(base, headers):
    """Pick a usable chat model for OpenAI-compatible endpoints.

    If MODEL is unavailable (or configured to an embedding model), pick the first
    non-embedding model from /models. Cache the decision for this process.
    """
    global _OPENAI_MODEL_CACHE
    if _OPENAI_MODEL_CACHE:
        return _OPENAI_MODEL_CACHE

    configured = MODEL
    try:
        r = requests.get(base + "/models", headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
        if not ids:
            _OPENAI_MODEL_CACHE = configured
            return configured

        if configured in ids and "embedding" not in configured.lower():
            _OPENAI_MODEL_CACHE = configured
            return configured

        for mid in ids:
            if "embedding" not in mid.lower():
                logger.warning("Configured model '%s' not usable. Falling back to '%s'.", configured, mid)
                _OPENAI_MODEL_CACHE = mid
                return mid

        # As a last resort, use the first model id.
        _OPENAI_MODEL_CACHE = ids[0]
        return ids[0]
    except Exception as e:
        logger.warning("Could not resolve model from /models (%s). Using configured model '%s'.", e, configured)
        _OPENAI_MODEL_CACHE = configured
        return configured


def query_embeddings(text_to_embed):
    api_url = f"{EMBEDDING_URL}{EMBEDDING_MODEL}"
    headers = {"Authorization": f"Bearer {EMBEDDING_TOKEN}"}
    response = requests.post(
        api_url,
        # headers=headers,
        json={"inputs": text_to_embed, "options": {"wait_for_model": True}})
    return response.json()


def get_model_names(base_url):
    """
    """
    client = Client(host=base_url)
    names = []
    for model in client.list()['models']:
        m = dict(model)
        names.append(m['model'])
    return names


def get_llm_response(
        system_prompt,
        user_prompt=None,
        temperature=0.0,
        top_k=25,
        top_p=0.3,
        repeat_penalty=1.1,
        prev_conversation=None,
        expected_fields_model=None,
):
    # --- HARD DEV GUARD: skip LLM entirely ---
    if os.getenv("DISABLE_LLM", "false").lower() == "true":
        logger.warning("DISABLE_LLM=true - skipping LLM call")
        return (
            "Hallo! Lass uns mit dem Interview beginnen. "
            "In welchem Fach möchtest du einen Abschluss machen?"
        )

    logger.info("System Prompt: %s", system_prompt)
    logger.info("User Prompt: %s", user_prompt)

    # Use user/assistant format instead of system role for llama3.2 compatibility
    messages = [
        {"role": "user", "content": system_prompt},
        {"role": "assistant", "content": "Understood, I will conduct the interview."},
    ]
    if prev_conversation:
        messages.extend(prev_conversation)
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})

    attempts = 5
    retry_delay = 1.0
    response = get_response(messages, temperature, top_k, top_p, repeat_penalty)
    while attempts > 0:
        if response is None or not hasattr(response, "message") or response.message.content == "":
            time.sleep(retry_delay)
            response = get_response(messages, temperature + 0.1, top_k, top_p, repeat_penalty)
            attempts -= 1
            retry_delay *= 2
        else:
            break

    logger.info('@llm: response::: ')
    logger.info(response)
    response_content = response.message.content if (response and hasattr(response, "message")) else None

    if not response_content:
        logger.warning("Empty response from LLM after retries; returning fallback text")
        return (
            "Ich konnte gerade keine Antwort vom Sprachmodell erhalten. Bitte versuche es erneut."
            if user_prompt and any(ch in user_prompt for ch in "äöüß")
            else "I could not get a response from the language model right now. Please try again."
        )
    logger.info("Response: %s", response_content)
    return response_content


def get_response(messages, temperature, top_k=25, top_p=0.3, repeat_penalty=1.1):
    """Call LLM via HTTP. Supports Ollama (/api/chat) and OpenAI-compatible servers (/v1/chat/completions)."""
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    base = BASE_URL.rstrip("/")
    is_openai_compat = "/v1" in base

    if is_openai_compat:
        # OpenAI-compatible API (KI-Connect, Open WebUI with /v1, etc.)
        logger.info("Send request via OpenAI-compatible API")
        try:
            model_to_use = _resolve_openai_model(base, headers)
            payload = {
                "model": model_to_use,
                "messages": messages,
                "stream": False,
                "temperature": temperature,
                "max_tokens": 512,
            }
            r = requests.post(base + "/chat/completions", json=payload, headers=headers, timeout=120)
            r.raise_for_status()
            data = r.json()
            logger.info("OpenAI API raw response: %s", data)
            content = _extract_openai_content(data)
            mock = type('MockResponse', (), {'message': type('msg', (), {'content': content})()})()
            return mock
        except Exception as e:
            logger.error("HTTP call to OpenAI-compatible API failed: %s", e)
            return None
    else:
        # Native Ollama API
        logger.info("Send request via Ollama API")
        try:
            payload = {
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_k": top_k,
                    "top_p": top_p,
                    "repeat_penalty": repeat_penalty,
                    "num_predict": OLLAMA_NUM_PREDICT,
                    "num_ctx": OLLAMA_NUM_CTX
                }
            }
            r = requests.post(base + "/api/chat", json=payload, headers=headers, timeout=120)
            r.raise_for_status()
            data = r.json()
            logger.info("Ollama raw response: %s", data)
            content = data.get("message", {}).get("content", "")
            mock = type('MockResponse', (), {'message': type('msg', (), {'content': content})()})()
            return mock
        except Exception as e:
            logger.error(f"HTTP call to Ollama failed: {e}")
            return None


def get_prompt(user, prompt_name):
    with open("config/prompts.json", "r", encoding="utf-8") as file:
        prompts = json.load(file)
    user_lang = get_language_by_id(user.language_id)
    prompt = prompts[user_lang.lang_code][prompt_name]
    return prompt


def get_intro_prompt(user, limit):
    return get_prompt(user, "intro_check").replace("${limit}", str(limit))


def get_context_prompt(context, user):
    subject = user.study_subject
    prompt = get_prompt(user, "context")
    prompt = prompt.replace(
        "${context}", context).replace(
        "${subject}", subject)
    return prompt


def get_frequency_validate_prompt(user, strategy):
    prompt = get_prompt(user, "validate_frequency")
    prompt = prompt.replace("${strategy_for_frequency}", str(strategy))
    return prompt


def get_frequency_prompt(user, context, strategy):
    prompt = get_prompt(user, "frequency")
    prompt = prompt.replace("${strategy}", str(strategy)).replace("${context}", context)
    return prompt


def get_format_frequency_prompt(user, strategy, reasoning_response):
    prompt = get_prompt(user, "format_frequency")
    prompt = prompt.replace(
        "${strategy_for_frequency}", str(strategy)).replace(
        "${reasoning_response}", reasoning_response)
    return prompt


def get_strategy_analysis_prompt(user):
    from .config import get_interview_config_path
    with open(get_interview_config_path(), "r", encoding="utf-8") as file:
        interview_context = json.load(file)
    user_lang = get_language_by_id(user.language_id)
    strat_info = []
    for category in interview_context[user_lang.lang_code]["categories"]:
        strat_info.append(category["strategies"])
    prompt = get_prompt(user, "recognise_strategy").replace("${strat_info}", str(strat_info))
    return prompt


def get_format_strategy_prompt(user, reasoning_response, conv_length, context, limit):
    from .config import get_interview_config_path
    with open(get_interview_config_path(), "r", encoding="utf-8") as file:
        interview_context = json.load(file)
    user_lang = get_language_by_id(user.language_id)
    strat_info = []
    for category in interview_context[user_lang.lang_code]["categories"]:
        strat_info.append(category["strategies"])
    prompt = get_prompt(user, "format_strategy").replace(
        "${reasoning_response}", reasoning_response).replace(
        "${strat_info}", str(strat_info)).replace(
        "${len(prev_conversation)}", str(conv_length)).replace(
        "${context}", context).replace(
        "${limit}", str(limit))
    return prompt


def get_complete_prompt(user, most_contexts_strat, const_strategy, avg_freq, total_strat, const_strategies):
    prompt = get_prompt(user, "interview_complete")
    from .config import get_interview_config_path
    with open(get_interview_config_path(), "r", encoding="utf-8") as file:
        interview_context = json.load(file)
    user_lang = get_language_by_id(user.language_id)
    strat_info = interview_context[user_lang.lang_code]["categories"]
    prompt = prompt.replace(
        "${most_contexts}", most_contexts_strat).replace(
        "${const_strategy}", const_strategy).replace(
        "${avg_freq}", str(avg_freq)).replace(
        "${total_strat}", str(total_strat)).replace(
        "${const_strategies}", str(const_strategies)).replace(
        "${strategies}", str(strat_info)
    )
    return prompt

def send_user_feedback(text):
    logger.info(f"[USER FEEDBACK] {text}")
