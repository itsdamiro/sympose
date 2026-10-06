"""`/sessions` and `/history` in the terminal chat (docs/decisions/057): the numbered list and open, rename, pin,
unpin and delete on a conversation by its number."""

import asyncio
import json
import os

import pytest
from helpers import write_persona

from sympose import engine
from sympose.cli import commands, sessions_command, turns
from sympose.cli.app import SymposeCLI
from sympose.engine import session, turn_cancel

A, B = "20261001T100000-aaaaaaaa", "20261001T110000-bbbbbbbb"
T1, T2 = "2026-10-01T10:00:00+00:00", "2026-10-01T11:00:00+00:00"


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


def lines_of(app):
    return [plain_text(c) for c in app.transcript.children]


@pytest.fixture(autouse=True)
def no_background_builds(monkeypatch):
    monkeypatch.setattr(engine, "refresh_recaps", lambda handle, model=None: None)
    monkeypatch.setattr(engine, "refresh_embeddings", lambda handle: None)
    monkeypatch.setattr(engine, "refresh_status_phrases", lambda handle, model=None: None)


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    write_persona(base, "samantha", "name: Samantha\nhandle: samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    yield base
    for sid in (A, B):
        turn_cancel.finish("samantha", sid)


def write(sid, stamp, title, turns=2, **meta):
    path = session.session_path("samantha", sid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [{"type": "meta", "session_id": sid, "handle": "samantha", "title": title, "created_at": stamp, "updated_at": stamp, **meta}]
    lines += [{"type": "turn", "timestamp": stamp, "user": f"{title} question {n}", "assistant": f"{title} answer {n}"} for n in range(turns)]
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(line) + "\n" for line in lines))


def drive(*arguments, before=None):
    """Run `/sessions <arguments>` one after another in a real app; `(the transcript lines after each, the app's
    state at the end)`."""
    out = {"lines": []}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            if before:
                before(app)
            opening = lines_of(app)  # what the app says at launch is not what is being tested
            for args in arguments:
                await sessions_command.run(app, args)
                await pilot.pause(0.1)
                now = lines_of(app)
                out["lines"].append(now[len(opening):] if now[: len(opening)] == opening else now)
            out["session_id"], out["generation"] = app.session_id, app.session_generation

    asyncio.run(scenario())
    return out


def test_both_names_are_commands_that_take_what_is_typed_after_them():
    for name in ("/sessions", "/history"):
        command = commands.find_command(name)
        assert command is not None and command.takes_args


def test_the_list_is_numbered_with_title_turns_and_pins(profiles):
    write(A, T1, "Garden plans", turns=3, pinned_at=T2)
    write(B, T2, "Trip", turns=1)

    lines = drive("")["lines"][0]

    assert lines[0].startswith("@samantha's conversations")
    assert lines[1].startswith("  1. Garden plans · 3 messages") and lines[1].endswith("pinned")
    assert lines[2].startswith("  2. Trip · 1 message ·") and "pinned" not in lines[2]


def test_no_conversations_says_so(profiles):
    assert drive("")["lines"][0] == ["No earlier conversations yet."]


def test_the_conversation_on_screen_is_marked(profiles):
    write(A, T1, "Garden plans")

    lines = drive("", before=lambda app: app.session_by_generation.__setitem__(app.session_generation, A))["lines"][0]

    assert lines[1].endswith("this one")


def test_typing_history_gives_the_same_list(profiles):
    write(A, T1, "Garden plans")
    out = {}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/history", "enter")
            await pilot.pause(0.3)
            out["lines"] = lines_of(app)

    asyncio.run(scenario())
    assert any(line.startswith("  1. Garden plans") for line in out["lines"])


def test_open_shows_where_the_conversation_stopped_and_continues_it(profiles):
    write(A, T1, "Garden plans", turns=6)
    write(B, T2, "Trip")

    out = drive("open 2")  # A is the older one, so number 2

    lines = out["lines"][0]
    assert out["session_id"] == A and out["generation"] == 1
    assert lines[0] == "(2 earlier messages not shown)"
    assert any("Garden plans answer 5" in line for line in lines) and not any("answer 1" in line for line in lines)
    assert lines[-1] == 'Continuing "Garden plans" (6 turns).'


