"""`sympose doctor` (docs/decisions/029): what it reports, what `--fix` changes, and what it never touches."""

import io
import json
import os

import pytest
from helpers import write_persona

from sympose import doctor, launcher, settings_store


@pytest.fixture
def base(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return profiles


def _run(fix=False):
    out = io.StringIO()
    return doctor.run(fix=fix, out=out), out.getvalue()


def _settings(base, text):
    (base.parent / "settings.json").write_text(text if isinstance(text, str) else json.dumps(text))
    return base.parent / "settings.json"


def test_an_installation_with_nothing_wrong_is_healthy(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"chat_model": "ollama_chat/x", "default_persona": "samantha"})

    code, out = _run()

    assert code == 0 and "Everything looks healthy." in out


def test_no_profiles_folder_and_no_settings_file_is_healthy(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "none"))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "none.json"))

    code, out = _run()

    assert code == 0 and out.endswith("Everything looks healthy.\n")


def test_a_mixed_case_persona_folder_is_reported_and_left_alone_without_fix(base):
    write_persona(base, "Grace", "name: Grace\n")

    code, out = _run()

    assert code == 1
    assert "'Grace' is not lower case" in out and "--fix would: rename it to 'grace'" in out
    assert os.listdir(base) == ["Grace"]


def test_fix_renames_a_mixed_case_persona_folder_with_everything_in_it(base):
    folder = write_persona(base, "Grace", "name: Grace\n")
    (folder / "sessions").mkdir()
    (folder / "sessions" / "one.jsonl").write_text("{}\n")

    code, out = _run(fix=True)

    assert code == 0 and "fixed: rename it to 'grace'" in out and "Fixed 1 problem(s)." in out
    assert os.listdir(base) == ["grace"]
    assert (base / "grace" / "sessions" / "one.jsonl").read_text() == "{}\n"
    assert (base / "grace" / "persona.yaml").read_text() == "name: Grace\n"


def test_a_folder_without_a_persona_file_is_not_a_persona_and_is_not_touched(base):
    (base / "Notes").mkdir()

    code, out = _run(fix=True)

    assert code == 0 and os.listdir(base) == ["Notes"]


def test_a_name_that_belongs_to_a_different_folder_is_taken_but_the_same_folder_is_not(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    assert doctor._taken(str(tmp_path / "a"), str(tmp_path / "b"))
    assert not doctor._taken(str(tmp_path / "a"), str(tmp_path / "a"))
    assert not doctor._taken(str(tmp_path / "a"), str(tmp_path / "missing"))


def test_a_lower_case_name_that_is_already_taken_is_not_renamed_over(base, monkeypatch):
    write_persona(base, "Grace", "name: Grace\n")
    monkeypatch.setattr(doctor, "_taken", lambda src, dst: True)

    code, out = _run(fix=True)

    assert code == 1 and "a different folder 'grace' exists" in out and "needs you" in out
    assert os.listdir(base) == ["Grace"]


@pytest.mark.parametrize("body", ["name: [unclosed\n", "- just\n- a list\n", "just text\n"])
def test_a_persona_file_that_cannot_be_read_is_reported_and_never_changed(base, body):
    folder = write_persona(base, "ada", body)

    code, out = _run(fix=True)

    assert code == 1 and "ada" in out and "the persona is missing" in out and "needs you" in out
    assert (folder / "persona.yaml").read_text() == body


def test_a_yaml_error_is_one_short_line_that_names_the_file_once_and_the_line(base):
    folder = write_persona(base, "ada", "name: ok\nrole: [unclosed\n")

    _, out = _run()

    assert out.count(str(folder / "persona.yaml")) == 1
    assert "expected ',' or ']'" in out and "(line 3)" in out


def test_a_settings_file_that_cannot_be_read_is_reported_and_never_overwritten(base):
    path = _settings(base, "{not json")

    code, out = _run(fix=True)

    assert code == 1 and str(path) in out and "every setting is at its default" in out
    assert path.read_text() == "{not json"


def test_a_settings_file_that_is_not_an_object_is_reported(base):
    path = _settings(base, "[1, 2]")

    code, out = _run(fix=True)

    assert code == 1 and "is not a JSON object" in out
    assert path.read_text() == "[1, 2]"


@pytest.mark.parametrize("key", ["chat_model", "default_persona"])
@pytest.mark.parametrize("value", [None, "", "   ", 5, ["x"]])
def test_fix_removes_a_setting_that_is_not_a_name_and_keeps_the_others(base, key, value):
    _settings(base, {key: value, "grounding_search": "keywords"})

    code_only, out_only = _run()
    code, out = _run(fix=True)

    assert code_only == 1 and f"the {key} setting is" in out_only and "--fix would: remove" in out_only
    assert code == 0 and f"fixed: remove {key}" in out
    assert json.loads((base.parent / "settings.json").read_text()) == {"grounding_search": "keywords"}


def test_fix_removes_a_default_persona_that_names_no_persona(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"default_persona": "nobody", "chat_model": "ollama_chat/x"})

    code, out = _run(fix=True)

    assert code == 0 and "'nobody' names no persona" in out
    assert json.loads((base.parent / "settings.json").read_text()) == {"chat_model": "ollama_chat/x"}


