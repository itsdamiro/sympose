"""A turn with a file attached (docs/decisions/089, `media`): the model's maker reads it when the user has allowed
`media`, the call goes straight to Google, the persona is told what happened either way, the record names the category
and holds none of the bytes. The model is a fake; the persona and settings are temporary."""

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import gemini_direct, media, memory, session, sharing, skills, tool_support, turn, web_access
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.prompt_text import ATTACHED_FILES, UNSUPPORTED_FILES, WITHHELD_FILES

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
PDF = media.make("paper.pdf", b"%PDF-1.4 the secret is blue")


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)
    monkeypatch.setattr(media, "_held", {})


@pytest.fixture
def calls(monkeypatch):
    """Both ways of calling a model, recording what each was given."""
    seen: list[dict] = []

    def litellm_way(messages, model=None, **kwargs):
        seen.append({"via": "call_model", "messages": [dict(m) for m in messages], **kwargs})
        return ModelReply("From the text.", 5)

    def direct_way(messages, model=None, **kwargs):
        seen.append({"via": "direct", "messages": [dict(m) for m in messages], **kwargs})
        return ModelReply("From the file.", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", litellm_way)
    monkeypatch.setattr(gemini_direct, "call", direct_way)
    return seen


def content_of(call):
    return call["messages"][-1]["content"]


def test_an_allowed_file_goes_to_google_inside_the_request_and_the_persona_is_told_it_is_attached(calls):
    sharing.set_approved(sharing.MEDIA, True)

    result = turn.run_turn("samantha", "what does [attached: paper.pdf] say?", model=CLOUD, files=(PDF,))

    (sent,) = calls
    assert sent["via"] == "direct" and sent["files"] == (PDF,)
    assert ATTACHED_FILES.format(names="paper.pdf") in content_of(sent) and WITHHELD_FILES.format(names="paper.pdf") not in content_of(sent)
    assert result.reply == "From the file." and result.cloud == [sharing.MEDIA] and result.withheld == []
    assert result.sent["cloud"] == [sharing.MEDIA]


def test_a_file_the_user_has_not_allowed_is_not_sent_and_the_persona_says_how_to_allow_it(calls):
    result = turn.run_turn("samantha", "what does [attached: paper.pdf] say?", model=CLOUD, files=(PDF,))

    (sent,) = calls
    assert sent["via"] == "call_model" and "files" not in sent
    assert WITHHELD_FILES.format(names="paper.pdf") in content_of(sent)
    assert result.cloud == [] and result.withheld == [sharing.MEDIA]


def test_a_local_model_is_told_it_cannot_read_files_and_nothing_is_reported_as_withheld(calls):
    sharing.set_approved(sharing.MEDIA, True)

    result = turn.run_turn("samantha", "what does [attached: paper.pdf] say?", model=LOCAL, files=(PDF,))

    (sent,) = calls
    assert sent["via"] == "call_model" and UNSUPPORTED_FILES.format(names="paper.pdf") in content_of(sent)
    assert result.cloud == [] and result.withheld == []


def test_the_record_keeps_the_words_and_none_of_the_bytes(calls, tmp_path):
    sharing.set_approved(sharing.MEDIA, True)

    first = turn.run_turn("samantha", "what does [attached: paper.pdf] say?", model=CLOUD, files=(PDF,))

    saved = session.history_as_messages(session.load_session("samantha", first.session_id))
    assert [m["content"] for m in saved if m["role"] == "user"] == ["what does [attached: paper.pdf] say?"]
    leaked = [p for p in tmp_path.rglob("*") if p.is_file() and b"the secret is blue" in p.read_bytes()]
    assert leaked == []


def test_a_follow_up_is_sent_the_file_again_for_five_messages_and_then_not(calls):
    sharing.set_approved(sharing.MEDIA, True)
    first = turn.run_turn("samantha", "read [attached: paper.pdf]", model=CLOUD, files=(PDF,))

    for n in range(media.CARRY_TURNS + 1):
        turn.run_turn("samantha", f"question {n}", session_id=first.session_id, model=CLOUD)

    assert [c["via"] for c in calls] == ["direct"] * (media.CARRY_TURNS + 1) + ["call_model"]
    assert all(c["files"] == (PDF,) for c in calls[:-1])
    assert ATTACHED_FILES.format(names="paper.pdf") in content_of(calls[1])


def test_a_new_conversation_does_not_get_the_file_of_another(calls):
    sharing.set_approved(sharing.MEDIA, True)
    turn.run_turn("samantha", "read [attached: paper.pdf]", model=CLOUD, files=(PDF,))

    turn.run_turn("samantha", "hello", model=CLOUD)

    assert calls[1]["via"] == "call_model"


def test_the_web_access_knob_does_not_decide_about_files(calls):
    settings_store.set(web_access.SETTING, web_access.OFF)
    sharing.set_approved(sharing.MEDIA, True)

    turn.run_turn("samantha", "read it", model=CLOUD, files=(PDF,))

    assert calls[0]["via"] == "direct" and calls[0]["files"] == (PDF,)


def test_a_turn_with_a_file_is_not_given_remember_so_the_file_cannot_steer_a_write_to_her_memory(calls):
    sharing.set_approved(sharing.MEDIA, True)
    settings_store.set(memory.REMEMBER_SETTING, True)

    turn.run_turn("samantha", "remember I like birds. [attached: paper.pdf]", model=CLOUD, files=(PDF,))
    turn.run_turn("samantha", "remember I like trees.", model=CLOUD)

    with_file, plain = calls
    assert with_file["via"] == "direct" and not with_file.get("tools")
    assert plain["via"] == "call_model" and any(t["function"]["name"] == "remember" for t in plain["tools"])


def test_a_file_is_not_held_for_later_when_google_refuses_it(monkeypatch, calls):
    sharing.set_approved(sharing.MEDIA, True)

    def refuse(messages, model=None, **kwargs):
        raise EngineModelError("Gemini refused the attached file (400: no pages)")

    monkeypatch.setattr(gemini_direct, "call", refuse)
    with pytest.raises(EngineModelError):
        turn.run_turn("samantha", "read it", model=CLOUD, files=(PDF,))

    assert media.plan(CLOUD, "samantha", "any", ()) == media.Plan() and media._held == {}


def with_the_file_skill(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", f"name: Samantha\nvault_folders: []\nsympose_reference: false\nskills: ['{skills.CAPTURE_FILE}']\n")


def test_the_file_capture_skill_is_given_to_a_turn_with_a_file_and_names_it_as_the_source(tmp_path, monkeypatch, calls):
    with_the_file_skill(tmp_path, monkeypatch)
    sharing.set_approved(sharing.MEDIA, True)

    turn.run_turn("samantha", "make study notes from [attached: paper.pdf]", model=CLOUD, files=(PDF,), edits=True)

    content = content_of(calls[0])
    assert f"Skill: {skills.CAPTURE_FILE}" in content and "The file: paper.pdf (type: pdf note)" in content
    assert "The video:" not in content and "The page:" not in content


def test_no_file_skill_on_a_turn_without_a_file_or_with_a_file_that_was_not_sent(tmp_path, monkeypatch, calls):
    with_the_file_skill(tmp_path, monkeypatch)

    turn.run_turn("samantha", "make study notes from [attached: paper.pdf]", model=CLOUD, files=(PDF,), edits=True)
    turn.run_turn("samantha", "make study notes", model=CLOUD, edits=True)

    assert all("Skill: capturing-from-a-file" not in content_of(c) for c in calls)


def test_a_refused_video_with_a_file_beside_it_is_an_error_not_a_quiet_fall_back_to_captions_that_drops_the_file(monkeypatch):
    from sympose.engine import captions, watch_call

    def refuse(messages, **kwargs):
        raise gemini_direct.WatchUnavailable("Gemini refused the request (400: no)")

    monkeypatch.setattr(gemini_direct, "call", refuse)
    monkeypatch.setattr(captions, "fetch", lambda *a, **k: pytest.fail("fell back to captions with a file attached"))
    call = watch_call.for_links(("https://www.youtube.com/watch?v=8jPQjjsBbIc",), files=(PDF,))

    with pytest.raises(EngineModelError, match="would not take the video or the attached file"):
        call([{"role": "user", "content": "hi"}])


def test_once_the_five_messages_are_used_up_the_persona_is_told_the_file_is_no_longer_attached(calls):
    sharing.set_approved(sharing.MEDIA, True)
    first = turn.run_turn("samantha", "read [attached: paper.pdf]", model=CLOUD, files=(PDF,))

    for n in range(media.CARRY_TURNS + 1):
        turn.run_turn("samantha", f"question {n}", session_id=first.session_id, model=CLOUD)

    carried, last = calls[1:-1], calls[-1]
    assert all("no longer attached" not in content_of(c) for c in carried)
    assert last["via"] == "call_model" and "paper.pdf" in content_of(last) and "no longer attached" in content_of(last)


def test_deleting_a_conversation_lets_go_of_its_files(calls):
    from sympose.engine import session_manage

    sharing.set_approved(sharing.MEDIA, True)
    first = turn.run_turn("samantha", "read [attached: paper.pdf]", model=CLOUD, files=(PDF,))
    assert media.plan(CLOUD, "samantha", first.session_id, ()).names == ("paper.pdf",)

    assert session_manage.delete("samantha", first.session_id) == session_manage.OK

    assert media.plan(CLOUD, "samantha", first.session_id, ()) == media.Plan()
