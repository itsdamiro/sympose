"""Stopping a reply from the terminal chat (docs/decisions/054): the Stop line under the input, a reply still
being written (thrown away, the message given back), a reply being revealed (shown whole at once) and the
messages that waited (still sent)."""

import asyncio
import threading
import time

import pytest
from helpers import write_persona

from sympose import engine, settings_store
from sympose.cli import commands, runtime, stop, turns
from sympose.cli.app import SymposeCLI
from sympose.engine import turn_cancel


def run_async(coro):
    return asyncio.run(coro)


async def wait_until(check, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out waiting for the condition"
        await asyncio.sleep(0.02)


def plain(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


def lines(app) -> list[str]:
    return [plain(child) for child in app.transcript.children]


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    write_persona(base, "samantha", "name: Samantha\nhandle: samantha\ntitle: Vault Companion\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    for name in ("refresh_recaps", "refresh_embeddings", "refresh_memory", "refresh_status_phrases"):
        monkeypatch.setattr(engine, name, lambda *a, **k: None)
    settings_store.set("status_typing", 0)


def engine_that(monkeypatch, behave):
    """`engine.run_turn` as a function that runs `behave(handle, message)` inside a turn the stop can reach,
    the way the real one does (`turn_cancel.begin`/`finish`), returning its reply."""

    def run_turn(handle, user_message, session_id=None, model=None):
        turn_cancel.begin(handle)
        try:
            reply = behave(handle, user_message)
            return engine.TurnResult(reply=reply, session_id="s1", grounding=[])
        finally:
            turn_cancel.finish(handle)

    monkeypatch.setattr(turns.engine, "run_turn", run_turn)


def writing_until_stopped(started: threading.Event):
    """A reply that never finishes by itself: it keeps checking, as the real model call does between chunks."""

    def behave(handle, message):
        started.set()
        for _ in range(500):
            time.sleep(0.01)
            turn_cancel.check()
        return "too late"

    return behave


def shown(app) -> bool:
    return app.query_one(stop.StopButton).has_class("active")


def test_the_stop_line_is_hidden_until_a_reply_is_being_written_and_hidden_again_after(monkeypatch):
    release = threading.Event()
    engine_that(monkeypatch, lambda h, m: (release.wait(5), "Hello there.")[1])

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not shown(app)
            task = asyncio.create_task(turns.send_message(app, "hi"))
            await wait_until(lambda: shown(app))
            release.set()
            await task
            await wait_until(lambda: not shown(app))  # the reveal is over too

    run_async(scenario())


def test_stopping_a_reply_being_written_throws_it_away_and_gives_the_message_back(monkeypatch):
    started = threading.Event()
    engine_that(monkeypatch, writing_until_stopped(started))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task = asyncio.create_task(turns.send_message(app, "write me a long essay"))
            await wait_until(started.is_set)
            await pilot.click(stop.StopButton)
            await wait_until(lambda: task.done())
            assert "Stopped. @samantha did not reply." in lines(app)
            assert not any("too late" in line for line in lines(app))
            assert app.composer.value == "write me a long essay"
            assert not shown(app) and app.stopping is False and app.generating == set()

    run_async(scenario())


def test_the_line_says_it_is_stopping_while_the_engine_ends_its_call(monkeypatch):
    started, release = threading.Event(), threading.Event()

    def behave(handle, message):
        started.set()
        while not release.is_set():  # a model that has not produced its next chunk yet
            time.sleep(0.01)
        turn_cancel.check()
        return "too late"

    engine_that(monkeypatch, behave)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task = asyncio.create_task(turns.send_message(app, "hi"))
            await wait_until(started.is_set)
            await pilot.click(stop.StopButton)
            assert plain(app.query_one(stop.StopButton)) == stop.STOPPING
            release.set()
            await task
            assert plain(app.query_one(stop.StopButton)) == stop.LABEL

    run_async(scenario())


def test_what_has_been_typed_since_is_not_overwritten_by_the_returned_message(monkeypatch):
    started = threading.Event()
    engine_that(monkeypatch, writing_until_stopped(started))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task = asyncio.create_task(turns.send_message(app, "first"))
            await wait_until(started.is_set)
            app.composer.value = "something new"
            await pilot.click(stop.StopButton)
            await task
            assert app.composer.value == "something new"
            assert "Stopped. @samantha did not reply." in lines(app)

    run_async(scenario())


def test_messages_that_waited_still_go_out_after_a_stop(monkeypatch):
    started = threading.Event()
    calls = []

    def behave(handle, message):
        calls.append(message)
        if message == "first":
            return writing_until_stopped(started)(handle, message)
        return "About the second."

    engine_that(monkeypatch, behave)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            first = asyncio.create_task(turns.send_message(app, "first"))
            await wait_until(started.is_set)
            second = asyncio.create_task(turns.send_message(app, "second"))  # joins the run, waits
            await asyncio.sleep(0.05)
            await pilot.click(stop.StopButton)
            await asyncio.gather(first, second)
            assert calls == ["first", "second"]
            await wait_until(lambda: any("About the second." in line for line in lines(app)))
            assert any("second" in line for line in lines(app))  # the message itself stays in the transcript

    run_async(scenario())


def test_a_reply_that_is_already_complete_is_not_thrown_away_by_a_stop(monkeypatch):
    committed, release = threading.Event(), threading.Event()

    def behave(handle, message):
        turn_cancel.commit()  # the reply is written: a stop is no longer accepted
        committed.set()
        release.wait(5)
        return "Here it is."

    engine_that(monkeypatch, behave)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task = asyncio.create_task(turns.send_message(app, "hi"))
            await wait_until(committed.is_set)
            await pilot.click(stop.StopButton)
            assert app.stopping is False and plain(app.query_one(stop.StopButton)) == stop.LABEL
            release.set()
            await task
            await wait_until(lambda: any("Here it is." in line for line in lines(app)))
            assert "Stopped. @samantha did not reply." not in lines(app)

    run_async(scenario())


def test_stopping_while_the_words_are_appearing_shows_the_whole_reply_at_once(monkeypatch):
    settings_store.set("reply_reveal", 1)  # one word a second: the reveal outlasts the test unless stopped
    words = " ".join(f"word{n}" for n in range(60))
    engine_that(monkeypatch, lambda h, m: words)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await turns.send_message(app, "hi")
            await wait_until(lambda: bool(app.active_reply_timers))
            assert shown(app) and not any("word59" in line for line in lines(app))
            await pilot.pause()  # the line was just shown: let the layout catch up before clicking it
            await pilot.click(stop.StopButton)
            await wait_until(lambda: any("word59" in line for line in lines(app)))
            assert not app.active_reply_timers and not app.reply_skips and not shown(app)

    run_async(scenario())


def test_a_refresh_while_a_stop_is_waiting_does_not_put_the_plain_label_back(monkeypatch):
    started, release = threading.Event(), threading.Event()

    def behave(handle, message):
        started.set()
        while not release.is_set():  # a model that has produced nothing yet: the stop is only noticed after
            time.sleep(0.01)
        turn_cancel.check()
        return "too late"

    engine_that(monkeypatch, behave)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task = asyncio.create_task(turns.send_message(app, "hi"))
            await wait_until(started.is_set)
            await pilot.click(stop.StopButton)
            stop.refresh_for(app)  # e.g. another reply finishing its reveal
            assert plain(app.query_one(stop.StopButton)) == stop.STOPPING
            release.set()
            await task

    run_async(scenario())


def test_the_message_is_not_given_back_in_another_conversation(monkeypatch):
    started = threading.Event()
    engine_that(monkeypatch, writing_until_stopped(started))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task = asyncio.create_task(turns.send_message(app, "meant for the first persona"))
            await wait_until(started.is_set)
            app.session_generation += 1  # a persona switch: the composer now belongs to another conversation
            await pilot.click(stop.StopButton)
            await task
            assert app.composer.value == ""

    run_async(scenario())


def test_clearing_the_transcript_while_a_reply_is_being_revealed_takes_the_stop_line_away(monkeypatch):
    settings_store.set("reply_reveal", 1)
    engine_that(monkeypatch, lambda h, m: " ".join(f"word{n}" for n in range(60)))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await turns.send_message(app, "hi")
            await wait_until(lambda: bool(app.active_reply_timers))
            await runtime.run_command(app, commands.find_command("/clear"))
            await pilot.pause()
            assert not app.reply_skips and not app.active_reply_timers and not shown(app)

    run_async(scenario())
