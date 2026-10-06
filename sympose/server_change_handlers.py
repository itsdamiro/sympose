"""Route handlers for a persona's pending changes and the user's annotations on a note (docs/decisions/070).

Nothing here writes the vault: the editor applies an accepted proposal to its own text and the note is saved by the
ordinary save, so these routes list, read and forget. A proposal's status (pending, or outdated because its passage
was rewritten) and an annotation's (attached, or detached) are worked out against the note as it is on disk now."""

from typing import Any

from fastapi import HTTPException

from sympose import note_changes as nc
from sympose import note_changes_store as store
from sympose.server_change_models import AnnotationChange, AnnotationCreate, ChangesResolve, DraftText
from sympose.server_handlers import read_note, require_profile


def _handle(persona: str | None) -> str:
    return require_profile(persona)["handle"]


def _key(path: str) -> str:
    """The note's path in the one form changes are kept under (`A/Note` and `A/Note.md` are one note); a path that
    leaves the vault is a bad request, not a server error."""
    try:
        return store.key(path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


def _on_disk(path: str, persona: str | None) -> tuple[bool, str, float | None]:
    """`(exists, text, mtime)` of the note; a new note a persona proposed is not on disk yet."""
    try:
        note = read_note(path, persona)
    except HTTPException as error:
        if error.status_code == 404:
            return False, "", None
        raise
    return True, note["content"], note["mtime"]


def list_drafts(persona: str | None) -> dict[str, Any]:
    handle = _handle(persona)
    for entry in store.entries(handle):
        if entry["annotations"]:
            exists, text, mtime = _on_disk(entry["path"], persona)
            if exists:
                nc.prune(handle, entry["path"], text, mtime)

    def text_of(path: str) -> str | None:
        exists, text, _ = _on_disk(path, persona)
        return text if exists else None

    return {"drafts": nc.drafts(handle, text_of)}


def get_changes(path: str, persona: str | None) -> dict[str, Any]:
    handle = _handle(persona)
    path = _key(path)
    exists, text, mtime = _on_disk(path, persona)
    if exists:
        nc.prune(handle, path, text, mtime)
    entry = store.read(handle, path)
    return {
        "path": path,
        "exists": exists,
        "mtime": mtime,
        "proposals": [{**p, "status": nc.status(p, text)} for p in entry["proposals"]],
        "annotations": [{**a, "status": nc.annotation_status(a, text)} for a in entry["annotations"]],
    }


def resolve_changes(body: ChangesResolve) -> dict[str, Any]:
    handle = _handle(body.persona)
    path = _key(body.path)
    entry = store.read(handle, path)
    ids = [p["id"] for p in entry["proposals"]] if body.all else body.ids
    if body.accepted:
        exists, text, _ = _on_disk(path, body.persona)
        if exists:
            nc.settle_comments(handle, path, text, ids)
    gone = []
    for proposal_id in ids:
        try:
            nc.discard_proposal(handle, path, proposal_id)
            gone.append(proposal_id)
        except KeyError:
            pass  # already forgotten (the other window got there first): not an error
    if not body.all and not gone and body.ids:
        raise HTTPException(status_code=404, detail="No such pending change.")
    return {"path": path, "resolved": gone}


def save_draft(body: DraftText) -> dict[str, Any]:
    handle = _handle(body.persona)
    path = _key(body.path)
    try:
        nc.edit_draft(handle, path, body.text)
    except KeyError:
        raise HTTPException(status_code=404, detail="That note has no new-note draft.") from None
    return {"path": path}


def add_annotation(body: AnnotationCreate) -> dict[str, Any]:
    handle = _handle(body.persona)
    path = _key(body.path)
    exists, text, _ = _on_disk(path, body.persona)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Note `{path}` not found.")
    try:
        if body.reply_to:
            return nc.reply(handle, path, body.reply_to, text=body.text, author="user")
        if not body.quote:
            raise HTTPException(status_code=400, detail="Give the passage to comment on, or the comment it answers.")
        context = (body.before, body.after) if body.before is not None and body.after is not None else None
        return nc.annotate(handle, path, text, quote=body.quote, text=body.text, author="user", start=body.start, context=context)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such comment.")
    except nc.CannotAnchor as error:
        raise HTTPException(status_code=422, detail=str(error))


def change_annotation(body: AnnotationChange) -> dict[str, Any]:
    handle = _handle(body.persona)
    path = _key(body.path)
    if body.state is None and body.text is None and body.verdict is None:
        raise HTTPException(status_code=400, detail="Nothing to change: give a state, a text or a verdict.")
    try:
        nc.change_annotation(handle, path, body.id, text=body.text, state=body.state, verdict=body.verdict)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such comment.")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"path": path, "id": body.id}


def delete_annotation(path: str, annotation_id: str, persona: str | None) -> dict[str, Any]:
    path = _key(path)
    try:
        nc.delete_annotation(_handle(persona), path, annotation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such comment.")
    return {"path": path, "id": annotation_id}
