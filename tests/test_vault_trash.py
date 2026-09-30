"""Tests for vault_trash.py — list/restore/purge of the trash-recovery
surface, including the clash-index round-trip and the locking added this
session."""

import os

import pytest

from sympose import vault_trash
from sympose.vault_trash_index import record_clashes
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND


@pytest.fixture
def vault(tmp_path):
    return str(tmp_path)


@pytest.fixture
def allowed(vault):
    return [vault]


def _trash(vault, rel_path, content="x"):
    """Puts a file straight into `.trash/<rel_path>`, as if `delete_note`
    had already moved it there."""
    dest = os.path.join(vault, vault_trash.TRASH_DIRNAME, rel_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        f.write(content)
    return dest


def test_list_trashed_empty_when_no_trash_dir(vault, allowed):
    assert vault_trash.list_trashed(vault, allowed) == []


def test_list_trashed_returns_items_newest_first(vault, allowed):
    _trash(vault, "A.md")
    a_path = os.path.join(vault, vault_trash.TRASH_DIRNAME, "A.md")
    os.utime(a_path, (1000, 1000))
    _trash(vault, "B.md")
    b_path = os.path.join(vault, vault_trash.TRASH_DIRNAME, "B.md")
    os.utime(b_path, (2000, 2000))

    rows = vault_trash.list_trashed(vault, allowed)
    assert [r["trash_path"] for r in rows] == ["B.md", "A.md"]
    assert rows[0]["original_path"] == "B.md"


def test_list_trashed_omits_entries_outside_allowed_dirs(vault):
    _trash(vault, "Scoped/A.md")
    # allowed_dirs is a different, unrelated subfolder — the original
    # location ("Scoped/A.md") resolves outside it.
    other_dir = os.path.join(vault, "Other")
    os.makedirs(other_dir)
    assert vault_trash.list_trashed(vault, [other_dir]) == []


def test_restore_moves_the_file_back(vault, allowed):
    _trash(vault, "A.md", "hello")
    result = vault_trash.restore(vault, allowed, "A.md")
    assert result == ("Restored to `A.md`", "A.md")
    assert os.path.exists(os.path.join(vault, "A.md"))
    assert not os.path.exists(os.path.join(vault, ".trash", "A.md"))


def test_restore_missing_entry_not_found(vault, allowed):
    assert vault_trash.restore(vault, allowed, "Nope.md") == (NOTE_NOT_FOUND, None)


def test_restore_rejects_path_outside_trash_root(vault, allowed):
    assert vault_trash.restore(vault, allowed, "../../etc/passwd") == (NOTE_DENIED, None)


def test_restore_onto_an_occupied_destination_is_rejected(vault, allowed):
    _trash(vault, "A.md")
    with open(os.path.join(vault, "A.md"), "w") as f:
        f.write("already here")
    assert vault_trash.restore(vault, allowed, "A.md") == (NOTE_EXISTS, None)
    # Both copies survive a rejected restore.
    assert os.path.exists(os.path.join(vault, ".trash", "A.md"))
    assert os.path.exists(os.path.join(vault, "A.md"))


def test_restore_honors_the_clash_index(vault, allowed):
    # Simulates what delete_note does on a same-named clash: the trashed
    # file gets a timestamp-suffixed name, and the index records what its
    # real original path was.
    _trash(vault, "A-20260101000000.md")
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    record_clashes(troot, {"A-20260101000000.md": "Notes/A.md"})

    result = vault_trash.restore(vault, allowed, "A-20260101000000.md")
    assert result == ("Restored to `Notes/A.md`", "Notes/A.md")
    assert os.path.exists(os.path.join(vault, "Notes", "A.md"))


def test_purge_deletes_permanently(vault, allowed):
    _trash(vault, "A.md")
    assert vault_trash.purge(vault, allowed, "A.md") == ""
    assert not os.path.exists(os.path.join(vault, ".trash", "A.md"))


def test_purge_missing_entry_not_found(vault, allowed):
    assert vault_trash.purge(vault, allowed, "Nope.md") == NOTE_NOT_FOUND


def test_purge_all_removes_every_in_scope_entry(vault, allowed):
    _trash(vault, "A.md")
    _trash(vault, "B.md")
    assert vault_trash.purge_all(vault, allowed) == 2
    assert vault_trash.list_trashed(vault, allowed) == []


# -- every file in the bin, not only notes (issue #100) ----------------------


def _bin_files(vault):
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    return sorted(
        os.path.relpath(os.path.join(cur, name), troot).replace(os.sep, "/")
        for cur, _, files in os.walk(troot)
        for name in files
    )


def _bin_dirs(vault):
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    return sorted(
        os.path.relpath(os.path.join(cur, name), troot).replace(os.sep, "/")
        for cur, dirs, _ in os.walk(troot)
        for name in dirs
    )


def test_list_trashed_lists_attachments_and_other_files_with_their_original_paths(vault, allowed):
    _trash(vault, "Trip/Plan.md")
    _trash(vault, "Trip/img/map.png", "png")
    _trash(vault, "Trip/img/sub/ticket.pdf", "pdf")
    _trash(vault, "Trip/board.canvas", "{}")
    rows = vault_trash.list_trashed(vault, allowed)
    assert sorted(r["trash_path"] for r in rows) == [
        "Trip/Plan.md", "Trip/board.canvas", "Trip/img/map.png", "Trip/img/sub/ticket.pdf",
    ]
    by_path = {r["trash_path"]: r for r in rows}
    assert by_path["Trip/img/map.png"]["original_path"] == "Trip/img/map.png"
    assert by_path["Trip/img/map.png"]["size"] == 3


def test_list_trashed_leaves_hidden_files_and_the_index_out_but_they_stay_in_the_bin(vault, allowed):
    _trash(vault, "Trip/Plan.md")
    _trash(vault, "Trip/.DS_Store")
    _trash(vault, "Trip/.obsidian/workspace.json")
    record_clashes(os.path.join(vault, vault_trash.TRASH_DIRNAME), {"Plan-1.md": "Trip/Plan.md"})
    assert [r["trash_path"] for r in vault_trash.list_trashed(vault, allowed)] == ["Trip/Plan.md"]


def test_a_listed_file_is_scoped_like_a_note(vault):
    _trash(vault, "Scoped/img/a.png")
    _trash(vault, "Other/img/b.png")
    rows = vault_trash.list_trashed(vault, [os.path.join(vault, "Scoped")])
    assert [r["trash_path"] for r in rows] == ["Scoped/img/a.png"]


def test_an_attachment_is_restored_to_where_it_was_recreating_its_folders(vault, allowed):
    _trash(vault, "Trip/img/map.png", "png")
    assert vault_trash.restore(vault, allowed, "Trip/img/map.png") == ("Restored to `Trip/img/map.png`", "Trip/img/map.png")
    assert open(os.path.join(vault, "Trip", "img", "map.png")).read() == "png"
    assert _bin_files(vault) == [] and _bin_dirs(vault) == []  # the emptied folders went with it


def test_an_attachment_is_purged_alone_and_its_emptied_folders_are_pruned(vault, allowed):
    _trash(vault, "Trip/img/map.png")
    _trash(vault, "Trip/Plan.md")
    assert vault_trash.purge(vault, allowed, "Trip/img/map.png") == ""
    assert _bin_files(vault) == ["Trip/Plan.md"] and _bin_dirs(vault) == ["Trip"]


def test_emptying_the_bin_removes_every_file_including_the_ones_the_list_does_not_show(vault, allowed):
    _trash(vault, "Trip/Plan.md")
    _trash(vault, "Trip/img/map.png")
    _trash(vault, "Trip/img/sub/ticket.pdf")
    _trash(vault, "Trip/board.canvas")
    _trash(vault, "Trip/.obsidian/workspace.json")
    _trash(vault, "Trip/.DS_Store")
    assert vault_trash.purge_all(vault, allowed) == 4  # what the list showed; hidden files go without being counted
    assert _bin_files(vault) == [] and _bin_dirs(vault) == []


def test_emptying_the_bin_also_removes_empty_folders_left_in_it(vault, allowed):
    os.makedirs(os.path.join(vault, ".trash", "Trip", "empty", "deeper"))
    _trash(vault, "Trip/Plan.md")
    vault_trash.purge_all(vault, allowed)
    assert _bin_dirs(vault) == []


def test_emptying_the_bin_leaves_what_is_outside_the_personas_folders_hidden_files_included(vault):
    _trash(vault, "Scoped/a.png")
    _trash(vault, "Scoped/.DS_Store")
    _trash(vault, "Other/b.png")
    _trash(vault, "Other/.DS_Store")
    assert vault_trash.purge_all(vault, [os.path.join(vault, "Scoped")]) == 1
    assert _bin_files(vault) == ["Other/.DS_Store", "Other/b.png"]
    assert "Scoped" not in _bin_dirs(vault)


def test_emptying_the_bin_forgets_the_original_paths_it_no_longer_needs(vault, allowed):
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    _trash(vault, "Trip-20260101000000/img/map.png")
    record_clashes(troot, {"Trip-20260101000000/img/map.png": "Trip/img/map.png"})
    vault_trash.purge_all(vault, allowed)
    from sympose.vault_trash_index import load_index

    assert load_index(troot) == {}


def test_emptying_the_bin_never_follows_a_link_out_of_it(vault, allowed, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "precious.png"
    outside.write_text("keep")
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    os.makedirs(os.path.join(troot, "Trip"))
    os.symlink(outside, os.path.join(troot, "Trip", "link.png"))
    os.symlink(outside.parent, os.path.join(troot, "Trip", "linkdir"))
    vault_trash.purge_all(vault, allowed)
    assert outside.read_text() == "keep"


def test_a_folder_deleted_with_its_attachments_leaves_nothing_behind_once_the_bin_is_emptied(vault, allowed):
    from sympose import vault_write_delete

    os.makedirs(os.path.join(vault, "Trip", "img"))
    for rel, data in (("Trip/Plan.md", "# Plan"), ("Trip/img/map.png", "png"), ("Trip/board.canvas", "{}")):
        with open(os.path.join(vault, rel), "w") as f:
            f.write(data)
    profile = {"handle": "s", "vault_folders": "*"}
    os.environ["VAULT_PATHS"] = vault
    try:
        assert "Moved folder to the bin" in vault_write_delete.delete_folder(profile, "Trip")
        assert len(vault_trash.list_trashed(vault, allowed)) == 3
        assert vault_trash.purge_all(vault, allowed) == 3
    finally:
        del os.environ["VAULT_PATHS"]
    assert _bin_files(vault) == [] and _bin_dirs(vault) == []


def test_a_scoped_emptying_keeps_the_index_the_files_it_left_still_need(vault):
    from sympose.vault_trash_index import load_index

    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    _trash(vault, "Scoped/a.png")
    _trash(vault, "Other-20260101000000/b.png")
    record_clashes(troot, {"Other-20260101000000/b.png": "Other/b.png"})
    vault_trash.purge_all(vault, [os.path.join(vault, "Scoped")])
    assert load_index(troot) == {"Other-20260101000000/b.png": "Other/b.png"}
    assert [r["original_path"] for r in vault_trash.list_trashed(vault, [os.path.join(vault, "Other")])] == ["Other/b.png"]


def test_emptying_leaves_the_bin_folder_itself_and_empty_folders_outside_the_scope(vault):
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    _trash(vault, "Scoped/a.png")
    os.makedirs(os.path.join(troot, "Other", "empty"))
    vault_trash.purge_all(vault, [os.path.join(vault, "Scoped")])
    assert os.path.isdir(os.path.join(troot, "Other", "empty"))
    vault_trash.purge_all(vault, [vault])
    assert os.path.isdir(troot) and _bin_files(vault) == [] and _bin_dirs(vault) == []


def test_emptying_a_vault_with_no_bin_removes_nothing(vault, allowed):
    assert vault_trash.purge_all(vault, allowed) == 0
    assert not os.path.exists(os.path.join(vault, vault_trash.TRASH_DIRNAME))


def test_the_index_survives_emptying_while_a_file_that_could_not_be_purged_still_needs_it(vault, allowed, tmp_path_factory):
    from sympose.vault_trash_index import load_index

    outside = tmp_path_factory.mktemp("outside") / "keep.png"
    outside.write_text("keep")
    troot = os.path.join(vault, vault_trash.TRASH_DIRNAME)
    os.makedirs(os.path.join(troot, "Trip-20260101000000"))
    os.symlink(outside, os.path.join(troot, "Trip-20260101000000", "keep.png"))  # a link out is never removed
    record_clashes(troot, {"Trip-20260101000000/keep.png": "Trip/keep.png"})
    vault_trash.purge_all(vault, allowed)
    assert outside.read_text() == "keep"
    assert load_index(troot) == {"Trip-20260101000000/keep.png": "Trip/keep.png"}
