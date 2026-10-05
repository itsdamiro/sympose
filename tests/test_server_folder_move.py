"""`PATCH /api/vault/folder/move` (docs/decisions/074, no clash), through the real app on a scratch vault and scratch
profiles: the move and its links, what follows it outside the vault's files (scopes, hidden list, pending changes), and
the question a move that changes what a persona can read has to be answered."""

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
        "Archive/Old.md": "old\n",
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


def move(client, path="People", destination="Archive", persona="samantha", **extra):
    return client.patch("/api/vault/folder/move", json={"path": path, "destination": destination, "persona": persona, **extra})


def test_the_folder_moves_and_the_answer_says_where_it_went_and_what_was_relinked(env):
    client, vault, _ = env

    res = move(client)

    assert res.status_code == 200
    body = res.json()
    assert body["path"] == "Archive/People" and body["relinked"] == 1 and body["failed"] == 0
    assert (vault / "Archive/People/Anna.md").exists() and not (vault / "People").exists()
    assert (vault / "Journal/Day.md").read_text() == "Met [[Archive/People/Anna]] and [[Anna]].\n"
    assert "Archive/People" in body["detail"] and "1 note relinked" in body["detail"]


def test_a_persona_whose_scope_names_the_folder_follows_it(env):
    client, _, profiles = env

    body = move(client).json()

    assert body["personas"] == ["Ada"] and body["personas_unchanged"] == []
    assert "folder scope updated for Ada" in body["detail"]
    assert (profiles / "ada/persona.yaml").read_text() == "# ada\nname: Ada\nvault_folders: ['Archive/People', 'Other']\n"
    assert yaml.safe_load((profiles / "grace/persona.yaml").read_text())["vault_folders"] == ["Other"]


def test_the_hidden_list_follows_for_this_vault(env):
    client, vault, _ = env
    vault_hidden.hide(str(vault), "People")
    vault_hidden.hide(str(vault), "People/Sub/Ben.md")

    move(client)

    assert vault_hidden.hidden_paths(str(vault)) == ["Archive/People", "Archive/People/Sub/Ben.md"]


def test_every_personas_pending_changes_and_comments_under_the_folder_follow(env):
    client, _, _ = env
    nc.propose_edit("samantha", "People/Anna.md", NOTE, find="three times", replace="four times", say="")
    nc.annotate("ada", "People/Sub/Ben.md", "Ben\n", quote="Ben", text="who?", author="user")

    move(client)

    assert [d["path"] for d in nc.drafts("samantha")] == ["Archive/People/Anna.md"]
    assert [d["path"] for d in nc.drafts("ada")] == ["Archive/People/Sub/Ben.md"]


def test_a_move_that_changes_what_a_persona_can_read_is_refused_until_the_user_confirms(env):
    client, vault, _ = env  # Grace reads Other; People inside it becomes hers

    res = move(client, destination="Other")

    assert res.status_code == 409 and "Grace gains 2 notes" in res.json()["detail"]
    assert (vault / "People/Anna.md").exists() and not (vault / "Other/People").exists()


def test_the_same_move_goes_ahead_when_confirmed(env):
    client, vault, _ = env

    res = move(client, destination="Other", confirm_reach=True)

    assert res.status_code == 200 and (vault / "Other/People/Anna.md").exists()


def test_a_move_that_changes_nobodys_reach_needs_no_confirmation(env):
    client, _, _ = env

    assert move(client).status_code == 200


def test_a_folder_of_that_name_already_there_is_refused_for_now_and_nothing_moves(env):
    client, vault, _ = env
    (vault / "Archive/People").mkdir()

    res = move(client)

    assert res.status_code == 409 and (vault / "People/Anna.md").exists()


def test_moving_a_top_level_folder_below_the_top_says_its_description_stopped_applying(env):
    client, vault, _ = env
    (vault / "People/People.md").write_text("About people\n")

    body = move(client).json()

    assert body["definition"] == "stops" and "no longer a top-level folder" in body["detail"]


@pytest.mark.parametrize("path, destination, status", [("Nope", "Archive", 404), ("People", "Nope", 404), ("People", "People/Sub", 400), ("People", "", 400), (".trash", "Archive", 403), ("People", ".trash", 403)])
def test_a_refused_move_answers_with_the_right_code_and_changes_nothing_anywhere(env, path, destination, status):
    client, vault, profiles = env
    vault_hidden.hide(str(vault), "People")
    nc.propose_edit("samantha", "People/Anna.md", NOTE, find="three times", replace="four times", say="")
    before = (profiles / "ada/persona.yaml").read_text()

    res = move(client, path, destination)

    assert res.status_code == status
    assert (vault / "People/Anna.md").exists()
    assert vault_hidden.hidden_paths(str(vault)) == ["People"]
    assert [d["path"] for d in nc.drafts("samantha")] == ["People/Anna.md"]
    assert (profiles / "ada/persona.yaml").read_text() == before


