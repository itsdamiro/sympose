"""The compaction record in a session file and what it does to the history (docs/decisions/055)."""

import json

import pytest
from helpers import write_persona

from sympose.engine import session, session_compaction


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(base)


def _session(turns: int, sid: str = "s1") -> str:
    for i in range(turns):
        session.append_turn("samantha", sid, f"question {i}", f"answer {i}")
    return sid


def _raw(sid: str, record: dict) -> None:
    with open(session.session_path("samantha", sid), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def test_a_compaction_is_appended_and_read_back(sessions_root):
    sid = _session(6)
    assert session_compaction.append("samantha", sid, 4, "The user is planning a trip.", "m")
    loaded = session.load_session("samantha", sid)
    assert loaded["compaction"]["through"] == 4
    assert session_compaction.notes(loaded) == "The user is planning a trip."
    assert len(loaded["turns"]) == 6  # every turn is still in the file


def test_the_file_is_only_added_to(sessions_root):
    sid = _session(3)
    path = session.session_path("samantha", sid)
    before = open(path, "rb").read()
    session_compaction.append("samantha", sid, 2, "notes", "m")
    assert open(path, "rb").read().startswith(before)


def test_a_session_that_was_never_used_gets_no_file(sessions_root):
    _session(1, "another")  # so the folder exists, and only the missing file is what refuses it
    assert session_compaction.append("samantha", "never-used", 1, "notes", "m") is False
    assert session.load_session("samantha", "never-used") is None


def test_the_last_record_in_the_file_is_the_one_in_force(sessions_root):
    sid = _session(8)
    session_compaction.append("samantha", sid, 3, "first notes", "m")
    session_compaction.append("samantha", sid, 6, "second notes", "m")
    loaded = session.load_session("samantha", sid)
    assert session_compaction.covered(loaded) == 6
    assert session_compaction.notes(loaded) == "second notes"


@pytest.mark.parametrize(
    "bad",
    [{"through": 0, "text": "x"}, {"through": True, "text": "x"}, {"through": "3", "text": "x"}, {"through": 3, "text": "  "}, {"through": 3}],
)
def test_a_damaged_record_is_skipped_and_the_earlier_one_stays(sessions_root, bad):
    sid = _session(6)
    session_compaction.append("samantha", sid, 3, "good notes", "m")
    _raw(sid, {"type": "compaction", **bad})
    loaded = session.load_session("samantha", sid)
    assert session_compaction.notes(loaded) == "good notes" and session_compaction.covered(loaded) == 3


def test_the_notes_never_stand_for_more_turns_than_there_are(sessions_root):
    sid = _session(2)
    _raw(sid, {"type": "compaction", "through": 50, "text": "notes"})
    loaded = session.load_session("samantha", sid)
    assert session_compaction.covered(loaded) == 2


def test_the_history_leaves_out_the_turns_the_notes_stand_for(sessions_root):
    sid = _session(6)
    session_compaction.append("samantha", sid, 4, "notes", "m")
    history = session.history_as_messages(session.load_session("samantha", sid))
    assert [m["content"] for m in history] == ["question 4", "answer 4", "question 5", "answer 5"]


def test_the_turn_cap_still_applies_to_the_turns_that_are_left(sessions_root):
    sid = _session(30)
    session_compaction.append("samantha", sid, 5, "notes", "m")
    history = session.history_as_messages(session.load_session("samantha", sid))
    assert len(history) == 2 * session.HISTORY_TURNS
    assert history[0]["content"] == "question 10"


def test_a_session_without_a_compaction_is_sent_as_before(sessions_root):
    sid = _session(3)
    loaded = session.load_session("samantha", sid)
    assert loaded["compaction"] is None and session_compaction.notes(loaded) is None
    assert len(session.history_as_messages(loaded)) == 6
