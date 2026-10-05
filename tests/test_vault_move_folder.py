"""Moving a vault folder into another (docs/decisions/074, no folder of that name there): the directory, the links that
name it rewritten to its full new path, with the checks that come first."""

import os

import pytest

from sympose import vault_write_move_folder as mf
from sympose.vault_write_relink_folder import rewrite_folder_links
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
    write(vault, "Journal/Day.md", "Met [[People/Anna|Anna]], ![[People/Sub/Cleo]] and [[Ben]].\r\n")
    write(vault, "Archive/Old.md", "old\n")
    write(vault, "Projects/Garden/People/Zed.md", "Zed\n")
    write(vault, "Other/Note.md", "[[Projects/Garden/People/Zed]] and [[Other/Note]]\n")


def test_the_directory_moves_with_everything_in_it_and_links_are_rewritten_to_the_full_new_path(vault):
    seed(vault)

    status, got = mf.move_folder_to_path(ALL, "People", "Archive")

    assert status == mf.OK and got.path == "Archive/People"
    assert not exists(vault, "People") and all(exists(vault, p) for p in ("Archive/People/Anna.md", "Archive/People/Sub/Cleo.md", "Archive/Old.md"))
    assert read(vault, "Archive/People/Anna.md") == "I know [[Archive/People/Ben]] and [[Cleo]].\n"
    assert read(vault, "Journal/Day.md") == "Met [[Archive/People/Anna|Anna]], ![[Archive/People/Sub/Cleo]] and [[Ben]].\r\n"
    assert (got.relinked, got.failed) == (2, 0)


def test_a_folder_moved_to_the_vault_root_and_a_link_that_named_its_old_parent_are_rewritten(vault):
    write(vault, "Projects/Garden/People/Zed.md", "Zed\n")
    write(vault, "Other/Note.md", "[[Projects/Garden/People/Zed]] and [[Other/Note]]\n")

    status, got = mf.move_folder_to_path(ALL, "Projects/Garden/People", "")

    assert status == mf.OK and got.path == "People" and exists(vault, "People/Zed.md") and not exists(vault, "Projects/Garden/People")
    assert read(vault, "Other/Note.md") == "[[People/Zed]] and [[Other/Note]]\n"


def test_a_link_by_a_shorter_qualifier_gets_the_full_path_too():
    inside = {"projects/garden/people/zed", "projects/garden/people/zed.md"}

    new, hits = rewrite_folder_links("[[People/Zed]] [[Garden/People/Zed]]", "Projects/Garden/People", "People", inside, "Archive/People")

    assert new == "[[Archive/People/Zed]] [[Archive/People/Zed]]" and hits == 2


def test_a_rename_still_keeps_the_qualifier_before_the_folder():
    new, hits = rewrite_folder_links("[[Projects/People/Zed]]", "Projects/People", "Team", {"projects/people/zed"})

    assert (new, hits) == ("[[Projects/Team/Zed]]", 1)


def test_a_name_already_taken_at_the_destination_is_refused_and_nothing_moves(vault):
    seed(vault)
    write(vault, "Archive/People/Other.md")

    status, got = mf.move_folder_to_path(ALL, "People", "Archive")

    assert (status, got) == (NOTE_EXISTS, None) and exists(vault, "People/Anna.md")


def test_a_file_with_the_folders_name_at_the_destination_is_refused(vault):
    seed(vault)
    write(vault, "Archive/People", "a file")

    assert mf.move_folder_to_path(ALL, "People", "Archive") == (NOTE_EXISTS, None)


@pytest.mark.parametrize("destination", ["People", "People/Sub", "", ])
def test_into_itself_into_its_own_folder_or_where_it_already_is_is_invalid(vault, destination):
    seed(vault)

    assert mf.move_folder_to_path(ALL, "People", destination) == (NOTE_INVALID_NAME, None)
    assert exists(vault, "People/Anna.md")


def test_into_its_present_parent_is_invalid(vault):
    seed(vault)

    assert mf.move_folder_to_path(ALL, "Projects/Garden", "Projects") == (NOTE_INVALID_NAME, None)


def test_a_missing_folder_or_destination_is_not_found(vault):
    seed(vault)

    assert mf.move_folder_to_path(ALL, "Nope", "Archive") == (NOTE_NOT_FOUND, None)
    assert mf.move_folder_to_path(ALL, "People", "Nope") == (NOTE_NOT_FOUND, None)


def test_a_dot_folder_and_a_destination_outside_the_persona_scope_are_denied(vault):
    seed(vault)
    write(vault, ".obsidian/x.md")

    assert mf.move_folder_to_path(ALL, ".obsidian", "Archive") == (NOTE_DENIED, None)
    assert mf.move_folder_to_path(ALL, "People", ".obsidian") == (NOTE_DENIED, None)
    assert mf.move_folder_to_path({"vault_folders": ["People"]}, "People", "Archive") == (NOTE_DENIED, None)