def test_a_persona_limited_to_other_folders_cannot_move_this_one(env):
    client, vault, _ = env

    assert move(client, persona="grace").status_code == 403 and (vault / "People/Anna.md").exists()


def test_an_unknown_persona_is_404(env):
    client, _, _ = env
    assert move(client, persona="nobody").status_code == 404


def test_a_folder_there_is_refused_with_no_answer_and_the_error_says_what_to_do(env):
    client, vault, _ = env
    (vault / "Archive/People").mkdir()

    res = move(client)

    assert res.status_code == 409 and "merge" in res.json()["detail"] and (vault / "People/Anna.md").exists()


def test_a_merge_with_files_in_both_waits_for_the_user_to_agree_to_renaming_the_incoming_ones(env):
    client, vault, _ = env
    (vault / "Archive/People").mkdir()
    (vault / "Archive/People/Anna.md").write_text("there\n")

    res = move(client, if_exists="merge")

    assert res.status_code == 409 and "Anna.md" in res.json()["detail"]
    assert (vault / "People/Anna.md").read_text() == NOTE and (vault / "Archive/People/Anna.md").read_text() == "there\n"


def test_a_merge_renames_the_incoming_notes_and_everything_follows_them(env):
    client, vault, profiles = env
    (vault / "Archive/People").mkdir()
    (vault / "Archive/People/Anna.md").write_text("there\n")
    nc.propose_edit("samantha", "People/Anna.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("samantha", "People/Sub/Ben.md", "Ben\n", find="Ben", replace="Benny", say="")

    res = move(client, if_exists="merge", rename_clashing_notes=True)

    assert res.status_code == 200
    body = res.json()
    assert body["path"] == "Archive/People" and body["merged"] is True and body["renamed"] == 1
    assert "merged" in body["detail"] and "1 file renamed" in body["detail"]
    assert (vault / "Archive/People/Anna.md").read_text() == "there\n" and (vault / "Archive/People/Anna (2).md").read_text() == NOTE
    assert (vault / "Journal/Day.md").read_text() == "Met [[Archive/People/Anna (2)]] and [[Anna]].\n"
    assert sorted(d["path"] for d in nc.drafts("samantha")) == ["Archive/People/Anna (2).md", "Archive/People/Sub/Ben.md"]
    assert "Archive/People" in (profiles / "ada/persona.yaml").read_text()


def test_a_merge_that_changes_a_personas_reach_still_asks(env):
    client, vault, _ = env
    (vault / "Other/People").mkdir()

    assert move(client, destination="Other", if_exists="merge").status_code == 409
    assert move(client, destination="Other", if_exists="merge", confirm_reach=True).status_code == 200


def test_moving_under_another_name_follows_in_the_scopes_and_leaves_the_folder_there_alone(env):
    client, vault, profiles = env
    (vault / "Archive/People").mkdir()
    (vault / "Archive/People/Zed.md").write_text("Zed\n")

    body = move(client, if_exists="rename", new_name="Friends").json()

    assert body["path"] == "Archive/Friends" and (vault / "Archive/People/Zed.md").exists() and (vault / "Archive/Friends/Anna.md").exists()
    assert "Archive/Friends" in (profiles / "ada/persona.yaml").read_text()


def test_a_bad_new_name_is_400_and_a_taken_one_409(env):
    client, vault, _ = env
    (vault / "Archive/People").mkdir()
    (vault / "Archive/Taken").mkdir()

    assert move(client, if_exists="rename", new_name="a/b").status_code == 400
    assert move(client, if_exists="rename", new_name="Taken").status_code == 409
    assert (vault / "People/Anna.md").exists()


def test_the_answer_says_when_a_merge_left_files_behind(env):
    client, vault, _ = env
    (vault / "Archive/People").mkdir()
    (vault / "People/.keep").write_text("mine")

    body = move(client, if_exists="merge").json()

    assert body["left_behind"] == 1 and "1 file left in `People`" in body["detail"] and (vault / "People/.keep").exists()
