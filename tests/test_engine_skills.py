"""Tests for sympose.engine.skills (docs/decisions/077): how a skill folder is read, which skills a persona carries,
which one a message picks, and where its steps sit in the prompt. How well a model follows one is measured in
live_skill_cases.py, not here."""

import re

import pytest

from sympose import settings_store
from sympose.engine import prompt, skills

ALL = skills.tools_of(ask=True, edit=True)
GOOD = "---\nname: {name}\ndescription: {desc}\n{extra}---\n{body}\n"


def write_skill(folder, name, desc="Writes a poem about the sea. Use when the user asks for a poem.", body="1. Write it.", extra=""):
    path = folder / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(GOOD.format(name=name, desc=desc, body=body, extra=extra), encoding="utf-8")


@pytest.fixture
def bundled(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "BUNDLED_DIR", str(tmp_path / "bundled"))
    return tmp_path / "bundled"


def test_a_valid_skill_is_read_with_its_tools():
    skill = skills.parse(GOOD.format(name="a-b", desc="Does x. Use when y.", body="Steps.", extra="tools: [propose_note]\n"), "a-b", "bundled")

    assert skill == skills.Skill("a-b", "Does x. Use when y.", "Steps.", ("propose_note",), "bundled")


def test_a_skill_can_ask_for_its_folders_shape_and_for_a_model_that_calls_tools():
    extra = "tools: [propose_note, tool_calls]\ncontext: folder\n"
    skill = skills.parse(GOOD.format(name="a-b", desc="Does x. Use when y.", body="Steps.", extra=extra), "a-b", "bundled")

    assert skill.context == skills.FOLDER
    assert not skills.can_carry_out(skill, skills.tools_of(ask=False, edit=True))  # a marker, not a call
    assert skills.can_carry_out(skill, skills.tools_of(ask=False, edit=True, calls=True))
    assert not skills.can_carry_out(skill, skills.tools_of(ask=False, edit=False, calls=True))  # nowhere to propose


@pytest.mark.parametrize(
    "text",
    [
        "no header\n",
        "---\nname: a-b\ndescription: d\ncontext: elsewhere\n---\nSteps.\n",  # a context nobody provides
        "---\nname: a-b\n---\nSteps.\n",  # no description
        "---\nname: other\ndescription: d\n---\nSteps.\n",  # not its folder's name
        "---\nname: A-b\ndescription: d\n---\nSteps.\n",  # not lowercase
        "---\nname: a-b\ndescription: d\n---\n\n",  # no steps
        "---\nname: a-b\ndescription: " + "x" * 401 + "\n---\nSteps.\n",  # description too long
        "---\nname: a-b\ndescription: d\ntools: nope\n---\nSteps.\n",  # tools is not a list
        "---\n: : bad\n---\nSteps.\n",  # unreadable header
    ],
)
def test_a_skill_with_a_bad_header_or_no_steps_is_skipped(text):
    assert skills.parse(text, "a-b", "bundled") is None


def test_a_persona_carries_the_bundled_skills_it_names_and_all_of_its_own(bundled, tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "profiles"))
    write_skill(bundled, "poem-writing")
    write_skill(bundled, "not-named")
    write_skill(tmp_path / "profiles" / "ada" / "skills", "her-own")

    carried = skills.carried({"handle": "ada", "skills": ["poem-writing"]})

    assert sorted(s.name for s in carried) == ["her-own", "poem-writing"]
    assert {s.name: s.source for s in carried} == {"her-own": "persona", "poem-writing": "bundled"}


def test_her_own_skill_replaces_a_bundled_one_of_the_same_name(bundled, tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "profiles"))
    write_skill(bundled, "poem-writing", body="Bundled steps.")
    write_skill(tmp_path / "profiles" / "ada" / "skills", "poem-writing", body="Her steps.")

    (only,) = skills.carried({"handle": "ada", "skills": ["poem-writing"]})

    assert only.body == "Her steps."


