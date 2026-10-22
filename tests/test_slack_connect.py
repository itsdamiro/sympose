"""What the Slack connection does with events, replies and start-up (docs/decisions/093). Slack's library is not used here:
the listeners are called the way it calls them, and `connect` is replaced."""

from types import SimpleNamespace

import pytest
from helpers import write_persona
from slack_shapes import BOT, OWNER, dm, mention

from sympose import settings_store, slack_approval, slack_channel, slack_connect, slack_credentials, slack_heartbeat
from sympose.engine import turn
from sympose.engine.turn_result import TurnResult


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nmodel: ollama_chat/gemma4:e4b\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv(slack_credentials.OWNER_VARIABLE, OWNER)
    for name in ("SLACK_SAMANTHA_BOT_TOKEN", "SLACK_SAMANTHA_APP_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    settings_store.set(slack_approval.SETTING, True)
    monkeypatch.setattr(turn, "run_turn", lambda handle, message, session_id=None, **_: TurnResult(reply=f"re: {message}", session_id=session_id))
    return base


class Say:
    def __init__(self):
        self.sent = []

    def __call__(self, **kwargs):
        self.sent.append(kwargs)


def test_a_message_is_answered_in_the_channel_it_came_from(home):
    on_event, _ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(dm("hi"), say)
    assert say.sent == [{"text": "re: hi", "thread_ts": None}]


def test_a_mention_is_answered_in_its_thread(home):
    on_event, _ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(mention(ts="5.5"), say)
    assert say.sent[0]["thread_ts"] == "5.5"


def test_an_event_that_is_not_a_message_says_nothing(home):
    on_event, _ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event({"event": {"type": "reaction_added"}}, say)
    on_event(dm(bot_id="B1"), say)
    assert say.sent == []


def test_an_event_that_is_not_a_message_is_ignored_without_an_error(home, caplog):
    on_event, _ = slack_connect.listeners("samantha", BOT)
    on_event({"event": {"type": "reaction_added"}}, Say())
    assert caplog.records == []


def test_a_redelivery_is_answered_once(home):
    on_event, _ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(dm("hi"), say)
    on_event(dm("hi"), say)
    assert len(say.sent) == 1


def test_a_failure_in_the_answer_does_not_escape_the_listener(home, monkeypatch):
    def broken(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(slack_channel, "answer", broken)
    on_event, _ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(dm("hi"), say)
    assert say.sent == []


def test_slash_new_is_acknowledged_and_answered_to_the_owner(home):
    _, on_new = slack_connect.listeners("samantha", BOT)
    acked, said = [], []
    on_new(lambda: acked.append(True), {"user_id": OWNER, "channel_id": "D0DM"}, said.append)
    assert acked and said == ["New conversation."]


def test_slash_new_from_a_stranger_is_acknowledged_and_unanswered(home):
    _, on_new = slack_connect.listeners("samantha", BOT)
    acked, said = [], []
    on_new(lambda: acked.append(True), {"user_id": "U0STRANGER", "channel_id": "D0DM"}, said.append)
    assert acked and said == []


# --- start-up -----------------------------------------------------------------------------------
class _Client:
    def is_connected(self):
        return True


class Handler:
    closed = False
    client = _Client()

    def close(self):
        self.closed = True


def _both(monkeypatch, handle):
    monkeypatch.setenv(f"SLACK_{handle.upper()}_BOT_TOKEN", "xoxb-1")
    monkeypatch.setenv(f"SLACK_{handle.upper()}_APP_TOKEN", "xapp-1")


class _Stop:
    """Stands in for `threading.Event` so `run` returns instead of waiting for Ctrl-C."""
    def wait(self):
        raise KeyboardInterrupt


def test_each_persona_with_tokens_is_connected_and_the_others_are_not(home, monkeypatch, capsys):
    write_persona(home, "archia", "name: Archia\n")
    _both(monkeypatch, "samantha")
    opened = []
    monkeypatch.setattr(slack_connect, "connect", lambda handle, bot, app: opened.append((handle, bot, app)) or Handler())
    monkeypatch.setattr(slack_connect, "threading", SimpleNamespace(Event=_Stop))
    assert slack_connect.run() == 0
    assert opened == [("samantha", "xoxb-1", "xapp-1")]
    assert "samantha is in Slack" in capsys.readouterr().out


def test_a_persona_slack_refuses_does_not_stop_the_others(home, monkeypatch, capsys):
    write_persona(home, "archia", "name: Archia\n")
    _both(monkeypatch, "samantha")
    _both(monkeypatch, "archia")

    def connect(handle, bot, app):
        if handle == "archia":
            raise RuntimeError("invalid_auth")
        return Handler()

    monkeypatch.setattr(slack_connect, "connect", connect)
    monkeypatch.setattr(slack_connect, "threading", SimpleNamespace(Event=_Stop))
    assert slack_connect.run() == 0
    err = capsys.readouterr()
    assert "archia is not connected (invalid_auth)" in err.err and "samantha is in Slack" in err.out


def test_connections_are_closed_when_stopped(home, monkeypatch):
    _both(monkeypatch, "samantha")
    handler = Handler()
    monkeypatch.setattr(slack_connect, "connect", lambda *_: handler)
    monkeypatch.setattr(slack_connect, "threading", SimpleNamespace(Event=_Stop))
    slack_connect.run()
    assert handler.closed


def test_a_connected_persona_shows_as_connected_while_it_runs_and_not_after(home, monkeypatch):
    _both(monkeypatch, "samantha")
    monkeypatch.setattr(slack_connect, "connect", lambda *_: Handler())
    seen = []

    class Looking:
        def wait(self):
            seen.append(slack_heartbeat.connected("samantha"))
            raise KeyboardInterrupt

    monkeypatch.setattr(slack_connect, "threading", SimpleNamespace(Event=Looking))
    slack_connect.run()
    assert seen == [True] and slack_heartbeat.connected("samantha") is False


def test_a_persona_slack_refused_is_not_shown_as_connected(home, monkeypatch):
    _both(monkeypatch, "samantha")

    def refuse(*_):
        raise RuntimeError("invalid_auth")

    monkeypatch.setattr(slack_connect, "connect", refuse)
    assert slack_connect.run() == 1
    assert slack_heartbeat.connected("samantha") is False


def test_nothing_is_connected_while_slack_is_switched_off(home, monkeypatch, capsys):
    _both(monkeypatch, "samantha")
    settings_store.set(slack_approval.SETTING, False)
    monkeypatch.setattr(slack_connect, "connect", lambda *_: pytest.fail("connected while switched off"))
    assert slack_connect.run() == 1
    assert "switched off" in capsys.readouterr().err


def test_nothing_is_connected_without_an_owner(home, monkeypatch, capsys):
    _both(monkeypatch, "samantha")
    monkeypatch.delenv(slack_credentials.OWNER_VARIABLE)
    monkeypatch.setattr(slack_connect, "connect", lambda *_: pytest.fail("connected without an owner"))
    assert slack_connect.run() == 1
    assert slack_credentials.OWNER_VARIABLE in capsys.readouterr().err


def test_no_persona_with_tokens_is_said(home, capsys):
    assert slack_connect.run() == 1
    assert "no persona has a Slack token pair" in capsys.readouterr().err
