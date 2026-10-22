"""The connection to Slack (docs/decisions/093): one Socket Mode connection for each persona that has a token pair, found
by looking at the roster, so no persona is named here. Each connection hands a message to `slack_channel.answer` and
says what comes back; nothing else happens in this module. `slack-bolt` is imported when a connection is made."""

import logging
import sys
import threading
from collections.abc import Callable
from typing import Any

from sympose import profile as profile_mod
from sympose import slack_channel, slack_credentials, slack_heartbeat, slack_manifest, slack_sessions
from sympose.slack_events import Incoming, parse

log = logging.getLogger(__name__)

NEW_COMMAND = slack_manifest.NEW_COMMAND["command"]  # the manifest declares it, so the two cannot differ


def listeners(handle: str, bot_user_id: str, seen: slack_sessions.Seen | None = None) -> tuple[Callable, Callable]:
    """What `handle`'s Slack App does with a message (or a mention) and with `/new`. Each is called by Slack's library,
    which has already acknowledged the event; neither raises, since a failure here would only be lost in a thread."""
    seen = seen or slack_sessions.Seen()

    def on_event(body: dict[str, Any], say: Callable[..., Any]) -> None:
        message = parse(body, bot_user_id)
        if message is None:
            return
        try:
            reply = slack_channel.answer(handle, message, seen)
        except Exception:
            log.exception("Slack: the answer of %s failed", handle)
            return
        if reply is not None:
            say(text=reply.text, thread_ts=reply.thread_ts)

    def on_new(ack: Callable[..., Any], command: dict[str, Any], respond: Callable[..., Any]) -> None:
        ack()
        channel = command.get("channel_id") or ""
        message = Incoming(command.get("user_id") or "", channel, NEW_COMMAND, "", None, channel.startswith("D"), None)
        reply = slack_channel.new_conversation(handle, message)
        if reply is not None:
            respond(reply.text)

    return on_event, on_new


def connect(handle: str, bot_token: str, app_token: str) -> Any:
    """Open `handle`'s connection and return its handler (so it can be closed). Raises when Slack refuses the tokens."""
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=bot_token)
    on_event, on_new = listeners(handle, app.client.auth_test()["user_id"])
    app.event("message")(on_event)
    app.event("app_mention")(on_event)
    app.command(NEW_COMMAND)(on_new)
    handler = SocketModeHandler(app, app_token)
    handler.connect()
    return handler


def run() -> int:
    """`sympose slack`: connect every persona that has tokens and stay up until stopped."""
    if slack_credentials.owner() is None:
        print(f"sympose slack: set {slack_credentials.OWNER_VARIABLE} in .env to your Slack user ID, so only you are answered.", file=sys.stderr)
        return 1
    if not slack_channel.approved():
        print("sympose slack: Slack is switched off in Sympose's settings. Switch it on there, then run this again.", file=sys.stderr)
        return 1
    handlers: dict[str, Any] = {}
    for persona in profile_mod.list_profiles():
        handle = persona["handle"]
        found = slack_credentials.tokens(handle)
        if found is None:
            continue
        try:
            handlers[handle] = connect(handle, *found)
        except Exception as e:  # Slack refused the tokens, or could not be reached: the other personas carry on
            print(f"sympose slack: {handle} is not connected ({e}).", file=sys.stderr)
            continue
        print(f"{handle} is in Slack.")
    if not handlers:
        print("sympose slack: no persona has a Slack token pair (SLACK_<HANDLE>_BOT_TOKEN and SLACK_<HANDLE>_APP_TOKEN in .env).", file=sys.stderr)
        return 1
    print("Slack is connected (Ctrl-C to stop).")
    stop_beating = slack_heartbeat.keep(handlers)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    stop_beating()
    for handler in handlers.values():
        handler.close()
    return 0


def manifest(handle: str) -> int:
    """`sympose slack manifest <handle>`: print the manifest to paste into Slack's "create an app from a manifest"."""
    text = slack_manifest.render(handle)
    if text is None:
        print(f"sympose slack: there is no persona called {handle!r}. Run `sympose doctor` to see the roster.", file=sys.stderr)
        return 1
    print(text)
    return 0
