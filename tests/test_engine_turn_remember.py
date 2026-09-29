"""`run_turn`'s `remember` mechanism (docs/decisions/041): a `remember` tool on a model that can
call tools, an inline marker on one that can't, both independent of `vault_lookup`'s own setting
and gated by `memory_remember`, a setting the user controls rather than something inferred from
what a model happens to be capable of. The model is a fake; the persona and settings are temporary."""

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import memory, memory_tools, tool_support, turn
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\nvault_folders: []\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.delenv("VAULT_PATHS", raising=False)  # remember does not need a vault
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    # CLOUD can call tools, LOCAL can't -- so a model's own capability, not its identity, picks
    # the mechanism (docs/decisions/041's "how", never "if").
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)
    return directory


def model_that(monkeypatch, *replies):
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


def test_remember_off_by_default_teaches_nothing_and_sends_no_tool(monkeypatch):
    seen = model_that(monkeypatch, ModelReply("Hi!", 5))

    result = turn.run_turn("samantha", "hello", model=CLOUD)

    assert "tools" not in seen[0]
    assert "say plainly that you can't do that yet" in seen[0]["messages"][0]["content"]
    assert "lookups" not in result.sent


def test_remember_on_with_a_tool_calling_model_gives_the_tool_and_writes_on_use(monkeypatch):
    settings_store.set(memory.REMEMBER_SETTING, True)
    seen = model_that(monkeypatch, asks("remember", '{"text": "Likes dark mode"}'), ModelReply("Got it!", 5))

    result = turn.run_turn("samantha", "remember that I like dark mode", model=CLOUD)

    assert seen[0]["tools"] == memory_tools.TOOLS
    assert result.reply == "Got it!"
    assert result.lookups == [{"tool": "remember", "saved": True}]
    assert result.sent["lookups"] == result.lookups and "mode" not in result.sent  # no vault_lookup chosen
    [entry] = memory.decisions("samantha")
    assert entry.endswith("Likes dark mode")


def test_remember_on_with_a_model_that_cant_call_tools_uses_the_marker_instead(monkeypatch):
    settings_store.set(memory.REMEMBER_SETTING, True)
    seen = model_that(monkeypatch, ModelReply("Got it!\n<!-- remember: Likes dark mode -->", 5))

    result = turn.run_turn("samantha", "remember that I like dark mode", model=LOCAL)

    assert "tools" not in seen[0]
    assert "<!-- remember:" in seen[0]["messages"][0]["content"]  # she was taught the marker
    assert result.reply == "Got it!"  # the marker never reaches the user
    assert result.lookups == [{"tool": "remember", "saved": True}]
    [entry] = memory.decisions("samantha")
    assert entry.endswith("Likes dark mode")


def test_the_marker_is_stripped_from_what_the_session_keeps_too(monkeypatch):
    settings_store.set(memory.REMEMBER_SETTING, True)
    model_that(monkeypatch, ModelReply("Got it!\n<!-- remember: Likes dark mode -->", 5))

    result = turn.run_turn("samantha", "remember that I like dark mode", model=LOCAL)

    from sympose.engine import session

    saved = session.load_session("samantha", result.session_id)
    assert saved["turns"][0]["assistant"] == "Got it!"


def test_a_reply_with_no_marker_writes_nothing(monkeypatch):
    settings_store.set(memory.REMEMBER_SETTING, True)
    model_that(monkeypatch, ModelReply("Just chatting.", 5))

    result = turn.run_turn("samantha", "hello", model=LOCAL)

    assert result.reply == "Just chatting." and result.lookups == []
    assert memory.decisions("samantha") == []


def test_a_model_that_refuses_the_remember_tool_falls_back_to_the_marker_the_same_turn(monkeypatch):
    settings_store.set(memory.REMEMBER_SETTING, True)
    seen = model_that(
        monkeypatch,
        EngineModelError("does not support tools"),
        ModelReply("hi anyway\n<!-- remember: Likes dark mode -->", 5),
    )

    result = turn.run_turn("samantha", "remember that I like dark mode", model=CLOUD)

    assert "tools" in seen[0] and "tools" not in seen[1]
    assert "<!-- remember:" in seen[1]["messages"][0]["content"]  # taught the marker on the retry
    assert result.reply == "hi anyway"  # the marker never reaches the user
    assert result.lookups == [{"tool": "remember", "saved": True}]
    [entry] = memory.decisions("samantha")
    assert entry.endswith("Likes dark mode")
    assert tool_support.can_call_tools(CLOUD) is True  # one failure does not take the option away
