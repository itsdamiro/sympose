"""Slack as a channel to a persona (docs/decisions/093): one Slack event in, the persona's reply out. This is the whole of
what Sympose does with a message; `slack_connect` only carries events from Slack to `answer` and replies back.

It holds no vault logic of its own: the turn is `turn.run_turn`, with every guard it has. What this module adds is who may
talk (the owner, before anything reaches the engine), the `slack` approval, which conversation a message belongs to, and
that one persona answers one message at a time."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from sympose import draft_accept, draft_limit
from sympose import profile as profile_mod
from sympose import slack_drafts, slack_files, slack_sessions
from sympose.engine import media
from sympose.engine import model as model_mod
from sympose.server_chat_locks import acquire, lock_for
from sympose.slack_approval import approved
from sympose.slack_credentials import owner
from sympose.slack_events import Incoming, conversation_key
from sympose.slack_text import to_mrkdwn
from sympose.slack_trace import note

log = logging.getLogger(__name__)

SWITCHED_OFF = "Slack is switched off in Sympose's settings, so nothing is answered here. Switch it on there and ask again."
NO_MODEL = "Sympose could not reach the model. Check that it is running, then ask again."
NO_PERSONA = "Sympose could not find this persona any more. Run `sympose doctor` to see why."
NOT_WAITING = "That draft is not waiting any more."


@dataclass(frozen=True)
class Reply:
    text: str
    thread_ts: str | None  # the thread to answer in; a direct message is answered in the channel itself
    prompts: tuple[dict[str, Any], ...] = ()  # messages of buttons to post after it, one for each draft shown whole


@dataclass(frozen=True)
class Decision:
    text: str
    final: bool  # the line replaces the buttons (the draft is decided); otherwise it is said to the owner alone and they stay


def _where(message: Incoming) -> str | None:
    return None if message.direct else message.thread_ts or message.ts


def answer(handle: str, message: Incoming, seen: slack_sessions.Seen, bot_token: str = "") -> Reply | None:
    """What the persona says to `message`, or `None` when nothing is said: the sender is not the owner (dropped here,
    with no reply and nothing about its text logged), the delivery was seen already, or the user stopped the turn.
    `bot_token` is the persona's, for downloading the files shared with the message: only after the checks above pass,
    so a stranger's file is never fetched."""
    allowed = owner()
    if allowed is None or message.user != allowed:
        note(handle, "ignored, not from the owner")
        return None
    if not seen.first_time(message.event_id):
        note(handle, "ignored, Slack delivered it again")
        return None
    where = _where(message)
    if not approved():
        note(handle, "Slack is switched off in settings, said so")
        return Reply(SWITCHED_OFF, where)
    profile = profile_mod.resolve_profile(handle)
    if profile is None:
        note(handle, "the persona was not found, said so")
        return Reply(NO_PERSONA, where)
    handle = profile["handle"]
    return _turn(handle, profile, message, where, bot_token)


def _turn(handle: str, profile: dict, message: Incoming, where: str | None, bot_token: str) -> Reply | None:
    from sympose.engine import turn  # imported here: it brings in litellm, a few seconds

    session_id = slack_sessions.session_for(handle, conversation_key(message))
    lock = lock_for(handle, session_id, model_mod.resolve_model(profile.get("model")))
    if not acquire(lock, handle, session_id):
        note(handle, "stopped before it ran, no reply")
        return None
    filing = draft_limit.Filing(draft_limit.SLACK)  # what the turn's drafts are filed as, and where they are listed as they are made
    try:
        # The files are fetched with the conversation's lock held, so a slow download does not let a later message overtake this one.
        files = slack_files.fetch(message.files, bot_token) if message.files else ()
        result = turn.run_turn(handle, slack_files.with_markers(message.text, files), session_id, edits=True, in_slack=True, files=files, filing=filing)
    except media.MediaRefused as e:
        note(handle, "the files could not be taken, said so")
        return Reply(str(e), where)
    except turn.PersonaNotFoundError:
        note(handle, "the persona was not found, said so")
        return Reply(NO_PERSONA, where)
    except turn.EngineModelError as e:
        note(handle, "the model failed, said so")
        log.warning("Slack turn for %s failed: %s", handle, e)
        return _with_drafts(NO_MODEL, slack_drafts.waiting(handle, filing.made), where)  # a note filed before the failure still waits, so it is shown
    except turn.TurnCancelled:
        note(handle, "stopped while answering, no reply")
        return None
    finally:
        lock.release()
    return _with_drafts(to_mrkdwn(result.reply), slack_drafts.waiting(handle, filing.made), where)


def _with_drafts(reply: str, drafts: list[dict[str, Any]], where: str | None) -> Reply:
    text, whole = slack_drafts.compose(reply, drafts)
    return Reply(text, where, tuple(slack_drafts.prompt(draft) for draft in whole))


def new_conversation(handle: str, message: Incoming) -> Reply | None:
    """`/new` in a direct message: from now on the conversation is another one. Ignored for anyone but the owner."""
    allowed = owner()
    if allowed is None or message.user != allowed:
        return None
    if not message.direct:
        return Reply("Start a new conversation by writing in a new thread.", _where(message))
    slack_sessions.start_over(handle, conversation_key(message))
    return Reply("New conversation.", None)


def decide(handle: str, user: str, action: str, value: str) -> Decision | None:
    """A press of Accept or Decline under a draft (docs/decisions/093, "Accept and Decline in Slack"), or `None` when nothing is
    said: the presser is not the owner (a channel's buttons are seen by everyone in it) or the button is not one of ours.
    Accepting is the one act here that writes the vault, and it is the owner's own."""
    accepting = action == slack_drafts.ACCEPT
    note(handle, f"button pressed ({'accept' if accepting else 'decline'})")
    allowed = owner()
    if allowed is None or user != allowed:
        note(handle, "ignored, not from the owner")
        return None
    try:
        path, proposal_id = json.loads(value)
    except (ValueError, TypeError):
        path = proposal_id = None
    if not (isinstance(path, str) and isinstance(proposal_id, str)):
        note(handle, "ignored, not a button of ours")
        return None
    if not approved():
        note(handle, "Slack is switched off in settings, said so")
        return Decision(SWITCHED_OFF, False)
    profile = profile_mod.resolve_profile(handle)
    if profile is None:
        note(handle, "the persona was not found, said so")
        return Decision(NO_PERSONA, False)
    try:
        done = (draft_accept.accept if accepting else draft_accept.decline)(profile["handle"], path, proposal_id)
    except draft_accept.Gone:
        note(handle, "no longer waiting, said so")
        return Decision(NOT_WAITING, True)
    except draft_accept.Refused as e:
        note(handle, "could not be saved, said so")
        return Decision(str(e), False)
    note(handle, "saved" if accepting else "declined")
    return Decision(slack_drafts.saved(done.name, done.path or "") if accepting else slack_drafts.declined(done.name), True)
