"""Tests for sympose.engine.memory_write (docs/decisions/041): staging a proposed
context.md/profile.md rewrite, applying it (with its rolling .bak), and discarding it."""

import threading

from helpers import write_persona

from sympose.engine import memory_write as mw


def _persona(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


# -- staging -------------------------------------------------------------------


def test_nothing_is_pending_when_nothing_was_staged(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert mw.has_pending("samantha") is False
    assert mw.pending_profile("samantha") is None
    assert mw.pending_context("samantha") is None


def test_staging_writes_a_pending_file_not_the_real_one(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    assert mw.stage_context("samantha", "Working on the Atlas migration.") is True
    assert mw.has_pending("samantha") is True
    assert mw.pending_context("samantha") == "Working on the Atlas migration."
    assert not (directory / "context.md").exists()
    assert (directory / "context.md.pending").exists()


def test_staging_profile_and_context_independently(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    mw.stage_profile("samantha", "Prefers concise replies.")
    assert mw.pending_profile("samantha") == "Prefers concise replies."
    assert mw.pending_context("samantha") is None


def test_staging_again_replaces_the_previous_proposal(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    mw.stage_context("samantha", "First proposal.")
    mw.stage_context("samantha", "Second proposal.")
    assert mw.pending_context("samantha") == "Second proposal."


# -- applying --------------------------------------------------------------------


def test_applying_writes_the_real_file(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    assert mw.apply_context("samantha", "Working on the Atlas migration.") is True
    assert (directory / "context.md").read_text() == "Working on the Atlas migration.\n"


def test_applying_backs_up_the_previous_content_first(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "profile.md").write_text("Old profile.\n")
    mw.apply_profile("samantha", "New profile.")
    assert (directory / "profile.md.bak").read_text() == "Old profile.\n"
    assert (directory / "profile.md").read_text() == "New profile.\n"


def test_applying_with_nothing_there_yet_writes_no_backup(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    mw.apply_context("samantha", "First content.")
    assert not (directory / "context.md.bak").exists()


def test_applying_on_an_unsafe_handle_fails_rather_than_raising(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert mw.apply_context("../escape", "x") is False


# -- discarding and accepting -----------------------------------------------------


def test_discard_pending_removes_both_pending_files(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    mw.stage_profile("samantha", "p")
    mw.stage_context("samantha", "c")
    mw.discard_pending("samantha")
    assert mw.has_pending("samantha") is False
    assert not (directory / "profile.md.pending").exists()
    assert not (directory / "context.md.pending").exists()


def test_discard_pending_with_nothing_staged_does_not_raise(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    mw.discard_pending("samantha")  # no assertion needed: just must not raise


def test_accept_pending_applies_and_clears_both_proposals(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    mw.stage_profile("samantha", "New profile.")
    mw.stage_context("samantha", "New context.")

    ok = mw.accept_pending("samantha")

    assert ok is True
    assert (directory / "profile.md").read_text() == "New profile.\n"
    assert (directory / "context.md").read_text() == "New context.\n"
    assert mw.has_pending("samantha") is False


def test_accept_pending_applies_only_whichever_file_was_staged(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    mw.stage_context("samantha", "New context only.")

    assert mw.accept_pending("samantha") is True

    assert not (directory / "profile.md").exists()
    assert (directory / "context.md").read_text() == "New context only.\n"


def test_accept_pending_with_nothing_staged_is_not_a_failure(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert mw.accept_pending("samantha") is True


# -- diff_text -------------------------------------------------------------------


def test_diff_text_shows_added_and_removed_lines():
    diff = mw.diff_text("Line one.\nLine two.", "Line one.\nLine three.", "context.md")
    assert "-Line two." in diff
    assert "+Line three." in diff
    assert "Line one." in diff  # unchanged, kept as context


def test_diff_text_against_a_file_that_does_not_exist_yet_shows_every_line_added():
    diff = mw.diff_text(None, "First content.", "profile.md")
    assert "+First content." in diff
    assert "profile.md (current)" in diff and "profile.md (proposed)" in diff


# -- concurrency: applies serialize on the same lock decisions.md's append already uses --------


def test_apply_serializes_on_its_own_write_lock(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    done = threading.Event()

    with mw._WRITE_LOCK:
        thread = threading.Thread(target=lambda: (mw.apply_context("samantha", "x"), done.set()))
        thread.start()
        blocked_while_held = not done.wait(timeout=0.2)

    thread.join(timeout=2)

    assert blocked_while_held is True
    assert done.is_set()
