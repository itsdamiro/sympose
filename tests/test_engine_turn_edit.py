"""`run_turn`'s edit tool (docs/decisions/072): a persona told the note open in the editor can propose changes to it,
as tool calls on a model that can call tools and as a marked block on one that cannot, in every mode but `plan`, and
only when the caller (the web app) asks for it. The model is a fake; the persona and settings are temporary."""

import pytest
from helpers import write_persona

from sympose import note_changes, settings_store
from sympose.engine import edit_mode, edit_tools, sharing, tool_support, turn
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
    sharing.set_approved(sharing.OPEN_NOTE, True)
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
    sharing.set_approved(sharing.OPEN_NOTE, True)
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


def test_a_cloud_model_is_not_sent_the_open_note_until_the_user_approves_it(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("I cannot see it.", 5))

    result = turn.run_turn("samantha", "make it four", model=CLOUD, open_note=NOTE)

    assert "three times" not in seen[0]["messages"][-1]["content"] and not waiting()
    assert result.sent["withheld"] == [sharing.OPEN_NOTE] and sharing.OPEN_NOTE not in result.sent["cloud"]


def test_an_approved_cloud_model_is_sent_the_open_note_and_the_turn_says_so(monkeypatch):
    sharing.set_approved(sharing.OPEN_NOTE, True)
    seen = model_that(monkeypatch, ModelReply("ok", 5), ModelReply("ok", 5))

    result = turn.run_turn("samantha", "make it four", model=CLOUD, open_note=NOTE)

    assert "three times" in seen[0]["messages"][-1]["content"]
    assert sharing.OPEN_NOTE in result.sent["cloud"] and result.sent["withheld"] == []


def test_a_comment_marker_in_a_turn_becomes_her_comment_on_the_open_note(monkeypatch):
    marker = '<!-- comment_on: {"find": "three times", "text": "Is that every week?"} -->'
    model_that(monkeypatch, ModelReply(f"One question.\n{marker}", 5))

    result = turn.run_turn("samantha", "what do you think?", model=LOCAL, open_note=NOTE)

    entry = store.read("samantha", NOTE.path)
    assert result.reply == "One question." and entry["annotations"][0]["author"] == "persona"
    assert result.lookups == [{"tool": "comment_on", "saved": True}]


def test_with_no_note_open_she_is_not_given_the_comment_tool(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("ok", 5))
    sharing.set_approved(sharing.OPEN_NOTE, True)

    turn.run_turn("samantha", "hi", model=CLOUD, edits=True)

    assert [t["function"]["name"] for t in seen[0]["tools"]] == ["propose_note"]


def test_the_users_open_comments_come_with_the_message_for_a_local_model(monkeypatch):
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="three times", text="Is that every week?", author="user")
    seen = model_that(monkeypatch, ModelReply("ok", 5))

    turn.run_turn("samantha", "any thoughts?", model=LOCAL, open_note=NOTE)

    assert "Is that every week?" in seen[0]["messages"][-1]["content"]


LONG = OpenNote("Garden plan.md", "# Garden\n\nIntro words.\n\n## Beds\n\nTomatoes by the fence.\nCarrots in the long bed.\n\n## Schedule\n\nWater every morning.\n")
POINTED = turn.edit_turn.Attached("Carrots in the long bed.")


def test_a_model_with_tools_gets_the_section_of_an_attached_passage_not_the_whole_note(monkeypatch):
    sharing.set_approved(sharing.OPEN_NOTE, True)
    seen = model_that(monkeypatch, ModelReply("ok", 5))

    turn.run_turn("samantha", "make this bold", model=CLOUD, open_note=LONG, attached=[POINTED])

    sent = seen[0]["messages"][-1]["content"]
    assert "Carrots in the long bed." in sent and "Tomatoes by the fence." in sent  # the section it is in
    assert "Water every morning." not in sent and "Intro words." not in sent  # not the rest
    assert "## Schedule" in sent  # but the headings are


def test_the_turn_record_counts_the_passages_attached_and_keeps_none_of_their_words(monkeypatch):
    model_that(monkeypatch, ModelReply("ok", 5), ModelReply("ok", 5))

    attached = turn.run_turn("samantha", "make this bold", model=LOCAL, open_note=LONG, attached=[POINTED, turn.edit_turn.Attached("Water every morning.")])
    plain = turn.run_turn("samantha", "hi", model=LOCAL, open_note=LONG)

    assert attached.sent["attached"] == 2 and "attached" not in plain.sent
    assert "Carrots" not in str(attached.sent)


def test_a_model_without_tools_gets_the_whole_note_whatever_is_attached(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("ok", 5))

    turn.run_turn("samantha", "make this bold", model=LOCAL, open_note=LONG, attached=[POINTED])

    assert "Water every morning." in seen[0]["messages"][-1]["content"]


def test_nothing_attached_or_an_attachment_not_in_the_note_sends_the_whole_note(monkeypatch):
    sharing.set_approved(sharing.OPEN_NOTE, True)
    seen = model_that(monkeypatch, ModelReply("ok", 5), ModelReply("ok", 5))

    turn.run_turn("samantha", "tidy", model=CLOUD, open_note=LONG)
    turn.run_turn("samantha", "tidy", model=CLOUD, open_note=LONG, attached=[turn.edit_turn.Attached("words that are not there")])

    assert all("Water every morning." in s["messages"][-1]["content"] for s in seen)


