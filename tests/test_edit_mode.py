"""How much a persona may do on the notes before the user's Accept (docs/decisions/072): the four modes, which one
counts for a persona (her untracked `persona.local.yaml`, then her shipped `persona.yaml`, then the global setting, then
`manual`), and the note a user is shown beside the more autonomous modes, specific to the model."""

import os
import shutil

import pytest

from sympose import profile, settings_store
from sympose.engine import edit_mode
from sympose.engine.settings_registry import GROUPS, SETTINGS, find

GEMMA, FLASH = "ollama_chat/gemma2:9b", "gemini/gemini-flash-latest"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    (tmp_path / "ada").mkdir()
    return tmp_path / "ada"


def write(home, name, text):
    (home / name).write_text(text, encoding="utf-8")


def test_the_four_modes_in_the_order_they_step_through():
    assert edit_mode.MODES == ("plan", "manual", "accept", "auto")
    assert edit_mode.DEFAULT == "manual"


def test_with_no_setting_the_global_mode_is_manual():
    assert edit_mode.mode() == "manual"


@pytest.mark.parametrize("value", ["plan", "manual", "accept", "auto"])
def test_a_global_mode_is_read_as_set(value):
    settings_store.set(edit_mode.SETTING, value)
    assert edit_mode.mode() == value


@pytest.mark.parametrize("value", ["yolo", "", 3, None, ["auto"]])
def test_a_global_value_a_hand_edit_made_unusable_is_manual(value):
    settings_store.set(edit_mode.SETTING, value)
    assert edit_mode.mode() == "manual"


def test_a_persona_with_no_mode_of_her_own_follows_the_global_one(home):
    write(home, "persona.yaml", "name: Ada\nhandle: ada\n")
    settings_store.set(edit_mode.SETTING, "plan")
    assert edit_mode.for_persona(profile.get_profile("ada")) == "plan"


def test_her_shipped_file_beats_the_global_setting(home):
    write(home, "persona.yaml", "name: Ada\nhandle: ada\nedit_mode: manual\n")
    settings_store.set(edit_mode.SETTING, "auto")
    assert edit_mode.for_persona(profile.get_profile("ada")) == "manual"


def test_the_users_local_file_beats_the_shipped_one(home):
    write(home, "persona.yaml", "name: Ada\nhandle: ada\nedit_mode: manual\n")
    write(home, "persona.local.yaml", "edit_mode: accept\n")
    assert edit_mode.for_persona(profile.get_profile("ada")) == "accept"


def test_an_unusable_value_in_her_files_falls_through_to_the_next_source(home):
    write(home, "persona.yaml", "name: Ada\nhandle: ada\nedit_mode: whatever\n")
    write(home, "persona.local.yaml", "edit_mode: 5\n")
    settings_store.set(edit_mode.SETTING, "plan")
    assert edit_mode.for_persona(profile.get_profile("ada")) == "plan"


def test_a_local_file_with_only_a_model_still_leaves_the_mode_to_the_shipped_file(home):
    write(home, "persona.yaml", "name: Ada\nhandle: ada\nedit_mode: plan\n")
    write(home, "persona.local.yaml", "model: a/b\n")
    p = profile.get_profile("ada")
    assert (p["model"], edit_mode.for_persona(p)) == ("a/b", "plan")


def test_no_profile_at_all_is_the_global_mode():
    settings_store.set(edit_mode.SETTING, "plan")
    assert edit_mode.for_persona(None) == "plan"


def test_shipped_samantha_is_manual_whatever_the_global_mode_is(monkeypatch, tmp_path):
    # Her shipped file only, copied: the real folder may hold the user's own untracked persona.local.yaml (their choice).
    shipped = tmp_path / "profiles" / "samantha"
    shipped.mkdir(parents=True)
    shutil.copy(os.path.join(os.path.dirname(__file__), "..", "profiles", "samantha", "persona.yaml"), shipped)
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "profiles"))
    settings_store.set(edit_mode.SETTING, "auto")
    assert edit_mode.for_persona(profile.get_profile("samantha")) == "manual"


def test_the_two_calmer_modes_have_nothing_to_warn_about():
    assert edit_mode.note("plan", GEMMA) is None
    assert edit_mode.note("manual", GEMMA) is None


@pytest.mark.parametrize("mode", ["accept", "auto"])
def test_a_measured_small_model_is_told_its_own_figures(mode):
    text = edit_mode.note(mode, GEMMA)
    assert "18" in text and "36" in text and "3 times" in text and "price" in text
    assert "read each change" in text.lower()


def test_gemma_is_one_model_whichever_way_ollama_names_it():
    assert edit_mode.note("auto", "ollama/gemma2:9b") == edit_mode.note("auto", GEMMA)


def test_a_model_measured_as_faithful_gets_the_short_form_with_its_figure():
    text = edit_mode.note("auto", FLASH)
    assert "35 times out of 36" in text and "invented notes" in text
    assert len(text) < len(edit_mode.note("auto", GEMMA))


@pytest.mark.parametrize("model", ["ollama_chat/llama3.2:3b", "openai/gpt-x", None, ""])
def test_a_model_not_measured_is_told_nothing_is_known_and_smaller_ones_are_expected_worse(model):
    text = edit_mode.note("accept", model)
    assert "not been measured" in text and "smaller" in text and "worse" in text


def test_the_setting_is_a_choice_among_the_modes_defaulting_to_manual():
    row = find(edit_mode.SETTING)
    assert row is not None and row.kind == "choice" and row.choices == edit_mode.MODES
    assert row.default() == "manual" and row.current() == "manual"
    assert row.group == "Editing" and row.group in GROUPS  # a group left out of GROUPS is a setting no screen lists
    assert sum(1 for s in SETTINGS if s.key == edit_mode.SETTING) == 1
