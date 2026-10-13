"""A reply that says a note or a change was made when nothing was filed (docs/decisions/082): the claim is read from the
reply (the sentences are from real `gemma4:e4b` runs), a turn with tools asks the model once more, and a reply that
still says it, or one from a model without tools, is followed by one line. The model is a fake."""

import pytest
from helpers import write_persona

from sympose import note_changes_store as store
from sympose import settings_store
from sympose.engine import edit_mode, lookup, tool_support, turn, unfiled
from sympose.engine.edit_turn import Edit, OpenNote
from sympose.engine.model import ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma4:e4b"
NOTE = OpenNote("Garden plan.md", "I run three times a week.\n")
FILED = [{"tool": "propose_note", "saved": True}]


@pytest.mark.parametrize("reply", [
    "I've drafted it for you! This note is ready in the Recipes folder.",
    "Hey, I've drafted your pesto recipe into the Recipes folder.",
    "I went ahead and put together a proposal for a new note.",
    "Got it. The Mushroom Risotto Recipe is now added to the Recipes folder.",
    "I have added the note to your Recipes folder.",
    "Done: I updated the draft with the new time.",
])
def test_a_reply_that_says_a_note_was_made_is_read_as_the_claim(reply):
    assert unfiled.claims(reply)


@pytest.mark.parametrize("reply", [
    "I can draft a new note for the Recipes folder using the established format.",
    "I'll draft it as soon as you give me the servings.",
    "I can't write notes into your vault myself.",
    "I haven't drafted anything yet.",
    "Your risotto note is saved in Recipes, with 3 servings.",
    "I've added that to what I remember about you.",
    "I did not change the note.",
    "Mushroom risotto sounds lovely. How many does it serve?",
])
def test_a_reply_that_only_talks_or_promises_is_not_read_as_the_claim(reply):
    assert not unfiled.claims(reply)


def test_a_claim_is_unfiled_unless_a_proposal_was_filed_this_turn():
    said = "I've drafted it for you."
    assert unfiled.said_but_not_filed(said, [])
    assert unfiled.said_but_not_filed(said, [{"tool": "propose_note", "saved": False}, {"tool": "search_notes", "found": 2}])
    assert not unfiled.said_but_not_filed(said, FILED)
    assert not unfiled.said_but_not_filed(said, [{"tool": "propose_edit", "saved": True}])
    assert not unfiled.said_but_not_filed("I have proposed Ada.", [{"tool": "propose_persona", "saved": True}])
    assert not unfiled.said_but_not_filed("I have proposed the change.", [{"tool": "propose_setting", "saved": True}])


def test_the_recheck_names_only_the_tool_she_has_and_leaves_a_fine_reply_alone():
    no_note = unfiled.recheck(Edit(edit_mode.MANUAL, True))
    with_note = unfiled.recheck(Edit(edit_mode.MANUAL, True, note=NOTE))

    asked = no_note("I've drafted it.", [])
    assert "propose_note" in asked and "propose_edit" not in asked
    assert "propose_note or propose_edit" in with_note("I've drafted it.", [])
    assert "not part of the user's message" in asked and "Never mention this line" in asked
    assert no_note("How many does it serve?", []) is None and no_note("I've drafted it.", FILED) is None


def test_the_recheck_names_the_persona_and_setting_tools_when_she_proposes():
    proposes = unfiled.recheck(Edit(edit_mode.MANUAL, True, proposes=True))
    with_note = unfiled.recheck(Edit(edit_mode.MANUAL, True, note=NOTE, proposes=True))

    assert "propose_note, propose_persona or propose_setting" in proposes("I've proposed her.", [])
    assert "propose_note, propose_edit, propose_persona or propose_setting" in with_note("I've proposed her.", [])


def test_converse_asks_again_once_and_the_second_reply_is_the_answer():
    sent = []
    replies = [ModelReply("I've drafted it.", 1), ModelReply("", None, tool_calls=(ToolCall("c1", "propose_note", "{}"),)), ModelReply("Filed it.", 2)]

    def call(messages, **kwargs):
        sent.append(list(messages))
        return replies.pop(0)

    def run_tool(persona, model, name, raw):
        return lookup.lookup_tools.Result("Proposed.", lookup={"tool": name, "saved": True})

    done = lookup.converse({}, [{"role": "user", "content": "add it"}], LOCAL, None, call=call, tools=[], run_tool=run_tool, recheck=lambda reply, seen: "FILE IT" if "drafted" in reply else None)

    assert done.reply.text == "Filed it." and done.lookups == [{"tool": "propose_note", "saved": True}]
    assert sent[1] == [{"role": "user", "content": "add it\n\nFILE IT"}]  # on the user's own message, the first reply left out
    assert sent[0] == [{"role": "user", "content": "add it"}]  # the caller's message is not changed


