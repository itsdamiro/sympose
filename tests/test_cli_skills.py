"""`/skills` in the terminal chat (docs/decisions/077, the amendment of 2026-10-20): the list where a row switches a skill
on or off, `add <path>` (copied in, off, and shown), `read <name>` and `remove <name>` (own skills, after a yes)."""

import asyncio

import pytest
from helpers import write_persona

from sympose import engine, persona_skills
from sympose.cli import commands, dispatch, skills_command
from sympose.cli.app import SymposeCLI
from sympose.engine import skills

SKILL = "---\nname: {name}\ndescription: Plans a trip itinerary. Use when the user wants to plan a trip.\n---\n1. Ask the dates.\n"


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


def lines_of(app):
    return [plain_text(c) for c in app.transcript.children]


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    write_persona(base, "samantha", "name: Samantha\nhandle: samantha\nskills: ['poem-writing']\n")
    bundled = tmp_path / "bundled" / "poem-writing"
    bundled.mkdir(parents=True)
    (bundled / "SKILL.md").write_text(SKILL.format(name="poem-writing"), encoding="utf-8")
    monkeypatch.setattr(skills, "BUNDLED_DIR", str(tmp_path / "bundled"))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    for name in ("refresh_recaps", "refresh_embeddings", "refresh_memory", "refresh_status_phrases"):
        monkeypatch.setattr(engine, name, lambda *a, **k: None)


@pytest.fixture
def folder(tmp_path):
    made = tmp_path / "elsewhere" / "trip-planning"
    made.mkdir(parents=True)
    (made / "SKILL.md").write_text(SKILL.format(name="trip-planning"), encoding="utf-8")
    return made


def drive(*arguments, after_each=None):
    """Run `/skills <arguments>` one after another in a real app; `(lines after each, the panel's rows then)`."""
    out = {"lines": [], "rows": []}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            opening = lines_of(app)
            for args in arguments:
                await skills_command.run(app, args)
                await pilot.pause(0.1)
                now = lines_of(app)
                out["lines"].append(now[len(opening):])
                out["rows"].append(
                    [(o.id, str(o.prompt)) for o in app.panel.options] if app.panel is not None and app.panel_kind in (skills_command.PICKER_KIND, skills_command.CONFIRM_KIND) else []
                )
                if after_each:
                    await after_each(app, pilot)
                    await pilot.pause(0.1)
                    out["lines"][-1] = lines_of(app)[len(opening):]

    asyncio.run(scenario())
    return out


def enabled(name):
    return {r["name"]: r["enabled"] for r in persona_skills.listing("samantha")}[name]


def test_it_is_a_command_that_takes_what_is_typed_after_it():
    command = commands.find_command("/skills")
    assert command is not None and command.takes_args


def test_the_list_has_a_row_for_each_skill_with_its_state(folder):
    persona_skills.add("samantha", str(folder))

    rows = drive("")["rows"][0]

    assert [r[0] for r in rows] == ["poem-writing", "trip-planning"]
    assert "poem-writing — on:" in rows[0][1] and "trip-planning — off, yours:" in rows[1][1]


def test_choosing_a_row_switches_that_skill_and_says_so(folder):
    persona_skills.add("samantha", str(folder))

    async def choose(app, pilot):
        skills_command.toggle(app, "trip-planning")

    out = drive("", after_each=choose)

    assert enabled("trip-planning") is True
    assert out["lines"][0][-1] == "trip-planning is now on."


def test_choosing_a_row_in_the_open_list_flips_it_both_ways_and_keeps_the_list_open(folder):
    persona_skills.add("samantha", str(folder))
    seen = []

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await skills_command.run(app, "")
            await pilot.pause(0.1)
            for _ in range(2):
                event = type("E", (), {"option_list": app.panel, "option": type("O", (), {"id": "poem-writing"})()})()
                await dispatch.on_option_selected(app, event)
                await pilot.pause(0.1)
                seen.append((enabled("poem-writing"), app.panel_kind))

    asyncio.run(scenario())

    assert seen == [(False, skills_command.PICKER_KIND), (True, skills_command.PICKER_KIND)]


def test_adding_a_folder_copies_it_in_off_and_shows_its_text(folder):
    out = drive(f"add {folder}")

    assert enabled("trip-planning") is False
    shown = out["lines"][0]
    assert shown[0].startswith("Added trip-planning. It is off")
    assert any("1. Ask the dates." in line for line in shown)
    assert any("Yours: it is sent only to a model on your computer" in line for line in shown)


def test_a_path_with_spaces_and_quotes_is_understood(tmp_path):
    made = tmp_path / "my skills" / "trip-planning"
    made.mkdir(parents=True)
    (made / "SKILL.md").write_text(SKILL.format(name="trip-planning"), encoding="utf-8")

    drive(f"add '{made}'")

    assert enabled("trip-planning") is False


def test_what_else_was_in_the_folder_is_said_not_used(folder):
    (folder / "run.sh").write_text("x", encoding="utf-8")

    assert "Only SKILL.md was copied. Nothing else in that folder is used." in drive(f"add {folder}")["lines"][0]


def test_a_refused_folder_says_why_and_adds_nothing(tmp_path):
    out = drive(f"add {tmp_path / 'nowhere'}")

    assert out["lines"][0] == ["There is no folder at that path."]
    assert [r["name"] for r in persona_skills.listing("samantha")] == ["poem-writing"]


def test_reading_a_skill_shows_its_state_and_its_text(folder):
    persona_skills.add("samantha", str(folder))

    shown = drive("read poem-writing")["lines"][0]

    assert shown[0].startswith("poem-writing — on.") and shown[0].endswith("Ships with Sympose.")
    assert "1. Ask the dates." in shown[1]


def test_reading_a_skill_that_is_not_there_says_so():
    assert drive("read nothing-here")["lines"][0] == ["There is no skill called nothing-here."]


def test_removing_asks_first_and_only_a_yes_deletes(folder):
    persona_skills.add("samantha", str(folder))

    out = drive("remove trip-planning")

    assert [r[0] for r in out["rows"][0]] == ["remove:trip-planning", "keep"]
    assert "trip-planning" in {r["name"] for r in persona_skills.listing("samantha")}  # asked, not done


def test_a_yes_removes_the_skill_and_says_so(folder):
    persona_skills.add("samantha", str(folder))

    async def yes(app, pilot):
        skills_command.apply_removal(app, "remove:trip-planning")

    out = drive("remove trip-planning", after_each=yes)

    assert out["lines"][0][-1] == "Removed trip-planning."
    assert [r["name"] for r in persona_skills.listing("samantha")] == ["poem-writing"]


def test_a_skill_that_ships_with_sympose_is_not_offered_for_removal():
    out = drive("remove poem-writing")

    assert out["lines"][0] == ["poem-writing ships with Sympose, so it can't be removed. Turn it off with /skills instead."]
    assert out["rows"][0] == []


def test_a_word_it_does_not_know_gives_the_usage():
    out = drive("frobnicate", "remove", "add")

    assert [lines[-1] for lines in out["lines"]] == [skills_command.USAGE] * 3
