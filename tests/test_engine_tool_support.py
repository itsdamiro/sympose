"""Which models can call tools (docs/decisions/040): when a model is remembered as unable, and how often a
running Ollama is asked. What Ollama says and what litellm's table says are tested in `test_engine_lookup`."""

import json

from sympose.engine import tool_support

CLOUD = "gemini/gemini-flash-latest"
LOCAL = "ollama_chat/some-model:9b"


def test_one_refusal_is_a_strike_not_a_verdict(monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    tool_support.note_refusal(CLOUD)

    assert tool_support.can_call_tools(CLOUD) is True


def test_two_refusals_in_a_row_mark_the_model_unable(monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    tool_support.note_refusal(CLOUD)
    tool_support.note_refusal(CLOUD)

    assert tool_support.can_call_tools(CLOUD) is False


def test_a_turn_that_worked_between_two_refusals_clears_the_first(monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    tool_support.note_refusal(CLOUD)
    tool_support.note_success(CLOUD)
    tool_support.note_refusal(CLOUD)

    assert tool_support.can_call_tools(CLOUD) is True


def test_strikes_are_kept_per_model(monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    tool_support.note_refusal(CLOUD)
    tool_support.note_refusal("gemini/other")

    assert tool_support.can_call_tools(CLOUD) and tool_support.can_call_tools("gemini/other")


def test_a_model_marked_unable_stays_unable_whatever_ollama_says(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tool_support, "urlopen", lambda request, timeout: calls.append(1) or _Ok(json.dumps({"capabilities": ["tools"]}).encode())
    )

    tool_support.mark_unable(LOCAL)

    assert tool_support.can_call_tools(LOCAL) is False and calls == []


class _Ok:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self.body


def test_a_failed_question_to_ollama_is_not_put_again_for_a_minute(monkeypatch):
    asked = []

    def refused(request, timeout):
        asked.append(1)
        raise OSError("connection refused")

    now = [1000.0]
    monkeypatch.setattr(tool_support, "urlopen", refused)
    monkeypatch.setattr(tool_support.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)

    tool_support.can_call_tools(LOCAL)
    tool_support.can_call_tools(LOCAL)
    now[0] += tool_support._OLLAMA_RETRY_SECONDS + 1
    tool_support.can_call_tools(LOCAL)

    assert len(asked) == 2  # once, then not within the minute, then again after it


def test_an_answer_from_ollama_is_kept_for_the_process(monkeypatch):
    asked = []
    monkeypatch.setattr(
        tool_support, "urlopen", lambda request, timeout: asked.append(1) or _Ok(json.dumps({"capabilities": ["tools"]}).encode())
    )
    now = [1000.0]
    monkeypatch.setattr(tool_support.time, "monotonic", lambda: now[0])

    tool_support.can_call_tools(LOCAL)
    now[0] += 10_000
    tool_support.can_call_tools(LOCAL)

    assert len(asked) == 1
