"""Tests for sympose.engine.skill_folder (docs/decisions/077): which folder a message names, and the text it adds to a
drafting skill (the folder's definition and one of its notes, exactly as stored). A temporary vault throughout."""

import pytest

from sympose.engine import skill_folder

PERSONA = {"handle": "ada", "vault_folders": ["*"]}
RECIPES = "# Recipes\n\nDishes we cook.\n\n## Template\n\n```\ntype: recipe\nservings:\ntags:\n```\n\nSections: Ingredients, Steps.\n"
PEOPLE = "# People\n\nWho we know.\n\n## Template\n\n```\ntype: person\nborn:\n```\n"


def put(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    put(root, "Recipes/Recipes.md", RECIPES)
    put(root, "Recipes/Soup.md", "---\ntype: recipe\nservings: 4\ntags: [soup]\n---\n# Soup\n\n## Ingredients\n- lentils\n\n## Steps\n1. Simmer.\n")
    put(root, "Recipes/Toast.md", "# Toast\n\nBread.\n")
    put(root, "People/People.md", PEOPLE)
    put(root, "People/Grace.md", "---\ntype: person\nborn: 1906\n---\n# Grace\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return root


def test_a_message_naming_a_folder_gets_its_definition_and_its_fullest_note(vault):
    text = skill_folder.shape_for(PERSONA, "add a note for a recipe: risotto")

    assert RECIPES.strip() in text
    assert "`Recipes/Soup.md`" in text  # the note with the most sections, not Toast
    assert "type: recipe\nservings: 4" in text  # as stored, frontmatter and all
    assert "People" not in text


def test_a_folder_is_found_by_its_name_or_by_a_constant_of_its_template(vault):
    assert "The folder People" in skill_folder.shape_for(PERSONA, "write up a note on a person")  # type: person
    assert "The folder People" in skill_folder.shape_for(PERSONA, "a new note in People")  # the name
    assert "The folder Recipes" in skill_folder.shape_for(PERSONA, "put this in my recipes")  # a plural


def test_two_equally_good_folders_or_none_gives_nothing(vault):
    put(vault, "Meals/Meals.md", "# Meals\n\n## Template\n\n```\ntype: recipe\n```\n")
    put(vault, "Meals/One.md", "# One\n")

    assert skill_folder.shape_for(PERSONA, "Recipes or Meals") is None  # the name of one, the template of the other
    assert skill_folder.shape_for(PERSONA, "good morning") is None


def test_a_folder_without_a_template_is_never_chosen(vault):
    put(vault, "Ideas/Ideas.md", "# Ideas\n\nNo template here.\n")
    put(vault, "Ideas/One.md", "# One\n")

    assert skill_folder.shape_for(PERSONA, "a note in Ideas") is None


def test_a_long_note_is_cut_after_a_whole_line_and_says_so(vault):
    put(vault, "Recipes/Soup.md", "## A\n## B\n" + "\n".join(f"line {i} " + "x" * 40 for i in range(200)))

    text = skill_folder.shape_for(PERSONA, "a recipe")

    assert text.endswith(skill_folder.CUT)
    assert all(line.endswith("x" * 40) for line in text.splitlines() if line.startswith("line "))  # no half line
    assert len(text) < skill_folder.MAX_DEFINITION + skill_folder.MAX_EXAMPLE + 400


def test_no_vault_gives_nothing(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)

    assert skill_folder.shape_for({"handle": "ada"}, "a recipe") is None
