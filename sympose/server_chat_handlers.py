"""The web chat's route handlers (docs/decisions/044): a thin door to `engine.run_turn`, the same call
the terminal makes. The engine does not queue (docs/decisions/008 does that at each channel's call
site), so this keeps the locks: two messages in one conversation always run in order, personas do not wait
for each other, and two conversations of one persona wait for each other unless `parallel_replies` lets them
run side by side (docs/decisions/057). A message that is waiting for its turn can be stopped. A lock cannot
span processes, so a terminal chat and a web chat writing the same session at the same moment are not
ordered against each other."""

from typing import Any

from fastapi import HTTPException

from sympose import server_chat_locks as locks
from sympose.engine import (
    compaction, context_estimate, model as model_mod, recap_refresh, semantic_refresh, session,
    session_compaction, status_phrases, turn, turn_status,
)
from sympose.engine.edit_turn import Attached, OpenNote
from sympose.engine.turn_cancel import request as cancel_requested
from sympose.server_handlers import require_profile
from sympose.server_models import ChatCancel, ChatCompact, ChatSessionStart, ChatTurn

def send_turn(body: ChatTurn) -> dict[str, Any]:
    profile = require_profile(body.persona)
    handle = profile["handle"]
    lock = locks.lock_for(handle, body.session_id, model_mod.resolve_model(profile.get("model")))
    if not locks.acquire(lock, handle, body.session_id):
        return {"cancelled": True}  # stopped while it waited for the other conversation's reply
    try:
        try:
            opened = OpenNote(body.open_note.path, body.open_note.text) if body.open_note else None
            attached = [Attached(a.quote, a.before, a.after) for a in body.attached]
            result = turn.run_turn(handle, body.message, body.session_id, open_note=opened, edits=body.edits, attached=attached)
        except turn.PersonaNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"{e} Run `sympose doctor` in a terminal to see why.")
        except turn.EngineModelError as e:
            raise HTTPException(status_code=502, detail=f"{e} Check that the model is running and reachable, then try again.")
        except turn.TurnCancelled:  # stopped by the user (docs/decisions/054): nothing was saved
            return {"cancelled": True}
    finally:
        lock.release()
    return {
        "reply": result.reply,
        "session_id": result.session_id,
        "model": result.model,
        "ttft_ms": result.ttft_ms,
        "truncated": result.truncated,
        "saved": result.saved,
        "searched": result.searched,
        "history_dropped": result.history_dropped,
        "condensed": result.condensed,
        "context_used": result.context_used,
        "context_limit": result.context_limit,
        "cloud": result.cloud,
        "withheld": result.withheld,
        "sent": result.sent,
    }


def cancel_turn(body: ChatCancel) -> dict[str, Any]:
    """Stop a reply in flight (docs/decisions/054): the conversation `session_id` names, or every reply the
    persona is writing when it is left out, or with `unnamed` only the reply of a first message that named no
    conversation. A message still waiting for its turn (docs/decisions/057) is stopped too and is not run. `stopping` is whether anything was stopped; the turn's own request answers
    `{"cancelled": true}` when the engine reaches its next check, so this does not wait for it."""
    handle = require_profile(body.persona)["handle"]
    running = cancel_requested(handle, body.session_id, unnamed=body.unnamed)
    return {"stopping": locks.stop_waiting(handle, body.session_id, unnamed=body.unnamed) or running}


def compact_session(body: ChatCompact) -> dict[str, Any]:
    """Condense the earlier part of the conversation into notes now, with the persona's model, and wait for
    it (docs/decisions/055). `status` says what happened (`done`, `nothing`, `too_small`, `failed`, `busy`); on
    every answer carries the notes in force, how many turns they stand for, and on `done` the size before and after. It does not
    take the persona's turn lock: a reply in flight is not held up by it, and the notes reach the turns after."""
    profile = require_profile(body.persona)
    handle = profile["handle"]
    try:
        found = session.load_session(handle, body.session_id)
    except ValueError:
        found = None
    if found is None:
        raise HTTPException(status_code=404, detail="That conversation is no longer there. Start a new one.")
    outcome = compaction.compact_now(handle, body.session_id, model_mod.resolve_model(profile.get("model")))
    # `text` is always the notes in force afterwards (the new ones on `done`, else any that already stood).
    text = outcome.text or session_compaction.notes(session.load_session(handle, body.session_id)) or ""
    return {
        "status": outcome.status, "covered": outcome.covered, "text": text,
        "before": outcome.before, "after": outcome.after,
    }


def get_status(persona: str | None, session_id: str | None = None) -> dict[str, Any]:
    """What the in-flight reply of the conversation `session_id` names (else the persona's oldest) is doing
    right now (`searching`, `reading`, `asking`), `queued` while its message waits for another conversation's
    reply to finish (docs/decisions/057), or `None` when nothing is running: the web chat polls this while it
    waits (docs/decisions/043). `indexing` is
    the whole percent of the search index build still running, or `None`: until it is done the reply searches
    by keyword, which the chat says (docs/decisions/044, amendment of 2026-10-01)."""
    handle = require_profile(persona)["handle"]
    phase = turn_status.phase(handle, session_id) or ("queued" if locks.is_waiting(handle, session_id) else None)
    return {"phase": phase, "indexing": semantic_refresh.progress()}


