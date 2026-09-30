"""Tests for sympose.engine.memory (docs/decisions/041): reading a persona's three
memory files, what a turn is allowed to use from them, and the one write path that
exists so far -- appending a dated line to decisions.md."""

import datetime

from helpers import write_persona

from sympose import settings_store
from sympose.engine import memory

_TODAY = datetime.date.today().isoformat()


def _persona(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


def _settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


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


# -- remember_enabled / remember_mode: a user setting, never inferred from capability ----------


def test_remember_is_off_by_default(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    assert memory.remember_enabled() is False
    assert memory.remember_mode(can_call_tools=True) is None
    assert memory.remember_mode(can_call_tools=False) is None


def test_remember_on_picks_the_mechanism_by_tool_calling_capability(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    settings_store.set(memory.REMEMBER_SETTING, True)
    assert memory.remember_enabled() is True
    assert memory.remember_mode(can_call_tools=True) == memory.TOOL
    assert memory.remember_mode(can_call_tools=False) == memory.MARKER


# -- append_decision: the one write path that exists so far ------------------------------------


def test_append_decision_adds_a_dated_line(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "decisions.md").write_text("- 2026-09-01: Chose SQLite over Postgres.\n")

    ok = memory.append_decision("samantha", "Kept the four retrieval modes")

    assert ok is True
    assert memory.decisions("samantha") == [
        "- 2026-09-01: Chose SQLite over Postgres.",
        f"- {_TODAY}: Kept the four retrieval modes",
    ]


def test_append_decision_creates_the_file_when_there_is_none_yet(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert memory.append_decision("samantha", "Start simple") is True
    assert memory.decisions("samantha") == [f"- {_TODAY}: Start simple"]


def test_append_decision_backs_up_the_previous_content_first(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    (directory / "decisions.md").write_text("- 2026-09-01: Chose SQLite over Postgres.\n")

    memory.append_decision("samantha", "Kept it simple")

    assert (directory / "decisions.md.bak").read_text() == "- 2026-09-01: Chose SQLite over Postgres.\n"


def test_append_decision_collapses_a_multiline_text_to_one_line(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    memory.append_decision("samantha", "  Line one.\n  Line two.  ")
    assert memory.decisions("samantha") == [
        f"- {_TODAY}: Line one. Line two."
    ]


def test_append_decision_refuses_a_blank_text(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert memory.append_decision("samantha", "   ") is False
    assert memory.decisions("samantha") == []


def test_append_decision_on_an_unsafe_handle_fails_rather_than_raising(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert memory.append_decision("../escape", "something") is False


def test_append_decision_serializes_on_its_own_write_lock(tmp_path, monkeypatch):
    # Proves `append_decision` actually acquires `_WRITE_LOCK` around its read-modify-write,
    # the fix for a lost-update race (two concurrent callers both reading the old content before
    # either writes back, so the second write silently drops the first's line): holding the lock
    # externally must block a concurrent call until it is released, not let it run anyway.
    import threading

    _persona(tmp_path, monkeypatch)
    done = threading.Event()

    with memory._WRITE_LOCK:
        thread = threading.Thread(target=lambda: (memory.append_decision("samantha", "x"), done.set()))
        thread.start()
        blocked_while_held = not done.wait(timeout=0.2)

    thread.join(timeout=2)

    assert blocked_while_held is True
    assert done.is_set()  # completed once the lock was released
    assert memory.decisions("samantha") == [f"- {_TODAY}: x"]


def test_a_memory_file_in_another_encoding_reads_as_nothing_and_is_never_overwritten(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    latin1 = "Préfère les réponses courtes.".encode("latin-1")
    (directory / "decisions.md").write_bytes(latin1)
    (directory / "profile.md").write_bytes(latin1)

    assert memory.profile("samantha") is None
    assert memory.decisions("samantha") == []
    assert memory.append_decision("samantha", "Kept the four retrieval modes") is False
    assert (directory / "decisions.md").read_bytes() == latin1
