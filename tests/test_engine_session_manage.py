"""Listing, renaming, pinning and deleting conversations (docs/decisions/057): the file stays append-only, a delete
moves it to the trash folder with its recap, and a reply being written is never deleted from under itself."""

import json
import os

import pytest
from helpers import write_persona

from sympose.engine import recap, session, session_manage, turn_cancel, turn_status


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    write_persona(base, "aria", "name: Aria\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def write(sid, stamp, handle="samantha", turns=2, title="hello there", **meta):
    """A conversation file with its turns stamped `stamp` (so the order does not depend on the clock)."""
    path = session.session_path(handle, sid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [{"type": "meta", "session_id": sid, "handle": handle, "title": title, "created_at": stamp, "updated_at": stamp, **meta}]
    lines += [
        {"type": "turn", "timestamp": stamp, "user": f"question {n}", "assistant": f"answer {n}"} for n in range(turns)
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(line) + "\n" for line in lines))
    return path


A, B, C = "20261001T100000-aaaaaaaa", "20261001T110000-bbbbbbbb", "20261001T120000-cccccccc"
T1, T2, T3 = "2026-10-01T10:00:00+00:00", "2026-10-01T11:00:00+00:00", "2026-10-01T12:00:00+00:00"


def ids(handle="samantha"):
    return [row["id"] for row in session_manage.list_sessions(handle)]


@pytest.fixture(autouse=True)
def _clean_replies():
    yield
    for handle in ("samantha", "aria"):
        for sid in (A, B, C, None):
            turn_cancel.finish(handle, sid)


# -- the list ---------------------------------------------------------------------------------------------------


def test_the_list_has_the_conversation_last_used_first_with_its_title_and_turns():
    write(A, T1, title="first talk", turns=3)
    write(B, T3, title="second talk", turns=1)

    rows = session_manage.list_sessions("samantha")

    assert [row["id"] for row in rows] == [B, A]
    assert rows[1]["title"] == "first talk" and rows[1]["turns"] == 3 and rows[1]["updated_at"] == T1
    assert rows[0]["pinned_at"] is None and rows[0]["replying"] is False


def test_an_older_conversation_that_was_continued_moves_up():
    write(A, T3, title="old but just used")
    write(B, T1)

    assert ids() == [A, B]


def test_pinned_conversations_come_first_in_the_order_they_were_pinned():
    write(A, T1, pinned_at=T3)
    write(B, T3)
    write(C, T2, pinned_at=T1)

    assert ids() == [C, A, B]


def test_a_blank_conversation_is_listed_only_when_it_is_the_newest():
    write(A, T1)
    write(B, T2, turns=0, title="")
    write(C, T3, turns=0, title="")

    assert ids() == [C, A]


def test_only_the_personas_own_conversations_are_listed():
    write(A, T1)
    write(B, T2, handle="aria")

    assert ids("samantha") == [A] and ids("aria") == [B]


def test_a_conversation_with_a_reply_in_flight_says_so():
    write(A, T1)
    turn_cancel.begin("samantha", A)

    assert session_manage.list_sessions("samantha")[0]["replying"] is True


# -- rename ----------------------------------------------------------------------------------------------------


def test_a_rename_is_a_later_line_and_nothing_written_is_touched():
    path = write(A, T1)
    before = open(path, "rb").read()

    assert session_manage.rename("samantha", A, "  Planning   the garden ") == "ok"

    after = open(path, "rb").read()
    assert after.startswith(before) and after.count(b"\n") == before.count(b"\n") + 1
    assert session.load_session("samantha", A)["meta"]["title"] == "Planning the garden"
    assert len(session.load_session("samantha", A)["turns"]) == 2


@pytest.mark.parametrize("title", ["", "   ", "x" * 81])
def test_a_title_that_is_empty_or_too_long_is_refused_and_changes_nothing(title):
    path = write(A, T1)
    before = open(path, "rb").read()

    assert session_manage.rename("samantha", A, title) == "bad_title"
    assert open(path, "rb").read() == before


def test_a_title_of_eighty_characters_is_taken():
    write(A, T1)

    assert session_manage.rename("samantha", A, "x" * 80) == "ok"


def test_renaming_a_conversation_that_is_not_there_is_not_found():
    assert session_manage.rename("samantha", A, "x") == "not_found"
    assert session_manage.rename("samantha", "../aria/x", "x") == "not_found"


def test_a_conversation_named_before_its_first_message_keeps_its_name():
    session.start_session("samantha", A)
    session_manage.rename("samantha", A, "My own name")

    session.append_turn("samantha", A, "a long first message about something else", "reply")

    assert session.load_session("samantha", A)["meta"]["title"] == "My own name"


def test_a_rename_keeps_the_pin():
    write(A, T1, pinned_at=T2)
    session_manage.rename("samantha", A, "new")

    assert session_manage.list_sessions("samantha")[0]["pinned_at"] == T2


# -- pin -------------------------------------------------------------------------------------------------------


def test_pinning_puts_a_conversation_first_and_unpinning_puts_it_back():
    write(A, T1)
    write(B, T3)
    assert ids() == [B, A]

    assert session_manage.pin("samantha", A, True) == "ok"
    assert ids() == [A, B]
    assert session_manage.pin("samantha", A, False) == "ok"
    assert ids() == [B, A] and session_manage.list_sessions("samantha")[1]["pinned_at"] is None


def test_pinning_one_already_pinned_keeps_its_place_and_writes_nothing():
    path = write(A, T1, pinned_at=T2)
    before = open(path, "rb").read()

    assert session_manage.pin("samantha", A, True) == "ok"
    assert open(path, "rb").read() == before


def test_unpinning_one_not_pinned_writes_nothing():
    path = write(A, T1)
    before = open(path, "rb").read()

    assert session_manage.pin("samantha", A, False) == "ok"
    assert open(path, "rb").read() == before


def test_pins_come_in_the_order_they_were_made():
    write(A, T1)
    write(B, T2)
    session_manage.pin("samantha", B, True)
    session_manage.pin("samantha", A, True)

    assert ids() == [B, A]


def test_pinning_a_conversation_that_is_not_there_is_not_found():
    assert session_manage.pin("samantha", A, True) == "not_found"


# -- delete ----------------------------------------------------------------------------------------------------


def test_a_delete_moves_the_conversation_and_its_recap_to_the_trash_and_nothing_is_destroyed(scratch):
    path = write(A, T1)
    original = open(path, "rb").read()
    recap.write("samantha", A, 2, "Talked about the garden.")

    assert session_manage.delete("samantha", A) == "ok"

    trash = scratch / "samantha" / "sessions" / ".trash"
    assert (trash / f"{A}.jsonl").read_bytes() == original
    assert (trash / f"{A}.recap.md").read_text(encoding="utf-8").strip().endswith("Talked about the garden.")
    assert session.load_session("samantha", A) is None and recap.load("samantha", A) is None
    assert ids() == [] and session.session_ids("samantha") == []


def test_a_delete_leaves_the_other_conversations_and_personas_alone():
    write(A, T1)
    write(B, T2)
    write(C, T3, handle="aria")

    session_manage.delete("samantha", A)

    assert ids() == [B] and ids("aria") == [C]


def test_a_conversation_with_a_reply_being_written_is_not_deleted():
    path = write(A, T1)
    turn_cancel.begin("samantha", A)

    assert session_manage.delete("samantha", A) == "busy"
    assert os.path.exists(path)


def test_a_reply_being_written_in_another_conversation_does_not_stop_a_delete():
    write(A, T1)
    write(B, T2)
    turn_cancel.begin("samantha", B)

    assert session_manage.delete("samantha", A) == "ok"


def test_a_phase_showing_for_the_conversation_also_keeps_it():
    write(A, T1)
    turn_status.bind("samantha", A)
    turn_status.set_phase("samantha", turn_status.ASKING)
    try:
        assert session_manage.delete("samantha", A) == "busy"
    finally:
        turn_status.set_phase("samantha", None)
        turn_status.unbind()


def test_deleting_one_that_is_not_there_or_not_a_conversation_of_the_persona_is_not_found():
    assert session_manage.delete("samantha", A) == "not_found"
    assert session_manage.delete("samantha", "../../aria/sessions/x") == "not_found"


def test_a_conversation_put_back_by_hand_and_deleted_again_does_not_replace_the_first_in_the_trash(scratch):
    path = write(A, T1, title="first version")
    session_manage.delete("samantha", A)
    trash = scratch / "samantha" / "sessions" / ".trash"
    write(A, T2, title="second version")

    session_manage.delete("samantha", A)

    assert sorted(p.name for p in trash.iterdir()) == [f"{A}.2.jsonl", f"{A}.jsonl"]
    assert "first version" in (trash / f"{A}.jsonl").read_text(encoding="utf-8")
    assert not os.path.exists(path)


def test_a_recap_is_not_needed_for_a_delete():
    write(A, T1)

    assert session_manage.delete("samantha", A) == "ok"
