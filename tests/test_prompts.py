"""
Unit tests for app/prompts.py.

No DB or Ollama required: language lookups are mocked.
The lru_cache is cleared before each test class to isolate cache state.
"""

import os
import sys
import pathlib
from unittest.mock import patch, MagicMock

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# prompts.py opens config/prompts.json relative to cwd — must run from backend/
os.chdir(str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(lang_code="en", study_subject="Biology"):
    user = MagicMock()
    user.language_id = 1
    user.study_subject = study_subject
    return user


def _stub_lang(lang_code="en"):
    lang = MagicMock()
    lang.lang_code = lang_code
    return lang


def _patch_lang(lang_code="en"):
    """Context manager: patch get_language_by_id to return a stub language."""
    return patch("app.prompts.get_language_by_id", return_value=_stub_lang(lang_code))


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

class TestCaching:
    def setup_method(self):
        from app.prompts import _load_prompts, _load_interview_config
        _load_prompts.cache_clear()
        _load_interview_config.cache_clear()

    def test_load_prompts_returns_dict(self):
        from app.prompts import _load_prompts
        result = _load_prompts()
        assert isinstance(result, dict)
        assert "en" in result
        assert "de" in result

    def test_load_prompts_cached(self):
        from app.prompts import _load_prompts
        first = _load_prompts()
        second = _load_prompts()
        assert first is second

    def test_load_interview_config_returns_dict(self):
        from app.prompts import _load_interview_config
        from app.config import get_interview_config_path
        result = _load_interview_config(get_interview_config_path())
        assert isinstance(result, dict)

    def test_load_interview_config_cached(self):
        from app.prompts import _load_interview_config
        from app.config import get_interview_config_path
        path = get_interview_config_path()
        first = _load_interview_config(path)
        second = _load_interview_config(path)
        assert first is second


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------

class TestGetPrompt:
    def test_returns_string(self):
        from app.prompts import get_prompt
        with _patch_lang("en"):
            result = get_prompt(_mock_user(), "system")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_german_system_prompt_differs_from_english(self):
        from app.prompts import get_prompt
        with _patch_lang("en"):
            en = get_prompt(_mock_user(), "system")
        with _patch_lang("de"):
            de = get_prompt(_mock_user(), "system")
        assert en != de

    def test_unknown_key_raises(self):
        from app.prompts import get_prompt
        with _patch_lang("en"):
            with pytest.raises(KeyError):
                get_prompt(_mock_user(), "no_such_key_xyz")


# ---------------------------------------------------------------------------
# get_intro_prompt
# ---------------------------------------------------------------------------

class TestGetIntroPrompt:
    def test_limit_substituted(self):
        from app.prompts import get_intro_prompt
        with _patch_lang("en"):
            result = get_intro_prompt(_mock_user(), limit=7)
        assert "${limit}" not in result
        assert "7" in result

    def test_returns_string(self):
        from app.prompts import get_intro_prompt
        with _patch_lang("en"):
            result = get_intro_prompt(_mock_user(), limit=3)
        assert isinstance(result, str)

    def test_german_contains_german_text(self):
        from app.prompts import get_intro_prompt
        with _patch_lang("de"):
            result = get_intro_prompt(_mock_user(), limit=6)
        # German prompts use "du" (informal pronoun)
        assert any(w in result.lower() for w in ("du", "sie", "fach", "studier"))


# ---------------------------------------------------------------------------
# get_context_prompt
# ---------------------------------------------------------------------------

class TestGetContextPrompt:
    def test_context_substituted(self):
        from app.prompts import get_context_prompt
        with _patch_lang("en"):
            result = get_context_prompt("exam preparation", _mock_user())
        assert "${context}" not in result
        assert "exam preparation" in result

    def test_subject_substituted(self):
        from app.prompts import get_context_prompt
        with _patch_lang("en"):
            result = get_context_prompt("lectures", _mock_user(study_subject="Physics"))
        assert "${subject}" not in result
        assert "Physics" in result

    def test_all_placeholders_replaced(self):
        from app.prompts import get_context_prompt
        with _patch_lang("en"):
            result = get_context_prompt("seminars", _mock_user(study_subject="Chemistry"))
        assert "${" not in result


# ---------------------------------------------------------------------------
# get_frequency_validate_prompt
# ---------------------------------------------------------------------------

class TestGetFrequencyValidatePrompt:
    def test_strategy_substituted(self):
        from app.prompts import get_frequency_validate_prompt
        with _patch_lang("en"):
            result = get_frequency_validate_prompt(_mock_user(), "001-001")
        assert "${strategy_for_frequency}" not in result
        assert "001-001" in result

    def test_returns_string(self):
        from app.prompts import get_frequency_validate_prompt
        with _patch_lang("en"):
            result = get_frequency_validate_prompt(_mock_user(), "some_strategy")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_frequency_prompt
# ---------------------------------------------------------------------------

class TestGetFrequencyPrompt:
    def test_strategy_and_context_substituted(self):
        from app.prompts import get_frequency_prompt
        with _patch_lang("en"):
            result = get_frequency_prompt(_mock_user(), context="exams", strategy="spaced repetition")
        assert "${strategy}" not in result
        assert "${context}" not in result
        assert "spaced repetition" in result
        assert "exams" in result

    def test_all_placeholders_replaced(self):
        from app.prompts import get_frequency_prompt
        with _patch_lang("en"):
            result = get_frequency_prompt(_mock_user(), context="term papers", strategy="002-001")
        assert "${" not in result


# ---------------------------------------------------------------------------
# get_format_frequency_prompt
# ---------------------------------------------------------------------------

class TestGetFormatFrequencyPrompt:
    def test_strategy_and_reasoning_substituted(self):
        from app.prompts import get_format_frequency_prompt
        with _patch_lang("en"):
            result = get_format_frequency_prompt(_mock_user(), "003-002", "The user said 3.")
        assert "${strategy_for_frequency}" not in result
        assert "${reasoning_response}" not in result
        assert "003-002" in result
        assert "The user said 3." in result

    def test_all_placeholders_replaced(self):
        from app.prompts import get_format_frequency_prompt
        with _patch_lang("en"):
            result = get_format_frequency_prompt(_mock_user(), "003-002", "answer was 2")
        assert "${" not in result


# ---------------------------------------------------------------------------
# get_strategy_analysis_prompt
# ---------------------------------------------------------------------------

class TestGetStrategyAnalysisPrompt:
    def test_returns_string(self):
        from app.prompts import get_strategy_analysis_prompt
        with _patch_lang("en"):
            result = get_strategy_analysis_prompt(_mock_user())
        assert isinstance(result, str)
        assert len(result) > 20

    def test_strat_info_substituted(self):
        from app.prompts import get_strategy_analysis_prompt
        with _patch_lang("en"):
            result = get_strategy_analysis_prompt(_mock_user())
        assert "${strat_info}" not in result


# ---------------------------------------------------------------------------
# get_format_strategy_prompt
# ---------------------------------------------------------------------------

class TestGetFormatStrategyPrompt:
    def test_all_placeholders_replaced(self):
        from app.prompts import get_format_strategy_prompt
        with _patch_lang("en"):
            result = get_format_strategy_prompt(
                _mock_user(),
                reasoning_response="Detected strategy X.",
                conv_length=4,
                context="seminars",
                limit=6,
            )
        assert "${" not in result

    def test_reasoning_in_result(self):
        from app.prompts import get_format_strategy_prompt
        with _patch_lang("en"):
            result = get_format_strategy_prompt(
                _mock_user(),
                reasoning_response="unique_reasoning_abc",
                conv_length=2,
                context="ctx",
                limit=6,
            )
        assert "unique_reasoning_abc" in result

    def test_conv_length_and_context_in_result(self):
        from app.prompts import get_format_strategy_prompt
        with _patch_lang("en"):
            result = get_format_strategy_prompt(
                _mock_user(),
                reasoning_response="r",
                conv_length=8,
                context="exam_preparation_xyz",
                limit=6,
            )
        assert "8" in result
        assert "exam_preparation_xyz" in result


# ---------------------------------------------------------------------------
# get_complete_prompt
# ---------------------------------------------------------------------------

class TestGetCompletePrompt:
    def test_all_placeholders_replaced(self):
        from app.prompts import get_complete_prompt
        with _patch_lang("en"):
            result = get_complete_prompt(
                _mock_user(),
                most_contexts_strat="001-001",
                const_strategy="002-002",
                avg_freq=3.5,
                total_strat=5,
                const_strategies=["001-001", "002-002"],
            )
        assert "${" not in result

    def test_contains_strategy_values(self):
        from app.prompts import get_complete_prompt
        with _patch_lang("en"):
            result = get_complete_prompt(
                _mock_user(),
                most_contexts_strat="strategy_most_ctx_xyz",
                const_strategy="strategy_const_xyz",
                avg_freq=2.5,
                total_strat=3,
                const_strategies=["s1", "s2"],
            )
        assert "strategy_most_ctx_xyz" in result
        assert "strategy_const_xyz" in result
        assert "2.5" in result
