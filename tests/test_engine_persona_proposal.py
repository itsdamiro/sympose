"""Tests for sympose.engine.persona_proposal and its place in a turn (docs/decisions/078): who is given the tool, that a
tool call ends in a request, that a proposal that fails a check is answered with what is wrong
and files nothing, and that she is told what the user decided, once. The model is a fake."""

import json
import os

import pytest
from helpers import write_persona

from sympose import look, settings_store
from sympose.engine import confirmations, edit_mode, followup, persona_proposal, sharing, tool_support, turn
from sympose.engine.model import ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
SOUL = "You are Ada, a warm tutor.\n\nHow you talk:\n- Gently.\n"
ARGS = {
    "name": "Ada", "title": "A tutor", "soul": SOUL, "icon": "graduation", "accent": "#3366cc", "accent_dark": "#99bbee",
    "folders": ["Recipes"], "edit_mode": "manual",
}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for folder in ("Work", "Recipes"):
        (vault / folder).mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: true\n")
    write_persona(profiles, "plain", "name: Plain\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)
    return profiles


def model_that(monkeypatch, *replies):
    seen, queue = [], list(replies)

    def call_model(messages, model=None, **kwargs):
        seen.append({"messages": [dict(m) for m in messages], "model": model, **kwargs})
        return queue.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def requests(sid):
    return confirmations.for_session("samantha", sid)


def test_the_tool_lists_the_icons_and_the_folders_she_can_read():
    function = persona_proposal.tool({"handle": "samantha", "vault_folders": "*"})["function"]

    assert function["name"] == "propose_persona"
    assert all(name in function["parameters"]["properties"]["icon"]["description"] for name in look.ICON_NAMES)
    assert "Recipes, Work" in function["parameters"]["properties"]["folders"]["description"]
    assert set(function["parameters"]["required"]) == {"name", "title", "soul", "icon", "accent", "accent_dark", "edit_mode", "folders"}


def test_the_tool_names_no_folder_when_the_model_may_not_be_told_them():
    sam = {"handle": "samantha", "vault_folders": "*"}

    text = json.dumps(persona_proposal.tool(sam, share_folders=False))

    assert "Recipes" not in text and "Work" not in text and "Leave this empty" in text
    assert "Recipes" in json.dumps(persona_proposal.tool(sam, share_folders=True))


def test_a_call_with_no_folders_files_a_request_for_the_user_to_complete():
    sam = {"handle": "samantha", "vault_folders": "*"}

    result = persona_proposal.run("samantha", "s1", sam, "propose_persona", json.dumps({**ARGS, "folders": []}), share_folders=False)

    assert result.lookup["saved"] is True and requests("s1")[0]["draft"]["folders"] == []


def test_every_real_tool_name_is_one_a_soul_may_not_mention():
    names = persona_proposal.tool_names()

    assert {"propose_persona", "propose_note", "search_notes", "open_note", "remember"} <= set(names)


def test_a_call_files_a_request_and_says_nothing_is_made_yet():
    sam = {"handle": "samantha", "vault_folders": "*"}

    result = persona_proposal.run("samantha", "s1", sam, "propose_persona", json.dumps(ARGS))

    assert result.lookup["saved"] is True and "nothing is made until they accept" in result.text
    assert [r["id"] for r in requests("s1")] == [result.lookup["request"]]


def test_a_call_that_fails_a_check_is_answered_with_what_is_wrong_and_files_nothing():
    sam = {"handle": "samantha", "vault_folders": "*"}

    result = persona_proposal.run("samantha", "s1", sam, "propose_persona", json.dumps({**ARGS, "icon": "smiley"}))

    assert result.lookup == {"tool": "propose_persona", "saved": False} and "icon must be one of" in result.text
    assert requests("s1") == []


@pytest.mark.parametrize("raw", ["not json", "{}", json.dumps({**ARGS, "folders": "Recipes"}), json.dumps({**ARGS, "name": 3})])
def test_arguments_that_cannot_be_read_are_said_so(raw):
    result = persona_proposal.run("samantha", "s1", {"handle": "samantha"}, "propose_persona", raw)

    assert "could not be read" in result.text and not result.lookup["saved"]


def test_another_tools_name_is_not_ours():
    assert persona_proposal.run("samantha", "s1", {}, "propose_note", "{}") is None


def test_a_model_with_tools_is_given_the_tool_and_a_call_makes_a_request(monkeypatch):
    call = ToolCall("c1", "propose_persona", json.dumps(ARGS))
    seen = model_that(monkeypatch, ModelReply("", None, tool_calls=(call,)), ModelReply("I have proposed Ada.", 5))

    result = turn.run_turn("samantha", "make me a tutor persona", model=CLOUD, edits=True)

    assert "propose_persona" in [t["function"]["name"] for t in seen[0]["tools"]]
    assert result.reply == "I have proposed Ada." and [r["draft"]["name"] for r in requests(result.session_id)] == ["Ada"]
    assert not os.path.exists(os.path.join(os.environ["SYMPOSE_PROFILES_DIR"], "ada"))


def test_a_cloud_model_is_told_the_vault_folders_only_when_the_user_has_allowed_them(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hello.", 5), ModelReply("Hello.", 5))

    turn.run_turn("samantha", "make me a tutor persona", model=CLOUD, edits=True)
    sharing.set_approved(sharing.VAULT_MAP, True)
    turn.run_turn("samantha", "make me a tutor persona", model=CLOUD, edits=True)

    without, with_it = (json.dumps(s["tools"]) for s in seen)
    assert "Recipes" not in without and "Leave this empty" in without
    assert "Recipes" in with_it


@pytest.mark.parametrize("who, kwargs", [("plain", {"edits": True}), ("samantha", {})])
def test_she_is_not_given_it_without_the_library_or_without_the_web_app(monkeypatch, who, kwargs):
    seen = model_that(monkeypatch, ModelReply("Hello.", 5))

    turn.run_turn(who, "make me a tutor persona", model=CLOUD, **kwargs)

    names = [t["function"]["name"] for t in seen[0].get("tools", [])]
    assert "propose_persona" not in names and "propose_persona" not in seen[0]["messages"][-1]["content"]


def test_a_model_without_tools_is_not_given_it_and_is_still_told_she_cannot_create_personas(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hello.", 5))

    turn.run_turn("samantha", "make me a tutor persona", model=LOCAL, edits=True)

    assert "tools" not in seen[0] and "propose_persona" not in seen[0]["messages"][-1]["content"]
    assert "can't create or change notes, personas, or settings" in seen[0]["messages"][0]["content"]


def test_her_prompt_stops_saying_she_cannot_create_personas_only_where_she_can_propose_one(monkeypatch):
    said = "can't create or change notes, personas, or settings"
    seen = model_that(monkeypatch, *[ModelReply("Hello.", 5)] * 4)

    turn.run_turn("samantha", "hello", model=CLOUD, edits=True)  # the web app, a model with tools: she may propose
    turn.run_turn("samantha", "hello", model=CLOUD)  # the terminal
    turn.run_turn("plain", "hello", model=CLOUD, edits=True)  # a persona without the library
    settings_store.set(edit_mode.SETTING, "plan")
    turn.run_turn("samantha", "hello", model=CLOUD, edits=True)  # plan: nothing is proposed

    system = [s["messages"][0]["content"] for s in seen]
    assert said not in system[0] and "can't create or change notes or settings" in system[0]
    assert said in system[1] and said in system[2] and said in system[3]


def test_plan_proposes_nothing(monkeypatch):
    settings_store.set(edit_mode.SETTING, "plan")
    seen = model_that(monkeypatch, ModelReply("Hello.", 5))

    turn.run_turn("samantha", "make me a tutor persona", model=CLOUD, edits=True)

    assert "tools" not in seen[0] and "propose_persona" not in seen[0]["messages"][-1]["content"]


def test_she_is_told_what_the_user_decided_once_and_the_conversation_keeps_only_what_was_said(monkeypatch):
    settings_store.set(followup.SETTING, "off")  # the search rewrite is a model call of its own; this test counts the turns' calls
    call = ToolCall("c1", "propose_persona", json.dumps(ARGS))
    model_that(monkeypatch, ModelReply("", None, tool_calls=(call,)), ModelReply("Here.", 5))
    first = turn.run_turn("samantha", "make me a tutor persona", model=CLOUD, edits=True)
    (request,) = requests(first.session_id)
    confirmations.resolve("samantha", request["id"], True, None, persona_proposal.tool_names())
    seen = model_that(monkeypatch, ModelReply("Glad.", 5), ModelReply("Fine.", 5))

    second = turn.run_turn("samantha", "thanks", model=CLOUD, edits=True, session_id=first.session_id)
    third = turn.run_turn("samantha", "and now?", model=CLOUD, edits=True, session_id=first.session_id)

    assert "You proposed a persona called Ada: the user accepted it and the persona now exists." in seen[0]["messages"][-1]["content"]
    assert "You proposed" not in seen[1]["messages"][-1]["content"]
    from sympose.engine import session

    assert [m["content"] for m in session.history_as_messages(session.load_session("samantha", third.session_id))][2] == "thanks"
    assert second.session_id == third.session_id
