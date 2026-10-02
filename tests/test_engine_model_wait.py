"""How long a model call may wait (docs/decisions/059, #124)."""

import httpx
import litellm
import pytest

from sympose import settings_store
from sympose.engine import model, model_wait
from sympose.engine.model import EngineModelError


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def prompt(characters: int) -> list[dict]:
    return [{"role": "user", "content": "x" * characters}]


def test_a_short_prompt_is_given_the_old_120_seconds():
    assert model_wait.seconds(prompt(40)) == 120


def test_the_wait_grows_with_the_prompt_one_second_for_every_forty_tokens():
    # 4,800 tokens at 4 characters each, the measured case (100 s cold on gemma2:9b): 120 + 120
    assert model_wait.seconds(prompt(4800 * 4)) == 240
    assert model_wait.seconds(prompt(6144 * 4)) == 120 + 153


def test_what_the_user_chose_is_the_whole_wait_whatever_the_prompt():
    settings_store.set("model_timeout", 45)
    assert model_wait.seconds(prompt(4800 * 4)) == 45
    settings_store.set("model_timeout", 900)
    assert model_wait.seconds(prompt(40)) == 900


@pytest.mark.parametrize("value", [0, 29, 3601, -5, 12.5, "300", True, None, [60]])
def test_a_value_that_cannot_be_used_is_automatic(value):
    settings_store.set("model_timeout", value)
    assert model_wait.chosen() is None
    assert model_wait.seconds(prompt(40)) == 120


def test_the_limits_are_accepted():
    for value in (30, 3600):
        settings_store.set("model_timeout", value)
        assert model_wait.chosen() == value


def test_a_message_without_text_counts_as_nothing():
    assert model_wait.seconds([{"role": "assistant", "content": None}, {"role": "user"}]) == 120


def test_the_call_is_given_the_wait_for_its_prompt(monkeypatch):
    seen = {}

    def completion(model, messages, stream, timeout):
        seen["read"] = timeout.read
        return iter([])

    monkeypatch.setattr(model.litellm, "completion", completion)
    with pytest.raises(EngineModelError):
        model.call_model(prompt(4800 * 4), model="ollama_chat/x")
    assert seen["read"] == 240


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout("slow"), litellm.Timeout("slow", "m", "ollama_chat")],
)
def test_a_call_that_ran_out_of_time_says_so_and_names_the_setting(monkeypatch, error):
    def completion(**_):
        raise error

    monkeypatch.setattr(model.litellm, "completion", completion)
    with pytest.raises(EngineModelError) as raised:
        model.call_model(prompt(40), model="ollama_chat/x")
    text = str(raised.value)
    assert "No answer from 'ollama_chat/x' in 120 seconds" in text and "model_timeout" in text


def test_a_timeout_that_caused_another_error_is_still_found(monkeypatch):
    def completion(**_):
        try:
            raise httpx.ReadTimeout("slow")
        except httpx.ReadTimeout as e:
            raise RuntimeError("wrapped") from e

    monkeypatch.setattr(model.litellm, "completion", completion)
    with pytest.raises(EngineModelError) as raised:
        model.call_model(prompt(40), model="ollama_chat/x")
    assert "model_timeout" in str(raised.value)


def test_any_other_failure_keeps_its_own_message(monkeypatch):
    def completion(**_):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(model.litellm, "completion", completion)
    with pytest.raises(EngineModelError) as raised:
        model.call_model(prompt(40), model="ollama_chat/x")
    assert "Couldn't reach model 'ollama_chat/x': refused" in str(raised.value)
