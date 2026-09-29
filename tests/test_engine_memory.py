"""Tests for sympose.engine.memory (docs/decisions/041): reading a persona's three
memory files, and what a turn is allowed to use from them."""

from helpers import write_persona

from sympose.engine import memory


def _persona(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


def test_a_persona_with_no_memory_files_reads_as_all_empty(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert memory.profile("samantha") is None
    assert memory.context("samantha") is None
    assert memory.decisions("samantha") == []


def test_profile_and_context_are_read_whole_and_stripped(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "profile.md").write_text("\n  Prefers concise replies.  \n")
    (directory / "context.md").write_text("Working on the Atlas migration.\n")
    assert memory.profile("samantha") == "Prefers concise replies."
    assert memory.context("samantha") == "Working on the Atlas migration."


def test_an_empty_memory_file_reads_as_none(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "profile.md").write_text("   \n")
    assert memory.profile("samantha") is None


def test_decisions_are_read_oldest_first_one_entry_per_line(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "decisions.md").write_text(
        "- 2026-09-01: Chose SQLite over Postgres.\n\n- 2026-09-15: Kept the four retrieval modes.\n"
    )
    assert memory.decisions("samantha") == [
        "- 2026-09-01: Chose SQLite over Postgres.",
        "- 2026-09-15: Kept the four retrieval modes.",
    ]


def test_a_freeform_line_in_decisions_is_kept_whole_not_dropped(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "decisions.md").write_text("just a note, not a dated bullet\n")
    assert memory.decisions("samantha") == ["just a note, not a dated bullet"]


def test_an_unsafe_handle_reads_as_nothing_rather_than_raising(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert memory.profile("../escape") is None
    assert memory.decisions("../escape") == []


# -- for_turn: what a turn may actually use -----------------------------------


def test_for_turn_when_allowed_returns_everything_on_disk(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "profile.md").write_text("Likes plain text.")
    (directory / "decisions.md").write_text("- 2026-09-01: Kept it simple.")

    mem = memory.for_turn("samantha", allowed=True)

    assert mem.profile == "Likes plain text."
    assert mem.context is None
    assert mem.decisions == ["- 2026-09-01: Kept it simple."]
    assert mem.withheld is False


def test_for_turn_when_not_allowed_returns_nothing_but_says_so(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "profile.md").write_text("Likes plain text.")

    mem = memory.for_turn("samantha", allowed=False)

    assert mem.profile is None and mem.context is None and mem.decisions == []
    assert mem.withheld is True  # something existed, so this is not silence


def test_for_turn_when_not_allowed_and_nothing_exists_is_not_withheld(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    mem = memory.for_turn("samantha", allowed=False)
    assert mem.withheld is False  # nothing to withhold, so nothing to say
