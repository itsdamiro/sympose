"""A persona's list of conversations and what the user can do to one (docs/decisions/057): rename it, pin it to
the top, delete it. The session file stays append-only (docs/decisions/049): a rename or a pin is a later meta
line, which wins on load, so nothing already written is touched. Delete is soft: the file and its recap move to
`sessions/.trash/` (the persona stops knowing the conversation, the user can move them back by hand); nothing
the user wrote is destroyed by a click. A conversation with a reply being written is not deleted."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from sympose.engine import recap, session, turn_cancel, turn_status
from sympose.engine.session_records import append_text

log = logging.getLogger(__name__)

TRASH = ".trash"
MAX_TITLE = 80
OK, NOT_FOUND, BAD_TITLE, BUSY, FAILED = "ok", "not_found", "bad_title", "busy", "failed"


def _row(handle: str, session_id: str, loaded: dict[str, Any]) -> dict[str, Any]:
    meta = loaded["meta"]
    return {
        "id": session_id,
        "title": str(meta.get("title") or ""),
        "turns": len(loaded["turns"]),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "pinned_at": meta.get("pinned_at") if isinstance(meta.get("pinned_at"), str) else None,
        "replying": turn_status.phase(handle, session_id) is not None or turn_cancel.running(handle, session_id),
    }


def list_sessions(handle: str) -> list[dict[str, Any]]:
    """The persona's conversations: the pinned ones first, in the order they were pinned, then the rest, the one
    last used first. A conversation with no turns is listed only when it is the newest: it is the new one the
    user opened on purpose (docs/decisions/044), and a blank one left behind is not worth a row."""
    rows: list[dict[str, Any]] = []
    for session_id in session.session_ids(handle):
        loaded = session.load_session(handle, session_id)
        if loaded is None or (not loaded["turns"] and rows):
            continue
        rows.append(_row(handle, session_id, loaded))
    pinned = sorted((row for row in rows if row["pinned_at"]), key=lambda row: row["pinned_at"])
    others = sorted((row for row in rows if not row["pinned_at"]), key=lambda row: row["updated_at"] or "", reverse=True)
    return pinned + others


def _append_meta(handle: str, session_id: str, meta: dict[str, Any]) -> bool:
    try:
        append_text(session.session_path(handle, session_id), json.dumps({**meta, "type": "meta"}) + "\n")
        return True
    except (OSError, ValueError) as e:
        log.warning("Could not update session %s: %s", session_id, e)
        return False


def rename(handle: str, session_id: str, title: str) -> str:
    """Give the conversation `title` (one line, up to `MAX_TITLE` characters)."""
    title = " ".join(title.split())
    if not title or len(title) > MAX_TITLE:
        return BAD_TITLE
    loaded = _load(handle, session_id)
    if loaded is None:
        return NOT_FOUND
    return OK if _append_meta(handle, session_id, {**loaded["meta"], "title": title}) else FAILED


def pin(handle: str, session_id: str, on: bool) -> str:
    """Pin the conversation to the top of the list, or unpin it. Pinning one already pinned keeps its place."""
    loaded = _load(handle, session_id)
    if loaded is None:
        return NOT_FOUND
    pinned = isinstance(loaded["meta"].get("pinned_at"), str)
    if pinned == on:  # already as wanted: nothing to write
        return OK
    meta = {key: value for key, value in loaded["meta"].items() if key != "pinned_at"}
    if on:
        meta["pinned_at"] = datetime.now(timezone.utc).isoformat()
    return OK if _append_meta(handle, session_id, meta) else FAILED


def delete(handle: str, session_id: str) -> str:
    """Move the conversation, and its recap, to `sessions/.trash/`. `BUSY` while a reply is being written into it."""
    if _load(handle, session_id) is None:
        return NOT_FOUND
    if turn_cancel.running(handle, session_id) or turn_status.phase(handle, session_id) is not None:
        return BUSY
    try:
        trash = os.path.join(session.sessions_dir(handle), TRASH)
        os.makedirs(trash, exist_ok=True)
        os.replace(session.session_path(handle, session_id), _free(trash, f"{session_id}.jsonl"))
        recap_file = recap.path(handle, session_id)
        if os.path.exists(recap_file):
            os.replace(recap_file, _free(trash, f"{session_id}.recap.md"))
    except (OSError, ValueError) as e:
        log.warning("Could not delete session %s: %s", session_id, e)
        return FAILED
    return OK


def _load(handle: str, session_id: str) -> dict[str, Any] | None:
    try:
        return session.load_session(handle, session_id)
    except ValueError:  # an id that is not one of this persona's files
        return None


def _free(directory: str, name: str) -> str:
    """`name` in `directory`, or with a number before its extension when one by that name is already there
    (a conversation deleted, put back by hand and deleted again): an earlier one in the trash is never replaced."""
    stem, ext = name.split(".", 1)
    path, number = os.path.join(directory, name), 1
    while os.path.exists(path):
        number += 1
        path = os.path.join(directory, f"{stem}.{number}.{ext}")
    return path
