"""The web chat's route handlers (docs/decisions/044): a thin door to `engine.run_turn`, the same call
the terminal makes. The engine does not queue (docs/decisions/008 does that at each channel's call
site), so this keeps one lock per persona: two messages for the same persona run in order, and
personas do not wait for each other. A lock cannot span processes, so a terminal chat and a web chat
writing the same session at the same moment are not ordered against each other."""

import threading
from typing import Any

from fastapi import HTTPException

from sympose.engine import model as model_mod, sharing, turn, turn_status
from sympose.server_handlers import require_profile
from sympose.server_models import ChatTurn

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
