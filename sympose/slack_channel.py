"""Slack as a channel to a persona (docs/decisions/093): one Slack event in, the persona's reply out. This is the whole of
what Sympose does with a message; `slack_connect` only carries events from Slack to `answer` and replies back.

It holds no vault logic of its own: the turn is `turn.run_turn`, with every guard it has. What this module adds is who may
talk (the owner, before anything reaches the engine), the `slack` approval, which conversation a message belongs to, and
that one persona answers one message at a time."""

import logging
from dataclasses import dataclass

from sympose import draft_limit, note_changes
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


@dataclass(frozen=True)
class Reply:
    text: str
    thread_ts: str | None  # the thread to answer in; a direct message is answered in the channel itself


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
    try:
        # The files are fetched with the conversation's lock held, so a slow download does not let a later message overtake this one.
        files = slack_files.fetch(message.files, bot_token) if message.files else ()
        with note_changes.new_notes_made() as made, note_changes.from_source(draft_limit.SLACK):
            result = turn.run_turn(handle, slack_files.with_markers(message.text, files), session_id, edits=True, in_slack=True, files=files)
    except media.MediaRefused as e:
        note(handle, "the files could not be taken, said so")
        return Reply(str(e), where)
    except turn.PersonaNotFoundError:
        note(handle, "the persona was not found, said so")
        return Reply(NO_PERSONA, where)
    except turn.EngineModelError as e:
        note(handle, "the model failed, said so")
        log.warning("Slack turn for %s failed: %s", handle, e)
        return Reply(slack_drafts.under(NO_MODEL, slack_drafts.waiting(handle, made)), where)  # a note filed before the failure still waits, so it is shown
    except turn.TurnCancelled:
        note(handle, "stopped while answering, no reply")
        return None
    finally:
        lock.release()
    return Reply(slack_drafts.under(to_mrkdwn(result.reply), slack_drafts.waiting(handle, made)), where)


def new_conversation(handle: str, message: Incoming) -> Reply | None:
    """`/new` in a direct message: from now on the conversation is another one. Ignored for anyone but the owner."""
    allowed = owner()
    if allowed is None or message.user != allowed:
        return None
    if not message.direct:
        return Reply("Start a new conversation by writing in a new thread.", _where(message))
    slack_sessions.start_over(handle, conversation_key(message))
    return Reply("New conversation.", None)
