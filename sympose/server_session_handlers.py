"""The web chat's list of past conversations (docs/decisions/057): list, rename, pin and delete. A thin door to
`engine.session_manage`, which owns what each does; this only turns its answers into HTTP ones."""

from typing import Any

from fastapi import HTTPException

from sympose.engine import session_archive, session_bin, session_manage
from sympose.server_handlers import require_profile
from sympose.server_models import ChatBinAction, ChatSessionArchive, ChatSessionUpdate

_ERRORS = {
    session_manage.NOT_FOUND: (404, "No such conversation."),
    session_manage.BAD_TITLE: (422, f"A title is one line of 1 to {session_manage.MAX_TITLE} characters."),
    session_manage.BUSY: (409, "A reply is being written in that conversation. Stop it first."),
    session_manage.FAILED: (500, "Couldn't save the change. Check that the folder can be written to."),
    session_manage.EXISTS: (409, "That conversation is already there, so nothing was replaced."),
    session_manage.BAD_ID: (404, "No such conversation in the Bin."),
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


_ARCHIVE_ERRORS = {
    session_archive.NOT_FOUND: (404, "No such conversation."),
    session_archive.BUSY: (409, "A reply is being written in that conversation. Stop it first."),
    session_archive.WAITING: (409, "An archive of this conversation is already waiting among the drafts, so a second one was not made."),
    session_archive.TOO_SHORT: (422, "That conversation is too short to archive."),
    session_archive.NO_VAULT: (422, "This persona has no vault to put a note in."),
    session_archive.NOT_ALLOWED: (422, "The model would send your messages to the cloud, which you have not allowed for recaps and archives."),
    session_archive.NOTHING_TO_KEEP: (422, "There was nothing in that conversation worth keeping."),
    session_archive.MODEL_FAILED: (502, "The model could not write the note. Try again."),
}


def archive_session(session_id: str, body: ChatSessionArchive) -> dict[str, Any]:
    """Draft a note that archives a conversation (docs/decisions/086): one model call, a new-note draft the user decides."""
    outcome, draft = session_archive.archive(require_profile(body.persona)["handle"], session_id, body.model)
    if draft is None:
        status, detail = _ARCHIVE_ERRORS[outcome]
        raise HTTPException(status_code=status, detail=detail)
    return {"draft": draft}


def list_bin(persona: str | None) -> dict[str, Any]:
    """The persona's deleted conversations, the last deleted first (the Bin keeps them apart from the notes)."""
    return {"sessions": session_bin.list_deleted(require_profile(persona)["handle"])}


def restore_from_bin(body: ChatBinAction) -> dict[str, Any]:
    """Put a deleted conversation back (409 when one by its id exists already)."""
    _raise_unless_ok(session_bin.restore(require_profile(body.persona)["handle"], body.id or ""))
    return {"restored": body.id}


def purge_from_bin(session_id: str, persona: str | None) -> dict[str, Any]:
    """Delete one conversation from the Bin for good."""
    _raise_unless_ok(session_bin.purge(require_profile(persona)["handle"], session_id))
    return {"deleted": session_id}


def empty_bin(body: ChatBinAction) -> dict[str, Any]:
    """Delete every conversation in the Bin for good."""
    return {"deleted": session_bin.empty(require_profile(body.persona)["handle"])}