def get_status_phrases(persona: str | None) -> dict[str, Any]:
    """The persona's own busy-line phrases (`own`), or the generic ones while it has none. The first read
    for a persona with none also starts the one-time background generation from its soul, the same lazy
    trigger the terminal uses at launch (docs/decisions/043, 044): it happens when the chat opens, not when
    a message is sent, so the model call does not compete with the first reply."""
    handle = require_profile(persona)["handle"]
    status_phrases.generate_in_background(handle)
    return {"phrases": status_phrases.phrases(handle), "own": status_phrases.has_own(handle)}


def get_context(persona: str | None, session_id: str | None) -> dict[str, Any]:
    """The context meter's estimate for the persona's current model and the conversation `session_id` names:
    the engine's own count of its system prompt plus the kept history against the model's prompt budget, no
    model call (docs/decisions/044, 018). Both `None` when there is nothing to count: no session or no reply
    yet, or a model whose window is unknown. It leans low where a real turn's figure leans high."""
    profile = require_profile(persona)
    figures = context_estimate.estimate(profile["handle"], session_id, model_mod.resolve_model(profile.get("model")))
    return {"used": figures[0], "limit": figures[1]} if figures else {"used": None, "limit": None}


def _latest_session(handle: str) -> tuple[str, dict[str, Any]] | None:
    """The newest of `handle`'s sessions, whichever channel wrote it. One with no turns yet counts: it is a
    conversation begun on purpose (`start_session`) and left blank."""
    for session_id in session.session_ids(handle):
        loaded = session.load_session(handle, session_id)
        if loaded:
            return session_id, loaded
    return None


def _start_background_builds(handle: str) -> None:
    """What the terminal starts at launch, started when a web chat opens: the recaps of the conversations held
    since the last one (ADR 023) and the search by meaning's index (ADR 027, only when that knob is on)."""
    recap_refresh.refresh_in_background(handle)
    semantic_refresh.refresh_in_background(handle)


def start_session(body: ChatSessionStart) -> dict[str, Any]:
    """A fresh, empty conversation, so a refresh before the first message shows it blank rather than
    bringing the previous one back. When the latest is already blank it is reused, so pressing the button
    twice does not leave empty files behind."""
    handle = require_profile(body.persona)["handle"]
    _start_background_builds(handle)
    latest = _latest_session(handle)
    if latest and not latest[1]["turns"]:
        return {"session_id": latest[0]}
    session_id = session.new_session_id()
    if not session.start_session(handle, session_id):
        raise HTTPException(status_code=500, detail="Could not start a new conversation.")
    return {"session_id": session_id}


def get_session(persona: str | None, session_id: str | None, before: int | None, limit: int) -> dict[str, Any]:
    """One section of a conversation, so a long one is loaded a piece at a time (docs/decisions/044): the
    last `limit` turns, or the `limit` turns before turn number `before`. `session_id` fixes which
    conversation the pages come from (the first page names it), so older pages stay in the same one even if
    another starts meanwhile; left out, it is the latest. Each turn carries its number, the running
    index into the whole conversation. The first page is the chat being opened, so it also starts the recaps
    of the conversations held since the last one (ADR 023); the terminal does that at launch, and a web chat
    has no launch. Nothing is asked of the model when none is missing."""
    handle = require_profile(persona)["handle"]
    if before is None:
        _start_background_builds(handle)
    if session_id:
        try:
            loaded = session.load_session(handle, session_id)
        except ValueError:
            loaded = None
        if loaded is None:
            raise HTTPException(status_code=404, detail="That conversation is no longer there. Start a new one.")
    else:
        found = _latest_session(handle)
        if found is None:
            return {"session_id": None, "turns": [], "start": 0, "total": 0, "has_more": False}
        session_id, loaded = found
    all_turns = loaded["turns"]
    total = len(all_turns)
    end = total if before is None else min(before, total)
    start = max(0, end - limit)
    return {
        "session_id": session_id,
        "turns": [
            {
                "index": start + offset,
                "user": t["user"],
                "assistant": t["assistant"],
                "timestamp": t.get("timestamp"),
                "model": t.get("model"),
                "ttft_ms": t.get("ttft_ms"),
                "truncated": t.get("truncated") is True,
                "sent": t.get("sent"),
            }
            for offset, t in enumerate(all_turns[start:end])
        ],
        "start": start,
        "total": total,
        "has_more": start > 0,
        # The notes standing for the start of the conversation (docs/decisions/055), or `None`.
        "compaction": (
            {"through": session_compaction.covered(loaded), "text": session_compaction.notes(loaded)}
            if session_compaction.notes(loaded) else None
        ),
    }
