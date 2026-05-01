"""
Interview completion integration test.

Simulates a complete interview end-to-end via the Flask test client:
  POST /startConversation  → bot greeting
  POST /reply (loop)       → drives interview through all steps until
                             the backend signals completion

The "answer script" uses fixed, realistic replies that should trigger:
  • intro   : student names a study subject
  • strategy: mentions at least one learning strategy per context
  • frequency: provides a numeric rating

Stats printed at the end:
  - total turns taken
  - HTTP status codes seen
  - conversation steps visited
  - whether interview_completed flag is True in DB

Usage
-----
    cd backend
    poetry run pytest ../tests/test_interview_completion.py -v -s
"""

import json
import os
import pathlib
import random
import sys
import time
import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import app as flask_app_instance, db as _db  # noqa: E402
from app.database.crud import get_user                 # noqa: E402

# ---------------------------------------------------------------------------
# Test user
# ---------------------------------------------------------------------------
# Each run gets a unique user ID so every completed interview adds a new member
# to the cohort, making the radar chart's average line more meaningful over time.
# Override with TEST_USERID=<id> to pin to a specific user (e.g. your browser ID).
_RUN_ID = f"test_bot_{int(time.time())}"
TEST_USER = os.getenv("TEST_USERID", _RUN_ID)
TEST_CLIENT = "web"       # must match the hardcoded client in StudentResults.vue
TEST_LANG = "en"

# ---------------------------------------------------------------------------
# Answer selection
# Chooses a reply based on what the bot just asked.
# ---------------------------------------------------------------------------

# Keywords that indicate a frequency/quantity question
_FREQUENCY_KEYWORDS = [
    "how often", "wie oft", "frequency", "scale", "rarely", "sometimes",
    "seldom", "rating", "rate", "1 (", "1 =", "1=", "(1)", "scale of 1",
    "on a scale", "auf einer skala", "how frequently", "how much",
]

