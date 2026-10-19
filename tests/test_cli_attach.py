"""`/attach` in the terminal chat (docs/decisions/089, `media`): a file named by its path goes with the next message,
marked in its words, and is not copied anywhere."""

import asyncio
from pathlib import Path

import pytest
from helpers import write_persona

from sympose import engine, settings_store
from sympose.cli import turns
from sympose.cli.app import SymposeCLI
from sympose.engine import media, turn_cancel


def run_async(coro):
    return asyncio.run(coro)


async def wait_until(check, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out waiting for the condition"
        await asyncio.sleep(0.02)


def lines(app) -> list[str]:
    return [child.content.plain if hasattr(child.content, "plain") else str(child.content) for child in app.transcript.children]


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


@pytest.fixture
def turns_seen(monkeypatch):
    seen = []

    def run_turn(handle, user_message, session_id=None, model=None, **kwargs):
        seen.append((user_message, kwargs.get("files", ())))
        return engine.TurnResult(reply="Read it.", session_id="s1", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", run_turn)
    return seen


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "My Paper.pdf"
    path.write_bytes(b"%PDF-1.4 hello")
    return path


async def type_line(pilot, app, text):
    app.composer.focus()
    await pilot.press(*text, "enter")
    await pilot.pause()


def test_a_file_named_by_its_path_goes_with_the_next_message_which_carries_its_marker(turns_seen, pdf):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, f"/attach {pdf}")
            assert any("Attached My Paper.pdf" in line for line in lines(app))
            await type_line(pilot, app, "what is in it?")
            await wait_until(lambda: turns_seen)
            message, files = turns_seen[0]
            assert message == "what is in it? [attached: My Paper.pdf]"
            assert [(f.name, f.mime, f.data) for f in files] == [("My Paper.pdf", "application/pdf", b"%PDF-1.4 hello")]
            assert app.pending_files == []

    run_async(scenario())


def test_a_path_with_escaped_spaces_or_quotes_as_a_file_manager_drag_pastes_it_is_read(turns_seen, pdf):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, "/attach " + str(pdf).replace(" ", "\\ "))
            await type_line(pilot, app, f"/attach '{pdf}'")
            assert [f.name for f in app.pending_files] == ["My Paper.pdf", "My Paper (2).pdf"]

    run_async(scenario())


@pytest.mark.parametrize(
    ("make", "said"),
    [
        (lambda tmp: tmp / "missing.pdf", "No file at"),
        (lambda tmp: (tmp / "notes.txt").write_text("x") and tmp / "notes.txt", "PDFs, images, sounds and videos"),
    ],
)
def test_a_file_that_is_not_there_or_not_read_is_said_and_nothing_waits(turns_seen, tmp_path, make, said):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, f"/attach {make(tmp_path)}")
            assert any(said in line for line in lines(app)) and app.pending_files == []

    run_async(scenario())


def test_a_file_over_the_size_limit_is_refused_before_it_is_read(turns_seen, pdf, monkeypatch):
    monkeypatch.setattr(media, "MAX_BYTES", 5)
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("read a file that is over the limit"))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, f"/attach {pdf}")
            assert any("too large" in line for line in lines(app)) and app.pending_files == []

    run_async(scenario())


def test_with_no_path_it_says_how_to_use_it_or_what_waits(turns_seen, pdf):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, "/attach")
            assert any(line.startswith("Usage: /attach") for line in lines(app))
            await type_line(pilot, app, f"/attach {pdf}")
            await type_line(pilot, app, "/attach")
            assert any(line == "Waiting for your next message: My Paper.pdf" for line in lines(app))

    run_async(scenario())


def test_a_message_with_no_file_attached_is_sent_as_it_always_was(turns_seen):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, "hello")
            await wait_until(lambda: turns_seen)
            assert turns_seen[0] == ("hello", ())

    run_async(scenario())


def test_a_stopped_reply_gives_back_its_words_and_its_file_without_marking_it_twice(monkeypatch, pdf):
    seen = []

    def run_turn(handle, user_message, session_id=None, model=None, **kwargs):
        seen.append((user_message, kwargs.get("files", ())))
        if len(seen) == 1:
            raise turn_cancel.TurnCancelled()
        return engine.TurnResult(reply="Read it.", session_id="s1", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await type_line(pilot, app, f"/attach {pdf}")
            await type_line(pilot, app, "read it")
            await wait_until(lambda: app.composer.value)
            assert app.composer.value == "read it [attached: My Paper.pdf]" and [f.name for f in app.pending_files] == ["My Paper.pdf"]
            await pilot.press("enter")
            await wait_until(lambda: len(seen) == 2)
            assert seen[1][0] == "read it [attached: My Paper.pdf]" and [f.name for f in seen[1][1]] == ["My Paper.pdf"]

    run_async(scenario())


def test_a_windows_path_keeps_its_backslashes_and_loses_only_its_quotes():
    from sympose.cli import attach_command

    assert attach_command.path_words('"C:\\Users\\me\\My Paper.pdf"', windows=True) == ["C:\\Users\\me\\My Paper.pdf"]
    assert attach_command.path_words("C:\\Users\\me\\paper.pdf", windows=True) == ["C:\\Users\\me\\paper.pdf"]
    assert attach_command.path_words("/a/My\\ Paper.pdf", windows=False) == ["/a/My Paper.pdf"]
    assert attach_command.path_words("/a/it's.pdf", windows=False) == ["/a/it's.pdf"]  # an unbalanced quote is kept as typed
