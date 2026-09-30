"""Tests for sympose.engine.status_phrases: a persona's own witty status-line phrases,
generated once from its soul and cached, with a generic fallback until then."""

import threading

import pytest
from helpers import write_persona

from sympose.engine import status_phrases
from sympose.engine.model import EngineModelError, ModelReply


@pytest.fixture(autouse=True)
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setattr(status_phrases, "_RUNNING", set())
    return directory


class Asked(list):
    def __init__(self):
        super().__init__()
        self.replies: list = [ModelReply("Thinking it through…\nOne sec…\nMulling it over…", 5)]


@pytest.fixture
def asked(monkeypatch):
    calls = Asked()

    def call_model(messages, model=None, **limits):
        calls.append({"messages": messages, "model": model, **limits})
        reply = calls.replies[min(len(calls), len(calls.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(status_phrases.model_mod, "call_model", call_model)
    return calls


# -- reading -----------------------------------------------------------------


def test_a_persona_with_no_phrases_yet_reads_the_fallback():
    assert status_phrases.has_own("samantha") is False
    assert status_phrases.phrases("samantha") == status_phrases.FALLBACK


def test_a_generated_file_is_read_back_one_phrase_per_line(profiles):
    (profiles / "status_phrases.md").write_text("Humming along…\nOne moment…\n")
    assert status_phrases.has_own("samantha") is True
    assert status_phrases.phrases("samantha") == ["Humming along…", "One moment…"]


def test_an_empty_phrases_file_reads_as_the_fallback(profiles):
    (profiles / "status_phrases.md").write_text("   \n")
    assert status_phrases.phrases("samantha") == status_phrases.FALLBACK


# -- generate() ----------------------------------------------------------------


def test_generate_writes_the_models_lines(asked, profiles):
    assert status_phrases.generate("samantha") is True
    assert (profiles / "status_phrases.md").read_text().splitlines() == [
        "Thinking it through…", "One sec…", "Mulling it over…",
    ]


def test_generate_sends_the_personas_soul(asked, profiles):
    (profiles / "soul.md").write_text("Warm, curious, a little wry.")
    status_phrases.generate("samantha")
    system, user = asked[0]["messages"]
    assert system["role"] == "system"
    assert user == {"role": "user", "content": "Warm, curious, a little wry."}


def test_generate_falls_back_to_the_default_soul_when_the_persona_has_none(asked):
    from sympose.engine import prompt

    status_phrases.generate("samantha")
    assert asked[0]["messages"][1]["content"] == prompt.DEFAULT_SOUL


def test_generate_does_nothing_when_the_persona_already_has_phrases(asked, profiles):
    (profiles / "status_phrases.md").write_text("Already here…\n")
    assert status_phrases.generate("samantha") is False
    assert len(asked) == 0
    assert (profiles / "status_phrases.md").read_text() == "Already here…\n"


def test_generate_strips_bullets_and_quotes_and_caps_the_count(asked):
    asked.replies = [ModelReply("\n".join(f'- "Line {i}"' for i in range(20)), 5)]
    status_phrases.generate("samantha")
    lines = status_phrases.phrases("samantha")
    assert lines[0] == "Line 0" and len(lines) == status_phrases._COUNT


def test_generate_with_no_persona_does_nothing(asked):
    assert status_phrases.generate("nobody") is False
    assert len(asked) == 0


def test_generate_when_the_model_fails_writes_nothing(asked):
    asked.replies = [EngineModelError("down")]
    assert status_phrases.generate("samantha") is False
    assert status_phrases.has_own("samantha") is False


def test_generate_with_an_empty_reply_writes_nothing(asked):
    asked.replies = [ModelReply("   \n  \n", 5)]
    assert status_phrases.generate("samantha") is False


# -- generate_in_background() ---------------------------------------------------


def test_background_generation_passes_the_chosen_model_on(monkeypatch):
    seen: list = []
    monkeypatch.setattr(status_phrases, "generate", lambda handle, model=None: seen.append((handle, model)))

    status_phrases.generate_in_background("samantha", "anthropic/claude-sonnet-5")
    for thread in threading.enumerate():
        if thread.name.startswith("phrases-"):
            thread.join(5)

    assert seen == [("samantha", "anthropic/claude-sonnet-5")]


def test_background_generation_is_skipped_when_already_has_phrases(profiles, monkeypatch):
    (profiles / "status_phrases.md").write_text("Already here…\n")
    called = []
    monkeypatch.setattr(status_phrases, "generate", lambda handle, model=None: called.append(handle))

    assert status_phrases.generate_in_background("samantha") is False
    assert called == []


def test_is_running_reflects_whether_a_generation_is_in_flight(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_generate(handle, model=None):
        started.set()
        release.wait(2)

    monkeypatch.setattr(status_phrases, "generate", slow_generate)

    assert status_phrases.is_running("samantha") is False
    status_phrases.generate_in_background("samantha")
    started.wait(2)
    assert status_phrases.is_running("samantha") is True
    release.set()
    for thread in threading.enumerate():
        if thread.name.startswith("phrases-"):
            thread.join(5)
    assert status_phrases.is_running("samantha") is False


def test_a_second_background_generation_while_one_runs_is_refused(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_generate(handle, model=None):
        started.set()
        release.wait(2)

    monkeypatch.setattr(status_phrases, "generate", slow_generate)

    assert status_phrases.generate_in_background("samantha") is True
    started.wait(2)
    assert status_phrases.generate_in_background("samantha") is False
    release.set()
    for thread in threading.enumerate():
        if thread.name.startswith("phrases-"):
            thread.join(5)


def test_generation_asks_in_the_chats_window(asked, monkeypatch):
    monkeypatch.setattr(status_phrases.budget, "_native_max", lambda model: 8192)
    status_phrases.generate("samantha", model="ollama_chat/gemma2:9b")
    assert asked[0]["num_ctx"] == status_phrases.budget.budget_for("ollama_chat/gemma2:9b").num_ctx
    assert asked[0]["max_tokens"] == status_phrases._MAX_REPLY_TOKENS


def test_a_cloud_models_reply_limit_is_not_the_small_local_one(asked, tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    status_phrases.generate("samantha", model="gemini/gemini-flash-latest")
    assert asked[0]["max_tokens"] > status_phrases._MAX_REPLY_TOKENS