# Three paraphrased variants per strategy code (strategy_code_map.json order).
# The pool is shuffled at test start so each run covers strategies in a different
# order, producing varied detected-strategy results across runs.
_STRATEGY_VARIANTS: dict[str, list[str]] = {
    "001-001": [  # rehearsal_mnemonics
        "I use flashcards and mnemonic devices to memorise key terms — I repeat them out loud until they really stick.",
        "I create rhymes and acronyms to help me remember important facts and recite them repeatedly before an exam.",
        "I write key formulas and vocabulary on small cards and test myself by going through the deck every morning.",
    ],
    "001-002": [  # practice_testing
        "I do as many past exam papers as I can find and then check my answers carefully to spot gaps in my knowledge.",
        "I make up my own quiz questions after reading each chapter and try to answer them without looking at the text.",
        "Before any exam I work through at least three past papers under timed conditions and mark them myself.",
    ],
    "002-001": [  # repetition_over_time
        "I spread my studying over several weeks, revisiting the same material multiple times with deliberate gaps in between.",
        "I use spaced repetition — reviewing material after one day, three days, then a week — letting the forgetting curve work for me.",
        "I start preparing months before the exam and keep returning to earlier topics so the knowledge really sinks in over time.",
    ],
    "003-001": [  # reviewing_records
        "I go back through all my lecture notes and readings from the semester to refresh my memory before the exam.",
        "I keep all my old assignments and marked work and review them to see what feedback I got and where I went wrong.",
        "I look through my previous essays and seminar notes to remind myself of the key arguments I've already encountered.",
    ],
    "004-001": [  # highlighting_underlining
        "I highlight the most important sentences in the textbook and underline key passages so they stand out when I review.",
        "I use different coloured highlighters — definitions in yellow, examples in pink, key arguments in green.",
        "I read a chapter once first, then go back and underline the sentences that summarise the main point of each paragraph.",
    ],
    "004-002": [  # organization
        "I organise my notes into structured outlines and group related concepts together so I can see how ideas connect.",
        "I create mind maps at the start of a topic to see how everything relates, then fill in the details as I study.",
        "I sort my study materials by theme rather than by lecture date so I can see the big picture across the whole module.",
    ],
    "004-003": [  # keeping_records
        "I keep a detailed study journal and write down everything important from lectures so I have a complete record to look back at.",
        "I take thorough notes during every lecture and summarise them into a single document at the end of each week.",
        "I log all the sources I've read and note the key points from each, so I can find them again when writing essays.",
    ],
    "004-004": [  # visualization
        "I draw diagrams and charts to visualise complex concepts and the relationships between different ideas.",
        "I make flowcharts to trace cause-and-effect chains and timelines to get a visual sense of how events unfolded.",
        "I sketch concept maps with arrows connecting related terms — seeing it visually helps me grasp the structure.",
    ],
    "005-001": [  # teaching_preparing_to_teach
        "I explain the material to my flatmate as if I were teaching it — if I can't explain it clearly, I know I need to study it more.",
        "I prepare short informal lectures for my study group where I have to present a topic, forcing me to truly understand it.",
        "I pretend I'm a lecturer and explain a concept from scratch to an imaginary student — gaps in my explanation reveal what I still need to learn.",
    ],
    "005-002": [  # self_explanation
        "I talk through the content out loud and ask myself questions to make sure I genuinely understand it rather than just memorising it.",
        "After reading a section I close the book and try to explain in my own words what I just read, then check if I missed anything.",
        "I narrate my thinking while solving problems, asking myself why each step works — it slows me down but deepens understanding.",
    ],
    "006-001": [  # goal_setting_planning
        "I set specific study goals for each session, like finishing a particular chapter, and plan my whole week around those targets.",
        "At the start of each semester I map out all the deadlines and work backwards to set weekly study targets for every module.",
        "I write down exactly what I want to achieve in each study session before I start, so I know when I'm done.",
    ],
    "006-002": [  # self_evaluating_regulation
        "I regularly quiz myself to see how well I know the material and then adjust my study plan depending on where I struggle most.",
        "I keep track of which topics I'm confident about and which ones I'm weak on, then shift more time towards the weaker areas.",
        "After each study session I briefly reflect on what went well and what I still don't understand, and update my plan accordingly.",
    ],
    "007-001": [  # environmental_structuring
        "I always study at the same desk, put my phone in another room, and use a white-noise app to block out distractions.",
        "I go to the library whenever I need to focus seriously — being in a quiet, dedicated space makes a huge difference.",
        "I keep my desk completely clear of everything except what I'm working on and switch off all notifications before I start.",
    ],
    "007-002": [  # self_consequences
        "I reward myself with a coffee break or an episode of a show after finishing a study block — it keeps me motivated.",
        "I tell myself I can only go out with friends once I've hit my study target for the day, which helps me stay on track.",
        "I set small personal rewards — like a favourite snack — that I only allow myself after completing a difficult task.",
    ],
    "007-003": [  # seeking_social_assistance
        "I ask my professor during office hours when I'm stuck, and I regularly join a study group to discuss difficult topics.",
        "Whenever I'm confused I post a question in the module forum or message a classmate — talking it through always helps.",
        "I form a small study group and we take turns explaining topics to each other and testing one another.",
    ],
    "007-004": [  # seeking_selecting_information
        "I search for additional resources online — YouTube explanations or academic papers — whenever the textbook isn't clear enough.",
        "I don't just rely on the course readings — I actively look for review articles and lecture videos from other universities.",
        "When I don't understand something from the slides I search for a clearer explanation in a different textbook or tutorial.",
    ],
    "007-005": [  # time_management
        "I use the Pomodoro technique: 25 minutes of focused work, then a 5-minute break. I block study slots in my calendar too.",
        "I plan my schedule at the beginning of each week, allocating specific time slots to each subject and sticking to them.",
        "I track how I actually spend my study time using a simple log, which shows me where I'm wasting time.",
    ],
}

# Flat shuffled pool — rebuilt at module load and re-shuffled per test run
_ANSWER_POOL: list[str] = []
_answer_idx: int = 0


def _build_answer_pool(seed: int | None = None) -> None:
    """Flatten all variants and shuffle for variety across runs."""
    global _ANSWER_POOL, _answer_idx
    pool = [v for variants in _STRATEGY_VARIANTS.values() for v in variants]
    rng = random.Random(seed)
    rng.shuffle(pool)
    _ANSWER_POOL = pool
    _answer_idx = 0


MAX_TURNS = 80       # safety cap; a normal interview takes ~5–15 turns
SLEEP_BETWEEN = 0    # seconds to wait between turns (0 = no delay)


def _choose_answer(bot_message: str) -> str:
    """Return a number 1-4 for frequency questions, a strategy description otherwise."""
    global _answer_idx
    msg_lower = (bot_message or "").lower()

    if any(kw in msg_lower for kw in _FREQUENCY_KEYWORDS):
        return "3"  # "often" — always a valid rating

    answer = _ANSWER_POOL[_answer_idx % len(_ANSWER_POOL)]
    _answer_idx += 1
    return answer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    flask_app_instance.config["TESTING"] = True
    with flask_app_instance.app_context():
        _db.create_all()
        yield flask_app_instance.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client, path: str, payload: dict) -> tuple[int, dict | str]:
    resp = client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
    )
    try:
        data = json.loads(resp.data)
    except Exception:
        data = resp.data.decode()
    return resp.status_code, data


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

