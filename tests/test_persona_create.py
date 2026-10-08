"""Tests for sympose.persona_create (docs/decisions/078): what a proposed persona must satisfy before the user is asked,
and the one function that makes the files. The vault and the profiles folder are temporary."""

import os

import pytest
import yaml
from helpers import write_persona

from sympose import look, persona_create
from sympose.persona_create import Draft

TOOLS = ("propose_note", "propose_edit", "propose_persona")
SOUL = "You are Ada, a warm tutor.\n\nHow you talk:\n- Gently, with a question at the end of a thought.\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for folder in ("Work", "Recipes", "Journal", ".obsidian", "Templates"):
        (vault / folder).mkdir(parents=True)
    (vault / "loose.md").write_text("x")
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    return profiles


SAM = {"handle": "samantha", "vault_folders": "*"}


def draft(**changes) -> Draft:
    base = dict(
        name="Ada", title="A warm tutor", soul=SOUL, icon="graduation", accent="#3366cc", accent_dark="rgb(120, 160, 230)",
        folders=("Recipes", "Work"), edit_mode="manual",
    )
    return Draft(**{**base, **changes})


def test_a_proposal_with_everything_right_has_no_problem(world):
    assert persona_create.problem(draft(), SAM, TOOLS) is None


def test_the_handle_is_the_name_in_lower_case_with_hyphens():
    assert persona_create.handle_for("Marie Curie") == "marie-curie"
    assert persona_create.handle_for("  Dr. O'Neil!  ") == "dr-o-neil"
    assert persona_create.handle_for("!!!") == ""


@pytest.mark.parametrize(
    "changes, words",
    [
        (dict(name=""), "name"),
        (dict(name="x" * 41), "name"),
        (dict(name="!!!"), "letter or digit"),
        (dict(name="Samantha"), "already exists"),
        (dict(title="t" * 81), "title"),
        (dict(icon="smiley"), "icon must be one of"),
        (dict(accent="red; background:url(x)"), "accent"),
        (dict(accent_dark="<b>"), "accent_dark"),
        (dict(soul="   "), "Give the soul"),
        (dict(soul="v" * 2501), "voice and temperament only"),
        (dict(soul="You talk gently. Call propose_note when asked."), "propose_note"),
        (dict(edit_mode="wild"), "edit_mode must be one of"),
        (dict(folders=("Recipes", "Secrets")), "Secrets"),
    ],
)
def test_each_problem_is_named_so_the_model_can_fix_it(world, changes, words):
    assert words in persona_create.problem(draft(**changes), SAM, TOOLS)


def test_a_soul_exactly_at_the_limit_passes_and_one_over_does_not(world):
    assert persona_create.problem(draft(soul="v" * persona_create.SOUL_LIMIT), SAM, TOOLS) is None
    assert persona_create.problem(draft(soul="v" * (persona_create.SOUL_LIMIT + 1)), SAM, TOOLS) is not None


def test_a_title_exactly_at_the_limit_passes(world):
    assert persona_create.problem(draft(title="t" * persona_create.MAX_TITLE), SAM, TOOLS) is None


def test_a_name_exactly_at_the_limit_passes(world):
    assert persona_create.problem(draft(name="a" * persona_create.MAX_NAME), SAM, TOOLS) is None


def test_a_proposal_may_leave_the_folders_to_the_user(world):
    assert persona_create.problem(draft(folders=()), SAM, TOOLS) is None


def test_the_error_for_a_stray_folder_names_none_when_the_model_may_not_be_told_the_vault_folders(world):
    message = persona_create.problem(draft(folders=("Secrets",)), SAM, TOOLS, reveal_folders=False)

    assert "Leave the folders out" in message
    assert not any(name in message for name in ("Journal", "Recipes", "Work", "Secrets"))


def test_the_error_for_a_stray_folder_lists_the_ones_she_can_read(world):
    message = persona_create.problem(draft(folders=("Secrets",)), SAM, TOOLS)

    assert "Journal, Recipes, Work" in message and ".obsidian" not in message and "Templates" not in message


def test_a_proposer_limited_to_some_folders_cannot_give_more(world):
    limited = {"handle": "ada", "vault_folders": ["Recipes"]}

    assert persona_create.readable_folders(limited) == ["Recipes"]
    assert persona_create.problem(draft(folders=("Recipes",)), limited, TOOLS) is None
    assert "Work" in persona_create.problem(draft(folders=("Recipes", "Work")), limited, TOOLS)


def test_create_writes_the_persona_and_its_soul_and_nothing_else(world):
    handle = persona_create.create(draft(name="Ada Lovelace"))

    folder = world / handle
    assert handle == "ada-lovelace" and sorted(os.listdir(folder)) == ["persona.yaml", "soul.md"]
    assert yaml.safe_load((folder / "persona.yaml").read_text()) == {
        "name": "Ada Lovelace", "handle": "ada-lovelace", "title": "A warm tutor", "icon": "graduation", "accent": "#3366cc",
        "accent_dark": "rgb(120, 160, 230)", "edit_mode": "manual", "vault_folders": ["Recipes", "Work"],
    }
    assert (folder / "soul.md").read_text() == SOUL.strip() + "\n"


def test_create_leaves_out_an_empty_title(world):
    handle = persona_create.create(draft(title="  "))

    assert "title" not in yaml.safe_load((world / handle / "persona.yaml").read_text())


def test_create_never_overwrites_a_persona(world):
    persona_create.create(draft())
    (world / "ada" / "soul.md").write_text("mine")

    with pytest.raises(FileExistsError):
        persona_create.create(draft())
    assert (world / "ada" / "soul.md").read_text() == "mine"
    with pytest.raises(FileExistsError):
        persona_create.create(draft(name="Samantha"))


def test_what_create_writes_is_what_the_roster_reads(world):
    from sympose import profile

    persona_create.create(draft())
    made = profile.get_profile("ada")

    assert made["name"] == "Ada" and made["icon"] == "graduation" and made["accent"] == "#3366cc"
    assert made["vault_folders"] == ["Recipes", "Work"] and made["sympose_reference"] is False


def test_the_engines_icon_names_are_the_web_apps():
    import re

    source = open(os.path.join(os.path.dirname(__file__), "..", "ui", "src", "lib", "persona-icons.ts"), encoding="utf-8").read()
    block = source[source.index("export const ICON_SET"):]
    block = block[: block.index("\n}\n")]
    names = re.findall(r'^\s+"?([a-z0-9-]+)"?:\s', block, re.M)

    assert sorted(names) == sorted(look.ICON_NAMES) and len(set(names)) == len(names)
