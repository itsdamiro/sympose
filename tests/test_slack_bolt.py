"""The listeners through Slack's own library (slack-bolt): arguments are handed over by name, and an event reaches the
right listener. Nothing goes to the network: authorising is a fake and the replies are caught."""

import json

import pytest
from helpers import write_persona
from slack_shapes import BOT, OWNER, dm, mention

pytest.importorskip("slack_bolt")
from slack_bolt import App, BoltRequest  # noqa: E402
from slack_bolt.authorization import AuthorizeResult  # noqa: E402

from sympose import note_changes, settings_store, slack_approval, slack_connect, slack_credentials, slack_drafts  # noqa: E402
from sympose.engine import turn  # noqa: E402
from sympose.engine.turn_result import TurnResult  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nmodel: ollama_chat/gemma4:e4b\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv(slack_credentials.OWNER_VARIABLE, OWNER)
    settings_store.set(slack_approval.SETTING, True)
    monkeypatch.setattr(turn, "run_turn", lambda handle, message, session_id=None, **_: TurnResult(reply=f"re: {message}", session_id=session_id))
    built = App(
        token_verification_enabled=False, request_verification_enabled=False, ignoring_self_events_enabled=False,
        authorize=lambda **_: AuthorizeResult(enterprise_id=None, team_id="T1", bot_token="xoxb-fake", bot_user_id=BOT),
    )
    on_event, on_new, on_press = slack_connect.listeners("samantha", BOT)
    built.event("message")(on_event)
    built.event("app_mention")(on_event)
    built.command(slack_connect.NEW_COMMAND)(on_new)
    built.action(slack_connect.BUTTONS)(on_press)
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


def _press(app, action_id, value, user=OWNER, extra=None):
    body = {
        "type": "block_actions", "team": {"id": "T1"}, "api_app_id": "A1", "user": {"id": user, "team_id": "T1"},
        "channel": {"id": "D0DM"}, "response_url": "https://example.test/r", "trigger_id": "t1",
        "actions": [{"type": "button", "action_id": action_id, "block_id": "b1", "value": value}], **(extra or {}),
    }
    form = "payload=" + __import__("urllib.parse", fromlist=["quote"]).quote(json.dumps(body))
    response = app.dispatch(BoltRequest(body=form, headers={"content-type": ["application/x-www-form-urlencoded"]}, mode="socket_mode"))
    app.listener_runner.listener_executor.shutdown(wait=True)
    return response


def _waiting_draft(tmp_path, monkeypatch):
    from helpers import write_persona as persona

    root = tmp_path / "vault"
    root.mkdir()
    persona(tmp_path / "profiles", "samantha", "name: Samantha\nmodel: ollama_chat/gemma4:e4b\nvault_folders: '*'\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    proposal = note_changes.propose_create("samantha", "new/q1", "# Seeds\n\nSow in March.\n", say="", title="Seeds", folder="Inbox")
    return root, json.dumps(["new/q1", proposal["id"]])


def _answers(monkeypatch):
    sent = []
    monkeypatch.setattr("slack_bolt.context.respond.respond.Respond.__call__", lambda self, text=None, **kw: sent.append({"text": text, **kw}))
    return sent


def test_pressing_accept_reaches_the_listener_by_the_library_and_the_message_becomes_the_outcome(app, tmp_path, monkeypatch):
    root, value = _waiting_draft(tmp_path, monkeypatch)
    sent = _answers(monkeypatch)

    assert _press(app, slack_drafts.ACCEPT, value).status == 200

    assert (root / "Inbox" / "Seeds.md").read_text() == "# Seeds\n\nSow in March.\n"
    (answer,) = sent
    assert answer["replace_original"] is True and answer["text"] == "Saved *Seeds* as `Inbox/Seeds.md`."
    assert answer["blocks"] == slack_drafts.outcome(answer["text"])["blocks"]


def test_pressing_decline_by_the_library_forgets_the_draft(app, tmp_path, monkeypatch):
    root, value = _waiting_draft(tmp_path, monkeypatch)
    sent = _answers(monkeypatch)

    _press(app, slack_drafts.DECLINE, value)

    assert not (root / "Inbox").exists() and note_changes.drafts("samantha") == []
    assert [a["text"] for a in sent] == ["Declined *Seeds*; nothing was saved."]


def test_a_press_by_someone_else_in_a_channel_changes_nothing_by_the_library(app, tmp_path, monkeypatch):
    root, value = _waiting_draft(tmp_path, monkeypatch)
    sent = _answers(monkeypatch)

    assert _press(app, slack_drafts.ACCEPT, value, user="U0STRANGER").status == 200

    assert sent == [] and not (root / "Inbox").exists() and len(note_changes.drafts("samantha")) == 1


def test_a_button_that_is_not_ours_is_not_handled(app, tmp_path, monkeypatch):
    root, value = _waiting_draft(tmp_path, monkeypatch)
    sent = _answers(monkeypatch)

    _press(app, "someone_elses_button", value)

    assert sent == [] and not (root / "Inbox").exists()