def test_an_attachment_does_not_change_which_note_her_changes_are_checked_against(monkeypatch):
    marker = '<!-- propose_edit: {"find": "Water every morning.", "replace": "Water at dawn.", "say": "Changed."} -->'
    model_that(monkeypatch, ModelReply(f"ok\n{marker}", 5))

    result = turn.run_turn("samantha", "change the schedule", model=LOCAL, open_note=LONG, attached=[POINTED])

    assert result.lookups == [{"tool": "propose_edit", "saved": True}]


def test_a_cloud_model_is_not_sent_the_comments_until_approved_and_the_turn_says_so(monkeypatch):
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="three times", text="Is that every week?", author="user")
    sharing.set_approved(sharing.OPEN_NOTE, True)
    seen = model_that(monkeypatch, ModelReply("ok", 5))

    result = turn.run_turn("samantha", "any thoughts?", model=CLOUD, open_note=NOTE)

    sent = seen[0]["messages"][-1]["content"]
    assert "Is that every week?" not in sent and "three times a week" in sent
    assert result.sent["withheld"] == [sharing.ANNOTATIONS]


def test_an_approved_cloud_model_gets_the_comments_and_the_record_names_the_category(monkeypatch):
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="three times", text="Is that every week?", author="user")
    sharing.set_approved(sharing.OPEN_NOTE, True)
    sharing.set_approved(sharing.ANNOTATIONS, True)
    seen = model_that(monkeypatch, ModelReply("ok", 5))

    result = turn.run_turn("samantha", "any thoughts?", model=CLOUD, open_note=NOTE)

    assert "Is that every week?" in seen[0]["messages"][-1]["content"]
    assert sharing.ANNOTATIONS in result.sent["cloud"] and result.sent["withheld"] == []


def test_the_second_message_of_a_conversation_says_which_comments_are_new_since_the_first(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("One", 5), ModelReply("Two", 5))
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="three times", text="Old doubt", author="user")

    first = turn.run_turn("samantha", "hello", model=LOCAL, open_note=NOTE, edits=True)
    monkeypatch.setattr(note_changes, "_now", lambda: "2999-01-01T00:00:00+00:00")  # after anything the first turn recorded
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="Pack charger", text="New doubt", author="user")
    turn.run_turn("samantha", "and now?", model=LOCAL, open_note=NOTE, edits=True, session_id=first.session_id)

    assert "since your last reply" not in seen[0]["messages"][-1]["content"]  # nothing to compare with yet
    second = seen[1]["messages"][-1]["content"]
    assert "On “Pack charger” (new since your last reply):" in second
    assert "On “three times” (from before your last reply):" in second


def test_the_label_is_relative_to_the_latest_message_not_the_first(monkeypatch):
    from datetime import datetime, timezone

    from sympose.engine import session

    clock = iter(f"2026-10-05T{hour}:00:00+00:00" for hour in ("10", "12", "14"))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(next(clock)).astimezone(tz or timezone.utc)

    monkeypatch.setattr(session, "datetime", Clock)
    seen = model_that(monkeypatch, ModelReply("One", 5), ModelReply("Two", 5), ModelReply("Three", 5))
    first = turn.run_turn("samantha", "hello", model=LOCAL, open_note=NOTE, edits=True)  # recorded at 10:00
    monkeypatch.setattr(note_changes, "_now", lambda: "2026-10-05T11:00:00+00:00")  # between messages one and two
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="three times", text="Asked between one and two", author="user")
    turn.run_turn("samantha", "second", model=LOCAL, open_note=NOTE, edits=True, session_id=first.session_id)  # 12:00
    turn.run_turn("samantha", "third", model=LOCAL, open_note=NOTE, edits=True, session_id=first.session_id)  # 14:00

    assert "(new since your last reply)" in seen[1]["messages"][-1]["content"]  # added after message one
    assert "(from before your last reply)" in seen[2]["messages"][-1]["content"]  # but not new at message three


def test_a_decision_on_her_comment_is_told_to_her_in_the_next_message_once(monkeypatch):
    from datetime import datetime, timezone

    from sympose.engine import session

    clock = iter(f"2026-10-05T{hour}:00:00+00:00" for hour in ("10", "12", "14"))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(next(clock)).astimezone(tz or timezone.utc)

    monkeypatch.setattr(session, "datetime", Clock)
    seen = model_that(monkeypatch, ModelReply("One", 5), ModelReply("Two", 5), ModelReply("Three", 5))
    note_changes.annotate("samantha", NOTE.path, NOTE.text, quote="three times", text="Is that right?", author="persona")
    root = store.read("samantha", NOTE.path)["annotations"][0]
    first = turn.run_turn("samantha", "hello", model=LOCAL, open_note=NOTE, edits=True)  # recorded at 10:00
    note_changes.reply("samantha", NOTE.path, root["id"], text="No, it is four.", author="user")
    monkeypatch.setattr(note_changes, "_now", lambda: "2026-10-05T11:00:00+00:00")  # between messages one and two
    note_changes.change_annotation("samantha", NOTE.path, root["id"], verdict=note_changes.DECLINED)
    turn.run_turn("samantha", "second", model=LOCAL, open_note=NOTE, edits=True, session_id=first.session_id)  # 12:00
    turn.run_turn("samantha", "third", model=LOCAL, open_note=NOTE, edits=True, session_id=first.session_id)  # 14:00

    assert "decided" not in seen[0]["messages"][-1]["content"]  # nothing to tell on the first message
    second = seen[1]["messages"][-1]["content"]
    assert "On “three times”: declined, the user wrote: No, it is four." in second
    assert "decided" not in seen[2]["messages"][-1]["content"]  # told once
