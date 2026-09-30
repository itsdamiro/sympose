"""Tests for sympose.vault_paths sandbox-containment logic — the persona
vault sandbox, and CODE_QUALITY_STANDARDS.md's directory/path-boundary-
safety rule. The configured/active vault list itself (ADR 003, ADR 004) is
`vault_registry`, tested in test_vault_registry.py."""

import os

import pytest

from sympose import vault_paths


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    """`get_master_vault()` resolves through `vault_registry`, which reads
    `settings_store` on every call — without this, a test here would
    silently read this checkout's real `./settings.json`."""
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


def test_wildcard_vault_folders_grants_full_root(vault_root):
    profile = {"vault_folders": ["*"]}
    assert vault_paths.get_allowed_dirs(profile) == [vault_root]


def test_scoped_vault_folders_grants_only_named_subfolder(vault_root):
    profile = {"vault_folders": ["Code"]}
    assert vault_paths.get_allowed_dirs(profile) == [
        os.path.join(vault_root, "Code")
    ]


def test_escaping_vault_folder_is_rejected(vault_root):
    profile = {"vault_folders": ["../../etc"]}
    allowed = vault_paths.get_allowed_dirs(profile)
    # the unsafe entry is dropped; falling back to the vault root itself
    # means it never resolves outside the sandbox.
    assert allowed == [vault_root]


def test_get_master_vault_reflects_the_active_vault(vault_root):
    assert vault_paths.get_master_vault() == vault_root


def test_get_vault_name_uses_the_disambiguated_registry_name(tmp_path, monkeypatch):
    work = tmp_path / "Work" / "Notes"
    personal = tmp_path / "Personal" / "Notes"
    work.mkdir(parents=True)
    personal.mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATHS", f"{work},{personal}")
    assert vault_paths.get_vault_name() == "Work/Notes"


def test_no_configured_vaults_resolves_to_none(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    assert vault_paths.get_master_vault() is None
    assert vault_paths.get_vault_name() is None


def test_looking_up_a_personas_folders_creates_nothing(vault_root):
    allowed = vault_paths.get_allowed_dirs({"vault_folders": ["Misspelt"]})

    assert os.listdir(vault_root) == []
    assert allowed == [os.path.join(vault_root, "Misspelt")]  # not widened to the whole vault


def test_looking_up_the_sandbox_does_not_create_a_vault_root_that_is_not_there(tmp_path, monkeypatch):
    missing = tmp_path / "no-such-vault"
    monkeypatch.setenv("VAULT_PATHS", str(missing))

    vault_paths.get_allowed_dirs({"vault_folders": ["*"]})
    vault_paths.get_allowed_dirs({"vault_folders": ["Notes"]})

    assert not missing.exists()


def test_a_note_written_into_a_folder_that_is_not_there_yet_creates_it(vault_root):
    from sympose import vault_write_create

    profile = {"vault_folders": ["Writing"]}
    assert vault_paths.get_primary_dir(profile) == os.path.join(vault_root, "Writing")
    assert not os.path.exists(os.path.join(vault_root, "Writing"))

    result = vault_write_create.create_note(profile, "First draft", "hello")

    assert result.startswith("Created note")
    assert os.listdir(os.path.join(vault_root, "Writing")) == ["First draft.md"]



def test_every_read_of_a_persona_pointed_at_a_missing_folder_is_empty_and_creates_nothing(vault_root):
    from sympose import vault_backlinks, vault_graph, vault_search
    from sympose.engine import grounding

    os.makedirs(os.path.join(vault_root, "Notes"))
    with open(os.path.join(vault_root, "Notes", "A.md"), "w", encoding="utf-8") as f:
        f.write("hello atlas [[B]]")
    profile = {"vault_folders": ["Note"]}  # a typo for Notes

    assert vault_search.search_structured(profile, "atlas") == []
    assert vault_graph.get_vault_graph(profile) == {"nodes": [], "links": []}
    assert vault_backlinks.get_backlinks(profile, "B") == []
    assert grounding.ground(profile, "what is atlas") == []
    assert os.listdir(vault_root) == ["Notes"]


def test_a_single_folder_written_as_a_string_grants_only_that_folder(vault_root):
    profile = {"vault_folders": "Code"}
    assert vault_paths.get_allowed_dirs(profile) == [os.path.join(vault_root, "Code")]
