"""Renaming a vault folder (docs/decisions/073): the directory, the links that name it, its definition note, with the
checks that come first. The personas' scopes, the hidden list and the persona's changes are the route's (test_server_folder)."""

import os

import pytest

from sympose import vault_write_rename_folder as rf
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_INVALID_NAME, NOTE_NOT_FOUND

ALL = {"vault_folders": ["*"]}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return str(root)


def write(vault, rel, text="body\n"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def read(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8", newline="") as f:
        return f.read()


def exists(vault, rel):
    return os.path.exists(os.path.join(vault, rel))


def seed(vault):
    write(vault, "People/Anna.md", "I know [[People/Ben]] and [[Cleo]].\n")
    write(vault, "People/Ben.md", "Ben\n")
    write(vault, "People/Sub/Cleo.md", "Cleo\n")
    write(vault, "People/Photos/anna.png", "png")
    write(vault, "Journal/Day.md", "Met [[People/Anna|Anna]], ![[People/Photos/anna.png]] and [[Ben]].\r\n")
    write(vault, "Other/Note.md", "[[Other/Note]] and [[People]]\n")


def test_the_directory_moves_with_everything_in_it_and_the_links_that_name_it_are_rewritten(vault):
    seed(vault)

    status, got = rf.rename_folder_to_path(ALL, "People", "Team")

    assert status == rf.OK and got.path == "Team"
    assert not exists(vault, "People") and all(exists(vault, p) for p in ("Team/Anna.md", "Team/Ben.md", "Team/Sub/Cleo.md", "Team/Photos/anna.png"))
    assert read(vault, "Team/Anna.md") == "I know [[Team/Ben]] and [[Cleo]].\n"
    assert read(vault, "Journal/Day.md") == "Met [[Team/Anna|Anna]], ![[Team/Photos/anna.png]] and [[Ben]].\r\n"
    assert read(vault, "Other/Note.md") == "[[Other/Note]] and [[People]]\n"  # a name-only link, and a link to a note of another folder
    assert (got.relinked, got.failed) == (2, 0)


@pytest.mark.parametrize("spelling", ["People", "/People/", "  People  ", "'People'", "People/", "./People"])
def test_the_folder_path_may_be_spelled_the_way_the_vault_accepts_it(vault, spelling):
    seed(vault)

    status, got = rf.rename_folder_to_path(ALL, spelling, "Team")

    assert status == rf.OK and got.path == "Team" and exists(vault, "Team/Anna.md")


def test_a_folder_in_a_folder_keeps_its_parent_and_the_new_name_stays_in_it(vault):
    write(vault, "A/People/Anna.md", "x\n")
    write(vault, "B/Note.md", "[[A/People/Anna]]\n")

    status, got = rf.rename_folder_to_path(ALL, "A/People", "Team")

    assert status == rf.OK and got.path == "A/Team" and exists(vault, "A/Team/Anna.md")
    assert read(vault, "B/Note.md") == "[[A/Team/Anna]]\n"


def test_the_definition_note_is_renamed_with_the_folder_and_the_links_to_it_follow(vault):
    write(vault, "People/People.md", "# People\n")
    write(vault, "People/Anna.md", "back to [[People]] or [[People/People]]\n")
    write(vault, "Journal/Day.md", "see [[People]]\n")

    status, got = rf.rename_folder_to_path(ALL, "People", "Team")

    assert status == rf.OK and got.definition is True
    assert exists(vault, "Team/Team.md") and not exists(vault, "Team/People.md")
    assert read(vault, "Team/Anna.md") == "back to [[Team]] or [[Team/Team]]\n"
    assert read(vault, "Journal/Day.md") == "see [[Team]]\n"


def test_a_definition_note_whose_new_name_is_taken_is_left_as_it_is(vault):
    write(vault, "People/People.md", "# People\n")
    write(vault, "People/Team.md", "already here\n")

    status, got = rf.rename_folder_to_path(ALL, "People", "Team")

    assert status == rf.OK and got.definition is False
    assert exists(vault, "Team/People.md") and read(vault, "Team/Team.md") == "already here\n"


def test_only_a_top_level_folder_has_a_definition_note_to_rename(vault):
    write(vault, "A/People/People.md", "x\n")

    _, got = rf.rename_folder_to_path(ALL, "A/People", "Team")

    assert got.definition is False and exists(vault, "A/Team/People.md")


@pytest.mark.parametrize("name", ["", "   ", ".", "..", "a/b", "a\\b", ".hidden", "bad[name", "bad]name", "bad|name", "bad#name"])
def test_a_name_that_is_not_one_plain_segment_is_refused_and_nothing_moves(vault, name):
    seed(vault)

    status, got = rf.rename_folder_to_path(ALL, "People", name)

    assert status in (NOTE_INVALID_NAME, NOTE_DENIED) and got is None and exists(vault, "People/Anna.md")


def test_a_name_that_is_taken_is_refused(vault):
    seed(vault)

    assert rf.rename_folder_to_path(ALL, "People", "Journal") == (NOTE_EXISTS, None)
    assert rf.rename_folder_to_path(ALL, "People", "Other") == (NOTE_EXISTS, None)
    assert exists(vault, "People/Anna.md")


def test_a_note_of_that_name_blocks_it_too(vault):
    seed(vault)
    write(vault, "Team", "a file called Team")

    assert rf.rename_folder_to_path(ALL, "People", "Team")[0] == NOTE_EXISTS


def test_a_change_of_case_only_is_not_a_clash(vault):
    seed(vault)

    status, got = rf.rename_folder_to_path(ALL, "People", "PEOPLE")

    assert status == rf.OK and got.path == "PEOPLE" and "PEOPLE" in os.listdir(vault)
    assert read(vault, "Journal/Day.md").startswith("Met [[PEOPLE/Anna|Anna]]")


def test_the_same_name_is_not_a_rename(vault):
    seed(vault)

    assert rf.rename_folder_to_path(ALL, "People", "People")[0] == NOTE_EXISTS


@pytest.mark.parametrize("path", ["Nope", "People/Anna.md", "", ".", "/"])
def test_what_is_not_a_folder_in_the_vault_is_not_found_or_denied(vault, path):
    seed(vault)

    assert rf.rename_folder_to_path(ALL, path, "Team")[0] in (NOTE_NOT_FOUND, NOTE_DENIED)


def test_the_bin_the_dot_folders_and_the_vault_root_are_never_renamed(vault):
    write(vault, ".trash/x.md", "x\n")
    write(vault, ".obsidian/app.json", "{}")

    for path in (".trash", ".obsidian", ".trash/x.md"):
        assert rf.rename_folder_to_path(ALL, path, "Team")[0] in (NOTE_DENIED, NOTE_NOT_FOUND)
    assert exists(vault, ".trash/x.md")


def test_a_persona_limited_to_other_folders_cannot_rename_a_folder_outside_her_scope(vault):
    seed(vault)

    status, got = rf.rename_folder_to_path({"vault_folders": ["Journal"]}, "People", "Team")

    assert status == NOTE_DENIED and got is None and exists(vault, "People/Anna.md")


def test_an_os_failure_is_reported_and_leaves_the_links_alone(vault, monkeypatch):
    seed(vault)
    monkeypatch.setattr(rf.os, "rename", lambda *a, **k: (_ for _ in ()).throw(OSError("busy")))

    status, got = rf.rename_folder_to_path(ALL, "People", "Team")

    assert status.startswith("Error") and got is None
    assert read(vault, "Journal/Day.md") == "Met [[People/Anna|Anna]], ![[People/Photos/anna.png]] and [[Ben]].\r\n"  # nothing was rewritten
    assert exists(vault, "People/Anna.md")


def test_the_other_files_of_a_vault_are_left_byte_for_byte(vault):
    seed(vault)
    write(vault, "Journal/Plain.md", "People/Anna is not a link, [md](People/Anna.md)\r\n")

    rf.rename_folder_to_path(ALL, "People", "Team")

    assert read(vault, "Journal/Plain.md") == "People/Anna is not a link, [md](People/Anna.md)\r\n"
