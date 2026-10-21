"""The listeners through Slack's own library (slack-bolt): arguments are handed over by name, and an event reaches the
right listener. Nothing goes to the network: authorising is a fake and the replies are caught."""

import json

import pytest
from helpers import write_persona
from slack_shapes import BOT, OWNER, dm, mention

pytest.importorskip("slack_bolt")
from slack_bolt import App, BoltRequest  # noqa: E402
from slack_bolt.authorization import AuthorizeResult  # noqa: E402

from sympose import settings_store, slack_approval, slack_channel, slack_connect  # noqa: E402
from sympose.engine import turn  # noqa: E402
from sympose.engine.turn_result import TurnResult  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nmodel: ollama_chat/gemma4:e4b\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv(slack_channel.OWNER_VARIABLE, OWNER)
    settings_store.set(slack_approval.SETTING, True)
    monkeypatch.setattr(turn, "run_turn", lambda handle, message, session_id=None, **_: TurnResult(reply=f"re: {message}", session_id=session_id))
    built = App(
        token_verification_enabled=False, request_verification_enabled=False, ignoring_self_events_enabled=False,
        authorize=lambda **_: AuthorizeResult(enterprise_id=None, team_id="T1", bot_token="xoxb-fake", bot_user_id=BOT),
    )
    on_event, on_new = slack_connect.listeners("samantha", BOT)
    built.event("message")(on_event)
    built.event("app_mention")(on_event)
    built.command(slack_connect.NEW_COMMAND)(on_new)
    return built


def _sent(monkeypatch):
    posted = []
    monkeypatch.setattr("slack_sdk.web.client.WebClient.chat_postMessage", lambda self, **kw: posted.append(kw) or {"ok": True})
    return posted


def _event(app, body):
    body = {**body, "team_id": "T1", "api_app_id": "A1"}
    response = app.dispatch(BoltRequest(body=json.dumps(body), mode="socket_mode"))
    app.listener_runner.listener_executor.shutdown(wait=True)
    return response


def test_a_direct_message_reaches_the_listener_and_is_answered(app, monkeypatch):
    posted = _sent(monkeypatch)
    assert _event(app, dm("hi")).status == 200
    assert [(p["text"], p["channel"]) for p in posted] == [("re: hi", "D0DM")]


def test_a_mention_is_answered_in_its_thread(app, monkeypatch):
    posted = _sent(monkeypatch)
    _event(app, mention(ts="5.5"))
    assert [(p["text"], p["thread_ts"]) for p in posted] == [("re: what is in my notes?", "5.5")]


def test_slash_new_gets_its_arguments_from_the_library(app, monkeypatch):
    from urllib.parse import urlencode

    answered = []
    monkeypatch.setattr("slack_bolt.context.respond.respond.Respond.__call__", lambda self, text=None, **kw: answered.append(text))
    form = urlencode({"command": "/new", "user_id": OWNER, "channel_id": "D0DM", "team_id": "T1", "api_app_id": "A1", "response_url": "https://example.test/r"})
    response = app.dispatch(BoltRequest(body=form, headers={"content-type": ["application/x-www-form-urlencoded"]}, mode="socket_mode"))
    app.listener_runner.listener_executor.shutdown(wait=True)
    assert response.status == 200 and answered == ["New conversation."]
