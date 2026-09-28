"""The meter's figure before the next message is sent (docs/decisions/018, "Update"): the persona's
system prompt plus the kept history, counted for a given model against that model's prompt budget."""

import pytest
from helpers import write_persona

from sympose.engine import budget, context_estimate, prompt, session

_LOCAL = "ollama_chat/gemma2:9b"
_CLOUD = "gpt-4o"


@pytest.fixture(autouse=True)
def windows(monkeypatch):
    """Known windows, whatever is installed here: 8,192 for the local model (prompt budget 8192 - 2048
    kept for the reply = 6,144), 100,000 for the cloud one (100000 - 4096 = 95,904)."""
    known = {_LOCAL: 8192, _CLOUD: 100_000}
    monkeypatch.setattr(budget, "_native_max", lambda model: known.get(model))


@pytest.fixture
def handle(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return "samantha"


def _talk(handle, session_id, *pairs):
    for user, reply in pairs:
        assert session.append_turn(handle, session_id, user, reply)


def test_the_figure_is_the_system_prompt_and_history_against_the_models_budget(handle):
    _talk(handle, "s1", ("what is in my vault?", "Some notes about fonts."))
    used, limit = context_estimate.estimate(handle, "s1", _LOCAL)
    assert limit == 6144
    history = [
        {"role": "user", "content": "what is in my vault?"},
        {"role": "assistant", "content": "Some notes about fonts."},
    ]
    assert used > budget.count_tokens(history, _LOCAL)  # the soul and the rules are in it too
    assert used < limit


def test_a_longer_conversation_counts_higher(handle):
    _talk(handle, "s1", ("hello", "hi there"))
    short = context_estimate.estimate(handle, "s1", _LOCAL)[0]
    _talk(handle, "s1", ("tell me about typography and layout", "Typography is the craft of setting type. " * 20))
    assert context_estimate.estimate(handle, "s1", _LOCAL)[0] > short + 100


def test_the_budget_is_the_one_of_the_model_asked_about(handle):
    _talk(handle, "s1", ("hello", "hi there"))
    assert context_estimate.estimate(handle, "s1", _LOCAL)[1] == 6144
    assert context_estimate.estimate(handle, "s1", _CLOUD)[1] == 95_904


def test_there_is_nothing_to_count_without_a_session_or_a_reply(handle):
    assert context_estimate.estimate(handle, None, _LOCAL) is None
    assert context_estimate.estimate(handle, "no-such-session", _LOCAL) is None


def test_there_is_nothing_to_count_for_an_unknown_persona_or_window(handle):
    _talk(handle, "s1", ("hello", "hi there"))
    assert context_estimate.estimate("nobody", "s1", _LOCAL) is None
    assert context_estimate.estimate(handle, "s1", "some-cloud-model-with-no-known-window") is None


def test_the_vault_map_counts_only_where_the_model_may_receive_it(handle, monkeypatch):
    _talk(handle, "s1", ("hello", "hi there"))
    monkeypatch.setattr(context_estimate.vault_map_mod, "build", lambda persona: "MAP OF THE VAULT")
    seen = []
    real = prompt.build_system_prompt

    def spy(persona, **kwargs):
        seen.append(kwargs)
        return real(persona, **kwargs)

    monkeypatch.setattr(context_estimate.prompt, "build_system_prompt", spy)
    context_estimate.estimate(handle, "s1", _LOCAL)  # a local model may receive everything
    context_estimate.estimate(handle, "s1", _CLOUD)  # a cloud one nothing the user has not approved
    assert seen[0] == {"vault_map": "MAP OF THE VAULT", "vault_map_withheld": False}
    assert seen[1] == {"vault_map": None, "vault_map_withheld": True}


def test_a_conversation_too_long_for_the_window_is_trimmed_like_a_real_turn_and_never_reads_above_the_budget(
    handle, monkeypatch
):
    monkeypatch.setattr(budget, "_native_max", lambda model: 2048)  # the smallest window: prompt budget 1,536
    for n in range(12):
        _talk(handle, "long", (f"question {n} " + "about typography " * 20, f"answer {n} " + "on layout " * 40))
    used, limit = context_estimate.estimate(handle, "long", _LOCAL)
    assert limit == 1536
    assert 0 < used <= limit  # counted whole it would be several times the budget


def test_instructions_that_alone_overflow_the_window_give_no_figure(handle, monkeypatch):
    _talk(handle, "s1", ("hello", "hi there"))
    monkeypatch.setattr(context_estimate.budget, "budget_for", lambda model: budget.Budget(5, None, None))
    assert context_estimate.estimate(handle, "s1", _LOCAL) is None
