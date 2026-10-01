"""`/model` saves the pick as the persona's own (docs/decisions/044, 046), so it is kept across restarts and
the web app sees it; each persona has its own model, so a persona switch drops the session's pick and the
new persona's saved model applies. Switching to a cloud model in a conversation already going asks first,
because earlier replies travel as history (044, amendment of 2026-10-01)."""

import asyncio
from types import SimpleNamespace

import pytest
import yaml
from helpers import write_persona

from sympose import engine, persona_model, profile
from sympose.cli import dispatch, options, picker, runtime, share
from sympose.cli.commands import find_command
from sympose.cli.selection import SelectionOption
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


OTHER_CLOUD = "openai/gpt-4o-mini"


async def pick(app, value):
    """Choose `value` in the model picker the way a keypress would, through the real dispatch."""
    await picker.open_picker(app, "model", "Model", [SelectionOption("row", value)])
    await dispatch.on_option_selected(app, SimpleNamespace(option_list=app.panel, option=SimpleNamespace(id=value)))


async def answer(app, value):
    await dispatch.on_option_selected(app, SimpleNamespace(option_list=app.panel, option=SimpleNamespace(id=value)))


def in_conversation(first):
    """A conversation is going on `first`; returns (app, pilot) parts through a callback-free scenario."""

    async def scenario(second, then=None):
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "model", first)
            app.session_by_generation[app.session_generation] = "20260930T100000-aaaaaaaa"  # a conversation is going
            before = len(lines(app))
            await pick(app, second)
            if then:
                await answer(app, then)
            return app.panel_kind, app.model_override.id, lines(app)[before:]

    return scenario


def test_a_local_to_cloud_switch_in_a_conversation_asks_first_and_changes_nothing_yet(profiles):
    kind, model, said = run_async(in_conversation(LOCAL)(CLOUD))
    assert kind == share.CONFIRM_KIND and model == LOCAL
    assert "earlier replies in this conversation" in " ".join(said) and "history" in " ".join(said)
    assert saved_model(profiles, "samantha") == LOCAL  # not saved either


def test_accepting_applies_the_switch_saves_it_and_tells_the_cloud_notice(profiles):
    kind, model, said = run_async(in_conversation(LOCAL)(CLOUD, then=CLOUD))
    assert model == CLOUD and saved_model(profiles, "samantha") == CLOUD
    assert any("Switched model to Claude Sonnet 5" in t for t in said) and any("is a cloud model" in t for t in said)


def test_keeping_leaves_the_model_and_the_saved_pick_alone(profiles):
    kind, model, said = run_async(in_conversation(LOCAL)(CLOUD, then=share.KEEP))
    assert model == LOCAL and saved_model(profiles, "samantha") == LOCAL
    assert not any("Switched model" in t for t in said)


def test_nothing_is_asked_for_an_empty_conversation_a_cloud_to_cloud_switch_or_a_local_switch(profiles):
    async def empty():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pick(app, CLOUD)  # no conversation yet
            return app.panel_kind, app.model_override.id

    kind, model = run_async(empty())
    assert kind != share.CONFIRM_KIND and model == CLOUD  # the /share list opens, as ADR 031 says, not a question
    for first, second in ((CLOUD, OTHER_CLOUD), (CLOUD, LOCAL), (LOCAL, LOCAL)):
        kind, model, said = run_async(in_conversation(first)(second))
        assert kind != share.CONFIRM_KIND and model == second


HAND = "openrouter/mistralai/mistral-large"


def test_a_model_named_by_hand_is_a_row_in_the_model_picker_and_counts_as_cloud(profiles):
    write_persona(profiles, "hand", f"name: Hand\nhandle: hand\nmodel: {HAND}\n")

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "persona", "hand")
            await runtime.run_command(app, find_command("/model"))
            ids = [app.panel.get_option_at_index(i).id for i in range(app.panel.option_count)]
            assert ids.count(HAND) == 1 and len(ids) == len(options.MODEL_OPTIONS) + 1
            assert share.in_cloud(app)  # the cloud notice and /share rules apply to it like a listed cloud model

    run_async(scenario())


def test_going_from_local_to_a_hand_named_cloud_model_in_a_conversation_asks_first(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            runtime.apply_picker_choice(app, "model", LOCAL)
            app.session_by_generation[app.session_generation] = "20260930T100000-aaaaaaaa"
            app.persona = options.PersonaOption("samantha", "Samantha", "", HAND)  # named by hand, not yet picked
            app.model_override = options.model_option_for(LOCAL)
            await pick(app, HAND)
            return app.panel_kind

    assert run_async(scenario()) == share.CONFIRM_KIND
