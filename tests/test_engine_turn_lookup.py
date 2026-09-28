"""`run_turn` when the persona looks up notes itself (docs/decisions/040): what each mode sends the model,
that `ask` never searches the vault before the reply, what the record keeps, and every way `ask` gives
way to `auto`. The model is a fake; the vault, persona and settings are temporary."""

import time

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import followup, session, tool_support, turn
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
ATLAS = "# Atlas\nWe chose SQLite for the Atlas prototype database."


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Projects").mkdir(parents=True)
    (vault / "Projects" / "Atlas.md").write_text(ATLAS)
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)
    settings_store.set("grounding_followups", "off")


def model_that(monkeypatch, *replies):
    """A model that answers with `replies` in turn (an exception is raised) and remembers each request."""
    seen: list[dict] = []
    queue = list(replies)

    def call_model(messages, model=None, **kwargs):
        seen.append({"messages": [dict(m) for m in messages], "model": model, **kwargs})
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def asks(name, arguments, call_id="c1"):
    return ModelReply("", None, tool_calls=(ToolCall(call_id, name, arguments),))


def no_auto_search(monkeypatch):
    def search(*args, **kwargs):
        raise AssertionError("the vault was searched for the message")

    monkeypatch.setattr(followup, "ground", search)


def test_auto_is_the_default_and_sends_no_tools(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("hi", 5))

    result = turn.run_turn("samantha", "tell me about the Atlas database", model=LOCAL)

    assert "tools" not in seen[0] and "search_notes" not in seen[0]["messages"][0]["content"]
    assert "SQLite" in seen[0]["messages"][-1]["content"]  # the notes were searched for and attached
    assert result.lookups == [] and "mode" not in result.sent and "lookups" not in result.sent