def test_a_default_persona_is_matched_without_regard_to_case(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"default_persona": "Samantha"})

    code, out = _run()

    assert code == 0 and out.endswith("Everything looks healthy.\n")


def test_a_default_persona_is_not_checked_when_there_is_no_profiles_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "none"))  # whole-vault mode answers to any handle
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    (tmp_path / "settings.json").write_text('{"default_persona": "grace"}')

    assert _run()[0] == 0


def test_a_default_persona_that_a_rename_makes_valid_survives_the_same_run(base, monkeypatch):
    def a_filesystem_that_keeps_case(handle):  # this machine's ignores case, so the order could not show
        return handle in os.listdir(base) and os.path.isfile(base / handle / "persona.yaml")

    monkeypatch.setattr(doctor, "_has_persona_file", a_filesystem_that_keeps_case)
    write_persona(base, "Grace", "name: Grace\n")
    _settings(base, {"default_persona": "grace"})

    code, _ = _run(fix=True)

    assert code == 0
    assert json.loads((base.parent / "settings.json").read_text()) == {"default_persona": "grace"}


def test_a_fix_that_fails_is_reported_and_the_run_still_ends_with_a_problem(base, monkeypatch):
    write_persona(base, "Grace", "name: Grace\n")

    def refuse(src, dst):
        raise PermissionError("no")

    monkeypatch.setattr(doctor.os, "rename", refuse)

    code, out = _run(fix=True)

    assert code == 1 and "could not fix it: no" in out


def test_the_command_reports_without_fix_and_fixes_with_it(base, capsys):
    write_persona(base, "Grace", "name: Grace\n")

    assert launcher.main(["doctor"]) == 1
    assert os.listdir(base) == ["Grace"] and "'Grace' is not lower case" in capsys.readouterr().out

    assert launcher.main(["doctor", "--fix"]) == 0
    assert os.listdir(base) == ["grace"]


# -- found in the review of the doctor ----------------------------------------------------------


def test_a_settings_fix_that_cannot_be_written_is_not_reported_as_fixed(base, monkeypatch):
    path = _settings(base, {"chat_model": None})
    monkeypatch.setattr(settings_store, "write_atomic_text", lambda *a: (_ for _ in ()).throw(OSError("disk full")))

    code, out = _run(fix=True)

    assert code == 1 and "could not fix it" in out and "fixed: remove" not in out
    assert json.loads(path.read_text()) == {"chat_model": None}


def test_a_persona_file_that_is_not_utf8_is_reported_not_a_crash(base):
    folder = write_persona(base, "ada", "name: Ada\n")
    (folder / "persona.yaml").write_bytes(b"name: Ad\xe9\n")

    code, out = _run(fix=True)

    assert code == 1 and "ada" in out and "the persona is missing" in out


def test_a_default_persona_with_a_stray_space_is_not_a_name_the_roster_has(base):
    write_persona(base, "grace", "name: Grace\n")
    _settings(base, {"default_persona": "grace "})

    code, out = _run(fix=True)

    assert code == 0 and "'grace ' names no persona" in out
    assert json.loads((base.parent / "settings.json").read_text()) == {}


@pytest.mark.parametrize("handle", ["a/b", "..", "../grace"])
def test_a_default_persona_that_is_not_a_plain_name_names_no_persona(base, handle):
    write_persona(base, "grace", "name: Grace\n")
    _settings(base, {"default_persona": handle})

    code, out = _run(fix=True)

    assert code == 0 and "names no persona" in out
    assert json.loads((base.parent / "settings.json").read_text()) == {}


def test_the_shipped_default_persona_needs_no_folder_of_its_own(base):
    write_persona(base, "grace", "name: Grace\n")  # profiles/ exists, with no samantha folder: she still answers
    _settings(base, {"default_persona": "samantha"})

    code, out = _run()

    assert code == 0 and out.endswith("Everything looks healthy.\n")


def test_a_default_persona_whose_file_is_unreadable_keeps_the_persons_choice(base):
    write_persona(base, "ada", "name: [oops\n")
    path = _settings(base, {"default_persona": "ada"})

    code, out = _run(fix=True)

    assert code == 1 and "names no persona" not in out  # the broken file is the finding, once
    assert json.loads(path.read_text()) == {"default_persona": "ada"}


