"""The web chat's route handlers (docs/decisions/044): a thin door to `engine.run_turn`, the same call
the terminal makes. The engine does not queue (docs/decisions/008 does that at each channel's call
site), so this keeps one lock per persona: two messages for the same persona run in order, and
personas do not wait for each other. A lock cannot span processes, so a terminal chat and a web chat
writing the same session at the same moment are not ordered against each other."""

import threading
from typing import Any

from fastapi import HTTPException

from sympose.engine import model as model_mod, session, sharing, turn, turn_status
from sympose.server_handlers import require_profile
from sympose.server_models import ChatSessionStart, ChatTurn

# Lifted with the cloud notice and share control (docs/decisions/044, slice 2): until then the web
# chat cannot tell the user what would leave the machine, so it only talks to local models.
CLOUD_NOT_AVAILABLE = "The web chat only uses local models for now: pick a local model for this persona to chat here."

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(handle: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(handle, threading.Lock())


def send_turn(body: ChatTurn) -> dict[str, Any]:
    profile = require_profile(body.persona)
    handle = profile["handle"]
    if not sharing.is_local(model_mod.resolve_model(profile.get("model"))):
        raise HTTPException(status_code=409, detail=CLOUD_NOT_AVAILABLE)
    with _lock_for(handle):
        try:
            result = turn.run_turn(handle, body.message, body.session_id)
        except turn.PersonaNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except turn.EngineModelError as e:
            raise HTTPException(status_code=502, detail=str(e))
    return {
        "reply": result.reply,
        "session_id": result.session_id,
        "model": result.model,
        "ttft_ms": result.ttft_ms,
        "truncated": result.truncated,
        "saved": result.saved,
        "searched": result.searched,
        "history_dropped": result.history_dropped,
        "context_used": result.context_used,
        "context_limit": result.context_limit,
        "cloud": result.cloud,
        "withheld": result.withheld,
        "sent": result.sent,
    }


def get_status(persona: str | None) -> dict[str, Any]:
    """What the persona's in-flight reply is doing right now (`searching`, `reading`, `asking`), or
    `None` when nothing is running: the web chat polls this while it waits (docs/decisions/043)."""
    return {"phase": turn_status.phase(require_profile(persona)["handle"])}


def _latest_session(handle: str) -> tuple[str, dict[str, Any]] | None:
    """The newest of `handle`'s sessions, whichever channel wrote it. One with no turns yet counts: it is a
    conversation begun on purpose (`start_session`) and left blank."""
    for session_id in session.session_ids(handle):
        loaded = session.load_session(handle, session_id)
        if loaded:
            return session_id, loaded
    return None


def start_session(body: ChatSessionStart) -> dict[str, Any]:
    """A fresh, empty conversation, so a refresh before the first message shows it blank rather than
    bringing the previous one back. When the latest is already blank it is reused, so pressing the button
    twice does not leave empty files behind."""
    handle = require_profile(body.persona)["handle"]
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
    index into the whole conversation."""
    handle = require_profile(persona)["handle"]
    if session_id:
        try:
            loaded = session.load_session(handle, session_id)
        except ValueError:
            loaded = None
        if loaded is None:
            raise HTTPException(status_code=404, detail=f"No session `{session_id}` for `{handle}`.")
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
    }
