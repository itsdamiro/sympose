"""`/model` saves the pick into the persona's own persona.yaml (docs/decisions/044), so it is kept across
restarts and the web app sees it; each persona has its own model, so a persona switch drops the session's
pick and the new persona's saved model applies. Switching to a cloud model in a conversation already going
says that earlier replies travel as history."""

import asyncio

import pytest
import yaml
from helpers import write_persona

from sympose import engine, persona_model, profile
from sympose.cli import options, runtime
from sympose.cli.app import SymposeCLI

CLOUD = "anthropic/claude-sonnet-5"
LOCAL = options.MODEL_OPTIONS[0].id


def run_async(coro):
    return asyncio.run(coro)


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


def lines(app):
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
    write_persona(base, "samantha", "name: Samantha\nhandle: samantha\n# hand-written\n")
    write_persona(base, "aria", "name: Aria\nhandle: aria\nmodel: gemini/gemini-flash-latest\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def saved_model(profiles, handle):
    """What the persona now resolves to: the local override (docs/decisions/046) over the shipped file."""
    return profile.get_profile(handle)["model"]


def test_a_model_pick_is_saved_into_the_active_personas_file_and_said(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "model", CLOUD)
            assert app.model_override.id == CLOUD
            assert any("Switched model to Claude Sonnet 5 — cloud. Saved for @samantha." in t for t in lines(app))

    run_async(scenario())
    assert saved_model(profiles, "samantha") == CLOUD
    shipped = (profiles / "samantha" / "persona.yaml").read_text()
    assert shipped == "name: Samantha\nhandle: samantha\n# hand-written\n"  # the shipped file is never written
    assert yaml.safe_load((profiles / "samantha" / "persona.local.yaml").read_text()) == {"model": CLOUD}
    assert saved_model(profiles, "aria") == "gemini/gemini-flash-latest"  # another persona is not touched


def test_a_pick_that_could_not_be_saved_still_applies_for_the_session_and_says_so(profiles, monkeypatch):

    def boom(*a, **k):
        raise OSError("disk full")

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            monkeypatch.setattr(persona_model, "write_atomic_text", boom)  # the disk refuses after the chat opened
            runtime.apply_picker_choice(app, "model", LOCAL)
            assert app.model_override.id == LOCAL
            assert any("Couldn't save it to @samantha's persona.yaml" in t and "this session only" in t for t in lines(app))

    run_async(scenario())
    assert not (profiles / "samantha" / "persona.local.yaml").exists()


def test_switching_persona_drops_the_session_pick_so_the_other_personas_own_model_applies(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "model", CLOUD)
            runtime.apply_picker_choice(app, "persona", "aria")
            assert app.model_override is None
            assert options.active_model(app.persona, app.model_override).id == "gemini/gemini-flash-latest"
            runtime.apply_picker_choice(app, "persona", "samantha")
            assert options.active_model(app.persona, app.model_override).id == CLOUD  # what was saved

    run_async(scenario())


def scenario_with_turn(profiles, first, second):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "model", first)
            app.session_id = "20260930T100000-aaaaaaaa"  # a conversation is going
            before = len(lines(app))
            runtime.apply_picker_choice(app, "model", second)
            return lines(app)[before:]

    return run_async(scenario())


def test_going_to_a_cloud_model_in_a_conversation_says_earlier_replies_are_sent_as_history(profiles):
    said = " ".join(scenario_with_turn(profiles, LOCAL, CLOUD))
    assert "Earlier replies in this conversation" in said and "history" in said


def test_no_history_notice_for_an_empty_conversation_a_cloud_to_cloud_switch_or_a_local_switch(profiles):
    async def empty():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "model", CLOUD)
            return " ".join(lines(app))

    assert "Earlier replies" not in run_async(empty())
    assert "Earlier replies" not in " ".join(scenario_with_turn(profiles, CLOUD, "openai/gpt-4o-mini"))
    assert "Earlier replies" not in " ".join(scenario_with_turn(profiles, CLOUD, LOCAL))
    assert "Earlier replies" not in " ".join(scenario_with_turn(profiles, LOCAL, LOCAL))  # nothing leaves
