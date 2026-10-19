"""Blank conversations are cleaned up at launch (docs/decisions/057, amendment of 2026-10-20): a file with only its meta
line, a day old, that is not the newest and has no reply being written. Nothing with a turn in it is ever touched."""

import os
import time

import pytest
from helpers import write_persona

from sympose.engine import recap_refresh, session, session_prune, turn_cancel

NEWEST, MIDDLE, OLD = "20261003T100000-cccccccc", "20261002T100000-bbbbbbbb", "20261001T100000-aaaaaaaa"
NOW = time.time()
TWO_DAYS_AGO = NOW - 2 * 24 * 3600


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def blank(session_id, mtime=TWO_DAYS_AGO):
    assert session.start_session("samantha", session_id)
    os.utime(session.session_path("samantha", session_id), (mtime, mtime))


def exists(session_id):
    return os.path.exists(session.session_path("samantha", session_id))


def test_a_blank_conversation_a_day_old_is_deleted_and_the_newest_is_kept():
    for sid in (NEWEST, MIDDLE, OLD):
        blank(sid)

    assert session_prune.prune_empty("samantha", NOW) == 2

    assert exists(NEWEST) and not exists(MIDDLE) and not exists(OLD)


def test_a_blank_conversation_touched_within_a_day_is_kept():
    blank(NEWEST)
    blank(MIDDLE, mtime=NOW - 3600)

    assert session_prune.prune_empty("samantha", NOW) == 0
    assert exists(MIDDLE)


def test_a_conversation_with_a_turn_is_kept_however_old():
    blank(NEWEST)
    session.append_turn("samantha", MIDDLE, "hello", "hi")
    os.utime(session.session_path("samantha", MIDDLE), (TWO_DAYS_AGO, TWO_DAYS_AGO))

    assert session_prune.prune_empty("samantha", NOW) == 0
    assert exists(MIDDLE)


def test_a_file_with_a_damaged_line_is_kept():
    blank(NEWEST)
    blank(MIDDLE)
    path = session.session_path("samantha", MIDDLE)
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"type": "turn", "user": "half a lin')
    os.utime(path, (TWO_DAYS_AGO, TWO_DAYS_AGO))

    assert session_prune.prune_empty("samantha", NOW) == 0
    assert exists(MIDDLE)


def test_a_conversation_with_a_reply_being_written_is_kept():
    blank(NEWEST)
    blank(MIDDLE)
    turn_cancel.begin("samantha", MIDDLE)
    try:
        assert session_prune.prune_empty("samantha", NOW) == 0
        assert exists(MIDDLE)
    finally:
        turn_cancel.finish("samantha", MIDDLE)


def test_a_persona_with_no_sessions_has_nothing_to_delete():
    assert session_prune.prune_empty("samantha", NOW) == 0


def test_the_launch_refresh_prunes_even_with_recaps_turned_off(monkeypatch):
    blank(NEWEST)
    blank(MIDDLE)
    monkeypatch.setattr(recap_refresh.recap, "enabled", lambda: False)

    recap_refresh.refresh("samantha")

    assert not exists(MIDDLE) and exists(NEWEST)


def test_a_blank_line_in_a_meta_only_file_does_not_keep_it():
    blank(NEWEST)
    blank(MIDDLE)
    path = session.session_path("samantha", MIDDLE)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n\n")
    os.utime(path, (TWO_DAYS_AGO, TWO_DAYS_AGO))

    assert session_prune.prune_empty("samantha", NOW) == 1
    assert not exists(MIDDLE)
