"""Which models can call tools (docs/decisions/040): when a model is remembered as unable, and how often a
running Ollama is asked. What Ollama says and what litellm's table says are tested in `test_engine_lookup`."""

import json
import threading

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


def test_concurrent_refusals_do_not_lose_a_strike(monkeypatch):
    """Regression test: two personas can fail on the same cloud model at the same instant.
    `_STRIKES[model] = _STRIKES.get(model, 0) + 1` is a read-modify-write, not one atomic step:
    the first thread's write is deliberately held back here until the second thread has read and
    written its own increment, off the same stale starting count. Without the lock the first
    thread's write clobbers the second's and one strike vanishes."""
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    first_call = threading.Event()
    proceed = threading.Event()
    used = [False]

    class SlowDict(dict):
        def __setitem__(self, key, value):
            if not used[0]:
                used[0] = True
                first_call.set()
                proceed.wait(timeout=0.5)
            dict.__setitem__(self, key, value)

    monkeypatch.setattr(tool_support, "_STRIKES", SlowDict())

    def refuse_first():
        tool_support.note_refusal(CLOUD)

    def refuse_second():
        assert first_call.wait(timeout=0.5)
        tool_support.note_refusal(CLOUD)
        proceed.set()

    t1 = threading.Thread(target=refuse_first)
    t2 = threading.Thread(target=refuse_second)
    t1.start()
    t2.start()
    t1.join(timeout=1)
    t2.join(timeout=1)

    assert tool_support._STRIKES[CLOUD] == 2


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


def test_a_timeout_from_ollama_is_asked_once_more_with_a_longer_limit(monkeypatch):
    limits = []

    def late_then_answers(request, timeout):
        limits.append(timeout)
        if len(limits) == 1:
            raise TimeoutError("timed out")
        return _Ok(json.dumps({"capabilities": ["tools"]}).encode())

    monkeypatch.setattr(tool_support, "urlopen", late_then_answers)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)  # the table lags

    assert tool_support.can_call_tools(LOCAL) is True
    assert limits == [tool_support._OLLAMA_TIMEOUT_SECONDS, tool_support._OLLAMA_SLOW_TIMEOUT_SECONDS]


def test_an_ollama_that_is_late_twice_is_taken_to_have_tools_not_left_to_litellms_table(monkeypatch, caplog):
    asked = []

    def late(request, timeout):
        asked.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(tool_support, "urlopen", late)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)

    assert tool_support.can_call_tools(LOCAL) is True
    assert tool_support.can_call_tools(LOCAL) is True and len(asked) == 2  # the minute of silence still says yes
    assert [r.levelname for r in caplog.records if "too slow" in r.message] == ["WARNING"]  # said once, not every turn


def test_a_connect_timeout_wrapped_in_urlerror_counts_as_late(monkeypatch):
    from urllib.error import URLError

    def late(request, timeout):
        raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr(tool_support, "urlopen", late)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)

    assert tool_support.can_call_tools(LOCAL) is True


def test_a_late_ollama_is_asked_again_after_the_minute_and_its_answer_wins(monkeypatch):
    answers = [TimeoutError("late"), TimeoutError("late"), ["completion"]]
    now = [1000.0]

    def ollama(request, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Ok(json.dumps({"capabilities": answer}).encode())

    monkeypatch.setattr(tool_support, "urlopen", ollama)
    monkeypatch.setattr(tool_support.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    assert tool_support.can_call_tools(LOCAL) is True
    now[0] += tool_support._OLLAMA_RETRY_SECONDS + 1
    assert tool_support.can_call_tools(LOCAL) is False


def test_a_refused_connection_is_not_retried_and_is_left_to_litellms_table(monkeypatch):
    asked = []

    def refused(request, timeout):
        asked.append(timeout)
        raise OSError("connection refused")

    monkeypatch.setattr(tool_support, "urlopen", refused)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)

    assert tool_support.can_call_tools(LOCAL) is False and len(asked) == 1


def test_a_late_ollama_that_then_refuses_is_no_longer_taken_to_have_tools(monkeypatch):
    answers = [TimeoutError("late"), TimeoutError("late"), OSError("connection refused")]
    now = [1000.0]

    def ollama(request, timeout):
        raise answers.pop(0)

    monkeypatch.setattr(tool_support, "urlopen", ollama)
    monkeypatch.setattr(tool_support.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)

    assert tool_support.can_call_tools(LOCAL) is True
    now[0] += tool_support._OLLAMA_RETRY_SECONDS + 1
    assert tool_support.can_call_tools(LOCAL) is False
    assert tool_support.can_call_tools(LOCAL) is False  # nor within the minute of silence that follows


def test_a_strike_and_the_marking_are_each_said_once_in_the_log(monkeypatch, caplog):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    tool_support.note_refusal(CLOUD)
    first = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    tool_support.note_refusal(CLOUD)
    second = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"][len(first):]

    assert first == [f"{CLOUD} failed with tools and worked without (strike 1 of 2)"]
    assert second == [f"{CLOUD} failed with tools and worked without (strike 2 of 2)", f"{CLOUD} is not given tools again until Sympose restarts"]
