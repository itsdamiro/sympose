"""A turn with a video link in it (docs/decisions/089): the model's maker watches it when the user has allowed `web`,
the call goes straight to Google, the persona is told what happened either way, and the record names it. The model
is a fake; the persona and settings are temporary."""

import json

import pytest
from helpers import write_persona

from sympose import note_changes_store, settings_store
from sympose.engine import captions, gemini_direct, memory, session, sharing, skills, tool_support, turn, web_access
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.model_tools import ToolCall
from sympose.engine.prompt_text import CAPTIONS, READING_PAGES, READING_SEARCH, WATCHING, WITHHELD_WEB

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


@pytest.fixture(autouse=True)
def words(monkeypatch):
    """The captions of the video: `words.raw` is what the library would give, an exception to raise one; `words.asked` the fetches."""
    class Fake:
        raw: object = ([(0.0, "Stress clouds thinking."), (30.0, "Sleep fixes it.")], "en", False)
        asked: list[str] = []

    Fake.asked = []

    def download(video, ipv6=False):
        Fake.asked.append(video)
        if isinstance(Fake.raw, Exception):
            raise Fake.raw
        return Fake.raw

    captions.forget()
    monkeypatch.setattr(captions, "_download", download)
    monkeypatch.setattr(captions, "GAP_SECONDS", 0)
    yield Fake
    captions.forget()


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
    monkeypatch.setattr(gemini_direct, "call", direct_way)
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


def test_the_off_setting_does_nothing_about_a_link(calls, words):
    settings_store.set(web_access.SETTING, web_access.OFF)
    sharing.set_approved(sharing.WEB, True)
    for model in (LOCAL, CLOUD):
        result = turn.run_turn("samantha", f"make notes from {LINK}", model=model)

    assert [c["via"] for c in calls] == ["call_model", "call_model"] and words.asked == []
    assert all(WATCHING not in c["messages"][-1]["content"] and CAPTIONS not in c["messages"][-1]["content"] for c in calls)
    assert result.withheld == []


def test_a_local_model_is_given_the_captions_in_place_of_the_video_and_nothing_goes_to_google(calls, words):
    result = turn.run_turn("samantha", f"make notes from {LINK}", model=LOCAL)

    (sent,) = calls
    content = sent["messages"][-1]["content"]
    assert sent["via"] == "call_model" and "links" not in sent and WATCHING not in content
    assert CAPTIONS in content and f"Video: {ADDRESS} (captions in en" in content and "[0:30] Sleep fixes it." in content
    assert content.index(CAPTIONS) < content.index("User's message:") and result.cloud == [] and result.withheld == []


def test_a_cloud_model_that_cannot_watch_is_given_the_captions_only_when_web_is_allowed(calls, words, monkeypatch):
    other = "openai/gpt-4o-mini"
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)
    turn.run_turn("samantha", f"summarize {LINK}", model=other)
    assert WITHHELD_WEB in calls[0]["messages"][-1]["content"] and words.asked == []

    sharing.set_approved(sharing.WEB, True)
    result = turn.run_turn("samantha", f"summarize {LINK}", model=other)

    assert CAPTIONS in calls[1]["messages"][-1]["content"] and result.cloud == [sharing.WEB]


def test_a_video_whose_captions_cannot_be_got_is_said_and_nothing_is_guessed(calls, words):
    words.raw = captions._Absent("the video has no captions")

    turn.run_turn("samantha", f"make notes from {LINK}", model=LOCAL)

    content = calls[0]["messages"][-1]["content"]
    assert "you could not get its captions" in content and f"{ADDRESS}: the video has no captions" in content
    assert CAPTIONS not in content and "Skill: capturing-from-a-link" not in content


def test_a_follow_up_gets_the_captions_again_without_fetching_them_again(calls, words):
    first = turn.run_turn("samantha", f"summarize {LINK}", model=LOCAL)

    turn.run_turn("samantha", "what about sleep?", session_id=first.session_id, model=LOCAL)

    assert all("[0:30] Sleep fixes it." in c["messages"][-1]["content"] for c in calls) and words.asked == ["8jPQjjsBbIc"]
    saved = session.history_as_messages(session.load_session("samantha", first.session_id))
    assert all("Sleep fixes it." not in m["content"] for m in saved)


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

    monkeypatch.setattr(gemini_direct, "call", direct)

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
    turn.run_turn("samantha", f"make a note from {LINK}", model=CLOUD)  # the terminal: nowhere to show a proposal

    assert all("Skill:" not in c["messages"][-1]["content"] for c in calls)


