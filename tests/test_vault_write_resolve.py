"""Resolving an existing note: a name is a path from the vault's root and resolves only as that path, never to a
note of the same name elsewhere (docs/decisions/047, #99)."""

import os

import pytest
from helpers import rename_note
from fastapi import HTTPException

from sympose import server_handlers, vault_write, vault_write_delete, vault_write_resolve
from sympose.vault_write_status import NOTE_NOT_FOUND


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


@pytest.fixture
def profile():
    return {"vault_folders": ["*"]}


def test_resolve_bare_name_at_allowed_dir_top_level(vault, profile):
    with open(os.path.join(vault, "Solo.md"), "w") as f:
        f.write("x")
    resolved = vault_write_resolve.resolve_existing_note(profile, "Solo")
    assert resolved == os.path.join(vault, "Solo.md")


# --- an exact path resolves only as that path ------------------------------------------------


def write_note(vault, rel, text="body"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


@pytest.mark.parametrize("name", ["A/Note.md", "A/Note", "Missing/Deeper/Note.md"])
def test_an_exact_path_that_does_not_exist_does_not_resolve_to_a_note_of_the_same_name(vault, profile, name):
    write_note(vault, "B/Note.md")
    assert vault_write_resolve.resolve_existing_note(profile, name) is None


def test_an_exact_path_resolves_to_that_note_even_when_another_has_the_same_name(vault, profile):
    write_note(vault, "A/Note.md", "a")
    write_note(vault, "B/Note.md", "b")
    assert vault_write_resolve.resolve_existing_note(profile, "B/Note") == os.path.join(vault, "B", "Note.md")


def test_a_top_level_name_is_the_note_at_the_top_of_the_vault_and_nothing_below_it(vault, profile):
    """#99: `Meeting.md` deleted or moved at the top, a stale screen asks for it: it must not become
    `Archive/Meeting.md`."""
    deeper = write_note(vault, "Archive/Meeting.md", "keep me")
    for name in ("Meeting", "Meeting.md", "meeting"):
        assert vault_write_resolve.resolve_existing_note(profile, name) is None
    top = write_note(vault, "Meeting.md", "top")
    assert vault_write_resolve.resolve_existing_note(profile, "Meeting") == top
    assert vault_write_resolve.resolve_existing_note(profile, "Archive/Meeting") == deeper


@pytest.mark.parametrize("ghost", ["Deep/Er/Note.md", "Code/Aa/Note.md"])
def test_a_name_without_its_folder_does_not_find_a_note_in_one(vault, profile, ghost):
    write_note(vault, ghost)
    assert vault_write_resolve.resolve_existing_note(profile, "Note") is None
    assert vault_write_resolve.resolve_existing_note({"vault_folders": ["Code"]}, "Note") is None


# The four callers: with only `B/Note.md` present, a request for `A/Note.md` (a tree that is out of
# date, a double click) must be "not found" and leave `B/Note.md` alone.


@pytest.fixture
def only_b(vault):
    return write_note(vault, "B/Note.md", "keep me")


def unchanged(path):
    with open(path, encoding="utf-8") as f:
        return f.read() == "keep me"


def test_reading_an_exact_path_that_is_gone_is_not_found(only_b):
    with pytest.raises(HTTPException) as exc_info:
        server_handlers.read_note("A/Note.md", None)
    assert exc_info.value.status_code == 404


def test_saving_an_exact_path_that_is_gone_is_not_found_and_overwrites_nothing(only_b, profile):
    assert vault_write.overwrite_note(profile, "A/Note.md", "clobbered") == NOTE_NOT_FOUND
    assert unchanged(only_b)


def test_renaming_an_exact_path_that_is_gone_is_not_found_and_moves_nothing(only_b, profile):
    assert rename_note(profile, "A/Note.md", "Other") == NOTE_NOT_FOUND
    assert unchanged(only_b)


def test_deleting_an_exact_path_that_is_gone_is_not_found_and_trashes_nothing(only_b, profile):
    assert vault_write_delete.delete_note(profile, "A/Note.md") == NOTE_NOT_FOUND
    assert unchanged(only_b)


def test_an_exact_path_does_not_fall_back_to_a_note_of_that_name_at_the_top_of_the_vault(vault, profile):
    write_note(vault, "Note.md")
    assert vault_write_resolve.resolve_existing_note(profile, "A/Note.md") is None


def test_an_exact_path_to_a_folder_is_not_a_note(vault, profile):
    os.makedirs(os.path.join(vault, "A", "Folder.md"))
    assert vault_write_resolve.resolve_existing_note(profile, "A/Folder.md") is None


@pytest.mark.parametrize("ghost", [".trash/Ghost.md", ".hidden/Ghost.md", "Attachments/Ghost.md"])
def test_a_name_does_not_find_a_note_in_the_bin_or_a_hidden_or_ignored_folder(vault, profile, ghost):
    write_note(vault, ghost)
    assert vault_write_resolve.resolve_existing_note(profile, "Ghost") is None


@pytest.mark.parametrize("link", ["Link.md", "Deep/Er/Link.md"])
def test_a_note_that_is_a_link_to_a_file_outside_the_vault_does_not_resolve(vault, profile, tmp_path_factory, link):
    outside = tmp_path_factory.mktemp("outside") / "secret.md"
    outside.write_text("secret")
    os.makedirs(os.path.dirname(os.path.join(vault, link)), exist_ok=True)
    os.symlink(outside, os.path.join(vault, link))
    assert vault_write_resolve.resolve_existing_note(profile, "Link") is None
