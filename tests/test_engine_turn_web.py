"""A turn with a video link in it (docs/decisions/089): the model's maker watches it when the user has allowed `web`,
the call goes straight to Google, the persona is told what happened either way, and the record names it. The model
is a fake; the persona and settings are temporary."""

import json

import pytest
from helpers import write_persona

from sympose import note_changes_store, settings_store
from sympose.engine import memory, session, sharing, skills, tool_support, turn, web_access
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.model_tools import ToolCall
from sympose.engine.prompt_text import WATCHING, WITHHELD_WEB

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
LINK = "https://youtu.be/8jPQjjsBbIc"
ADDRESS = "https://www.youtube.com/watch?v=8jPQjjsBbIc"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)


@pytest.fixture
def calls(monkeypatch):
    """Both ways of calling a model, recording what each was given: `via` says which one a reply came by."""
    seen: list[dict] = []

    def litellm_way(messages, model=None, **kwargs):
        seen.append({"via": "call_model", "messages": [dict(m) for m in messages], **kwargs})
        return ModelReply("From the text.", 5)

    def direct_way(messages, model=None, **kwargs):
        seen.append({"via": "direct", "messages": [dict(m) for m in messages], **kwargs})
        return ModelReply("From the video.", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", litellm_way)
    monkeypatch.setattr(turn.gemini_direct, "call", direct_way)
    return seen


def test_an_allowed_link_goes_to_google_with_the_video_and_the_persona_is_told_it_is_attached(calls):
    sharing.set_approved(sharing.WEB, True)

    result = turn.run_turn("samantha", f"make notes from {LINK}", model=CLOUD)

    (sent,) = calls
    assert sent["via"] == "direct" and sent["links"] == (ADDRESS,)
    assert WATCHING in sent["messages"][-1]["content"] and WITHHELD_WEB not in sent["messages"][-1]["content"]
    assert result.reply == "From the video." and result.cloud == [sharing.WEB] and result.withheld == []
    assert result.sent["cloud"] == [sharing.WEB]


def test_a_link_the_user_has_not_allowed_is_not_opened_and_the_persona_says_how_to_allow_it(calls):
    result = turn.run_turn("samantha", f"make notes from {LINK}", model=CLOUD)

    (sent,) = calls
    assert sent["via"] == "call_model" and "links" not in sent
    assert WITHHELD_WEB in sent["messages"][-1]["content"] and WATCHING not in sent["messages"][-1]["content"]
    assert result.cloud == [] and result.withheld == [sharing.WEB]


def test_a_local_model_and_the_off_setting_do_nothing_about_a_link(calls):
    sharing.set_approved(sharing.WEB, True)
    turn.run_turn("samantha", f"make notes from {LINK}", model=LOCAL)
    settings_store.set(web_access.SETTING, web_access.OFF)
    result = turn.run_turn("samantha", f"make notes from {LINK}", model=CLOUD)

    assert [c["via"] for c in calls] == ["call_model", "call_model"]
    assert all(WATCHING not in c["messages"][-1]["content"] and WITHHELD_WEB not in c["messages"][-1]["content"] for c in calls)
    assert result.withheld == []


def test_a_message_without_a_link_is_an_ordinary_turn(calls):
    sharing.set_approved(sharing.WEB, True)

    result = turn.run_turn("samantha", "hello", model=CLOUD)

    assert calls[0]["via"] == "call_model" and result.cloud == []


def test_a_follow_up_keeps_the_video_and_the_conversation_keeps_only_what_was_said(calls):
    sharing.set_approved(sharing.WEB, True)
    first = turn.run_turn("samantha", f"summarize {LINK}", model=CLOUD)

    turn.run_turn("samantha", "what does he say about the passport?", session_id=first.session_id, model=CLOUD)

    assert [c["via"] for c in calls] == ["direct", "direct"] and calls[1]["links"] == (ADDRESS,)
    saved = session.history_as_messages(session.load_session("samantha", first.session_id))
    assert [m["content"] for m in saved if m["role"] == "user"] == [f"summarize {LINK}", "what does he say about the passport?"]


def test_the_tool_loop_is_given_the_direct_call_so_the_persona_keeps_her_tools(monkeypatch, calls):
    sharing.set_approved(sharing.WEB, True)
    note = '{"title": "Stress", "text": "# Stress\\n\\nCortisol clouds thinking.", "say": "Drafted."}'
    answers = [ModelReply("", 5, tool_calls=(ToolCall("call_0", "propose_note", note),)), ModelReply("Drafted it from the video.", 5)]
    seen = []

    def direct(messages, model=None, **kwargs):
        seen.append(kwargs)
        return answers.pop(0)

    monkeypatch.setattr(turn.gemini_direct, "call", direct)

    result = turn.run_turn("samantha", f"make a note from {LINK}", model=CLOUD, edits=True)

    assert len(seen) == 2 and all(k["links"] == (ADDRESS,) and k["tools"] for k in seen)
    assert result.reply == "Drafted it from the video." and calls == []
    assert result.lookups == [{"tool": "propose_note", "saved": True}]


def test_a_turn_that_watches_a_video_is_not_given_remember_so_the_video_cannot_steer_a_write_to_her_memory(calls):
    sharing.set_approved(sharing.WEB, True)
    settings_store.set(memory.REMEMBER_SETTING, True)

    turn.run_turn("samantha", f"remember I like birds. {LINK}", model=CLOUD)
    turn.run_turn("samantha", "remember I like trees.", model=CLOUD)

    watched, plain = calls
    assert watched["via"] == "direct" and not watched.get("tools")
    assert plain["via"] == "call_model" and plain["tools"] and any(t["function"]["name"] == "remember" for t in plain["tools"])


def with_the_capture_skill(tmp_path, monkeypatch):
    """Samantha carries the capture skill and may propose a note (the web app's call: `edits`)."""
    base = tmp_path / "profiles"
    write_persona(base, "samantha", f"name: Samantha\nvault_folders: []\nsympose_reference: false\nskills: ['{skills.CAPTURE}']\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))


def test_a_video_turn_is_given_the_capture_skill_and_the_videos_address_even_when_the_message_is_only_a_link(tmp_path, monkeypatch, calls):
    with_the_capture_skill(tmp_path, monkeypatch)
    sharing.set_approved(sharing.WEB, True)

    first = turn.run_turn("samantha", LINK, model=CLOUD, edits=True)
    turn.run_turn("samantha", "save that as a note", model=CLOUD, edits=True, session_id=first.session_id)  # the link is carried

    for sent in calls:
        content = sent["messages"][-1]["content"]
        assert f"Skill: {skills.CAPTURE}" in content and f"The video: {ADDRESS}" in content and WATCHING in content


def test_no_capture_skill_without_a_video_to_watch_or_a_way_to_show_a_proposal(tmp_path, monkeypatch, calls):
    with_the_capture_skill(tmp_path, monkeypatch)
    turn.run_turn("samantha", f"make a note from {LINK}", model=CLOUD, edits=True)  # `web` not allowed: nothing watched
    sharing.set_approved(sharing.WEB, True)
    turn.run_turn("samantha", f"make a note from {LINK}", model=LOCAL, edits=True)  # a model that cannot watch
    turn.run_turn("samantha", f"make a note from {LINK}", model=CLOUD)  # the terminal: nowhere to show a proposal

    assert all("Skill:" not in c["messages"][-1]["content"] for c in calls)


def filed_texts():
    return [p["text"] for e in note_changes_store.entries("samantha") for p in e["proposals"] if p.get("kind") == "create"]


def test_a_note_proposed_on_a_video_turn_has_its_timestamps_linked_by_the_tool_and_by_the_marker(monkeypatch):
    sharing.set_approved(sharing.WEB, True)
    stamped = "- [2:30] The first part"
    note = json.dumps({"title": "Talk", "text": f"# Talk\n\n{stamped}", "say": "Drafted."})
    answers = [ModelReply("", 5, tool_calls=(ToolCall("call_0", "propose_note", note),)), ModelReply("Drafted it.", 5)]
    monkeypatch.setattr(turn.gemini_direct, "call", lambda messages, model=None, **kwargs: answers.pop(0))

    turn.run_turn("samantha", f"make a note from {LINK}", model=CLOUD, edits=True)

    assert filed_texts() == [f"# Talk\n\n- [2:30]({ADDRESS}&t=150s) The first part"]  # one note so far, so its place does not matter

    # The model refuses tools on the first call, so the turn is run again with the marker instead.
    other = json.dumps({"title": "Talk two", "text": "# Talk two\n\n- [0:45] Another", "say": "Drafted."})
    refused = [EngineModelError("no tools"), ModelReply(f"Done. <!-- propose_note: {other} -->", 5)]

    def direct(messages, model=None, **kwargs):
        step = refused.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    monkeypatch.setattr(turn.gemini_direct, "call", direct)
    turn.run_turn("samantha", f"make another note from {LINK}", model=CLOUD, edits=True)

    assert len(filed_texts()) == 2 and any(f"- [0:45]({ADDRESS}&t=45s) Another" in text for text in filed_texts())
