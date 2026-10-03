"""A persona's own files, edited from the web (docs/decisions/061): the four the user may open, read as they are in
effect, saved with a conflict check and a `.bak`, the soul as a local override of the shipped file, and the
staged rewrites of the memory files."""

import os

import pytest
from helpers import write_persona

from sympose import persona_editable as pe
from sympose import persona_files


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


def _put(directory, name, text):
    (directory / name).write_text(text)
    return (directory / name).stat().st_mtime


def test_it_lists_the_four_files_in_order_with_what_each_is(home):
    files = pe.list_files("samantha")
    assert [f["name"] for f in files] == ["soul.md", "profile.md", "context.md", "decisions.md"]
    assert [f["label"] for f in files] == ["Soul", "Profile", "Context", "Decisions"]
    assert all(f["description"] for f in files)


def test_it_says_which_exist_which_soul_is_local_and_which_have_a_rewrite_waiting(home):
    _put(home, "soul.md", "shipped")
    _put(home, "profile.md", "facts")
    _put(home, "profile.md.pending", "new facts")
    by_name = {f["name"]: f for f in pe.list_files("samantha")}
    assert by_name["soul.md"]["exists"] and not by_name["soul.md"]["local"]
    assert by_name["profile.md"]["exists"] and by_name["profile.md"]["pending"]
    assert not by_name["context.md"]["exists"] and not by_name["context.md"]["pending"]
    _put(home, "soul.local.md", "mine")
    assert {f["name"]: f for f in pe.list_files("samantha")}["soul.md"]["local"] is True


def test_it_reads_the_file_in_effect_whole_and_with_its_mtime(home):
    mtime = _put(home, "profile.md", "  likes small steps\n\n")
    got = pe.read("samantha", "profile.md")
    assert got == {"name": "profile.md", "content": "  likes small steps\n\n", "mtime": mtime, "local": False}


def test_a_file_not_written_yet_opens_empty_so_it_can_be_started(home):
    assert pe.read("samantha", "context.md") == {"name": "context.md", "content": "", "mtime": None, "local": False}


def test_the_soul_read_is_the_local_copy_when_there_is_one(home):
    _put(home, "soul.md", "shipped")
    assert pe.read("samantha", "soul.md")["content"] == "shipped"
    mtime = _put(home, "soul.local.md", "mine")
    assert pe.read("samantha", "soul.md") == {"name": "soul.md", "content": "mine", "mtime": mtime, "local": True}


def test_only_the_four_names_can_be_reached(home):
    _put(home, "persona.yaml", "secret: 1")
    for name in ("persona.yaml", "../persona.yaml", "sessions", "soul.local.md", "profile.md.bak", ""):
        assert pe.read("samantha", name) is None
        assert pe.write("samantha", name, "x", None) == pe.UNKNOWN
    assert (home / "persona.yaml").read_text() == "secret: 1"


def test_saving_a_memory_file_replaces_it_and_keeps_the_last_version(home):
    mtime = _put(home, "profile.md", "old")
    assert pe.write("samantha", "profile.md", "new text", mtime) == pe.OK
    assert (home / "profile.md").read_text() == "new text"
    assert (home / "profile.md.bak").read_text() == "old"


def test_saving_a_file_that_changed_on_disk_is_refused_and_leaves_it_alone(home):
    mtime = _put(home, "profile.md", "old")
    os.utime(home / "profile.md", (mtime + 50, mtime + 50))  # the engine, or the terminal, wrote it meanwhile
    assert pe.write("samantha", "profile.md", "mine", mtime) == pe.CONFLICT
    assert (home / "profile.md").read_text() == "old"
    assert not (home / "profile.md.bak").exists()


def test_saving_with_no_precondition_just_saves_and_a_missing_file_is_created(home):
    assert pe.write("samantha", "decisions.md", "- 2026-10-03 chose SQLite", None) == pe.OK
    assert (home / "decisions.md").read_text() == "- 2026-10-03 chose SQLite"
    assert not (home / "decisions.md.bak").exists()  # nothing to keep


def test_saving_the_soul_writes_a_local_copy_and_never_the_shipped_file(home):
    shipped = _put(home, "soul.md", "shipped voice")
    assert pe.write("samantha", "soul.md", "my voice", shipped) == pe.OK  # the version it opened is the shipped one
    assert (home / "soul.md").read_text() == "shipped voice"
    assert (home / "soul.local.md").read_text() == "my voice"
    local = (home / "soul.local.md").stat().st_mtime
    assert pe.write("samantha", "soul.md", "my voice, again", local) == pe.OK  # now it checks against its own copy
    assert (home / "soul.local.md.bak").read_text() == "my voice"
    assert pe.write("samantha", "soul.md", "stale", shipped) == pe.CONFLICT


def test_resetting_the_soul_puts_the_shipped_one_back_and_keeps_the_users_text(home):
    _put(home, "soul.md", "shipped")
    _put(home, "soul.local.md", "mine")
    assert pe.reset_soul("samantha") is True
    assert not (home / "soul.local.md").exists() and (home / "soul.md").read_text() == "shipped"
    assert (home / "soul.local.md.bak").read_text() == "mine"  # what they wrote is not thrown away
    assert pe.reset_soul("samantha") is False  # nothing to reset


def test_the_engine_reads_the_local_soul_first(home):
    _put(home, "soul.md", "shipped voice")
    assert persona_files.load_soul("samantha") == "shipped voice"
    _put(home, "soul.local.md", "my voice")
    assert persona_files.load_soul("samantha") == "my voice"
    _put(home, "soul.local.md", "   \n")  # an emptied local copy falls back to the shipped one
    assert persona_files.load_soul("samantha") == "shipped voice"


def test_a_waiting_rewrite_is_read_with_a_diff_against_the_current_file(home):
    _put(home, "context.md", "working on Atlas")
    _put(home, "context.md.pending", "working on Atlas and the budget")
    got = pe.pending("samantha", "context.md")
    assert got["text"] == "working on Atlas and the budget"
    assert "-working on Atlas" in got["diff"] and "+working on Atlas and the budget" in got["diff"]
    assert pe.pending("samantha", "profile.md") is None
    assert pe.pending("samantha", "soul.md") is None and pe.pending("samantha", "decisions.md") is None


def test_accepting_applies_that_file_only_and_keeps_the_old_version(home):
    _put(home, "profile.md", "old profile")
    _put(home, "profile.md.pending", "new profile")
    _put(home, "context.md.pending", "new context")
    assert pe.accept_pending("samantha", "profile.md") is True
    assert (home / "profile.md").read_text().strip() == "new profile"
    assert (home / "profile.md.bak").read_text() == "old profile"
    assert not (home / "profile.md.pending").exists()
    assert (home / "context.md.pending").exists()  # the other proposal waits


def test_discarding_removes_the_proposal_and_changes_nothing_else(home):
    _put(home, "profile.md", "keep me")
    _put(home, "profile.md.pending", "proposal")
    assert pe.discard_pending("samantha", "profile.md") is True
    assert not (home / "profile.md.pending").exists() and (home / "profile.md").read_text() == "keep me"
    assert pe.discard_pending("samantha", "profile.md") is False  # none left
