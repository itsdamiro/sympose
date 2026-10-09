"""Tests for sympose.engine.skill_tools and the `ask` mode of skills (docs/decisions/077): the skills a turn offers, what
`use_skill` gives back, and how it composes with the other tools. How well a model chooses is measured in
live_skill_cases.py, not here."""

import json

from sympose import settings_store
from sympose.engine import persona_tools, prompt, skill_tools, skills

ALL = skills.tools_of(ask=True, edit=True)
POEM = skills.Skill("poem-writing", "Writes a poem about the sea.", "1. Write it.", (), "bundled")
TRIP = skills.Skill("trip-planning", "Plans a trip.", "1. Plan it.", ("open_note",), "bundled")
HERS = skills.Skill("her-own", "Her private job.", "1. Secret.", (), "persona")
OFFERED = [POEM, TRIP]


def test_use_skill_gives_the_steps_and_names_the_skill_in_the_record():
    result = skill_tools.run(OFFERED, "use_skill", json.dumps({"name": "trip-planning"}))

    assert result.text == skills.text_for(TRIP)
    assert result.lookup == {"tool": "use_skill", "query": "trip-planning", "found": 1}


def test_calling_it_again_gives_another_skill():
    first = skill_tools.run(OFFERED, "use_skill", {"name": "poem-writing"})
    second = skill_tools.run(OFFERED, "use_skill", {"name": "trip-planning"})

    assert "Write it." in first.text and "Plan it." in second.text


def test_a_name_that_was_not_offered_is_refused_with_the_names_that_were():
    result = skill_tools.run(OFFERED, "use_skill", {"name": "her-own"})

    assert "Plan it." not in result.text and "Secret" not in result.text
    assert "poem-writing, trip-planning" in result.text
    assert result.lookup["found"] == 0


def test_unreadable_arguments_say_what_is_wanted():
    assert "give name as text" in skill_tools.run(OFFERED, "use_skill", "{not json").text
    assert "give name as text" in skill_tools.run(OFFERED, "use_skill", {"name": 3}).text


def test_a_name_that_is_not_ours_is_left_for_the_next_tool():
    assert skill_tools.run(OFFERED, "search_notes", {}) is None


def test_the_tool_lists_only_the_offered_names():
    spec = skill_tools.tool(OFFERED)["function"]

    assert spec["parameters"]["properties"]["name"]["enum"] == ["poem-writing", "trip-planning"]


def test_the_tool_composes_with_the_others_and_alone_it_is_the_only_tool():
    tools, run = persona_tools.for_turn(ask=False, remember=False, offered=OFFERED)

    assert [t["function"]["name"] for t in tools] == ["use_skill"]
    assert "Write it." in run({"handle": "ada"}, "m", "use_skill", {"name": "poem-writing"}).text
    assert "There is no tool called search_notes." in run({"handle": "ada"}, "m", "search_notes", {}).text
    assert persona_tools.for_turn(ask=False, remember=False, offered=[]) is None


def test_a_skill_of_her_own_is_offered_to_a_local_model_only(monkeypatch):
    monkeypatch.setattr(skills, "carried", lambda persona: [POEM, HERS])

    assert [s.name for s in skills.usable({"handle": "ada"}, ALL, True)] == ["poem-writing", "her-own"]
    assert [s.name for s in skills.usable({"handle": "ada"}, ALL, False)] == ["poem-writing"]


def test_a_skill_whose_tool_is_missing_is_not_offered(monkeypatch):
    monkeypatch.setattr(skills, "carried", lambda persona: [POEM, TRIP])

    assert [s.name for s in skills.usable({"handle": "ada"}, skills.tools_of(False, True), True)] == ["poem-writing"]


def test_the_menu_lists_each_skill_on_a_line():
    assert skills.menu(OFFERED) == "- poem-writing: Writes a poem about the sea.\n- trip-planning: Plans a trip."


def test_ask_mode_is_a_choice_and_a_model_without_tools_is_still_given_auto(monkeypatch, tmp_path):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    settings_store.set(skills.LOOKUP_SETTING, skills.ASK)

    assert skills.mode() == skills.ASK
    # No match for small talk; `select` still works for the model that cannot call tools.
    monkeypatch.setattr(skills, "carried", lambda persona: [POEM])
    assert skills.select({"handle": "ada"}, "write a poem about the sea", ALL, True).name == "poem-writing"
    assert skills.select({"handle": "ada"}, "good morning", ALL, True) is None


def test_the_menu_takes_the_place_of_the_steps_in_the_turn():
    menu = prompt.build_user_turn("hello", [], skill=skills.menu(OFFERED), skill_menu=True)
    steps = prompt.build_user_turn("hello", [], skill=skills.text_for(POEM))

    assert menu.index("use_skill") < menu.index("- poem-writing") < menu.index("User's message: hello")
    assert "use_skill" not in steps
