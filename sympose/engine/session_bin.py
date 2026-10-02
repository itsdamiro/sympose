"""The Bin's conversations (docs/decisions/057): what `session_manage.delete` moved to `sessions/.trash/`, listed, put
back, or deleted for good. A trashed conversation is `<id>.jsonl` with its recap beside it as `<id>.recap.md`; when
an earlier one by that id is already there the later one is `<id>.2.jsonl`, and so on, so the name in the trash
(without its extension) is what names it here, and the conversation's own id is what comes before the first dot.
The deletion time is the file's modification time, which `delete` sets when it moves the file."""

import logging
import os
from typing import Any

from sympose.engine import recap, session
from sympose.engine.session_manage import BAD_ID, EXISTS, FAILED, NOT_FOUND, OK, TRASH

log = logging.getLogger(__name__)


def _dir(handle: str) -> str:
    return os.path.join(session.sessions_dir(handle), TRASH)


def _names(handle: str) -> list[str]:
    try:
        return sorted(n.removesuffix(".jsonl") for n in os.listdir(_dir(handle)) if n.endswith(".jsonl"))
    except OSError:
        return []


def _file(handle: str, name: str, extension: str = "jsonl") -> str | None:
    """The trash file for `name`, or `None` when `name` is not a plain file name (so no id reaches outside the trash)."""
    if not name or name != os.path.basename(name) or name.startswith("."):
        return None
    return os.path.join(_dir(handle), f"{name}.{extension}")


def list_deleted(handle: str) -> list[dict[str, Any]]:
    """The deleted conversations, the last deleted first: `id` (its name in the trash), `title`, `turns`,
    `deleted_at` (epoch seconds) and `pinned_at`."""
    rows = []
    for name in _names(handle):
        path = _file(handle, name)
        loaded = session.load_session(handle, f"{TRASH}/{name}")  # the trash is inside the sessions folder
        if path is None or loaded is None:
            continue
        meta = loaded["meta"]
        rows.append({
            "id": name,
            "title": str(meta.get("title") or ""),
            "turns": len(loaded["turns"]),
            "deleted_at": os.path.getmtime(path),
            "pinned_at": meta.get("pinned_at") if isinstance(meta.get("pinned_at"), str) else None,
        })
    return sorted(rows, key=lambda row: row["deleted_at"], reverse=True)


def restore(handle: str, name: str) -> str:
    """Put the conversation (and its recap, if it has one) back under its own id. `EXISTS` when a conversation
    by that id is there already: it is never replaced."""
    source = _file(handle, name)
    if source is None:
        return BAD_ID
    if not os.path.exists(source):
        return NOT_FOUND
    try:
        target = session.session_path(handle, name.split(".", 1)[0])
        if os.path.exists(target):
            return EXISTS
        recap_source, recap_target = _file(handle, name, "recap.md"), recap.path(handle, name.split(".", 1)[0])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.replace(source, target)
        if recap_source and os.path.exists(recap_source) and not os.path.exists(recap_target):
            os.makedirs(os.path.dirname(recap_target), exist_ok=True)
            os.replace(recap_source, recap_target)
    except (OSError, ValueError) as e:
        log.warning("Could not restore conversation %s: %s", name, e)
        return FAILED
    return OK


def purge(handle: str, name: str) -> str:
    """Delete the conversation and its recap from the trash for good."""
    source = _file(handle, name)
    if source is None:
        return BAD_ID
    if not os.path.exists(source):
        return NOT_FOUND
    try:
        os.remove(source)
        recap_source = _file(handle, name, "recap.md")
        if recap_source and os.path.exists(recap_source):
            os.remove(recap_source)
    except OSError as e:
        log.warning("Could not delete conversation %s for good: %s", name, e)
        return FAILED
    return OK


def empty(handle: str) -> int:
    """Delete every conversation in the trash for good; how many there were."""
    done = 0
    for name in _names(handle):
        if purge(handle, name) == OK:
            done += 1
    return done
