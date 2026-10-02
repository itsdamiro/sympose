"""`past_chats` `ask` (docs/decisions/056): the two tools for earlier conversations, what they may open, what
a cloud model is not sent, how they compose with the other tools, and `run_turn` with them and without. The
model is a fake; the persona, conversations and settings are temporary."""

import json

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.cli import grounded_list
from sympose.engine import chat_tools, followup, past_chats, persona_tools, prompt, session, tool_support, turn
from sympose.engine.model import ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "anthropic/claude-sonnet-5"
NEW = "20260924T090000-aaaaaaaa"
OLD = "20260923T090000-bbbbbbbb"
OLDER = "20260922T090000-cccccccc"
PERSONA = {"handle": "samantha", "name": "Samantha"}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    (tmp_path / "vault").mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)
    monkeypatch.setattr(followup, "enabled", lambda: False)
    monkeypatch.setattr(past_chats, "_CACHE", {})
    settings_store.set("past_chats", "ask")
    settings_store.set("vault_lookup", "auto")


def _talk(sid, *pairs):
    for user, reply in pairs:
        session.append_turn("samantha", sid, user, reply)


def _atlas():
    _talk(OLD, ("I am choosing a database for Atlas", "I would pick SQLite for Atlas."), ("and the logo?", "Ask Lena."))


def model_that(monkeypatch, *replies):
    seen, queue = [], list(replies)

    def call_model(messages, model=None, **kwargs):
        seen.append({"messages": [dict(m) for m in messages], "model": model, **kwargs})
        return queue.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def asks(name, arguments, call_id="c1"):
    return ModelReply("", None, tool_calls=(ToolCall(call_id, name, arguments),))


# -- the tools --


def test_search_chats_gives_the_exchange_with_its_conversation_id_and_both_sides():
    _atlas()

    result = chat_tools.run("samantha", NEW, LOCAL, "search_chats", json.dumps({"query": "Atlas database"}))

    assert f"[id: {OLD}]" in result.text and "message 1" in result.text
    assert "User: I am choosing a database for Atlas" in result.text and "You: I would pick SQLite for Atlas." in result.text
    assert result.chats == [{**result.chats[0], "session": OLD, "turn": 1, "how": "searched"}]
    assert result.lookup == {"tool": "search_chats", "query": "Atlas database", "found": 1}


def test_a_search_needs_no_word_of_the_past_for_one_specific_word():
    _atlas()

    assert chat_tools.run("samantha", NEW, LOCAL, "search_chats", {"query": "Lena"}).chats[0]["turn"] == 2


def test_a_search_that_finds_nothing_says_so():
    _atlas()

    result = chat_tools.run("samantha", NEW, LOCAL, "search_chats", {"query": "quantum chromodynamics"})

    assert "found nothing in your earlier conversations" in result.text and result.chats == []
    assert result.lookup["found"] == 0


def test_a_search_never_reads_the_conversation_in_progress():
    _talk(NEW, ("the Atlas database", "SQLite."))

    assert chat_tools.run("samantha", NEW, LOCAL, "search_chats", {"query": "Atlas database"}).chats == []


def test_open_chat_gives_the_whole_conversation_in_order():
    _atlas()

    result = chat_tools.run("samantha", NEW, LOCAL, "open_chat", {"id": OLD})

    assert result.text.index("message 1") < result.text.index("message 2") and "Ask Lena." in result.text
    assert [(c["turn"], c["how"]) for c in result.chats] == [(1, "opened"), (2, "opened")]
    assert result.lookup == {"tool": "open_chat", "id": OLD, "found": 2}


@pytest.mark.parametrize("bad", ["../../etc/passwd", f"{OLD}.jsonl", "profiles/samantha/sessions/x", "nope", NEW])
def test_open_chat_takes_only_an_id_from_the_persona_own_list_and_never_the_current_one(bad):
    _atlas()
    _talk(NEW, ("current conversation text", "secret reply"))

    result = chat_tools.run("samantha", NEW, LOCAL, "open_chat", {"id": bad})

    assert "No earlier conversation" in result.text and "secret reply" not in result.text and result.chats == []


