"""Committing a proposed rewrite of `context.md`/`profile.md` (docs/decisions/041): staging (`ask`
mode) and applying (`auto` mode, or a staged proposal accepted through `/memory review`). `memory.py`
owns reading the three memory files and appending to `decisions.md`; this is the one place a whole
file is replaced -- the one persona-memory write a weak model can lose or garble existing content
on, not just add to, which is exactly what `memory_rewrite`'s `ask`/`auto` gate exists to weigh.

    profiles/<handle>/context.md.pending    a staged proposal, not yet on the file it would replace
    profiles/<handle>/profile.md.pending

Every apply also rolls the file's current content into `<file>.bak` first, the same rolling
one-generation backup `memory.append_decision` already leaves for `decisions.md`."""

import difflib
import os
import threading

from sympose.atomic_write import write_atomic_text
from sympose.engine.memory import CONTEXT_FILENAME, PROFILE_FILENAME, read_file
from sympose.persona_files import persona_dir, profiles_dir
from sympose.security import is_safe_path

CONTEXT_PENDING = f"{CONTEXT_FILENAME}.pending"
PROFILE_PENDING = f"{PROFILE_FILENAME}.pending"

# One lock for every persona, not one per handle -- the same reasoning `memory.py`'s own
# `_WRITE_LOCK` already uses: a rewrite (background refresh, or a review accepted in the CLI) is
# rare enough that the contention a finer lock would avoid never happens in practice.
_WRITE_LOCK = threading.Lock()


def _path(handle: str, filename: str) -> str | None:
    try:
        path = os.path.join(persona_dir(handle), filename)
    except ValueError:
        return None
    return path if is_safe_path(path, profiles_dir()) else None


def pending_profile(handle: str) -> str | None:
    return read_file(handle, PROFILE_PENDING)


def pending_context(handle: str) -> str | None:
    return read_file(handle, CONTEXT_PENDING)


def has_pending(handle: str) -> bool:
    return pending_profile(handle) is not None or pending_context(handle) is not None


def _write(handle: str, filename: str, text: str) -> bool:
    path = _path(handle, filename)
    if path is None:
        return False
    with _WRITE_LOCK:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            write_atomic_text(path, text.strip() + "\n")
        except OSError:
            return False
    return True


def stage_profile(handle: str, text: str) -> bool:
    return _write(handle, PROFILE_PENDING, text)


def stage_context(handle: str, text: str) -> bool:
    return _write(handle, CONTEXT_PENDING, text)


def _apply(handle: str, filename: str, text: str) -> bool:
    path = _path(handle, filename)
    if path is None:
        return False
    with _WRITE_LOCK:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                current = f.read()
        except FileNotFoundError:
            current = ""
        except OSError:
            return False
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if current:
                write_atomic_text(f"{path}.bak", current)
            write_atomic_text(path, text.strip() + "\n")
        except OSError:
            return False
    return True


def apply_profile(handle: str, text: str) -> bool:
    return _apply(handle, PROFILE_FILENAME, text)


def apply_context(handle: str, text: str) -> bool:
    return _apply(handle, CONTEXT_FILENAME, text)


def discard_pending(handle: str) -> None:
    """Removes any staged proposal without applying it -- a no-op, never raising, when there is
    none (the same posture `memory.py`'s own reads use)."""
    with _WRITE_LOCK:
        for filename in (PROFILE_PENDING, CONTEXT_PENDING):
            path = _path(handle, filename)
            if path is None:
                continue
            try:
                os.remove(path)
            except OSError:
                pass


def diff_text(old: str | None, new: str, label: str) -> str:
    """A unified plain-text diff between `old` (the file's current content, or `None` when it
    doesn't exist yet) and `new` (a staged proposal), for `/memory review` -- docs/decisions/041's
    "Sympose computes a plain-text diff between the file's current content and the model's
    proposed rewrite, and writes only after the user confirms it"."""
    return "\n".join(
        difflib.unified_diff(
            (old or "").splitlines(), new.splitlines(),
            fromfile=f"{label} (current)", tofile=f"{label} (proposed)", lineterm="",
        )
    )


def accept_pending(handle: str) -> bool:
    """Applies whichever of `context.md`/`profile.md` has a staged proposal, then clears the
    staging either way -- a partly-applied accept must not be retried against a file one half of
    it already changed. `True` when there was nothing staged (accepting nothing is not a failure)
    or everything staged applied; `False` when an apply failed."""
    profile_text, context_text = pending_profile(handle), pending_context(handle)
    ok = True
    if profile_text is not None:
        ok = apply_profile(handle, profile_text) and ok
    if context_text is not None:
        ok = apply_context(handle, context_text) and ok
    discard_pending(handle)
    return ok