def test_the_second_ask_counts_the_line_it_added_and_the_reply_only_when_that_reply_is_kept():
    def converse(messages, tools_first):
        replies = ([ModelReply("", None, tool_calls=(ToolCall("c1", "search_notes", "{}"),))] if tools_first else []) + [ModelReply("I've drafted it.", 1), ModelReply("ok", 2)]
        run_tool = lambda persona, model, name, raw: lookup.lookup_tools.Result("", lookup={"tool": name, "found": 0})  # noqa: E731
        return lookup.converse({}, messages, LOCAL, None, call=lambda m, **k: replies.pop(0), tools=[], run_tool=run_tool, recheck=lambda reply, seen: "FILE IT PLEASE" if "drafted" in reply else None)

    on_the_message = converse([{"role": "user", "content": "add it"}], tools_first=False).tokens_added
    after_tools = converse([{"role": "user", "content": "add it"}], tools_first=True).tokens_added

    assert on_the_message == lookup._tokens("FILE IT PLEASE", LOCAL) > 0
    assert after_tools > lookup._tokens("FILE IT PLEASE", LOCAL) + lookup._tokens("I've drafted it.", LOCAL) - 1


def test_converse_keeps_the_first_reply_and_adds_the_line_as_a_message_when_tools_ran_before_it():
    sent = []
    replies = [ModelReply("", None, tool_calls=(ToolCall("c1", "search_notes", "{}"),)), ModelReply("I've drafted it.", 1), ModelReply("Right: not filed.", 2)]

    def call(messages, **kwargs):
        sent.append(list(messages))
        return replies.pop(0)

    def run_tool(persona, model, name, raw):
        return lookup.lookup_tools.Result("Found 2.", lookup={"tool": name, "found": 2})

    done = lookup.converse({}, [{"role": "user", "content": "add it"}], LOCAL, None, call=call, tools=[], run_tool=run_tool, recheck=lambda reply, seen: "FILE IT" if "drafted" in reply else None)

    assert done.reply.text == "Right: not filed."
    assert sent[2][-2:] == [{"role": "assistant", "content": "I've drafted it."}, {"role": "user", "content": "FILE IT"}]
    assert sent[2][0] == {"role": "user", "content": "add it"}


def test_converse_asks_only_once_even_if_the_second_reply_says_it_again():
    calls = []

    def call(messages, **kwargs):
        calls.append(1)
        return ModelReply("I've drafted it.", 1)

    done = lookup.converse({}, [{"role": "user", "content": "x"}], LOCAL, None, call=call, tools=[], run_tool=None, recheck=lambda reply, seen: "again")

    assert len(calls) == 2 and done.reply.text == "I've drafted it."


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)
    settings_store.set(edit_mode.SETTING, edit_mode.MANUAL)


def model_that(monkeypatch, *replies):
    queue, seen = list(replies), []

    def call_model(messages, model=None, **kwargs):
        seen.append([dict(m) for m in messages])
        return queue.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def waiting():
    return [p for e in store.entries("samantha") for p in e["proposals"]]


def test_a_turn_with_tools_that_says_it_drafted_is_asked_again_and_files_it(scratch, monkeypatch):
    call = ToolCall("c1", "propose_note", '{"text": "# Risotto", "say": "A risotto."}')
    seen = model_that(monkeypatch, ModelReply("I've drafted it for you.", 1), ModelReply("", None, tool_calls=(call,)), ModelReply("Filed it; take a look.", 2))

    result = turn.run_turn("samantha", "add a risotto note", model=LOCAL, edits=True)

    assert result.reply == "Filed it; take a look." and len(waiting()) == 1 and len(seen) == 3
    second = seen[1]
    assert second[-1]["role"] == "user" and "propose_note" in second[-1]["content"] and "add a risotto note" in second[-1]["content"]
    assert not any("I've drafted it for you." in str(m["content"]) for m in second)  # the false reply is not shown again
    assert not any("Sympose, not part of" in str(m["content"]) for m in seen[0])


def test_a_reply_that_still_says_it_after_the_second_try_is_followed_by_the_line(scratch, monkeypatch):
    model_that(monkeypatch, ModelReply("I've drafted it for you.", 1), ModelReply("It is ready in your Recipes folder, I have added the note.", 2))

    result = turn.run_turn("samantha", "add a risotto note", model=LOCAL, edits=True)

    assert result.reply.endswith("\n\n" + unfiled.NOTHING_FILED) and waiting() == []


def test_a_model_without_tools_that_says_it_drafted_gets_the_line_with_no_second_call(scratch, monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)
    seen = model_that(monkeypatch, ModelReply("I've drafted it for you.", 1))

    result = turn.run_turn("samantha", "add a risotto note", model="ollama_chat/gemma2:9b", edits=True)

    assert result.reply == "I've drafted it for you.\n\n" + unfiled.NOTHING_FILED and len(seen) == 1


def test_a_plan_conversation_and_a_turn_that_asks_nothing_of_the_notes_are_left_alone(scratch, monkeypatch):
    settings_store.set(edit_mode.SETTING, edit_mode.PLAN)
    model_that(monkeypatch, ModelReply("I've drafted it for you.", 1))
    assert turn.run_turn("samantha", "add a note", model=LOCAL, edits=True).reply == "I've drafted it for you."

    model_that(monkeypatch, ModelReply("I've drafted it for you.", 1))
    assert turn.run_turn("samantha", "add a note", model=LOCAL).reply == "I've drafted it for you."  # the terminal asks for no edits