def test_ask_does_not_search_the_vault_for_the_message_and_says_how_the_persona_works(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    no_auto_search(monkeypatch)
    seen = model_that(monkeypatch, ModelReply("Hello!", 5))

    result = turn.run_turn("samantha", "tell me about the Atlas database", model=LOCAL)

    system, user = seen[0]["messages"][0]["content"], seen[0]["messages"][-1]["content"]
    assert "search_notes" in system and "open_note" in system and "Sympose does not search" in system
    assert "the search is automatic" not in system and "SQLite" not in user
    assert "Notes found in the vault" not in user and "No notes in the vault matched" not in user
    assert user.endswith("User's message: tell me about the Atlas database")
    assert seen[0]["tools"] and result.reply == "Hello!" and result.lookups == []
    assert result.sent["mode"] == "ask" and result.sent["lookups"] == [] and result.sent["rewrite"] is False


def test_a_lookup_reaches_the_reply_the_header_and_the_record(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    no_auto_search(monkeypatch)
    seen = model_that(monkeypatch, asks("search_notes", '{"query": "Atlas database"}'), ModelReply("SQLite, per Atlas.", 40))

    result = turn.run_turn("samantha", "tell me about the Atlas database", model=LOCAL)

    assert len(seen) == 2 and "SQLite" in seen[1]["messages"][-1]["content"]
    assert result.reply == "SQLite, per Atlas."
    assert result.lookups == [{"tool": "search_notes", "query": "Atlas database", "found": 1}]
    assert [hit["rel_path"] for hit in result.grounding] == ["Projects/Atlas.md"]
    assert result.sent["mode"] == "ask" and result.sent["lookups"] == result.lookups
    assert [n["path"] for n in result.sent["notes"]] == ["Projects/Atlas.md"]
    assert "SQLite" not in str(result.sent)  # the record keeps paths, never text
    assert result.ttft_ms is not None and result.ttft_ms >= 40
    saved = session.load_session("samantha", result.session_id)
    assert saved["turns"][-1]["assistant"] == "SQLite, per Atlas." and saved["turns"][-1]["sent"]["mode"] == "ask"


def test_the_lookups_are_not_part_of_the_history_the_next_turn_is_sent(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    seen = model_that(
        monkeypatch, asks("search_notes", '{"query": "Atlas"}'), ModelReply("SQLite.", 5), ModelReply("Anything else?", 5)
    )
    first = turn.run_turn("samantha", "what did we choose for Atlas?", model=LOCAL)

    turn.run_turn("samantha", "thanks", session_id=first.session_id, model=LOCAL)

    history = seen[2]["messages"][1:-1]
    assert [m["role"] for m in history] == ["user", "assistant"] and "tool" not in str(history).lower()
    assert "SQLite" not in history[0]["content"]


def test_a_model_that_cannot_call_tools_runs_auto_and_the_record_says_so(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)
    seen = model_that(monkeypatch, ModelReply("hi", 5))

    result = turn.run_turn("samantha", "tell me about the Atlas database", model=LOCAL)

    assert "tools" not in seen[0] and "SQLite" in seen[0]["messages"][-1]["content"]
    assert result.sent["mode"] == "auto" and result.sent["lookups"] == []


def test_a_persona_with_no_vault_is_given_no_tools(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    monkeypatch.delenv("VAULT_PATHS")
    seen = model_that(monkeypatch, ModelReply("hi", 5))

    result = turn.run_turn("samantha", "hello", model=LOCAL)

    assert "tools" not in seen[0]
    assert "mode" not in result.sent  # neither the model nor the setting is why nothing was looked up


def test_a_model_that_refuses_the_tools_is_run_as_auto_and_after_two_in_a_row_not_asked_again(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    seen = model_that(
        monkeypatch,
        EngineModelError("does not support tools"), ModelReply("from notes", 5),  # turn 1: refused, then auto
        EngineModelError("does not support tools"), ModelReply("again", 5),  # turn 2: refused again, then auto
        ModelReply("no tools now", 5),  # turn 3: not asked to use them
    )

    first = turn.run_turn("samantha", "tell me about the Atlas database", model=LOCAL)
    second = turn.run_turn("samantha", "and now?", session_id=first.session_id, model=LOCAL)
    third = turn.run_turn("samantha", "and now?", session_id=first.session_id, model=LOCAL)

    assert first.reply == "from notes" and "tools" not in seen[1] and "SQLite" in seen[1]["messages"][-1]["content"]
    assert first.sent["mode"] == "auto" and "tools" in seen[2]  # one failure does not take the option away
    assert "tools" not in seen[4] and third.sent["mode"] == "auto"  # two in a row does
    assert second.reply == "again"
    assert session.load_session("samantha", first.session_id)["turns"][0]["assistant"] == "from notes"


def test_one_refusal_between_turns_that_worked_never_takes_the_option_away(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    seen = model_that(
        monkeypatch,
        EngineModelError("rate limited"), ModelReply("auto", 5),  # a hiccup
        ModelReply("worked", 5),  # tools work: the strike is gone
        EngineModelError("rate limited"), ModelReply("auto", 5),  # another hiccup
        ModelReply("worked again", 5),
    )
    sid = None
    for message in ("one", "two", "three"):
        sid = turn.run_turn("samantha", message, session_id=sid, model=LOCAL).session_id
    result = turn.run_turn("samantha", "four", session_id=sid, model=LOCAL)

    assert "tools" in seen[-1] and result.reply == "worked again" and tool_support.can_call_tools(LOCAL)


def test_when_auto_fails_too_the_error_is_the_users_and_the_model_is_not_marked(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    model_that(monkeypatch, EngineModelError("no route"), EngineModelError("no route either"))

    with pytest.raises(EngineModelError, match="no route either"):
        turn.run_turn("samantha", "hello", model=LOCAL)

    assert tool_support.can_call_tools(LOCAL) is True


def test_a_failure_after_a_tool_ran_is_not_taken_for_a_refusal_of_tools(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    seen = model_that(monkeypatch, asks("search_notes", '{"query": "Atlas"}'), EngineModelError("connection dropped"))

    with pytest.raises(EngineModelError, match="connection dropped"):
        turn.run_turn("samantha", "what did we choose?", model=LOCAL)

    assert len(seen) == 2 and tool_support.can_call_tools(LOCAL) is True


def test_a_cloud_model_is_told_what_was_held_back_and_the_turn_says_so(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    seen = model_that(monkeypatch, asks("search_notes", '{"query": "Atlas database"}'), ModelReply("I can't use them.", 5))

    result = turn.run_turn("samantha", "tell me about the Atlas database", model=CLOUD)

    tool_result = seen[1]["messages"][-1]["content"]
    assert "SQLite" not in tool_result and "/share" in tool_result
    assert "SQLite" not in str(seen)
    assert "notes" in result.withheld and result.grounding == [] and result.sent["mode"] == "ask"


def test_a_cloud_model_gets_what_the_user_approved_and_the_turn_says_it_was_sent(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    settings_store.set("cloud_share", ["notes"])
    seen = model_that(monkeypatch, asks("search_notes", '{"query": "Atlas database"}'), ModelReply("SQLite.", 5))

    result = turn.run_turn("samantha", "tell me about the Atlas database", model=CLOUD)

    assert "SQLite" in seen[1]["messages"][-1]["content"]
    assert "notes" in result.cloud and "notes" not in result.withheld


def test_the_tool_result_counts_in_the_context_the_meter_shows(tmp_path, monkeypatch):
    (tmp_path / "vault" / "Long.md").write_text("word " * 400)
    monkeypatch.setattr(turn.budget, "budget_for", lambda model: turn.budget.Budget(9000, None, None))
    model_that(monkeypatch, ModelReply("hi", 5))
    plain = turn.run_turn("samantha", "hello there", model=LOCAL).context_used
    settings_store.set("vault_lookup", "ask")
    model_that(monkeypatch, asks("open_note", '{"path": "Long"}'), ModelReply("hi", 5))

    asked = turn.run_turn("samantha", "hello there", model=LOCAL).context_used

    assert asked - plain > 300  # the note the persona read now counts, which the conversation had not held


def test_the_time_to_first_token_includes_the_rounds_before_the_reply(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    replies = [asks("search_notes", '{"query": "Atlas"}'), ModelReply("SQLite.", 40)]

    def slow_model(messages, model=None, **kwargs):
        time.sleep(0.06)
        return replies.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", slow_model)

    result = turn.run_turn("samantha", "what did we choose for Atlas?", model=LOCAL)

    assert result.ttft_ms >= 60 + 40
