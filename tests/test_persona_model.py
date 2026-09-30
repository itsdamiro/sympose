"""Saving a persona's model (docs/decisions/046): the pick goes into the untracked `persona.local.yaml`,
the shipped `persona.yaml` is never written, and a bad override never costs a persona its place."""

import pytest
import yaml

from sympose import persona_model, profile

FILE = "name: 'Samantha'\nhandle: 'samantha'\n# hand-written\nvault_folders: '*'\nmodel: 'ollama_chat/gemma2:9b'\n"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    (tmp_path / "samantha").mkdir()
    (tmp_path / "samantha" / "persona.yaml").write_text(FILE, encoding="utf-8")
    return tmp_path / "samantha"


def test_a_pick_is_written_to_the_local_file_and_the_shipped_file_is_untouched(home):
    assert persona_model.set_model("samantha", "gemini/gemini-flash-latest") is True
    assert (home / "persona.yaml").read_text(encoding="utf-8") == FILE
    assert yaml.safe_load((home / "persona.local.yaml").read_text(encoding="utf-8")) == {"model": "gemini/gemini-flash-latest"}
    assert profile.get_profile("samantha")["model"] == "gemini/gemini-flash-latest"  # the override wins


def test_a_second_pick_replaces_the_first(home):
    persona_model.set_model("samantha", "a/one")
    persona_model.set_model("samantha", "b/two")
    assert profile.get_profile("samantha")["model"] == "b/two"


def test_clearing_deletes_the_override_and_the_shipped_model_applies_again(home):
    persona_model.set_model("samantha", "a/one")
    assert persona_model.set_model("samantha", None) is True
    assert not (home / "persona.local.yaml").exists()
    assert profile.get_profile("samantha")["model"] == "ollama_chat/gemma2:9b"


def test_clearing_when_there_is_no_override_is_fine(home):
    assert persona_model.set_model("samantha", None) is True
    assert list(p.name for p in home.iterdir()) == ["persona.yaml"]


def test_a_quote_or_colon_in_the_id_reads_back_the_same(home):
    persona_model.set_model("samantha", "o'brien/model: x")
    assert profile.get_profile("samantha")["model"] == "o'brien/model: x"


@pytest.mark.parametrize("junk", ["model: [unclosed\n", "- just\n- a list\n", "model: 5\n", "model: ''\n", "model: \n"])
def test_an_invalid_override_is_ignored_and_the_persona_still_loads(home, junk):
    (home / "persona.local.yaml").write_text(junk, encoding="utf-8")
    assert profile.get_profile("samantha")["model"] == "ollama_chat/gemma2:9b"


def test_an_override_that_is_not_utf8_is_ignored(home):
    (home / "persona.local.yaml").write_bytes(b"model: '\xff\xfe'\n")
    assert profile.get_profile("samantha")["model"] == "ollama_chat/gemma2:9b"


def test_the_override_takes_only_the_model_key(home):
    (home / "persona.local.yaml").write_text("model: a/one\nname: Hijacked\nvault_folders: []\n", encoding="utf-8")
    p = profile.get_profile("samantha")
    assert p["model"] == "a/one" and p["name"] == "Samantha" and p["vault_folders"] == "*"


def test_a_missing_persona_or_an_unsafe_handle_is_not_written(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    assert persona_model.set_model("nobody", "m/x") is False
    assert persona_model.set_model("../evil", "m/x") is False
    assert list(tmp_path.iterdir()) == []


def test_a_failed_write_reports_false_and_leaves_no_override(home, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(persona_model, "write_atomic_text", boom)
    assert persona_model.set_model("samantha", "m/x") is False
    assert not (home / "persona.local.yaml").exists()
