"""
Unit tests for the interview protocol logic in app/steps.py (and the language of the
pending-summary message in app/core.py).

No DB or LLM required: all lookups and LLM calls are mocked.
"""

import sys
import pathlib
from unittest.mock import patch, MagicMock

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _lang(code):
    lang = MagicMock()
    lang.lang_code = code
    return lang


def _user(strategy_for_frequency="004-001"):
    user = MagicMock()
    user.language_id = "lang-id"
    user.conversation_state.strategy_for_frequency = strategy_for_frequency
    return user


def _conv(*user_answers, question="Wie gehst du vor?"):
    """Assistant question followed by alternating user answers / assistant follow-ups."""
    conv = [{"role": "assistant", "content": question}]
    for answer in user_answers:
        conv.append({"role": "user", "content": answer})
        conv.append({"role": "assistant", "content": "Rückfrage"})
    return conv[:-1] if user_answers else conv


# ===========================================================================
# parse_frequency
# ===========================================================================

class TestParseFrequency:
    @pytest.mark.parametrize("text,expected", [
        ("3", 3),
        ("1", 1),
        ("4.", 4),
        ("drei", 3),
        ("Vier!", 4),
        ("eins", 1),
        ("three", 3),
        ("3-4", 3),
        ("3 bis 4", 3),
        ("eins bis zwei", 1),
        ("Ich würde sagen 2", 2),
        ("2,5", 2),
    ])
    def test_valid_takes_first_number(self, text, expected):
        from app.steps import parse_frequency
        assert parse_frequency(text) == expected

    @pytest.mark.parametrize("text", [
        "", "5", "0", "10 mal", "oft", "manchmal", "ein bisschen", "Einsatz", None,
    ])
    def test_invalid_returns_none(self, text):
        from app.steps import parse_frequency
        assert parse_frequency(text) is None

    def test_first_number_out_of_range_is_invalid(self):
        from app.steps import parse_frequency
        assert parse_frequency("5 oder 4") is None


# ===========================================================================
# frequency_step
# ===========================================================================

class TestFrequencyStep:
    QUESTION = "Wie oft fasst du Texte zusammen? Gib deine Antwort auf einer Skala von 1 bis 4."

    def _run(self, conv, lang="de"):
        from app.steps import frequency_step
        with patch("app.steps.get_language_by_id", return_value=_lang(lang)):
            return frequency_step(_user("004-001"), conv)

    def test_valid_answer_completes(self):
        strategy, freq, status, _ = self._run(_conv("3", question=self.QUESTION))
        assert (strategy, freq, status) == ("004-001", 3, "completed")

    def test_only_latest_answer_is_parsed(self):
        # an earlier "4" must not be picked up when the latest answer is "2"
        conv = _conv("vier oder so", question=self.QUESTION)
        conv += [{"role": "assistant", "content": self.QUESTION}, {"role": "user", "content": "2"}]
        _, freq, status, _ = self._run(conv)
        assert (freq, status) == (2, "completed")

    def test_invalid_answer_repeats_question_with_hint(self):
        from app.steps import _FREQ_HINT_DE
        strategy, freq, status, comment = self._run(_conv("oft", question=self.QUESTION))
        assert (strategy, freq, status) == ("004-001", 0, "in_progress")
        assert comment == f"{_FREQ_HINT_DE} {self.QUESTION}"

    def test_repeated_question_does_not_stack_hints(self):
        from app.steps import _FREQ_HINT_DE
        repeated = f"{_FREQ_HINT_DE} {self.QUESTION}"
        _, _, status, comment = self._run(_conv("keine Ahnung", question=repeated))
        assert status == "in_progress"
        assert comment == repeated

    def test_english_hint(self):
        from app.steps import _FREQ_HINT_EN
        _, _, _, comment = self._run(_conv("often", question="How often?"), lang="en")
        assert comment == f"{_FREQ_HINT_EN} How often?"


# ===========================================================================
# strategy_step
# ===========================================================================

