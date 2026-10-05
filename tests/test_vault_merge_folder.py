"""Moving a folder onto one of the same name (docs/decisions/074, slice 3): moving it under another name, or merging it
into the one there with what is in both renamed, never overwritten, and the links that named it following."""

import os

import pytest

from sympose import vault_write_move_folder as mf
from sympose.vault_write_merge_folder import free_name
from sympose.vault_write_status import NOTE_EXISTS, NOTE_INVALID_NAME

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


def merge(vault, **kw):
    return mf.move_folder_to_path(ALL, "People", "Archive", if_exists="merge", **kw)


def test_a_merge_with_nothing_in_both_puts_the_files_in_merges_subfolders_and_removes_the_emptied_folder(vault):
    write(vault, "People/Anna.md", "I know [[People/Ben]].\n")
    write(vault, "People/Sub/Cleo.md", "Cleo\n")
    write(vault, "Archive/People/Ben.md", "Ben\n")
    write(vault, "Archive/People/Sub/Dan.md", "Dan\n")
    write(vault, "Journal/Day.md", "[[People/Sub/Cleo]] [[People/Ben]]\n")

    status, got = merge(vault)

    assert status == mf.OK and got.path == "Archive/People" and got.merged and got.renamed_notes == ()
    assert not exists(vault, "People")
    assert all(exists(vault, p) for p in ("Archive/People/Anna.md", "Archive/People/Ben.md", "Archive/People/Sub/Cleo.md", "Archive/People/Sub/Dan.md"))
    assert read(vault, "Journal/Day.md") == "[[Archive/People/Sub/Cleo]] [[People/Ben]]\n"  # Ben was already there: not one of the incoming files


def test_a_merge_with_notes_in_both_does_nothing_until_the_user_agrees_to_rename_the_incoming_ones(vault):
    write(vault, "People/Anna.md", "incoming\n")
    write(vault, "Archive/People/Anna.md", "there\n")

    assert merge(vault) == (NOTE_EXISTS, None)
    assert read(vault, "People/Anna.md") == "incoming\n" and read(vault, "Archive/People/Anna.md") == "there\n"


def test_the_incoming_note_gets_the_first_free_number_and_the_one_there_is_never_touched(vault):
    write(vault, "People/Anna.md", "incoming\n")
    write(vault, "Archive/People/Anna.md", "there\n")
    write(vault, "Archive/People/Anna (2).md", "also there\n")

    status, got = merge(vault, rename_clashing_notes=True)

    assert status == mf.OK and got.renamed_notes == (("People/Anna.md", "People/Anna (3).md"),)
    assert read(vault, "Archive/People/Anna.md") == "there\n" and read(vault, "Archive/People/Anna (2).md") == "also there\n"
    assert read(vault, "Archive/People/Anna (3).md") == "incoming\n" and not exists(vault, "People")


def test_links_that_named_the_incoming_note_follow_it_and_those_to_the_one_there_stay(vault):
    write(vault, "People/Anna.md", "incoming\n")
    write(vault, "People/Ben.md", "Ben, see [[People/Anna]]\n")
    write(vault, "Archive/People/Anna.md", "there\n")
    write(vault, "Journal/Day.md", "[[People/Anna]] and [[Archive/People/Anna]]\n")

    merge(vault, rename_clashing_notes=True)

    assert read(vault, "Journal/Day.md") == "[[Archive/People/Anna (2)]] and [[Archive/People/Anna]]\n"
    assert read(vault, "Archive/People/Ben.md") == "Ben, see [[Archive/People/Anna (2)]]\n"


def test_a_clash_in_a_subfolder_and_an_image_in_both_are_renamed_too(vault):
    write(vault, "People/Sub/Cleo.md", "incoming\n")
    write(vault, "People/photo.png", "new")
    write(vault, "Archive/People/Sub/Cleo.md", "there\n")
    write(vault, "Archive/People/photo.png", "old")

    status, got = merge(vault, rename_clashing_notes=True)

    assert status == mf.OK and got.renamed_notes == (("People/Sub/Cleo.md", "People/Sub/Cleo (2).md"),) and got.renamed_others == 1
    assert read(vault, "Archive/People/Sub/Cleo (2).md") == "incoming\n" and read(vault, "Archive/People/Sub/Cleo.md") == "there\n"
    assert read(vault, "Archive/People/photo (2).png") == "new" and read(vault, "Archive/People/photo.png") == "old"


