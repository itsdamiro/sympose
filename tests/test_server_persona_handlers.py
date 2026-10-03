"""Tests for sympose.server_persona_handlers — the GET /api/personas roster,
matching ui/src/lib/personas.ts's PersonasResponse contract exactly
(docs/decisions/009)."""

from helpers import write_persona
import pytest

from sympose import server_persona_handlers as ph


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def test_no_profiles_dir_returns_a_single_default_samantha_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "does-not-exist"))

    result = ph.get_personas()

    assert result["default"] == "samantha"
    assert len(result["personas"]) == 1
    entry = result["personas"][0]
    assert entry["handle"] == "samantha"
    assert entry["is_default"] is True
    assert entry["skills"] == []
    assert entry["model"]  # falls back to DEFAULT_LOCAL_MODEL, never blank


def test_roster_shape_matches_the_frontend_contract(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "dev", 
        "name: Dev\nvault_folders:\n  - Code\nmodel: ollama_chat/foo\nskills:\n  - triage\n"
    )
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    result = ph.get_personas()

    assert result["default"] == "samantha"
    by_handle = {p["handle"]: p for p in result["personas"]}
    assert set(by_handle) == {"samantha", "dev"}
    assert by_handle["samantha"]["is_default"] is True
    assert by_handle["dev"]["is_default"] is False
    assert by_handle["dev"]["model"] == "ollama_chat/foo"
    assert by_handle["dev"]["skills"] == ["triage"]


def test_is_default_follows_a_configured_custom_default(tmp_path, monkeypatch):
    from sympose import settings_store

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "dev", "name: Dev\nvault_folders:\n  - Code\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    settings_store.set("default_persona", "dev")

    result = ph.get_personas()

    assert result["default"] == "dev"
    by_handle = {p["handle"]: p for p in result["personas"]}
    assert by_handle["dev"]["is_default"] is True
    assert by_handle["samantha"]["is_default"] is False


def test_a_personas_shown_model_follows_the_chat_model_setting(tmp_path, monkeypatch):
    from sympose import settings_store

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    settings_store.set("chat_model", "anthropic/claude-sonnet-5")

    entry = ph.get_personas()["personas"][0]

    # What's displayed must be what a turn would actually run on.
    assert entry["model"] == "anthropic/claude-sonnet-5"


def test_roster_carries_each_personas_look_and_drops_a_value_of_an_unsafe_shape(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nicon: brain\naccent: 'oklch(0.55 0.13 233)'\naccent_dark: '#7ad'\n")
    write_persona(profiles, "dev", "name: Dev\nvault_folders: '*'\nicon: 'x; y'\naccent: 'red; background:url(//evil)'\n")
    write_persona(profiles, "plain", "name: Plain\nvault_folders: '*'\nicon: 3\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    by_handle = {p["handle"]: p for p in ph.get_personas()["personas"]}

    assert (by_handle["samantha"]["icon"], by_handle["samantha"]["accent"], by_handle["samantha"]["accent_dark"]) == (
        "brain", "oklch(0.55 0.13 233)", "#7ad",
    )
    for handle in ("dev", "plain"):  # left to the app's own defaults, never passed on unchecked
        assert (by_handle[handle]["icon"], by_handle[handle]["accent"], by_handle[handle]["accent_dark"]) == (None, None, None)