class TestStrategyStep:
    def _run(self, raw_strategies, conv):
        from app.steps import strategy_step
        valid_ids = {"001-001", "004-001", "004-002", "008-001"}
        with patch("app.steps.USE_RAG_STRATEGY", False), \
                patch("app.steps._detect_strategies_llm", return_value=raw_strategies), \
                patch("app.steps.validate_strategies",
                      side_effect=lambda ids: [s for s in ids if s in valid_ids]), \
                patch("app.steps._strategy_conversational_comment", return_value="Rückfrage"):
            return strategy_step(_user(), "Prüfungsvorbereitung", conv)

    def test_detected_strategies_complete_deduplicated(self):
        strategies, status, _ = self._run(
            ["004-001", "001-001", "004-001", "008-001", "other", "kein-id"], _conv("Ich fasse zusammen")
        )
        assert status == "completed"
        assert strategies == ["004-001", "001-001"]

    def test_detected_on_later_answer_still_completes(self):
        strategies, status, _ = self._run(["004-002"], _conv("a", "b", "c", "d"))
        assert (strategies, status) == (["004-002"], "completed")

    def test_nothing_detected_asks_follow_up(self):
        strategies, status, comment = self._run([], _conv("weiß nicht"))
        assert (strategies, status, comment) == ([], "in_progress", "Rückfrage")

    def test_only_other_counts_as_nothing_detected(self):
        strategies, status, _ = self._run(["008-001", "other"], _conv("weiß nicht"))
        assert (strategies, status) == ([], "in_progress")

    def test_follow_ups_are_limited(self):
        from app.steps import MAX_FOLLOWUPS, OTHER_STRATEGY
        # first answer + MAX_FOLLOWUPS answers to follow-ups → still in progress up to the limit
        answers = ["x"] * MAX_FOLLOWUPS
        assert self._run([], _conv(*answers))[1] == "in_progress"

        answers = ["x"] * (MAX_FOLLOWUPS + 1)
        strategies, status, _ = self._run([], _conv(*answers))
        assert (strategies, status) == ([OTHER_STRATEGY], "abandon")


# ===========================================================================
# intro_step
# ===========================================================================

class TestIntroStep:
    def _run(self, json_output, conv, valid=True):
        from app.steps import intro_step
        with patch("app.steps.try_get_json_completion", return_value=(json_output, valid)), \
                patch("app.steps.get_intro_prompt", return_value=""), \
                patch("app.steps.get_prompt", return_value=""), \
                patch("app.steps.get_language_by_id", return_value=_lang("de")):
            return intro_step(_user(), conv)

    def test_subject_completes_regardless_of_llm_status(self):
        out = {"study_subject": "Mathematik", "status": "in_progress", "comment": "x"}
        assert self._run(out, _conv("Mathe"))[:2] == ("Mathematik", "completed")

    @pytest.mark.parametrize("subject", ["", "unknown", "null", "Unbekannt"])
    def test_missing_subject_asks_again(self, subject):
        out = {"study_subject": subject, "status": "in_progress", "comment": "Welches Fach?"}
        assert self._run(out, _conv("Hallo")) == ("", "in_progress", "Welches Fach?")

    def test_invalid_json_uses_fallback_question(self):
        subject, status, comment = self._run("garbage", _conv("Hallo"), valid=False)
        assert (subject, status) == ("", "in_progress")
        assert "Fach" in comment

    def test_follow_ups_are_limited(self):
        from app.steps import MAX_FOLLOWUPS
        out = {"study_subject": "", "status": "in_progress", "comment": "?"}
        assert self._run(out, _conv(*["x"] * MAX_FOLLOWUPS))[1] == "in_progress"
        assert self._run(out, _conv(*["x"] * (MAX_FOLLOWUPS + 1)))[:2] == ("unknown", "abandon")


# ===========================================================================
# try_get_json_completion — fields split across nesting levels
# ===========================================================================

class TestJsonEnvelopeMerge:
    def test_strategies_nested_status_top_level(self):
        from app.steps import try_get_json_completion, StepStrategieStepperFields
        llm_out = (
            '```json\n{"complete": {"strategies": ["004-001"]}, '
            '"status": "completed", "comment": "Weiter"}\n```'
        )
        with patch("app.steps.get_llm_response", return_value=llm_out):
            result, valid = try_get_json_completion(
                1, 0.0, 0.2, "sys", expected_fields_model=StepStrategieStepperFields
            )
        assert valid is True
        assert result["strategies"] == ["004-001"]
        assert result["status"] == "completed"
        assert result["comment"] == "Weiter"


# ===========================================================================
# core._pending_summary_message — must follow the user's language
# ===========================================================================

class TestPendingSummaryLanguage:
    @pytest.mark.parametrize("code,needle", [
        ("de", "Das Interview ist abgeschlossen"),
        ("en", "The interview is complete"),
    ])
    def test_language(self, code, needle):
        from app.core import _pending_summary_message
        with patch("app.core.get_language_by_id", return_value=_lang(code)):
            assert needle in _pending_summary_message(_user())
