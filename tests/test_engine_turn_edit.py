"""`run_turn`'s edit tool (docs/decisions/072): a persona told the note open in the editor can propose changes to it,
as tool calls on a model that can call tools and as a marked block on one that cannot, in every mode but `plan`, and
only when the caller (the web app) asks for it. The model is a fake; the persona and settings are temporary."""

import pytest
from helpers import write_persona

from sympose import note_changes, settings_store
from sympose.engine import edit_mode, edit_tools, tool_support, turn
from sympose.engine.edit_turn import OpenNote
from sympose.engine.model import ModelReply
from sympose.engine.model_tools import ToolCall
from sympose import note_changes_store as store

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
NOTE = OpenNote("Garden plan.md", "I run three times a week.\n\n- Pack charger\n")
MARKER = '<!-- propose_edit: {"find": "three times", "replace": "four times", "say": "Changed the count."} -->'


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)


def model_that(monkeypatch, *replies):
    seen, queue = [], list(replies)

    def call_model(messages, model=None, **kwargs):
        seen.append({"messages": [dict(m) for m in messages], "model": model, **kwargs})
        return queue.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def waiting() -> list[dict]:
    entry = store.read("samantha", NOTE.path)
    return entry["proposals"] if entry else []


def test_a_turn_that_does_not_ask_for_edits_gets_none_of_it(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hi", 5))

    turn.run_turn("samantha", "hello", model=LOCAL)

    assert "propose_edit" not in seen[0]["messages"][-1]["content"] and "tools" not in seen[0]


def test_the_open_note_and_the_rules_come_with_the_message_but_the_conversation_keeps_only_the_message(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hi", 5))

    result = turn.run_turn("samantha", "make it four", model=LOCAL, open_note=NOTE)

    sent = seen[0]["messages"][-1]["content"]
    assert "three times a week" in sent and "make it four" in sent and "<!-- propose_edit:" in sent
    from sympose.engine import session
    saved = session.load_session("samantha", result.session_id)
    assert session.history_as_messages(saved)[0]["content"] == "make it four"


def test_a_marker_from_a_model_that_cannot_call_tools_becomes_a_proposal_and_leaves_the_reply(monkeypatch):
    model_that(monkeypatch, ModelReply(f"I will change the count.\n{MARKER}", 5))

    result = turn.run_turn("samantha", "make it four", model=LOCAL, open_note=NOTE)

    assert result.reply == "I will change the count."
    (p,) = waiting()
    assert (p["find"], p["replace"]) == ("three times", "four times")
    assert result.lookups == [{"tool": "propose_edit", "saved": True}]


def test_a_model_that_can_call_tools_is_given_the_pair_and_the_call_makes_a_proposal(monkeypatch):
    call = ToolCall("c1", "propose_edit", '{"find": "three times", "replace": "four times", "say": "s"}')
    seen = model_that(monkeypatch, ModelReply("", None, tool_calls=(call,)), ModelReply("Proposed it.", 5))

    result = turn.run_turn("samantha", "make it four", model=CLOUD, open_note=NOTE)

    assert seen[0]["tools"] == edit_tools.TOOLS
    assert result.reply == "Proposed it." and len(waiting()) == 1
    assert "<!--" not in seen[0]["messages"][-1]["content"]


def test_plan_gives_no_tool_and_no_note_and_a_marker_she_writes_anyway_is_left_alone(monkeypatch):
    settings_store.set(edit_mode.SETTING, "plan")
    seen = model_that(monkeypatch, ModelReply(f"Sure.\n{MARKER}", 5))

    result = turn.run_turn("samantha", "make it four", model=CLOUD, open_note=NOTE)

    assert "tools" not in seen[0] and "three times a week" not in seen[0]["messages"][-1]["content"]
    assert waiting() == []
    assert "propose_edit" in result.reply  # not ours to strip when nothing was offered; shown as written


def test_a_passage_found_twice_is_told_to_the_user_not_filed(monkeypatch):
    twice = OpenNote("Garden plan.md", "- Pack charger\n- Pack charger\n")
    bad = '<!-- propose_edit: {"find": "- Pack charger", "replace": "x", "say": "s"} -->'
    model_that(monkeypatch, ModelReply(f"Done.\n{bad}", 5))

    result = turn.run_turn("samantha", "rename it", model=LOCAL, open_note=twice)

    assert "could not be placed" in result.reply and waiting() == []


def test_edits_on_with_no_note_open_offers_a_new_note_only(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Here.\n" + '<!-- propose_note: {"text": "# Seeds", "title": "Seeds", "say": "s"} -->', 5))

    turn.run_turn("samantha", "write a seed note", model=LOCAL, edits=True)

    assert "propose_note" in seen[0]["messages"][-1]["content"] and "propose_edit" not in seen[0]["messages"][-1]["content"]
    assert note_changes.drafts("samantha")[0]["name"] == "Seeds"


def test_when_the_tools_are_refused_the_turn_is_retried_with_the_marker(monkeypatch):
    from sympose.engine import lookup
    calls = {"n": 0}

    def call_model(messages, model=None, **kwargs):
        calls["n"] += 1
        if "tools" in kwargs and kwargs["tools"]:
            raise lookup.ToolsRefused("no")
        return ModelReply(f"ok\n{MARKER}", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    monkeypatch.setattr(lookup.model_mod, "call_model", call_model, raising=False)

    result = turn.run_turn("samantha", "make it four", model=CLOUD, open_note=NOTE)

    assert len(waiting()) == 1 and result.reply == "ok"
