"""What the Slack connection does with events, replies and start-up (docs/decisions/093). Slack's library is not used here:
the listeners are called the way it calls them, and `connect` is replaced."""

from types import SimpleNamespace

import pytest
from helpers import write_persona
from slack_shapes import BOT, OWNER, dm, mention, shared

from sympose import settings_store, slack_approval, slack_channel, slack_connect, slack_credentials, slack_drafts, slack_files, slack_heartbeat
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
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(dm("hi"), say)
    assert say.sent == [{"text": "re: hi", "thread_ts": None}]


def test_a_mention_is_answered_in_its_thread(home):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(mention(ts="5.5"), say)
    assert say.sent[0]["thread_ts"] == "5.5"


def test_an_event_that_is_not_a_message_says_nothing(home):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event({"event": {"type": "reaction_added"}}, say)
    on_event(dm(bot_id="B1"), say)
    assert say.sent == []


def test_an_event_that_is_not_a_message_is_ignored_without_an_error(home, caplog):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event({"event": {"type": "reaction_added"}}, Say())
    assert caplog.records == []


def test_a_redelivery_is_answered_once(home):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(dm("hi"), say)
    on_event(dm("hi"), say)
    assert len(say.sent) == 1


def test_a_failure_in_the_answer_does_not_escape_the_listener(home, monkeypatch):
    def broken(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(slack_channel, "answer", broken)
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()
    on_event(dm("hi"), say)
    assert say.sent == []


def test_slash_new_is_acknowledged_and_answered_to_the_owner(home):
    _, on_new, _ = slack_connect.listeners("samantha", BOT)
    acked, said = [], []
    on_new(lambda: acked.append(True), {"user_id": OWNER, "channel_id": "D0DM"}, said.append)
    assert acked and said == ["New conversation."]


def test_slash_new_from_a_stranger_is_acknowledged_and_unanswered(home):
    _, on_new, _ = slack_connect.listeners("samantha", BOT)
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


# --- the line in the terminal for each message (slack_trace) ---------------------------------------
def _lines(capsys):
    return [line.split(" ", 1)[1] for line in capsys.readouterr().out.splitlines()]


def test_a_message_that_is_answered_has_a_line_when_it_arrives_and_one_when_it_is_answered(home, capsys):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event(dm("a secret about the vault"), Say())
    arrived, answered = _lines(capsys)
    assert arrived == "samantha: message received (direct)"
    assert answered.startswith("samantha: replied after ") and answered.endswith(" s")


def test_a_mention_is_a_message_received_in_a_channel(home, capsys):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event(mention(), Say())
    assert _lines(capsys)[0] == "samantha: message received (channel)"


def test_an_event_that_is_not_a_message_has_no_line(home, capsys):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event({"event": {"type": "reaction_added"}}, Say())
    assert capsys.readouterr().out == ""


def test_a_failed_answer_is_a_line_and_not_a_reply_line(home, monkeypatch, capsys):
    def broken(*_a, **_k):
        raise RuntimeError("boom with a secret")

    monkeypatch.setattr(slack_channel, "answer", broken)
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event(dm("hi"), Say())
    assert _lines(capsys) == ["samantha: message received (direct)", "samantha: the answer failed (RuntimeError), see below"]


def test_a_reply_slack_would_not_take_is_a_line_and_does_not_escape(home, capsys):
    def broken(**_k):
        raise BrokenPipeError("pipe")

    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event(dm("hi"), broken)
    assert _lines(capsys) == ["samantha: message received (direct)", "samantha: the reply could not be sent (BrokenPipeError), see below"]


def test_a_message_that_gets_no_reply_has_the_line_of_its_reason_and_no_replied_line(home, capsys):
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    on_event(dm("hi", user="U0STRANGER"), Say())
    assert _lines(capsys) == ["samantha: message received (direct)", "samantha: ignored, not from the owner"]


def test_the_personas_bot_token_downloads_the_files_of_its_messages(home, monkeypatch):
    got = []
    monkeypatch.setattr(slack_files, "fetch", lambda files, token: got.append(token) or ())
    on_event, *_ = slack_connect.listeners("samantha", BOT, bot_token="xoxb-samantha")
    on_event(dm("read this", subtype="file_share", files=[shared()]), Say())
    assert got == ["xoxb-samantha"]


def test_connect_gives_the_listeners_the_bot_token_it_was_opened_with(home, monkeypatch):
    pytest.importorskip("slack_bolt")
    import slack_bolt
    from slack_bolt.adapter import socket_mode

    got, events = [], {}

    class App:
        def __init__(self, token):
            self.client = SimpleNamespace(auth_test=lambda: {"user_id": BOT})

        def event(self, name):
            return lambda listener: events.setdefault(name, listener)

        def command(self, name):
            return lambda listener: listener

        def action(self, pattern):
            return lambda listener: listener

    class Handler:
        def __init__(self, app, token):
            pass

        def connect(self):
            pass

    monkeypatch.setattr(slack_bolt, "App", App)
    monkeypatch.setattr(socket_mode, "SocketModeHandler", Handler)
    monkeypatch.setattr(slack_files, "fetch", lambda files, token: got.append(token) or ())
    slack_connect.connect("samantha", "xoxb-samantha", "xapp-samantha")
    events["message"](dm("read this", subtype="file_share", files=[shared()]), Say())
    assert got == ["xoxb-samantha"]


def test_connect_listens_for_the_two_buttons_and_nothing_else(home, monkeypatch):
    pytest.importorskip("slack_bolt")
    import slack_bolt
    from slack_bolt.adapter import socket_mode

    patterns = []

    class App:
        def __init__(self, token):
            self.client = SimpleNamespace(auth_test=lambda: {"user_id": BOT})

        def event(self, name):
            return lambda listener: listener

        def command(self, name):
            return lambda listener: listener

        def action(self, pattern):
            patterns.append(pattern)
            return lambda listener: listener

    class Connection:
        def __init__(self, app, token):
            pass

        def connect(self):
            pass

    monkeypatch.setattr(slack_bolt, "App", App)
    monkeypatch.setattr(socket_mode, "SocketModeHandler", Connection)

    slack_connect.connect("samantha", "xoxb-1", "xapp-1")

    (pattern,) = patterns
    assert pattern.search(slack_drafts.ACCEPT) and pattern.search(slack_drafts.DECLINE)
    assert not pattern.search("sympose_accept_all") and not pattern.search("xsympose_accept") and not pattern.search("other_accept") and not pattern.search("")


# --- buttons under a draft, and a press (ADR 093, amendment of 2026-10-23) --------------------------
def _reply(*prompts, thread_ts=None):
    return slack_channel.Reply("The reply.", thread_ts, tuple(prompts))


def test_each_message_of_buttons_follows_the_reply_in_the_same_place(home, monkeypatch):
    first = {"text": "Save *One*?", "blocks": [{"type": "section"}]}
    second = {"text": "Save *Two*?", "blocks": [{"type": "section"}]}
    monkeypatch.setattr(slack_channel, "answer", lambda *a: _reply(first, second, thread_ts="5.5"))
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()

    on_event(mention(ts="5.5"), say)

    assert say.sent == [{"text": "The reply.", "thread_ts": "5.5"}, {**first, "thread_ts": "5.5"}, {**second, "thread_ts": "5.5"}]


def test_a_reply_with_no_buttons_posts_one_message(home, monkeypatch):
    monkeypatch.setattr(slack_channel, "answer", lambda *a: _reply())
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    say = Say()

    on_event(dm("hi"), say)

    assert len(say.sent) == 1


def test_buttons_that_could_not_be_sent_leave_the_reply_standing_and_are_a_line(home, monkeypatch, capsys):
    monkeypatch.setattr(slack_channel, "answer", lambda *a: _reply({"text": "Save *One*?", "blocks": []}, {"text": "Save *Two*?", "blocks": []}))
    on_event, *_ = slack_connect.listeners("samantha", BOT)
    sent = []

    def say(**kwargs):
        sent.append(kwargs)
        if len(sent) > 1:
            raise BrokenPipeError()

    on_event(dm("hi"), say)

    assert len(sent) == 2  # the reply, then the first buttons; the second is not tried after the first failed
    assert "the buttons could not be sent (BrokenPipeError), see below\n" in capsys.readouterr().out


def _press(body, decision, monkeypatch):
    seen = []
    monkeypatch.setattr(slack_channel, "decide", lambda *a: seen.append(a) or decision)
    _, _, on_press = slack_connect.listeners("samantha", BOT)
    acked, responded = [], []
    on_press(lambda: acked.append(True), body, lambda **kw: responded.append(kw))
    return seen, acked, responded


def _pressed(action="sympose_accept", value='["new/a", "p1"]', user=OWNER):
    return {"type": "block_actions", "user": {"id": user}, "actions": [{"action_id": action, "value": value}]}


def test_a_press_is_acknowledged_and_a_decided_draft_replaces_its_buttons_with_one_line(home, monkeypatch):
    seen, acked, responded = _press(_pressed(), slack_channel.Decision("Saved *Seeds* as `Inbox/Seeds.md`.", True), monkeypatch)

    assert acked == [True] and seen == [("samantha", OWNER, "sympose_accept", '["new/a", "p1"]')]
    assert responded == [{"replace_original": True, **slack_drafts.outcome("Saved *Seeds* as `Inbox/Seeds.md`.")}]


def test_a_refusal_is_said_to_the_owner_alone_and_the_buttons_stay(home, monkeypatch):
    _, _, responded = _press(_pressed(), slack_channel.Decision("Seeds could not be saved.", False), monkeypatch)

    assert responded == [{"text": "Seeds could not be saved.", "response_type": "ephemeral", "replace_original": False}]


def test_a_press_from_anyone_else_is_acknowledged_and_nothing_is_said(home, monkeypatch):
    _, acked, responded = _press(_pressed(user="U0STRANGER"), None, monkeypatch)

    assert acked == [True] and responded == []


def test_a_press_with_a_body_missing_its_parts_is_acknowledged_and_asks_for_nothing_unreadable(home, monkeypatch):
    seen, acked, _ = _press({}, None, monkeypatch)

    assert acked == [True] and seen == [("samantha", "", "", "")]


def test_a_press_that_fails_is_a_line_and_a_private_word_and_never_escapes(home, monkeypatch, capsys):
    def broken(*_a):
        raise OSError("disk")

    monkeypatch.setattr(slack_channel, "decide", broken)
    _, _, on_press = slack_connect.listeners("samantha", BOT)
    responded = []

    on_press(lambda: None, _pressed(), lambda **kw: responded.append(kw))

    assert responded == [{"text": slack_connect.PRESS_FAILED, "response_type": "ephemeral", "replace_original": False}]
    assert "the press failed (OSError), see below\n" in capsys.readouterr().out


def test_a_press_whose_answer_cannot_be_sent_does_not_escape(home, monkeypatch):
    monkeypatch.setattr(slack_channel, "decide", lambda *a: slack_channel.Decision("x", True))
    _, _, on_press = slack_connect.listeners("samantha", BOT)

    def broken(**_kw):
        raise BrokenPipeError()

    on_press(lambda: None, _pressed(), broken)
