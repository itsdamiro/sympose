"""`run_turn` and skills (docs/decisions/077): the steps of the skill a message calls for sit in the user's turn, a
persona's own skills go only to a local model, and a skill needing a tool the turn lacks is not offered. The model is a
fake; the persona and settings are temporary."""

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import sharing, skills, tool_support, turn
from sympose.engine.edit_turn import OpenNote
from sympose.engine.model import ModelReply

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
TRIP = "---\nname: trip-planning\ndescription: Plans a trip itinerary. Use when the user wants to plan a journey or trip.\n---\n1. Ask the dates.\n"
POEM = (
    "---\nname: poem-writing\ndescription: Writes a poem about the sea. Use when the user asks for a poem.\n{extra}---\n"
    "1. Write it.\n"
)
ASK = "help me plan a trip to Lisbon"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\nskills: ['poem-writing']\n")
    (base / "samantha" / "skills" / "trip-planning").mkdir(parents=True)
    (base / "samantha" / "skills" / "trip-planning" / "SKILL.md").write_text(TRIP, encoding="utf-8")
    bundled = tmp_path / "bundled" / "poem-writing"
    bundled.mkdir(parents=True)
    (bundled / "SKILL.md").write_text(POEM.format(extra=""), encoding="utf-8")
    monkeypatch.setattr(skills, "BUNDLED_DIR", str(tmp_path / "bundled"))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)
    return tmp_path


def last_turn(monkeypatch, message, model, **kwargs):
    seen = []

    def call_model(messages, model=None, **_):
        seen.append(messages[-1]["content"])
        return ModelReply("ok", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    turn.run_turn("samantha", message, model=model, **kwargs)
    return seen[0]


def test_the_skill_a_message_calls_for_sits_before_the_message(monkeypatch):
    content = last_turn(monkeypatch, ASK, LOCAL)

    assert content.endswith(f"Skill: trip-planning\n1. Ask the dates.\n\nUser's message: {ASK}")


def test_a_message_that_calls_for_none_gets_none(monkeypatch):
    assert "Skill:" not in last_turn(monkeypatch, "good morning, how are you?", LOCAL)


def test_skills_off_sends_none(monkeypatch):
    settings_store.set(skills.LOOKUP_SETTING, skills.OFF)

    assert "Skill:" not in last_turn(monkeypatch, ASK, LOCAL)


def test_a_personas_own_skill_is_not_sent_to_a_cloud_model_but_a_bundled_one_is(monkeypatch):
    assert "Skill:" not in last_turn(monkeypatch, ASK, CLOUD)
    assert "Skill: poem-writing" in last_turn(monkeypatch, "please write me a poem about the sea", CLOUD)


def test_a_skill_needing_the_edit_tool_is_offered_only_where_the_caller_can_show_a_proposal(tmp_path, monkeypatch):
    (tmp_path / "bundled" / "poem-writing" / "SKILL.md").write_text(POEM.format(extra="tools: [propose_note]\n"), encoding="utf-8")
    message = "please write me a poem about the sea"

    assert "Skill:" not in last_turn(monkeypatch, message, LOCAL)  # the terminal: no edits
    assert "Skill: poem-writing" in last_turn(monkeypatch, message, LOCAL, edits=True, open_note=OpenNote("a.md", "x"))


DRAFTING = (
    "---\nname: drafting-a-note\ndescription: Drafts a new note in a folder. Use when the user asks to add a new note such as a recipe.\n"
    "tools: [propose_note, tool_calls]\ncontext: folder\n---\n1. Copy the shape.\n"
)


def the_message_turn(monkeypatch, message, model, **kwargs):
    """What the model is sent as the message's own turn: with a vault there is a search-rewrite call before it."""
    seen = []

    def call_model(messages, model=None, **_):
        seen.append(messages[-1]["content"])
        return ModelReply("ok", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    turn.run_turn("samantha", message, model=model, **kwargs)
    return next((c for c in seen if "User's message:" in c), "")


def with_a_recipes_vault(tmp_path, monkeypatch):
    vault = tmp_path / "vault" / "Recipes"
    vault.mkdir(parents=True)
    (vault / "Recipes.md").write_text("# Recipes\n\n## Template\n\n```\ntype: recipe\n```\n", encoding="utf-8")
    (vault / "Soup.md").write_text("---\ntype: recipe\n---\n# Soup\n\n## Steps\n", encoding="utf-8")
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    write_persona(tmp_path / "profiles", "samantha", "name: Samantha\nvault_folders: ['*']\nsympose_reference: false\nskills: ['drafting-a-note']\n")
    (tmp_path / "bundled" / "drafting-a-note").mkdir(parents=True)
    (tmp_path / "bundled" / "drafting-a-note" / "SKILL.md").write_text(DRAFTING, encoding="utf-8")


def test_a_drafting_skill_brings_the_folders_shape_and_only_to_a_model_that_calls_tools(tmp_path, monkeypatch):
    with_a_recipes_vault(tmp_path, monkeypatch)
    message = "add a new note for a recipe: risotto"
    note = OpenNote("a.md", "x")

    assert "Skill:" not in the_message_turn(monkeypatch, message, LOCAL, edits=True, open_note=note)  # a marker, not a call
    settings_store.set(sharing.SETTING, [sharing.NOTES])
    content = the_message_turn(monkeypatch, message, CLOUD, edits=True, open_note=note)

    assert "Skill: drafting-a-note" in content
    assert "The folder Recipes and the shape its notes take" in content and "`Recipes/Soup.md`" in content
    assert content.index("The folder Recipes") < content.index("User's message:")


def test_a_cloud_model_not_allowed_the_notes_gets_the_skill_without_the_folders_notes(tmp_path, monkeypatch):
    with_a_recipes_vault(tmp_path, monkeypatch)
    settings_store.set(sharing.SETTING, [])

    content = the_message_turn(monkeypatch, "add a new note for a recipe: risotto", CLOUD, edits=True, open_note=OpenNote("a.md", "x"))

    assert "Skill: drafting-a-note" in content
    assert "The folder Recipes" not in content and "Soup" not in content