def test_a_turn_on_captions_is_given_the_capture_skill_and_the_videos_address_on_a_model_that_calls_tools(tmp_path, monkeypatch, calls):
    with_the_capture_skill(tmp_path, monkeypatch)
    sharing.set_approved(sharing.WEB, True)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    turn.run_turn("samantha", f"make a note from {LINK}", model="openai/gpt-4o-mini", edits=True)

    content = calls[0]["messages"][-1]["content"]
    assert f"Skill: {skills.CAPTURE}" in content and f"The video: {ADDRESS}" in content and CAPTIONS in content and WATCHING not in content


def test_a_video_with_no_captions_gets_no_capture_skill_and_a_cut_video_is_told_where_it_stops(tmp_path, monkeypatch, calls, words):
    with_the_capture_skill(tmp_path, monkeypatch)
    sharing.set_approved(sharing.WEB, True)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)
    words.raw = captions._Absent("the video has no captions")

    turn.run_turn("samantha", f"make a note from {LINK}", model="openai/gpt-4o-mini", edits=True)

    assert f"Skill: {skills.CAPTURE}" not in calls[0]["messages"][-1]["content"]


def test_a_long_video_is_cut_to_half_the_models_window_and_the_prompt_says_where_it_stops(calls, words):
    words.raw = ([(float(t), "word " * 20) for t in range(0, 7200, 10)], "en", False)

    turn.run_turn("samantha", f"summarize {LINK}", model=LOCAL)

    content = calls[0]["messages"][-1]["content"]
    assert "The captions stop at" in content and "of a video 1:59:50 long" in content
    assert len(content) < 4096 * captions.TOKEN_CHARS  # the window of this model, in characters


def test_a_turn_on_captions_is_not_given_remember_either(monkeypatch, calls):
    other = "openai/gpt-4o-mini"
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)
    sharing.set_approved(sharing.WEB, True)
    settings_store.set(memory.REMEMBER_SETTING, True)

    turn.run_turn("samantha", f"remember I like birds. {LINK}", model=other)
    turn.run_turn("samantha", "remember I like trees.", model=other)

    captioned, plain = calls
    assert not any(t["function"]["name"] == "remember" for t in captioned.get("tools") or [])
    assert any(t["function"]["name"] == "remember" for t in plain["tools"])


def filed_texts():
    return [p["text"] for e in note_changes_store.entries("samantha") for p in e["proposals"] if p.get("kind") == "create"]


def test_a_note_proposed_on_a_video_turn_has_its_timestamps_linked_by_the_tool_and_by_the_marker(monkeypatch):
    sharing.set_approved(sharing.WEB, True)
    stamped = "- [2:30] The first part"
    note = json.dumps({"title": "Talk", "text": f"# Talk\n\n{stamped}", "say": "Drafted."})
    answers = [ModelReply("", 5, tool_calls=(ToolCall("call_0", "propose_note", note),)), ModelReply("Drafted it.", 5)]
    monkeypatch.setattr(gemini_direct, "call", lambda messages, model=None, **kwargs: answers.pop(0))

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

    monkeypatch.setattr(gemini_direct, "call", direct)
    turn.run_turn("samantha", f"make another note from {LINK}", model=CLOUD, edits=True)

    assert len(filed_texts()) == 2 and any(f"- [0:45]({ADDRESS}&t=45s) Another" in text for text in filed_texts())


def test_when_google_will_not_take_the_video_the_captions_stand_in_and_the_turn_goes_on_the_ordinary_way(monkeypatch, calls, words):
    sharing.set_approved(sharing.WEB, True)

    def refused(messages, model=None, **kwargs):
        calls.append({"via": "direct", "messages": [dict(m) for m in messages], **kwargs})
        raise gemini_direct.WatchUnavailable("Gemini refused the request (400: nope)")

    monkeypatch.setattr(gemini_direct, "call", refused)

    result = turn.run_turn("samantha", f"summarize {LINK}", model=CLOUD)

    assert [c["via"] for c in calls] == ["direct", "call_model"]
    content = calls[1]["messages"][-1]["content"]
    assert WATCHING not in content and CAPTIONS in content and "[0:30] Sleep fixes it." in content
    assert result.reply == "From the text."


def test_when_google_will_not_take_the_video_and_there_are_no_captions_the_user_is_told_both(monkeypatch, calls, words):
    sharing.set_approved(sharing.WEB, True)
    words.raw = captions._Absent("the video has no captions")
    monkeypatch.setattr(gemini_direct, "call", lambda *a, **k: (_ for _ in ()).throw(gemini_direct.WatchUnavailable("no")))

    with pytest.raises(EngineModelError, match="would not take the video.*the video has no captions"):
        turn.run_turn("samantha", f"summarize {LINK}", model=CLOUD)


