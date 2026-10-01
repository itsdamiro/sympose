"""`/compact` and the header notice in the terminal chat (docs/decisions/055)."""

import asyncio

import pytest
from helpers import write_persona

from sympose import engine, settings_store
from sympose.cli import commands, compact_command, trim_notice, turns
from sympose.cli.app import SymposeCLI
from sympose.engine import compaction, session, session_compaction


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


def _lines(app):
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
    return base


def run_async(coro):
    return asyncio.run(coro)


# -- the notice --------------------------------------------------------------


def test_the_notice_says_how_many_turns_the_notes_stand_for():
    assert trim_notice.segment(0, False, 14) == " · 14 earlier turns condensed"
    assert trim_notice.segment(0, False, 1) == " · 1 earlier turn condensed"
    assert trim_notice.segment(2, False, 14) == " · 14 earlier turns condensed · 2 older turns out of context"


def test_the_notice_is_silent_with_nothing_condensed_or_when_turned_off():
    assert trim_notice.segment(0, False, 0) == ""
    settings_store.set(trim_notice.SETTING, False)
    assert trim_notice.segment(0, False, 14) == ""


def _headers(monkeypatch, condensed_by_reply: list[int]) -> list[str]:
    """The header of each reply, when the engine says the notes stood for the given turns on each."""
    replies = iter(condensed_by_reply)

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        return engine.TurnResult(reply="ok", session_id="s", ttft_ms=1840, model="m", condensed=next(replies))

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    found: list[str] = []

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            for n, text in enumerate(["one", "two", "three"][: len(condensed_by_reply)], start=1):
                await pilot.press(*text, "enter")
                for _ in range(100):
                    await pilot.pause(0.1)
                    headers = [plain_text(c).split("\n")[0] for c in app.transcript.children if plain_text(c).startswith("@samantha")]
                    if len(headers) == n:
                        found.append(headers[-1])
                        break
                else:
                    raise AssertionError(f"no reply header {n}")

    run_async(scenario())
    return found


def test_the_notice_is_shown_on_the_reply_that_first_used_the_notes_and_when_they_grow(profiles, monkeypatch):
    first, second, third = _headers(monkeypatch, [0, 9, 9])
    assert "condensed" not in first
    assert "9 earlier turns condensed" in second
    assert "condensed" not in third  # the same notes again: not said on every reply


def test_the_notice_comes_back_when_a_later_compaction_covers_more(profiles, monkeypatch):
    _, second, third = _headers(monkeypatch, [0, 9, 12])
    assert "9 earlier turns condensed" in second and "12 earlier turns condensed" in third


# -- /compact ----------------------------------------------------------------


def test_compact_is_listed_among_the_commands():
    assert commands.find_command("/compact") is not None


def _compact(monkeypatch, outcome, with_session=True, notes_on_file: str | None = None):
    calls = []

    def fake(handle, session_id, model, wait=300.0):
        calls.append((handle, session_id, model))
        return outcome

    monkeypatch.setattr(compact_command.compaction, "compact_now", fake)
    cleared = []
    monkeypatch.setattr(compact_command.meter, "clear", lambda app: cleared.append(True))
    started = []
    monkeypatch.setattr(compact_command.meter_estimate, "start", lambda app, model_id: started.append(model_id))
    out = {}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            if with_session:
                app.session_by_generation[app.session_generation] = "sess-1"
                if notes_on_file:
                    session.append_turn("samantha", "sess-1", "hello", "hi")
                    session_compaction.append("samantha", "sess-1", 1, notes_on_file, "m")
            app.composer.focus()
            await pilot.press(*"/compact", "enter")
            for _ in range(100):
                await pilot.pause(0.1)
                if not with_session or calls:
                    break
            await pilot.pause(0.3)
            out["lines"] = _lines(app)

    run_async(scenario())
    return out["lines"], calls, cleared, started


def test_compact_before_any_message_says_there_is_nothing_to_condense(profiles, monkeypatch):
    lines, calls, _, _ = _compact(monkeypatch, compaction.Outcome(compaction.DONE), with_session=False)
    assert any("has not started yet" in line for line in lines) and calls == []


def test_compact_shows_the_notes_and_refreshes_the_meter(profiles, monkeypatch):
    done = compaction.Outcome(compaction.DONE, 11, "The user is building Pantry.", 600, 120)
    lines, calls, cleared, started = _compact(monkeypatch, done)
    assert calls and calls[0][:2] == ("samantha", "sess-1")
    assert any("Condensed the first 11 turns into notes (600 to 120 tokens)" in line for line in lines)
    assert any(line == "The user is building Pantry." for line in lines)
    assert cleared == [True] and len(started) == 1  # the meter is cleared and re-estimated


@pytest.mark.parametrize(
    "status,words",
    [
        (compaction.NOTHING, "Nothing to condense yet"),
        (compaction.TOO_SMALL, "Nothing to gain yet"),
        (compaction.FAILED, "could not be written"),
        (compaction.BUSY, "Already condensing"),
    ],
)
def test_compact_says_why_when_it_wrote_nothing(profiles, monkeypatch, status, words):
    lines, _, cleared, _ = _compact(monkeypatch, compaction.Outcome(status))
    assert any(words in line for line in lines) and cleared == []


def test_compact_with_nothing_more_to_fold_still_shows_the_notes_in_force(profiles, monkeypatch):
    lines, *_ = _compact(monkeypatch, compaction.Outcome(compaction.NOTHING), notes_on_file="The user likes SQLite.")
    assert any("The notes now: The user likes SQLite." in line for line in lines)
