"""`PATCH /api/vault/folder` (docs/decisions/073), through the real app on a scratch vault and scratch profiles: the
rename and its links, then what lives outside the vault's files and follows it: the personas' own folder scopes, the
hidden list, and every persona's pending changes and comments."""


import pytest
import yaml
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import note_changes as nc
from sympose import vault_hidden
from sympose.server import create_app

NOTE = "I run three times a week. The beds are raised.\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for rel, text in {
        "People/Anna.md": NOTE,
        "People/Sub/Ben.md": "Ben\n",
        "Journal/Day.md": "Met [[People/Anna]] and [[Anna]].\n",
        "Other/Note.md": "Other\n",
    }.items():
        (vault / rel).parent.mkdir(parents=True, exist_ok=True)
        (vault / rel).write_text(text)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    write_persona(profiles, "ada", "# ada\nname: Ada\nvault_folders: ['People', 'Other']\n")
    write_persona(profiles, "grace", "name: Grace\nvault_folders: ['Other']\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return TestClient(create_app()), vault, profiles


def rename(client, path="People", new_name="Team", persona="samantha"):
    return client.patch("/api/vault/folder", json={"path": path, "new_name": new_name, "persona": persona})


def test_the_folder_is_renamed_and_the_answer_says_where_it_went_and_what_was_relinked(env):
    client, vault, _ = env

    res = rename(client)

    assert res.status_code == 200
    body = res.json()
    assert body["path"] == "Team" and body["relinked"] == 1 and body["failed"] == 0
    assert (vault / "Team/Anna.md").exists() and not (vault / "People").exists()
    assert (vault / "Journal/Day.md").read_text() == "Met [[Team/Anna]] and [[Anna]].\n"
    assert "Team" in body["detail"]


def test_a_persona_whose_scope_names_the_folder_follows_it_and_is_named_in_the_answer(env):
    client, _, profiles = env

    body = rename(client).json()

    assert body["personas"] == ["Ada"] and body["personas_unchanged"] == []
    assert "folder scope updated for Ada" in body["detail"] and "1 note relinked" in body["detail"]
    text = (profiles / "ada/persona.yaml").read_text()
    assert text == "# ada\nname: Ada\nvault_folders: ['Team', 'Other']\n"
    assert yaml.safe_load((profiles / "grace/persona.yaml").read_text())["vault_folders"] == ["Other"]


def test_the_hidden_list_follows_for_this_vault(env):
    client, vault, _ = env
    vault_hidden.hide(str(vault), "People")
    vault_hidden.hide(str(vault), "People/Sub/Ben.md")

    rename(client)

    assert vault_hidden.hidden_paths(str(vault)) == ["Team", "Team/Sub/Ben.md"]


def test_every_personas_pending_changes_and_comments_under_the_folder_follow(env):
    client, _, _ = env
    nc.propose_edit("samantha", "People/Anna.md", NOTE, find="three times", replace="four times", say="")
    nc.annotate("ada", "People/Sub/Ben.md", "Ben\n", quote="Ben", text="who?", author="user")
    nc.propose_edit("samantha", "Other/Note.md", "Other\n", find="Other", replace="Another", say="")

    rename(client)

    assert [d["path"] for d in nc.drafts("samantha") if d["path"].startswith(("Team", "People"))] == ["Team/Anna.md"]
    assert [d["path"] for d in nc.drafts("ada")] == ["Team/Sub/Ben.md"]
    assert [d["path"] for d in nc.drafts("samantha") if d["path"] == "Other/Note.md"] == ["Other/Note.md"]


@pytest.mark.parametrize("path, new_name, status", [("Nope", "Team", 404), ("People", "Other", 409), ("People", "a/b", 400), ("People", "bad|name", 400), (".trash", "Team", 403), ("People", "", 403)])
def test_a_refused_rename_answers_with_the_right_code_and_changes_nothing_anywhere(env, path, new_name, status):
    client, vault, profiles = env
    vault_hidden.hide(str(vault), "People")
    nc.propose_edit("samantha", "People/Anna.md", NOTE, find="three times", replace="four times", say="")
    before = (profiles / "ada/persona.yaml").read_text()

    res = rename(client, path, new_name)

    assert res.status_code == status
    assert (vault / "People/Anna.md").exists()
    assert vault_hidden.hidden_paths(str(vault)) == ["People"]
    assert [d["path"] for d in nc.drafts("samantha")] == ["People/Anna.md"]
    assert (profiles / "ada/persona.yaml").read_text() == before


def test_a_persona_limited_to_other_folders_cannot_rename_this_one(env):
    client, vault, _ = env

    res = rename(client, persona="grace")

    assert res.status_code == 403 and (vault / "People/Anna.md").exists()


def test_an_unknown_persona_is_404(env):
    client, _, _ = env
    assert rename(client, persona="nobody").status_code == 404


def test_a_persona_whose_file_cannot_be_rewritten_is_named_as_needing_a_manual_edit(env, monkeypatch):
    client, _, profiles = env
    from sympose import persona_scope

    def refuse(path, text, *a, **k):
        raise OSError("read-only")

    monkeypatch.setattr(persona_scope, "write_atomic_text", refuse)

    body = rename(client).json()

    assert body["personas"] == [] and body["personas_unchanged"] == ["Ada"]
    assert "['People', 'Other']" in (profiles / "ada/persona.yaml").read_text()
    assert "Ada" in body["detail"]