def test_a_dangling_link_where_the_lower_case_name_would_go_counts_as_taken(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").symlink_to(tmp_path / "gone")

    assert doctor._taken(str(tmp_path / "a"), str(tmp_path / "b"))


# -- the models section (ADR 029, "which models are in use") ------------------------------------------------


def test_the_default_setup_says_that_nothing_leaves_the_computer(base):
    write_persona(base, "samantha", "name: Samantha\n")

    code, out = _run()

    assert code == 0
    assert "Models and what leaves this computer:" in out
    assert "chat model: ollama_chat/gemma2:9b: local, nothing leaves this computer" in out
    assert "embedding model: ollama/nomic-embed-text: local, nothing leaves this computer" in out


def test_a_cloud_chat_model_with_nothing_approved_is_reported_but_is_not_a_problem(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"chat_model": "gemini/gemini-flash-latest"})

    code, out = _run()

    assert code == 0 and out.endswith("Everything looks healthy.\n")
    assert (
        "chat model: gemini/gemini-flash-latest: cloud, it receives your messages and this conversation; "
        "from your vault it may receive: nothing; held back: notes, properties, recaps, vault_map, connections"
    ) in out


def test_the_approved_categories_are_listed_and_the_rest_are_held_back(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"chat_model": "gemini/x", "cloud_share": ["recaps", "notes", "bogus"]})

    _, out = _run()

    assert "from your vault it may receive: notes, recaps; held back: properties, vault_map, connections" in out


def test_a_persona_with_a_model_of_its_own_is_listed_and_one_without_is_not(base):
    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "grace", "name: Grace\nmodel: openrouter/some-model\n")

    _, out = _run()

    assert "persona grace: openrouter/some-model: cloud" in out
    assert "persona samantha" not in out


def test_a_persona_model_that_is_not_text_is_left_out_of_the_report(base):
    write_persona(base, "grace", "name: Grace\nmodel: [1, 2]\n")

    code, out = _run()

    assert code == 0 and "persona grace" not in out


def test_a_cloud_embedding_model_without_approval_for_notes_is_a_finding_that_needs_the_person(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"embedding_model": "gemini/text-embedding"})

    code, out = _run(fix=True)

    assert code == 1
    assert "embedding model: gemini/text-embedding: cloud, it would receive every passage of your notes" in out
    assert "notes are searched by keyword" in out and "needs you" in out


def test_a_cloud_embedding_model_with_notes_approved_is_not_a_finding(base):
    write_persona(base, "samantha", "name: Samantha\n")
    _settings(base, {"embedding_model": "gemini/text-embedding", "cloud_share": ["notes"]})

    code, out = _run()

    assert code == 0 and "cloud, it would receive every passage of your notes and every message" in out


# -- a persona's folder that is not in the vault (ADR 029, issue #51) ----------------------------------------


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "Notes").mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return root


def test_a_vault_folder_that_is_not_in_the_vault_is_reported_and_nothing_is_created(base, vault):
    write_persona(base, "grace", "name: Grace\nvault_folders: ['Note']\n")  # a typo for Notes

    code, out = _run(fix=True)

    assert code == 1
    assert "the persona 'grace' lists the folder 'Note', which is not in any of your vaults" in out
    assert "needs you" in out
    assert os.listdir(vault) == ["Notes"]


def test_a_folder_that_is_in_one_of_the_vaults_is_not_reported(base, vault, tmp_path, monkeypatch):
    other = tmp_path / "other"
    (other / "Writing").mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATHS", f"{vault},{other}")
    write_persona(base, "grace", "name: Grace\nvault_folders: ['Notes', 'Writing']\n")

    code, out = _run()

    assert code == 0 and "which is not in" not in out


@pytest.mark.parametrize("entry", ["'*'", "['*']", "['all']", "['']", "[]", "[3]"])
def test_whole_vault_or_unusable_entries_are_not_reported_as_missing_folders(base, vault, entry):
    write_persona(base, "grace", f"name: Grace\nvault_folders: {entry}\n")

    code, out = _run()

    assert code == 0 and "which is not in" not in out


def test_with_no_vault_configured_a_persona_folder_is_not_reported(base, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    write_persona(base, "grace", "name: Grace\nvault_folders: ['Note']\n")

    code, out = _run()

    assert code == 0 and "which is not in" not in out


def test_a_folder_written_as_one_string_instead_of_a_list_is_checked_as_a_whole_name(base, vault):
    write_persona(base, "grace", "name: Grace\nvault_folders: 'Notes'\n")
    write_persona(base, "anais", "name: Anais\nvault_folders: 'Note'\n")

    code, out = _run()

    assert code == 1
    assert out.count("which is not in") == 1 and "the persona 'anais' lists the folder 'Note'" in out