def test_open_chat_cannot_open_a_conversation_in_the_bin():
    import os

    _atlas()
    trash = os.path.join(session.sessions_dir("samantha"), ".trash")
    os.makedirs(trash)
    os.replace(session.session_path("samantha", OLD), os.path.join(trash, f"{OLD}.jsonl"))

    assert "No earlier conversation" in chat_tools.run("samantha", NEW, LOCAL, "open_chat", {"id": OLD}).text


def test_a_long_conversation_is_cut_with_a_marker_and_only_what_was_shown_is_recorded():
    _talk(OLD, *[(f"message {n} " + "x" * 2000, "reply " + "y" * 2000) for n in range(1, 8)])

    result = chat_tools.run("samantha", NEW, LOCAL, "open_chat", {"id": OLD})

    assert "The conversation continues" in result.text and len(result.text) < chat_tools.MAX_CHARS + 600
    assert 0 < len(result.chats) < 7


def test_unknown_tools_and_unreadable_arguments_are_results_not_errors():
    assert "no tool called nope" in chat_tools.run("samantha", NEW, LOCAL, "nope", {}).text
    assert "could not be read" in chat_tools.run("samantha", NEW, LOCAL, "search_chats", "{not json").text
    assert "could not be read" in chat_tools.run("samantha", NEW, LOCAL, "open_chat", {"id": 7}).text


def test_a_cloud_model_gets_the_conversation_only_when_chats_are_allowed():
    _atlas()

    held = chat_tools.run("samantha", NEW, CLOUD, "search_chats", {"query": "Atlas database"})
    assert "SQLite" not in held.text and "/share" in held.text and "never talked about it" in held.text
    assert held.chats == [] and held.withheld == {"chats": 1}
    opened = chat_tools.run("samantha", NEW, CLOUD, "open_chat", {"id": OLD})
    assert "Ask Lena" not in opened.text and opened.withheld == {"chats": 2}

    settings_store.set("cloud_share", ["chats"])
    assert "SQLite" in chat_tools.run("samantha", NEW, CLOUD, "search_chats", {"query": "Atlas database"}).text


# -- composing with the other tools --


def test_each_capability_runs_only_its_own_tools():
    _atlas()
    tools, run = persona_tools.for_turn(False, False, True, NEW)
    assert [t["function"]["name"] for t in tools] == ["search_chats", "open_chat"]
    assert "No note" not in run(PERSONA, LOCAL, "search_chats", {"query": "Atlas database"}).text
    assert "no tool called search_notes" in run(PERSONA, LOCAL, "search_notes", {"query": "x"}).text  # no vault tool by name

    tools, run = persona_tools.for_turn(True, False, False, NEW)
    assert "search_chats" not in [t["function"]["name"] for t in tools]
    assert "no tool called search_chats" in run(PERSONA, LOCAL, "search_chats", {"query": "Atlas"}).text
    assert persona_tools.for_turn(False, False, False) is None


def test_the_modes_say_what_was_chosen_and_what_the_model_can_do(monkeypatch):
    assert persona_tools.resolve(PERSONA, LOCAL).chats is True and persona_tools.resolve(PERSONA, LOCAL).chose_chats is True
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)
    monkeypatch.setattr(tool_support, "_ollama_says_tools", lambda model: None)
    modes = persona_tools.resolve(PERSONA, LOCAL)
    assert modes.chats is False and modes.chose_chats is True
    settings_store.set("past_chats", "auto")
    assert persona_tools.resolve(PERSONA, LOCAL).chose_chats is False


# -- a turn --


