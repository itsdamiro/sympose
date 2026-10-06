"""A persona's own files, edited from the web (docs/decisions/061): `soul.md`, `profile.md`, `context.md` and
`decisions.md`, by an allow-list of names and never a path, so nothing else in a persona's folder (its
`persona.yaml`, its sessions) can be reached.

The soul is the shipped, tracked default, which the app never writes (docs/decisions/046): a saved soul goes to
`soul.local.md`, an untracked copy `load_soul` reads first, and the editor opens whichever is in effect (a reset
moves the copy aside to `soul.local.md.bak`, so what the user wrote is kept). The memory
files (docs/decisions/041) are already the user's own and are saved in place. Every save keeps the previous
content in `<file>.bak` and presents the mtime the editor opened the file at, as a note's save does, so a change
made meanwhile (the engine appending a decision, the terminal) is refused instead of overwritten.

A rewrite the engine staged for `profile.md` or `context.md` (`<file>.pending`, `engine/memory_write.py`) is read
here with a diff against the current file, then accepted or discarded one file at a time, the web's counterpart of
the terminal's `/memory review`."""

import os
import threading
from typing import Any

from sympose.atomic_write import write_atomic_text
from sympose.engine import memory_write
from sympose.persona_files import SOUL_FILENAME, SOUL_LOCAL_FILENAME, persona_dir, profiles_dir
from sympose.security import is_safe_path
from sympose.vault_write_concurrency import current_mtime, mtime_matches

OK, CONFLICT, FAILED, UNKNOWN = "ok", "conflict", "failed", "unknown"

# The four names, in the order the menu lists them, each with what it is in a user's words.
FILES: dict[str, tuple[str, str]] = {
    "soul.md": ("Soul", "How the persona talks: its voice and temperament."),
    "profile.md": ("Profile", "What the persona knows about you: stable facts and preferences."),
    "context.md": ("Context", "What is active right now: projects and blockers."),
    "decisions.md": ("Decisions", "A dated log of what you decided, and why."),
}
_PENDING = {"profile.md": memory_write.PROFILE_PENDING, "context.md": memory_write.CONTEXT_PENDING}
_APPLY = {"profile.md": memory_write.apply_profile, "context.md": memory_write.apply_context}
_LOCK = threading.Lock()


def _path(handle: str, filename: str) -> str | None:
    try:
        path = os.path.join(persona_dir(handle), filename)
    except ValueError:
        return None
    return path if is_safe_path(path, profiles_dir()) else None


def _effective(handle: str, name: str) -> str | None:
    """The file this name is read from: the soul's local copy when there is one, else the file itself."""
    if name == SOUL_FILENAME:
        local = _path(handle, SOUL_LOCAL_FILENAME)
        if local and os.path.isfile(local):
            return local
    return _path(handle, name)


def _target(handle: str, name: str) -> str | None:
    """The file a save goes to: the soul's local copy (the shipped soul is never written), else the file itself."""
    return _path(handle, SOUL_LOCAL_FILENAME if name == SOUL_FILENAME else name)


def list_files(handle: str) -> list[dict[str, Any]]:
    local = _path(handle, SOUL_LOCAL_FILENAME)
    rows = []
    for name, (label, description) in FILES.items():
        path = _effective(handle, name)
        pending = _path(handle, _PENDING[name]) if name in _PENDING else None
        rows.append({
            "name": name, "label": label, "description": description,
            "exists": bool(path and os.path.isfile(path)),
            "local": name == SOUL_FILENAME and bool(local and os.path.isfile(local)),
            "pending": bool(pending and os.path.isfile(pending)),
        })
    return rows


def read(handle: str, name: str) -> dict[str, Any] | None:
    """The file as it is in effect, whole and untouched, with its mtime (`None` while it does not exist yet, so a
    file not written so far opens empty and a first save creates it). `None` for a name outside the four."""
    if name not in FILES:
        return None
    path = _effective(handle, name)
    if path is None:
        return None
    local = name == SOUL_FILENAME and os.path.basename(path) == SOUL_LOCAL_FILENAME
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return {"name": name, "content": content, "mtime": current_mtime(path), "local": local}


def write(handle: str, name: str, text: str, expected_mtime: float | None) -> str:
    if name not in FILES:
        return UNKNOWN
    effective, target = _effective(handle, name), _target(handle, name)
    if effective is None or target is None:
        return FAILED
    with _LOCK:
        if not mtime_matches(effective, expected_mtime):  # the version the editor opened, not the file it will write
            return CONFLICT
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.isfile(target):
                with open(target, "r", encoding="utf-8") as f:
                    write_atomic_text(f"{target}.bak", f.read())
            write_atomic_text(target, text)
        except (OSError, UnicodeDecodeError):
            return FAILED
    return OK


def reset_soul(handle: str) -> bool:
    """Puts the shipped soul back in effect by moving the local copy aside to `soul.local.md.bak`, so what the user
    wrote is not thrown away. `False` when there was no local copy."""
    path = _path(handle, SOUL_LOCAL_FILENAME)
    if path is None:
        return False
    with _LOCK:
        try:
            os.replace(path, f"{path}.bak")
        except OSError:
            return False
    return True


def pending(handle: str, name: str) -> dict[str, str] | None:
    """The rewrite waiting for `profile.md` or `context.md`, and a diff of it against the file as it is now."""
    if name not in _PENDING:
        return None
    text = memory_write.pending_profile(handle) if name == "profile.md" else memory_write.pending_context(handle)
    if text is None:
        return None
    current = read(handle, name)
    return {"text": text, "diff": memory_write.diff_text((current or {}).get("content") or None, text, name)}


def _drop(handle: str, name: str) -> None:
    path = _path(handle, _PENDING[name])
    if path is None:
        return
    with _LOCK:
        try:
            os.remove(path)
        except OSError:
            pass


def accept_pending(handle: str, name: str) -> bool:
    waiting = pending(handle, name)
    if waiting is None:
        return False
    ok = _APPLY[name](handle, waiting["text"])  # rolls the current content into `<file>.bak`
    _drop(handle, name)
    return ok


def discard_pending(handle: str, name: str) -> bool:
    if pending(handle, name) is None:
        return False
    _drop(handle, name)
    return True
