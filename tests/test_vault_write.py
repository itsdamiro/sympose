"""Regression tests for vault_write_rename / vault_write_delete's locking —
confirms the get_file_locks(src, dst) refactor didn't change normal,
non-concurrent behavior (see CODE_QUALITY_STANDARDS.md §7: verify after any
meaningful edit)."""

import os

import pytest
from helpers import rename_note

from sympose import vault_write_delete
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


@pytest.fixture
def profile():
    return {"vault_folders": ["*"]}


def test_rename_moves_the_file(vault, profile):
    with open(os.path.join(vault, "A.md"), "w") as f:
        f.write("hello")
    result = rename_note(profile, "A", "B")
    assert result == "Renamed to `B.md`"
    assert not os.path.exists(os.path.join(vault, "A.md"))
    assert os.path.exists(os.path.join(vault, "B.md"))


def test_rename_onto_an_existing_note_is_rejected(vault, profile):
    with open(os.path.join(vault, "A.md"), "w") as f:
        f.write("a")
    with open(os.path.join(vault, "B.md"), "w") as f:
        f.write("b")
    assert rename_note(profile, "A", "B") == NOTE_EXISTS
    # Neither file was touched by the rejected rename.
    assert os.path.exists(os.path.join(vault, "A.md"))
    assert os.path.exists(os.path.join(vault, "B.md"))


def test_rename_missing_note_not_found(vault, profile):
    assert rename_note(profile, "Nope", "B") == NOTE_NOT_FOUND


def test_rename_survives_a_concurrent_delete_and_recreate_race(vault, profile):
    """Regression test for a `/code-review` finding: `os.path.samefile` had
    no `try`/`except`, so a concurrent request racing in between path
    resolution and the in-lock re-check (deleting `src`, creating
    something new at `dst`) could raise an uncaught `FileNotFoundError`,
    escaping this module's sentinel-only contract as an unhandled 500."""
    src_path = os.path.join(vault, "Draft.md")
    with open(src_path, "w") as f:
        f.write("draft")

    def racing_get_backlinks(profile, stem):
        # Simulates another request landing while this rename is still
        # resolving backlinks, before its own lock is acquired: the
        # source note is deleted and something else now occupies the
        # destination path.
        os.remove(src_path)
        with open(os.path.join(vault, "Final.md"), "w") as f:
            f.write("someone else's note")
        return []

    result = rename_note(
        profile,
        "Draft",
        "Final",
        get_backlinks_fn=racing_get_backlinks,
        find_notes_by_stem_fn=lambda profile, stem: [],
    )
    # Must not raise -- degrades to the module's own error contract instead.
    assert result.startswith("Error:")
    # The racing write is never silently clobbered by the failed rename.
    with open(os.path.join(vault, "Final.md")) as f:
        assert f.read() == "someone else's note"


def test_delete_empty_folder_removes_it_outright(vault, profile):
    os.makedirs(os.path.join(vault, "Empty"))
    result = vault_write_delete.delete_folder(profile, "Empty")
    assert "Deleted empty folder" in result
    assert not os.path.exists(os.path.join(vault, "Empty"))


def test_delete_nonempty_folder_moves_to_trash(vault, profile):
    os.makedirs(os.path.join(vault, "Stuff"))
    with open(os.path.join(vault, "Stuff", "note.md"), "w") as f:
        f.write("x")
    result = vault_write_delete.delete_folder(profile, "Stuff")
    assert "Moved folder to the bin" in result
    assert not os.path.exists(os.path.join(vault, "Stuff"))
    assert os.path.exists(os.path.join(vault, ".trash", "Stuff", "note.md"))


def test_delete_folder_resolving_to_vault_root_is_denied(vault, profile):
    assert vault_write_delete.delete_folder(profile, ".") == NOTE_DENIED
    # The vault root itself must survive a rejected delete.
    assert os.path.isdir(vault)


def test_delete_folder_on_trash_itself_is_denied(vault, profile):
    os.makedirs(os.path.join(vault, ".trash"))
    assert vault_write_delete.delete_folder(profile, ".trash") == NOTE_DENIED
    assert os.path.isdir(os.path.join(vault, ".trash"))


# -- the per-path lock table does not grow without bound (#114) --------------------


def test_a_lock_nobody_holds_is_forgotten():
    import gc

    from sympose import vault_write

    for i in range(50):
        with vault_write.get_file_lock(f"/vault/note-{i}.md"):
            pass
    gc.collect()
    assert not [p for p in vault_write._locks if p.startswith("/vault/note-")]


def test_two_writers_on_one_path_still_share_one_lock_while_it_is_held():
    from sympose import vault_write

    with vault_write.get_file_lock("/vault/shared.md") as _:
        again = vault_write.get_file_lock("/vault/shared.md")
        assert again.locked()  # the very lock the first writer holds, not a fresh one


def test_a_lock_held_across_a_collection_keeps_excluding_a_second_writer():
    import gc
    import threading

    from sympose import vault_write

    got_it = threading.Event()
    with vault_write.get_file_lock("/vault/held.md"):
        gc.collect()

        def second():
            with vault_write.get_file_lock("/vault/held.md"):
                got_it.set()

        t = threading.Thread(target=second)
        t.start()
        assert not got_it.wait(0.3)  # still blocked while the first holds it
    t.join(2)
    assert got_it.is_set()