class TestInterviewCompletion:

    @pytest.mark.skipif(
        os.getenv("DISABLE_LLM", "false").lower() == "true",
        reason="Interview completion requires a live LLM — set DISABLE_LLM=false and point BASE_URL at a running Ollama instance",
    )
    def test_full_interview(self, client):
        stats = {
            "turns": 0,
            "status_codes": [],
            "steps_seen": set(),
            "bot_messages": [],
            "errors": [],
        }

        # ── 0. Shuffle answer pool for variety ───────────────────────────
        seed = int(time.time())
        _build_answer_pool(seed=seed)
        print(f"\n[USER] {TEST_USER}  →  http://localhost:5000/#/results?userid={TEST_USER}")
        print(f"[SEED] Answer pool seed: {seed}  (re-run with same seed to reproduce)")

        # ── 1. Start conversation ────────────────────────────────────────
        status, data = _post(client, "/startConversation", {
            "language": TEST_LANG,
            "client": TEST_CLIENT,
            "userid": TEST_USER,
        })
        stats["status_codes"].append(status)
        assert status == 200, f"/startConversation returned {status}: {data}"

        greeting = data.get("message") if isinstance(data, dict) else data
        stats["bot_messages"].append(f"[START] {greeting}")
        print(f"\n[BOT] {greeting}")

        # ── 2. Reply loop ────────────────────────────────────────────────
        last_bot_msg = greeting  # seed with the greeting for first answer choice
        interview_done = False

        with flask_app_instance.app_context():
            for turn in range(MAX_TURNS):
                # intro turn: always name a subject
                if turn == 0:
                    answer = "I'm studying Computer Science."
                else:
                    answer = _choose_answer(last_bot_msg)

                print(f"\n[USER turn {turn + 1}] {answer}")

                status, data = _post(client, "/reply", {
                    "message": answer,
                    "client": TEST_CLIENT,
                    "userid": TEST_USER,
                })
                stats["turns"] += 1
                stats["status_codes"].append(status)

                if status != 200:
                    msg = data.get("message") if isinstance(data, dict) else data
                    stats["errors"].append(f"Turn {turn + 1}: HTTP {status} – {msg}")
                    print(f"  [ERROR] HTTP {status}: {msg}")
                    # Don't abort — keep track and continue to see if it recovers
                    continue

                bot_msg = data.get("message") if isinstance(data, dict) else data
                stats["bot_messages"].append(f"[T{turn + 1}] {bot_msg}")
                print(f"[BOT] {bot_msg}")
                last_bot_msg = bot_msg or ""

                # Check DB state
                user = get_user(TEST_USER, TEST_CLIENT)
                assert user is not None
                step = user.conversation_state.current_conversation_step
                stats["steps_seen"].add(step)

                if user.conversation_state.interview_completed:
                    interview_done = True
                    print(f"\n✓ Interview marked completed after {turn + 1} turns")
                    break

                if step == "complete":
                    interview_done = True
                    print(f"\n✓ Reached 'complete' step after {turn + 1} turns")
                    break

                if SLEEP_BETWEEN:
                    time.sleep(SLEEP_BETWEEN)

        # ── 3. Print stats ───────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("INTERVIEW COMPLETION TEST — STATS")
        print("=" * 60)
        print(f"  Total turns taken : {stats['turns']}")
        print(f"  Max turns allowed : {MAX_TURNS}")
        print(f"  Steps visited     : {sorted(stats['steps_seen'])}")
        print(f"  Status codes seen : {sorted(set(stats['status_codes']))}")
        print(f"  Errors            : {len(stats['errors'])}")
        for e in stats["errors"]:
            print(f"    • {e}")
        print(f"  Interview done    : {interview_done}")
        print("=" * 60)

        assert interview_done, (
            f"Interview did NOT complete within {MAX_TURNS} turns. "
            f"Last step: {sorted(stats['steps_seen'])[-1] if stats['steps_seen'] else 'unknown'}. "
            f"Errors: {stats['errors']}"
        )
        assert len(stats["errors"]) == 0, f"Errors occurred during interview: {stats['errors']}"
