"""The Bin's conversations (docs/decisions/057): deleted ones listed, put back or deleted for good."""

import json
import os

import pytest
from helpers import write_persona

from sympose.engine import recap, session, session_bin, session_manage

A, B = "20261001T100000-aaaaaaaa", "20261001T110000-bbbbbbbb"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))


def make(sid, title="a title", recap_text=None):
    assert session.start_session("samantha", sid)
    session.append_turn("samantha", sid, f"{title} please", "ok")
    assert session_manage.rename("samantha", sid, title) == session_manage.OK
    if recap_text:
        os.makedirs(session.recaps_dir("samantha"), exist_ok=True)
        with open(recap.path("samantha", sid), "w", encoding="utf-8") as f:
            f.write(recap_text)


def test_a_deleted_conversation_is_listed_with_its_title_turns_and_deletion_time():
    make(A, "movies")
    os.utime(session.session_path("samantha", A), (1, 1))  # last written long ago
    assert session_manage.delete("samantha", A) == session_manage.OK
    [row] = session_bin.list_deleted("samantha")
    assert (row["id"], row["title"], row["turns"]) == (A, "movies", 1)
    assert row["deleted_at"] > 1_000_000_000  # when it was deleted, not when it was last written


def test_the_last_deleted_is_listed_first():
    make(A)
    make(B)
    session_manage.delete("samantha", A)
    session_manage.delete("samantha", B)
    os.utime(os.path.join(session.sessions_dir("samantha"), ".trash", f"{A}.jsonl"), (9_000_000_000, 9_000_000_000))
    assert [row["id"] for row in session_bin.list_deleted("samantha")] == [A, B]


def test_nothing_deleted_lists_nothing():
    assert session_bin.list_deleted("samantha") == []


def test_restoring_puts_the_conversation_and_its_recap_back_as_they_were():
    make(A, "movies", recap_text="<!-- turns: 1 -->\nTalked films.")
    session_manage.pin("samantha", A, True)
    session_manage.delete("samantha", A)
    assert A not in session.session_ids("samantha")
    assert session_bin.restore("samantha", A) == session_manage.OK
    row = next(r for r in session_manage.list_sessions("samantha") if r["id"] == A)
    assert row["title"] == "movies" and row["pinned_at"]
    assert os.path.exists(recap.path("samantha", A))
    assert session_bin.list_deleted("samantha") == []


def test_restoring_never_replaces_a_conversation_by_that_id():
    make(A, "movies")
    session_manage.delete("samantha", A)
    make(A, "a newer one by the same id")
    assert session_bin.restore("samantha", A) == session_manage.EXISTS
    assert session.load_session("samantha", A)["meta"]["title"] == "a newer one by the same id"
    assert [row["id"] for row in session_bin.list_deleted("samantha")] == [A]


def test_a_conversation_deleted_twice_comes_back_by_its_own_id():
    make(A, "first")
    session_manage.delete("samantha", A)
    make(A, "second")
    session_manage.delete("samantha", A)
    names = sorted(row["id"] for row in session_bin.list_deleted("samantha"))
    assert names == [A, f"{A}.2"]
    assert session_bin.restore("samantha", f"{A}.2") == session_manage.OK
    assert session.load_session("samantha", A)["meta"]["title"] == "second"


def test_a_name_that_is_not_in_the_bin_is_refused():
    assert session_bin.restore("samantha", "nothing") == session_manage.NOT_FOUND
    assert session_bin.purge("samantha", "nothing") == session_manage.NOT_FOUND


@pytest.mark.parametrize("name", ["../x", "a/b", "", ".hidden", "..", "../../profiles/samantha/persona"])
def test_a_name_that_leaves_the_bin_is_refused(name):
    assert session_bin.restore("samantha", name) == session_manage.BAD_ID
    assert session_bin.purge("samantha", name) == session_manage.BAD_ID


def test_purging_deletes_the_conversation_and_its_recap_for_good():
    make(A, recap_text="<!-- turns: 1 -->\nx")
    make(B)
    session_manage.delete("samantha", A)
    session_manage.delete("samantha", B)
    assert session_bin.purge("samantha", A) == session_manage.OK
    trash = os.path.join(session.sessions_dir("samantha"), ".trash")
    assert sorted(os.listdir(trash)) == [f"{B}.jsonl"]


def test_emptying_deletes_every_one_and_says_how_many():
    make(A)
    make(B)
    session_manage.delete("samantha", A)
    session_manage.delete("samantha", B)
    assert session_bin.empty("samantha") == 2
    assert session_bin.list_deleted("samantha") == []
    assert session_bin.empty("samantha") == 0


def test_a_damaged_file_in_the_bin_is_skipped_not_fatal():
    make(A)
    session_manage.delete("samantha", A)
    trash = os.path.join(session.sessions_dir("samantha"), ".trash")
    with open(os.path.join(trash, "junk.jsonl"), "w") as f:
        f.write(json.dumps({"type": "nothing"}) + "\n")
    assert [row["id"] for row in session_bin.list_deleted("samantha")] == [A]