def test_a_file_over_the_size_limit_is_not_read(bundled):
    write_skill(bundled, "huge", body="x" * (skills.MAX_FILE + 1))

    assert skills.carried({"handle": "ada", "skills": ["huge"]}) == []


def test_the_best_match_is_chosen_and_small_talk_chooses_none(bundled):
    write_skill(bundled, "poem-writing")
    write_skill(bundled, "trip-planning", desc="Plans a trip itinerary. Use when the user wants to plan a journey or trip.")
    persona = {"handle": "ada", "skills": ["poem-writing", "trip-planning"]}

    assert skills.select(persona, "please write me a poem about the sea", ALL, True).name == "poem-writing"
    assert skills.select(persona, "help me plan a trip to Lisbon", ALL, True).name == "trip-planning"
    assert skills.select(persona, "good morning, how are you?", ALL, True) is None


def test_skills_off_chooses_none(bundled):
    write_skill(bundled, "poem-writing")
    settings_store.set(skills.LOOKUP_SETTING, skills.OFF)

    assert skills.select({"handle": "ada", "skills": ["poem-writing"]}, "write me a poem about the sea", ALL, True) is None


def test_a_skill_is_not_offered_where_a_tool_it_names_is_missing(bundled):
    write_skill(bundled, "poem-writing", extra="tools: [open_note, propose_note]\n")
    persona = {"handle": "ada", "skills": ["poem-writing"]}
    message = "write me a poem about the sea"

    assert skills.select(persona, message, skills.tools_of(ask=False, edit=False), True) is None
    assert skills.select(persona, message, skills.tools_of(ask=True, edit=False), True) is None  # no editing
    assert skills.select(persona, message, skills.tools_of(ask=False, edit=True), True) is None  # no lookups
    assert skills.select(persona, message, skills.tools_of(ask=True, edit=True), True).name == "poem-writing"


def test_a_long_body_is_cut_after_a_whole_line_and_says_so():
    body = "\n".join(f"line {i} " + "x" * 40 for i in range(100))
    settings_store.set(skills.CAP_SETTING, 600)

    text = skills.text_for(skills.Skill("a-b", "d", body))

    lines = text.splitlines()
    assert lines[0] == "Skill: a-b" and lines[-1] == skills.CUT_NOTE
    assert re.fullmatch(r"line \d+ x{40}", lines[-2])  # a whole line, not a piece of one
    assert len(text) <= 600 + len("Skill: a-b\n") + len(skills.CUT_NOTE) + 1


def test_a_cut_that_falls_exactly_on_a_line_end_keeps_that_line():
    settings_store.set(skills.CAP_SETTING, skills.MIN_CAP)
    second = "b" * (skills.MIN_CAP - len("first\n"))  # the cap ends right after this line: its newline is next
    body = f"first\n{second}\nthird line"

    lines = skills.text_for(skills.Skill("a-b", "d", body)).splitlines()

    assert lines[1:3] == ["first", second] and lines[-1] == skills.CUT_NOTE and "third line" not in lines


def test_a_body_exactly_the_cap_long_is_whole():
    settings_store.set(skills.CAP_SETTING, skills.MIN_CAP)
    body = "a" * skills.MIN_CAP

    assert skills.text_for(skills.Skill("a-b", "d", body)) == f"Skill: a-b\n{body}"


def test_a_file_exactly_the_size_limit_is_read_and_one_byte_more_is_not(bundled):
    for name, size in (("exact", skills.MAX_FILE), ("over", skills.MAX_FILE + 1)):
        (bundled / name).mkdir(parents=True)
        text = GOOD.format(name=name, desc="d", body="", extra="")
        (bundled / name / "SKILL.md").write_text(text + "x" * (size - len(text.encode())), encoding="utf-8")

    assert [s.name for s in skills.carried({"handle": "ada", "skills": ["exact", "over"]})] == ["exact"]


def test_a_body_within_the_cap_is_whole_and_has_no_note():
    assert skills.text_for(skills.Skill("a-b", "d", "1. One.\n2. Two.")) == "Skill: a-b\n1. One.\n2. Two."


