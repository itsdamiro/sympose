"""
Vault note writes: `overwrite_note` (the web app editor saving an
*existing* note back to disk verbatim), plus the shared primitives
(`get_file_lock`, `write_atomic_text`) that `vault_write_create.py`,
`vault_write_delete.py`, and `vault_write_rename.py` build on.
"""

import os
import threading
import weakref
from contextlib import ExitStack, contextmanager
from typing import Any, Iterator

from sympose import vault_paths
from sympose.atomic_write import write_atomic_text
from sympose.vault_write_concurrency import NOTE_CONFLICT, mtime_matches
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND, NOTE_NOT_TEXT

# Weak values: a path's lock lives only while some writer holds or waits on it, so the table
# does not grow by one lock for every path ever touched (#114). A lock nobody references can
# be forgotten safely: the next writer for that path simply creates a fresh one.
_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
_locks_guard = threading.Lock()


def get_file_lock(path: str) -> threading.Lock:
    """One lock per absolute file path, so two writers racing on the same
    note serialize instead of interleaving their writes. Use it as
    `with get_file_lock(p):` -- the `with` is what keeps the lock alive
    while it is held."""
    with _locks_guard:
        lock = _locks.get(path)
        if lock is None:
            lock = _locks[path] = threading.Lock()
        return lock


@contextmanager
def get_file_locks(*paths: str) -> Iterator[None]:
    """Acquires `get_file_lock` for each of `paths`, always in sorted order —
    an operation that needs two paths locked at once (a rename's source and
    destination, a restore's trash source and original destination) must
    always acquire them in the same order as any other operation racing it,
    or two such operations can deadlock each acquiring one lock and waiting
    on the other."""
    with ExitStack() as stack:
        for p in sorted(set(paths)):
            stack.enter_context(get_file_lock(p))
        yield


def _with_line_endings(text: str, on_disk: bytes) -> str:
    """`text` (the editor's, with LF) in the line-break style most of the file on disk has: CRLF if more of its
    breaks are CRLF than bare LF, else LF (docs/decisions/048)."""
    crlf = on_disk.count(b"\r\n")
    if crlf > on_disk.count(b"\n") - crlf:
        return text.replace("\r\n", "\n").replace("\n", "\r\n")
    return text


def overwrite_note(
    profile: dict[str, Any],
    note_name: str,
    content: str,
    *,
    expected_mtime: float | None = None,
) -> str:
    """Replace an *existing* vault note's file with `content`, verbatim (the
    editor already owns the whole document, frontmatter included). Resolves
    the same file a read would return, so a web app save lands back on the
    note it was opened from. Overwrite only — a path with no existing file
    returns `NOTE_NOT_FOUND` rather than creating one; a path outside the
    persona's sandbox returns `NOTE_DENIED`; a caller-supplied
    `expected_mtime` that no longer matches the file on disk returns
    `NOTE_CONFLICT` instead of clobbering a concurrent write."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope

    target_file = resolve_existing_note(profile, note_name)
    if target_file is None:
        return NOTE_NOT_FOUND
    if not vault_paths.is_within_any(target_file, allowed_dirs):
        return NOTE_DENIED
    with get_file_lock(target_file):
        if not mtime_matches(target_file, expected_mtime):
            return NOTE_CONFLICT

        rel_display = os.path.relpath(target_file, mv)
        try:
            with open(target_file, "rb") as f:
                on_disk = f.read()
            try:
                on_disk.decode("utf-8")
            except UnicodeDecodeError:
                return NOTE_NOT_TEXT  # saving would replace bytes the editor could not show (docs/decisions/048)
            text = _with_line_endings(content.rstrip("\n") + "\n", on_disk)
            write_atomic_text(target_file, text, newline="")
            return f"Saved note: `{rel_display}`"
        except Exception as e:
            return f"Error: Failed to write note: {e}"