def test_ask_attaches_nothing_tells_her_about_the_tools_and_sends_them(monkeypatch):
    _atlas()
    seen = model_that(monkeypatch, ModelReply("Hello!", 5))

    result = turn.run_turn("samantha", "what did you say about the Atlas database last time?", session_id=NEW, model=LOCAL)

    system = seen[0]["messages"][0]["content"]
    assert prompt.CHAT_TOOLS_TEXT in system and prompt.CHATS_LABEL not in system and "SQLite" not in system
    assert [t["function"]["name"] for t in seen[0]["tools"]] == ["search_chats", "open_chat"]
    assert result.sent["chats_mode"] == "ask" and "chats" not in result.sent and result.sent["lookups"] == []
    assert "looked nothing up" in "\n".join(grounded_list.render(result.sent))


def test_a_search_reaches_the_reply_and_the_record_by_id_never_text(monkeypatch):
    _atlas()
    seen = model_that(
        monkeypatch, asks("search_chats", json.dumps({"query": "Atlas database"})), ModelReply("You said SQLite.", 5),
    )

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW, model=LOCAL)

    tool_message = seen[1]["messages"][-1]
    assert tool_message["role"] == "tool" and "I would pick SQLite for Atlas." in tool_message["content"]
    assert result.sent["chats"] == [{"session": OLD, "turn": 1, "how": "searched"}]
    assert result.sent["lookups"] == [{"tool": "search_chats", "query": "Atlas database", "found": 1}]
    assert "SQLite" not in json.dumps(result.sent) and result.reply == "You said SQLite."
    assert result.sent["chats_mode"] == "ask"


def test_a_model_that_cannot_call_tools_runs_auto_and_the_record_says_so(monkeypatch):
    _atlas()
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)
    monkeypatch.setattr(tool_support, "_ollama_says_tools", lambda model: None)
    seen = model_that(monkeypatch, ModelReply("ok", 5))

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW, model=LOCAL)

    assert "tools" not in seen[0] and "You: I would pick SQLite for Atlas." in seen[0]["messages"][0]["content"]
    assert prompt.CHAT_TOOLS_TEXT not in seen[0]["messages"][0]["content"]
    assert result.sent["chats_mode"] == "auto" and result.sent["chats"][0]["how"] == "auto"
    lines = grounded_list.render(result.sent)
    assert any("You chose ask for earlier conversations, but this model can't call tools" in line for line in lines)


def test_a_cloud_search_without_the_category_is_withheld_and_recorded_as_such(monkeypatch):
    _atlas()
    seen = model_that(monkeypatch, asks("search_chats", {"query": "Atlas database"}), ModelReply("I cannot use them.", 5))

    result = turn.run_turn("samantha", "what did you say about Atlas?", session_id=NEW, model=CLOUD)

    assert "SQLite" not in seen[1]["messages"][-1]["content"] and "/share" in seen[1]["messages"][-1]["content"]
    assert "chats" in result.withheld and "chats" not in result.cloud and "chats" not in result.sent


def test_the_grounded_list_reads_back_the_chat_lookups():
    sent = {
        "notes": [], "recaps": [], "searched": None, "history_dropped": 0, "rewrite": False, "chats_mode": "ask",
        "chats": [{"session": OLD, "turn": 1, "how": "searched"}],
        "lookups": [{"tool": "search_chats", "query": "Atlas", "found": 1}, {"tool": "open_chat", "id": OLD, "found": 2}],
    }

    text = "\n".join(grounded_list.render(sent))

    assert 'searched earlier conversations for "Atlas" (1 found)' in text and f'opened earlier conversation "{OLD}"' in text
    assert "1 exchange from earlier conversations" in text


def test_a_refused_first_call_runs_the_turn_again_as_auto_and_says_so(monkeypatch):
    from sympose.engine.model import EngineModelError

    _atlas()
    seen = []
    replies = [EngineModelError("tools are not supported"), ModelReply("ok", 5)]

    def call_model(messages, model=None, **kwargs):
        seen.append(kwargs)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW, model=LOCAL)

    assert seen[0].get("tools") and not seen[1].get("tools")
    assert result.sent["chats_mode"] == "auto" and result.sent["chats"][0]["how"] == "auto"