def test_a_header_closing_line_must_be_three_dashes_alone():
    ok = "---\nname: a-b\ndescription: d\n---  \nSteps.\n"
    four = "---\nname: a-b\ndescription: d\n----\nSteps.\n"

    assert skills.parse(ok, "a-b", "bundled").body == "Steps."
    assert skills.parse(four, "a-b", "bundled") is None


def test_a_name_with_other_than_ascii_letters_digits_and_single_hyphens_is_refused():
    for name in ("caf\u00e9", "a--b", "-a", "a-", "a_b"):
        assert skills.parse(GOOD.format(name=name, desc="d", body="Steps.", extra=""), name, "bundled") is None


def test_a_file_saved_with_a_byte_order_mark_is_read(bundled):
    folder = bundled / "poem-writing"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_bytes(b"\xef\xbb\xbf" + GOOD.format(name="poem-writing", desc="d", body="Steps.", extra="").encode())

    assert [s.name for s in skills.carried({"handle": "ada", "skills": ["poem-writing"]})] == ["poem-writing"]


def test_only_the_bundled_skills_a_persona_names_are_read(bundled, monkeypatch):
    write_skill(bundled, "named")
    write_skill(bundled, "unnamed")
    opened = []
    real = open
    monkeypatch.setattr("builtins.open", lambda path, *a, **k: (opened.append(str(path)), real(path, *a, **k))[1])

    skills.carried({"handle": "ada", "skills": ["named"]})

    assert any("named" in p for p in opened) and not any("unnamed" in p for p in opened)


def test_a_skill_of_the_personas_own_is_never_given_to_a_model_that_is_not_local(bundled, tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "profiles"))
    write_skill(bundled, "poem-writing")
    write_skill(tmp_path / "profiles" / "ada" / "skills", "trip-planning", desc="Plans a trip itinerary. Use when the user wants to plan a journey or trip.")
    persona = {"handle": "ada", "skills": ["poem-writing"]}

    assert skills.select(persona, "help me plan a trip to Lisbon", ALL, True).name == "trip-planning"
    assert skills.select(persona, "help me plan a trip to Lisbon", ALL, False) is None
    assert skills.select(persona, "please write me a poem about the sea", ALL, False).name == "poem-writing"  # a bundled one still goes


def test_the_least_cap_is_accepted_and_one_below_it_is_not():
    settings_store.set(skills.CAP_SETTING, skills.MIN_CAP)
    assert skills.cap() == skills.MIN_CAP
    settings_store.set(skills.CAP_SETTING, skills.MIN_CAP - 1)
    assert skills.cap() == skills.DEFAULT_CAP


def test_a_name_with_capitals_is_refused_even_when_it_is_its_folders():
    assert skills.parse(GOOD.format(name="Poem-writing", desc="d", body="Steps.", extra=""), "Poem-writing", "bundled") is None


def test_a_cap_below_the_least_or_not_a_number_is_the_default():
    for bad in (10, True, "big", None):
        settings_store.set(skills.CAP_SETTING, bad)
        assert skills.cap() == skills.DEFAULT_CAP


def test_the_skill_sits_right_before_the_message():
    turn = prompt.build_user_turn("write me a poem", [], skill="Skill: poem-writing\n1. Write it.")

    assert turn.endswith(f"{prompt.SKILL_LABEL}\nSkill: poem-writing\n1. Write it.\n\nUser's message: write me a poem")
    assert prompt.build_user_turn("hi", []).count("Skill") == 0


def test_the_bundled_skills_are_valid_and_samantha_carries_the_measured_one():
    import yaml

    bundled_names = {s.name for s in skills._read(skills.BUNDLED_DIR, "bundled")}
    with open("profiles/samantha/persona.yaml", encoding="utf-8") as f:
        wanted = set(yaml.safe_load(f)["skills"])

    # The drafting skill ships but is not carried until it is reliable (docs/decisions/077, amendment).
    assert bundled_names == {"deriving-a-persona-soul", "drafting-a-note-in-a-folders-style"}
    assert wanted == {"deriving-a-persona-soul"}