def test_a_folder_where_the_one_there_has_a_file_is_renamed_like_a_file(vault):
    write(vault, "People/Sub/Cleo.md", "Cleo\n")
    write(vault, "Archive/People/Sub", "a file")

    status, got = merge(vault, rename_clashing_notes=True)

    assert status == mf.OK and read(vault, "Archive/People/Sub") == "a file" and read(vault, "Archive/People/Sub (2)/Cleo.md") == "Cleo\n"


def test_hidden_files_stay_behind_and_keep_the_folder(vault):
    write(vault, "People/Anna.md")
    write(vault, "People/.keep", "mine")
    write(vault, "Archive/People/.keep", "theirs")

    status, got = merge(vault)

    assert status == mf.OK and got.left_behind == 1 and exists(vault, "Archive/People/Anna.md")
    assert read(vault, "People/.keep") == "mine" and read(vault, "Archive/People/.keep") == "theirs" and not exists(vault, "People/Anna.md")


def test_a_hidden_file_and_a_hidden_folder_with_no_clash_stay_behind_too(vault):
    write(vault, "People/Anna.md")
    write(vault, "People/.keep", "mine")
    write(vault, "People/.git/config", "git")
    write(vault, "Archive/People/Ben.md")

    status, got = merge(vault)

    assert status == mf.OK and got.left_behind == 1 and exists(vault, "People/.keep") and exists(vault, "People/.git/config")
    assert not exists(vault, "Archive/People/.keep") and not exists(vault, "Archive/People/.git")


def test_merge_with_no_folder_there_is_a_plain_move(vault):
    write(vault, "People/Anna.md")
    write(vault, "Archive/Old.md")

    status, got = merge(vault)

    assert status == mf.OK and not got.merged and exists(vault, "Archive/People/Anna.md")


def test_a_folder_there_with_no_answer_given_is_refused_and_nothing_moves(vault):
    write(vault, "People/Anna.md")
    write(vault, "Archive/People/Ben.md")

    assert mf.move_folder_to_path(ALL, "People", "Archive") == (NOTE_EXISTS, None)
    assert exists(vault, "People/Anna.md")


def test_moving_under_another_name_keeps_the_other_folder_and_rewrites_links_to_the_new_name(vault):
    write(vault, "People/Anna.md", "Anna\n")
    write(vault, "Archive/People/Ben.md", "Ben\n")
    write(vault, "Journal/Day.md", "[[People/Anna]] [[Archive/People/Ben]]\n")

    status, got = mf.move_folder_to_path(ALL, "People", "Archive", if_exists="rename", new_name=" Friends ")

    assert status == mf.OK and got.path == "Archive/Friends" and not got.merged
    assert exists(vault, "Archive/Friends/Anna.md") and exists(vault, "Archive/People/Ben.md") and not exists(vault, "People")
    assert read(vault, "Journal/Day.md") == "[[Archive/Friends/Anna]] [[Archive/People/Ben]]\n"


@pytest.mark.parametrize("name, status", [("", "denied"), ("a/b", NOTE_INVALID_NAME), (".hid", NOTE_INVALID_NAME), ("bad|name", NOTE_INVALID_NAME), ("Other", NOTE_EXISTS)])
def test_a_bad_or_taken_new_name_is_refused_and_nothing_moves(vault, name, status):
    write(vault, "People/Anna.md")
    write(vault, "Archive/Other/x.md")

    got, details = mf.move_folder_to_path(ALL, "People", "Archive", if_exists="rename", new_name=name)

    assert details is None and (got == status or status == "denied") and exists(vault, "People/Anna.md")


def test_the_first_free_number_skips_every_folder_given():
    assert free_name("Anna.md", False) == "Anna (2).md"


def test_a_folder_name_with_a_dot_is_numbered_whole(vault):
    write(vault, "a/v1.2/x.md")
    assert free_name("v1.2", True, os.path.join(vault, "a")) == "v1.2 (2)"