def test_any_other_trouble_with_google_is_not_met_with_the_captions(monkeypatch, calls, words):
    sharing.set_approved(sharing.WEB, True)
    monkeypatch.setattr(gemini_direct, "call", lambda *a, **k: (_ for _ in ()).throw(EngineModelError("Gemini refused the request (429: quota)")))

    with pytest.raises(EngineModelError, match="429"):
        turn.run_turn("samantha", f"summarize {LINK}", model=CLOUD)

    assert words.asked == [] and calls == []


PAGE = "https://example.com/post"


def test_an_allowed_page_link_goes_to_google_with_its_tool_and_the_persona_is_told_to_say_it_is_from_the_page(calls):
    sharing.set_approved(sharing.WEB, True)

    result = turn.run_turn("samantha", f"what does {PAGE} say?", model=CLOUD)

    (sent,) = calls
    assert sent["via"] == "direct" and sent["links"] == () and sent["server_tools"] == (web_access.PAGE_TOOL,)
    content = sent["messages"][-1]["content"]
    assert READING_PAGES in content and READING_SEARCH not in content and WATCHING not in content and WITHHELD_WEB not in content
    assert result.cloud == [sharing.WEB] and result.withheld == []


def test_a_page_link_the_user_has_not_allowed_is_not_read_and_the_persona_says_how_to_allow_it(calls):
    result = turn.run_turn("samantha", f"what does {PAGE} say?", model=CLOUD)

    (sent,) = calls
    assert sent["via"] == "call_model" and WITHHELD_WEB in sent["messages"][-1]["content"] and READING_PAGES not in sent["messages"][-1]["content"]
    assert result.withheld == [sharing.WEB]


def test_auto_searches_on_a_turn_with_no_link_and_says_what_the_web_is_not(calls):
    settings_store.set(web_access.SETTING, web_access.AUTO)
    sharing.set_approved(sharing.WEB, True)

    result = turn.run_turn("samantha", "what is new in python?", model=CLOUD)

    (sent,) = calls
    assert sent["via"] == "direct" and sent["server_tools"] == (web_access.SEARCH_TOOL, web_access.PAGE_TOOL)
    assert READING_SEARCH in sent["messages"][-1]["content"] and READING_PAGES not in sent["messages"][-1]["content"]
    assert result.cloud == [sharing.WEB]


def test_auto_without_the_users_approval_or_on_another_model_is_an_ordinary_turn_and_says_nothing_of_it(calls):
    settings_store.set(web_access.SETTING, web_access.AUTO)

    unapproved = turn.run_turn("samantha", "what is new in python?", model=CLOUD)
    local = turn.run_turn("samantha", "what is new in python?", model=LOCAL)

    assert [c["via"] for c in calls] == ["call_model", "call_model"]
    for sent in calls:
        assert READING_SEARCH not in sent["messages"][-1]["content"] and WITHHELD_WEB not in sent["messages"][-1]["content"]
    assert unapproved.withheld == [] and not local.cloud


def test_a_turn_that_searches_or_reads_a_page_is_not_given_remember(calls):
    sharing.set_approved(sharing.WEB, True)
    settings_store.set(memory.REMEMBER_SETTING, True)

    turn.run_turn("samantha", f"remember I like birds. {PAGE}", model=CLOUD)
    settings_store.set(web_access.SETTING, web_access.AUTO)
    turn.run_turn("samantha", "remember I like trees.", model=CLOUD)
    settings_store.set(web_access.SETTING, web_access.ASKED)
    turn.run_turn("samantha", "remember I like ferns.", model=CLOUD)

    page, searching, plain = calls
    assert page["via"] == "direct" and not page.get("tools")
    assert searching["via"] == "direct" and not searching.get("tools")
    assert plain["via"] == "call_model" and any(t["function"]["name"] == "remember" for t in plain["tools"])


def test_a_follow_up_about_a_page_reads_it_again_and_the_page_capture_skill_comes_with_the_pages_address(tmp_path, monkeypatch, calls):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", f"name: Samantha\nvault_folders: []\nsympose_reference: false\nskills: ['{skills.CAPTURE_PAGE}']\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    sharing.set_approved(sharing.WEB, True)

    first = turn.run_turn("samantha", PAGE, model=CLOUD, edits=True)
    turn.run_turn("samantha", "save that as a note", model=CLOUD, edits=True, session_id=first.session_id)

    for sent in calls:
        content = sent["messages"][-1]["content"]
        assert sent["server_tools"] == (web_access.PAGE_TOOL,)
        assert f"Skill: {skills.CAPTURE_PAGE}" in content and f"The page: {PAGE}" in content and "The video:" not in content
