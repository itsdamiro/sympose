"""A turn that came from Slack (docs/decisions/093): the model is told so, in its text alone, and is given no tool that needs an
editor, since nothing of that reaches the user there. The model is a fake; the persona and settings are temporary."""

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import lookup, session, sharing, tool_support, turn
from sympose.engine.model import ModelReply

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
ASK = "Draft a note about seeds."


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\n")
    write_persona(base, "reference", "name: Reference\nvault_folders: []\nsympose_reference: true\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)
    sharing.set_approved(sharing.OPEN_NOTE, True)


def model_that(monkeypatch, *replies):
    seen, queue = [], list(replies)

    def call_model(messages, model=None, **kwargs):
        seen.append({"messages": [dict(m) for m in messages], "model": model, **kwargs})
        return queue.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def names(call) -> list[str]:
    return [t["function"]["name"] for t in call["tools"]]


def test_the_model_is_told_it_is_in_slack_before_the_request_and_the_conversation_keeps_only_the_request(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hi", 5))

    result = turn.run_turn("samantha", ASK, model=LOCAL, edits=True, in_slack=True)

    sent = seen[0]["messages"][-1]["content"]
    assert turn.SLACK in sent and sent.index(turn.SLACK) < sent.index(ASK)
    assert session.history_as_messages(session.load_session("samantha", result.session_id))[0]["content"] == ASK


def test_the_other_ways_in_are_not_told_they_are_in_slack(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hi", 5), ModelReply("Hi", 5))

    turn.run_turn("samantha", ASK, model=LOCAL, edits=True)
    turn.run_turn("samantha", ASK, model=LOCAL, edits=True, unattended=True)

    assert all(turn.SLACK not in call["messages"][-1]["content"] for call in seen)


def test_the_retry_without_tools_is_still_told(monkeypatch):
    sent = []

    def call_model(messages, model=None, **kwargs):
        if kwargs.get("tools"):
            raise lookup.ToolsRefused("no")
        sent.append(messages[-1]["content"])
        return ModelReply("ok", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    monkeypatch.setattr(lookup.model_mod, "call_model", call_model, raising=False)

    turn.run_turn("samantha", ASK, model=CLOUD, edits=True, in_slack=True)

    assert sent and turn.SLACK in sent[-1]


def test_a_persona_in_slack_is_not_given_the_tool_that_opens_a_note_in_an_editor(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("ok", 5), ModelReply("ok", 5))

    turn.run_turn("samantha", "hi", model=CLOUD, edits=True)
    turn.run_turn("samantha", "hi", model=CLOUD, edits=True, in_slack=True)

    assert names(seen[0]) == ["propose_note", "show_note", "propose_folder_definition"]
    assert names(seen[1]) == ["propose_note", "propose_folder_definition"]
    assert "show_note" not in seen[1]["messages"][-1]["content"]


def test_a_persona_in_slack_cannot_offer_a_persona_or_a_setting_that_waits_on_a_card_it_cannot_show(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("ok", 5), ModelReply("ok", 5))

    turn.run_turn("reference", "hi", model=CLOUD, edits=True)
    turn.run_turn("reference", "hi", model=CLOUD, edits=True, in_slack=True)

    assert {"propose_persona", "propose_setting"} <= set(names(seen[0]))
    assert not {"propose_persona", "propose_setting"} & set(names(seen[1]))
    assert "propose_persona" not in seen[1]["messages"][-1]["content"]


def test_a_model_without_tools_is_not_told_how_to_open_a_note_in_slack_even_when_the_user_allowed_it(monkeypatch):
    settings_store.set("show_note_marker", True)
    seen = model_that(monkeypatch, ModelReply("ok", 5), ModelReply("ok", 5))

    turn.run_turn("samantha", "hi", model=LOCAL, edits=True)
    turn.run_turn("samantha", "hi", model=LOCAL, edits=True, in_slack=True)

    assert "show_note" in seen[0]["messages"][-1]["content"]
    assert "show_note" not in seen[1]["messages"][-1]["content"]
    assert "propose_note" in seen[1]["messages"][-1]["content"]  # a new note it may still offer


def test_a_show_note_marker_in_a_slack_reply_is_removed_and_opens_nothing(monkeypatch):
    settings_store.set("show_note_marker", True)
    model_that(monkeypatch, ModelReply('Here you go.\n<!-- show_note: {"path": "Seeds.md"} -->', 5))

    result = turn.run_turn("samantha", "show me Seeds", model=LOCAL, edits=True, in_slack=True)

    assert result.reply == "Here you go."
    assert [(r["tool"], r["saved"]) for r in result.lookups] == [("show_note", False)]
