"""The web chat's list of past conversations (docs/decisions/057): list, rename, pin and delete. A thin door to
`engine.session_manage`, which owns what each does; this only turns its answers into HTTP ones."""

from typing import Any

from fastapi import HTTPException

from sympose.engine import session_manage
from sympose.server_handlers import require_profile
from sympose.server_models import ChatSessionUpdate

_ERRORS = {
    session_manage.NOT_FOUND: (404, "No such conversation."),
    session_manage.BAD_TITLE: (422, f"A title is one line of 1 to {session_manage.MAX_TITLE} characters."),
    session_manage.BUSY: (409, "A reply is being written in that conversation. Stop it first."),
    session_manage.FAILED: (500, "Could not save the change."),
}


def _raise_unless_ok(outcome: str) -> None:
    if outcome != session_manage.OK:
        status, detail = _ERRORS[outcome]
        raise HTTPException(status_code=status, detail=detail)


def list_sessions(persona: str | None) -> dict[str, Any]:
    """The persona's conversations, the pinned ones first (docs/decisions/057)."""
    return {"sessions": session_manage.list_sessions(require_profile(persona)["handle"])}


def update_session(session_id: str, body: ChatSessionUpdate) -> dict[str, Any]:
    """Rename and/or pin or unpin a conversation; the same row the list gives comes back."""
    handle = require_profile(body.persona)["handle"]
    if body.title is not None:
        _raise_unless_ok(session_manage.rename(handle, session_id, body.title))
    if body.pinned is not None:
        _raise_unless_ok(session_manage.pin(handle, session_id, body.pinned))
    row = next((row for row in session_manage.list_sessions(handle) if row["id"] == session_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail=_ERRORS[session_manage.NOT_FOUND][1])
    return row


def delete_session(session_id: str, persona: str | None) -> dict[str, Any]:
    """Move a conversation to the trash folder (soft delete: nothing is destroyed)."""
    _raise_unless_ok(session_manage.delete(require_profile(persona)["handle"], session_id))
    return {"deleted": session_id}
