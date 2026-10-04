"""Route handlers for a persona's pending changes and the user's annotations on a note (docs/decisions/070).

Nothing here writes the vault: the editor applies an accepted proposal to its own text and the note is saved by the
ordinary save, so these routes list, read and forget. A proposal's status (pending, or outdated because its passage
was rewritten) and an annotation's (attached, or detached) are worked out against the note as it is on disk now."""

from typing import Any

from fastapi import HTTPException

from sympose import note_changes as nc
from sympose import note_changes_store as store
from sympose.server_change_models import AnnotationChange, AnnotationCreate, ChangesResolve
from sympose.server_handlers import read_note, require_profile


def _handle(persona: str | None) -> str:
    return require_profile(persona)["handle"]


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
    return {"drafts": nc.drafts(_handle(persona))}


def get_changes(path: str, persona: str | None) -> dict[str, Any]:
    handle = _handle(persona)
    exists, text, mtime = _on_disk(path, persona)
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
    entry = store.read(handle, body.path)
    ids = [p["id"] for p in entry["proposals"]] if body.all else body.ids
    gone = []
    for proposal_id in ids:
        try:
            nc.discard_proposal(handle, body.path, proposal_id)
            gone.append(proposal_id)
        except KeyError:
            pass  # already forgotten (the other window got there first): not an error
    if not body.all and not gone and body.ids:
        raise HTTPException(status_code=404, detail="No such pending change.")
    return {"path": body.path, "resolved": gone}


def add_annotation(body: AnnotationCreate) -> dict[str, Any]:
    handle = _handle(body.persona)
    exists, text, _ = _on_disk(body.path, body.persona)
    if not exists:
        raise HTTPException(status_code=404, detail=f"Note `{body.path}` not found.")
    try:
        return nc.annotate(handle, body.path, text, quote=body.quote, text=body.text, author="user", reply_to=body.reply_to, start=body.start)
    except nc.CannotAnchor as error:
        raise HTTPException(status_code=422, detail=str(error))


def change_annotation(body: AnnotationChange) -> dict[str, Any]:
    handle = _handle(body.persona)
    if body.state is None and body.text is None:
        raise HTTPException(status_code=400, detail="Nothing to change: give a state or a text.")
    try:
        nc.change_annotation(handle, body.path, body.id, text=body.text, state=body.state)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such comment.")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"path": body.path, "id": body.id}


def delete_annotation(path: str, annotation_id: str, persona: str | None) -> dict[str, Any]:
    try:
        nc.delete_annotation(_handle(persona), path, annotation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such comment.")
    return {"path": path, "id": annotation_id}
