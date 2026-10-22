"""Slack as a channel to a persona (docs/decisions/093): one Slack event in, the persona's reply out. This is the whole of
what Sympose does with a message; `slack_connect` only carries events from Slack to `answer` and replies back.

It holds no vault logic of its own: the turn is `turn.run_turn`, with every guard it has. What this module adds is who may
talk (the owner, before anything reaches the engine), the `slack` approval, which conversation a message belongs to, and
that one persona answers one message at a time."""

import logging
from dataclasses import dataclass

from sympose import note_changes
from sympose import profile as profile_mod
from sympose import slack_drafts, slack_sessions
from sympose.engine import model as model_mod
from sympose.server_chat_locks import acquire, lock_for
from sympose.slack_approval import approved
from sympose.slack_credentials import owner
from sympose.slack_events import Incoming, conversation_key
from sympose.slack_text import to_mrkdwn

log = logging.getLogger(__name__)

SWITCHED_OFF = "Slack is switched off in Sympose's settings, so nothing is answered here. Switch it on there and ask again."
NO_MODEL = "Sympose could not reach the model. Check that it is running, then ask again."
NO_PERSONA = "Sympose could not find this persona any more. Run `sympose doctor` to see why."


@dataclass(frozen=True)
class Reply:
    text: str
    thread_ts: str | None  # the thread to answer in; a direct message is answered in the channel itself


def _where(message: Incoming) -> str | None:
    return None if message.direct else message.thread_ts or message.ts


def answer(handle: str, message: Incoming, seen: slack_sessions.Seen) -> Reply | None:
    """What the persona says to `message`, or `None` when nothing is said: the sender is not the owner (dropped here,
    with no reply and nothing about its text logged), the delivery was seen already, or the user stopped the turn."""
    allowed = owner()
    if allowed is None or message.user != allowed or not seen.first_time(message.event_id):
        return None
    where = _where(message)
    if not approved():
        return Reply(SWITCHED_OFF, where)
    profile = profile_mod.resolve_profile(handle)
    if profile is None:
        return Reply(NO_PERSONA, where)
    handle = profile["handle"]
    return _turn(handle, profile, message, where)


def _turn(handle: str, profile: dict, message: Incoming, where: str | None) -> Reply | None:
    from sympose.engine import turn  # imported here: it brings in litellm, a few seconds

    session_id = slack_sessions.session_for(handle, conversation_key(message))
    lock = lock_for(handle, session_id, model_mod.resolve_model(profile.get("model")))
    if not acquire(lock, handle, session_id):
        return None
    try:
        with note_changes.new_notes_made() as made:
            result = turn.run_turn(handle, message.text, session_id, edits=True, in_slack=True)
    except turn.PersonaNotFoundError:
        return Reply(NO_PERSONA, where)
    except turn.EngineModelError as e:
        log.warning("Slack turn for %s failed: %s", handle, e)
        return Reply(slack_drafts.under(NO_MODEL, slack_drafts.waiting(handle, made)), where)  # a note filed before the failure still waits, so it is shown
    except turn.TurnCancelled:
        return None
    finally:
        lock.release()
    text = to_mrkdwn(result.reply)
    if result.withheld:
        text += f"\n\n_Held back from the model: {', '.join(result.withheld)}._"
    return Reply(slack_drafts.under(text, slack_drafts.waiting(handle, made)), where)


def new_conversation(handle: str, message: Incoming) -> Reply | None:
    """`/new` in a direct message: from now on the conversation is another one. Ignored for anyone but the owner."""
    allowed = owner()
    if allowed is None or message.user != allowed:
        return None
    if not message.direct:
        return Reply("Start a new conversation by writing in a new thread.", _where(message))
    slack_sessions.start_over(handle, conversation_key(message))
    return Reply("New conversation.", None)