def test_a_message_after_open_continues_the_conversation_that_was_opened(profiles, monkeypatch):
    write(A, T1, "Garden plans")
    sent = []

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        sent.append(session_id)
        return engine.TurnResult(reply="ok", session_id=session_id, ttft_ms=10, model="m")

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await sessions_command.run(app, "open 1")
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            for _ in range(50):
                await pilot.pause(0.1)
                if sent:
                    break

    asyncio.run(scenario())
    assert sent == [A]


def test_open_with_a_number_that_is_not_there_says_so_and_changes_nothing(profiles):
    write(A, T1, "Garden plans")

    out = drive("open 5", "open x", "open")

    assert all("There is no conversation number" in lines[-1] for lines in out["lines"])
    assert out["session_id"] is None and out["generation"] == 0


def test_rename_pin_and_unpin_act_on_the_numbered_conversation(profiles):
    write(A, T1, "Garden plans")
    write(B, T2, "Trip")

    out = drive("rename 2 Allotment", "pin 2", "")
    lines_after_pin = out["lines"][2]

    assert out["lines"][0][-1] == "Renamed." and out["lines"][1][-1] == "Pinned."
    assert lines_after_pin[-2].startswith("  1. Allotment") and lines_after_pin[-2].endswith("pinned")
    assert session.load_session("samantha", A)["meta"]["title"] == "Allotment"
    assert drive("unpin 1", "")["lines"][1][-2].startswith("  1. Trip")


def test_a_title_that_is_missing_or_too_long_is_refused(profiles):
    write(A, T1, "Garden plans")

    out = drive("rename 1", "rename 1 " + "x" * 90)

    assert all("1 to 80 characters" in lines[-1] for lines in out["lines"])
    assert session.load_session("samantha", A)["meta"]["title"] == "Garden plans"


def test_delete_moves_the_conversation_to_the_trash_folder(profiles):
    write(A, T1, "Garden plans")

    out = drive("delete 1", "")

    assert out["lines"][0][-1] == "Moved to the Bin (/sessions bin)."
    assert out["lines"][1][-1] == "No earlier conversations yet."
    assert (profiles / "samantha" / "sessions" / ".trash" / f"{A}.jsonl").exists()


def test_deleting_the_conversation_on_screen_starts_the_next_message_in_a_new_one(profiles):
    write(A, T1, "Garden plans")

    out = drive("delete 1", before=lambda app: app.session_by_generation.__setitem__(app.session_generation, A))

    assert out["session_id"] is None and out["generation"] == 1


def test_a_conversation_with_a_reply_being_written_is_not_deleted(profiles):
    write(A, T1, "Garden plans")
    turn_cancel.begin("samantha", A)

    out = drive("delete 1")

    assert "A reply is being written" in out["lines"][0][-1]
    assert session.load_session("samantha", A) is not None


def test_an_unknown_word_shows_the_usage(profiles):
    assert drive("tidy")["lines"][0][-1].startswith("Usage: /sessions")


# -- the Bin (ADR 057): /sessions bin, restore <n>, purge <n> ------------------


def test_the_bin_lists_what_was_deleted_by_number(profiles):
    write(A, T1, "Garden plans")
    write(B, T2, "Trip", turns=1)

    seen = drive("delete 1", "delete 1", "bin")["lines"]
    out = seen[2][len(seen[1]):]  # what each command shows is added to what the earlier ones did

    assert out[0].startswith("Deleted conversations")
    assert sorted(line[5:].split(" · ")[0] for line in out[1:]) == ["Garden plans", "Trip"]
    assert all("message" in line and "deleted 20" in line for line in out[1:])


def test_an_empty_bin_says_so(profiles):
    assert drive("bin")["lines"][0] == ["The Bin has no deleted conversations."]


def test_restore_brings_a_deleted_conversation_back_into_the_list(profiles):
    write(A, T1, "Garden plans")

    lines = drive("delete 1", "restore 1", "")["lines"]

    assert lines[1][-1].startswith("Restored")
    assert lines[2][len(lines[1]) + 1].startswith("  1. Garden plans")


def test_purge_deletes_one_for_good(profiles):
    write(A, T1, "Garden plans")

    lines = drive("delete 1", "purge 1", "bin")["lines"]

    assert lines[1][-1] == "Deleted for good."
    assert lines[2][len(lines[1]):] == ["The Bin has no deleted conversations."]
    assert not os.path.exists(os.path.join(session.sessions_dir("samantha"), ".trash", f"{A}.jsonl"))


def test_restore_of_a_number_the_bin_does_not_have_says_so(profiles):
    assert "no conversation number 3" in drive("restore 3")["lines"][0][-1]
