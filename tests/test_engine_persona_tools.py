"""Tests for sympose.engine.persona_tools (docs/decisions/040 and 041): resolving `ask` and
`remember` against a model's own capability, and composing whichever apply into one tool list
and one dispatcher for `lookup.converse`."""

from helpers import write_persona

from sympose import settings_store
from sympose.engine import lookup, lookup_tools, memory, memory_tools, persona_tools, tool_support

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"


def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def _vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))


def _persona(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


# -- for_turn: composing the tool list and dispatcher ----------------------------------------


def test_neither_capability_gives_no_tools_at_all():
    assert persona_tools.for_turn(ask=False, remember=False) is None


def test_ask_alone_gives_only_the_vault_tools():
    tools, run = persona_tools.for_turn(ask=True, remember=False)
    assert tools == lookup_tools.TOOLS


def test_remember_alone_gives_only_the_memory_tool():
    tools, run = persona_tools.for_turn(ask=False, remember=True)
    assert tools == memory_tools.TOOLS


def test_both_give_both_tool_lists():
    tools, run = persona_tools.for_turn(ask=True, remember=True)
    assert tools == [*lookup_tools.TOOLS, *memory_tools.TOOLS]


def test_the_dispatcher_tries_remember_first_then_falls_back_to_vault_tools(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    persona = {"handle": "samantha", "vault_folders": ["*"]}
    tools, run = persona_tools.for_turn(ask=True, remember=True)

    remembered = run(persona, LOCAL, "remember", '{"text": "x"}')
    assert remembered.lookup["tool"] == "remember"

    searched = run(persona, LOCAL, "search_notes", '{"query": "x"}')
    assert searched.lookup.get("tool") != "remember"  # fell through to lookup_tools, not swallowed


def test_the_dispatcher_with_ask_off_never_reaches_vault_tools(tmp_path, monkeypatch):
    # A persona given only `remember` (docs/decisions/041) must not be able to search or open
    # notes just because a model calls one of those names anyway -- `ask` gates the vault tools
    # regardless of what a model sends, the same way the tool list itself does.
    root = tmp_path / "vault"
    (root / "Private").mkdir(parents=True)
    (root / "Private" / "Secret.md").write_text("# Secret\nDo not tell anyone.")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    _persona(tmp_path, monkeypatch)
    persona = {"handle": "samantha", "vault_folders": ["*"]}
    tools, run = persona_tools.for_turn(ask=False, remember=True)

    result = run(persona, LOCAL, "open_note", '{"path": "Private/Secret.md"}')

    assert "Secret" not in result.text and "tell anyone" not in result.text
    assert "no tool called" in result.text.lower()


def test_the_dispatcher_with_remember_off_never_calls_memory_tools(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    persona = {"handle": "samantha", "vault_folders": ["*"]}
    tools, run = persona_tools.for_turn(ask=True, remember=False)

    # "remember" isn't one of the composed tools, but the dispatcher itself must still not
    # route it to memory_tools when `remember` is False -- it should reach lookup_tools instead
    # and come back as lookup_tools' own unknown-tool answer.
    result = run(persona, LOCAL, "remember", '{"text": "x"}')
    assert result.lookup.get("tool") == "remember"
    assert "no tool called" in result.text.lower()


# -- resolve: `ask`/`remember` against real settings and model capability -------------------


def test_resolve_with_nothing_configured_is_all_off(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    _vault(tmp_path, monkeypatch)
    persona = {"vault_folders": ["*"]}

    modes = persona_tools.resolve(persona, LOCAL)

    assert modes == persona_tools.Modes(ask=False, chose_ask=False, remember=None)


def test_resolve_ask_needs_both_the_setting_and_a_vault(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    settings_store.set(lookup.SETTING, lookup.ASK)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    modes = persona_tools.resolve({"vault_folders": ["*"]}, CLOUD)

    assert modes.chose_ask is False  # no vault to look up
    assert modes.ask is False


def test_resolve_ask_needs_the_model_to_call_tools_too(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    _vault(tmp_path, monkeypatch)
    settings_store.set(lookup.SETTING, lookup.ASK)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)

    cloud_modes = persona_tools.resolve({"vault_folders": ["*"]}, CLOUD)
    local_modes = persona_tools.resolve({"vault_folders": ["*"]}, LOCAL)

    assert cloud_modes.ask is True and cloud_modes.chose_ask is True
    assert local_modes.ask is False and local_modes.chose_ask is True  # chosen, just not runnable here


def test_resolve_remember_follows_the_setting_and_the_models_own_capability(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    _vault(tmp_path, monkeypatch)
    settings_store.set(memory.REMEMBER_SETTING, True)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)

    assert persona_tools.resolve({"vault_folders": ["*"]}, CLOUD).remember == memory.TOOL
    assert persona_tools.resolve({"vault_folders": ["*"]}, LOCAL).remember == memory.MARKER


def test_resolve_remember_does_not_need_a_vault(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    settings_store.set(memory.REMEMBER_SETTING, True)

    modes = persona_tools.resolve({"vault_folders": ["*"]}, LOCAL)

    assert modes.ask is False and modes.remember is not None
