"""
`<vault>/.trash` recovery surface.

`vault_write_delete.delete_note` moves a note, and `delete_folder` a whole folder, to
`<vault>/.trash/<original relpath>` instead of unlinking it. This module is the read / restore /
purge half of that contract: list what is recoverable, move one file back to where it came from,
or unlink it for good. The bin holds every file a deleted folder held (attachments, PDFs, canvases,
not only notes), so it lists, restores and purges every file, and emptying it removes them all
(docs/decisions/045, issue #100). The clash-index sidecar that
tracks a timestamp-suffixed trash name's real original path lives in
`vault_trash_index.py`.

Every function sandbox-checks both ends against the caller's allowed vault
folders and never raises across the API boundary — a bad path comes back as
one of `vault_write_status`'s shared sentinels, not a 500.
"""

import os
from typing import Any

from sympose.security import is_safe_path
from sympose.vault_paths import is_within_any
from sympose import vault_trash_folders
from sympose.vault_trash_index import INDEX_FILENAME, forget_clash, load_index, original_relpath
from sympose.vault_write import get_file_lock, get_file_locks
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND

TRASH_DIRNAME = ".trash"


def _prune_empty_dirs(root: str, start: str) -> None:
    """Walk up from `start`, removing now-empty directories, stopping at
    `root` (exclusive) or the first non-empty parent. Best-effort."""
    cur = start
    try:
        root_real = os.path.realpath(root)
        while os.path.realpath(cur) != root_real and is_safe_path(cur, root):
            if os.listdir(cur):
                break
            os.rmdir(cur)
            cur = os.path.dirname(cur)
    except OSError:
        pass


def list_trashed(mv: str, allowed_dirs: list[str]) -> list[dict[str, Any]]:
    """Recoverable files under `<mv>/.trash` (notes and everything else a deleted folder held),
    newest deletion first. Each row: `{trash_path, original_path, deleted_at (mtime epoch), size}`, plus `folder` (its bin directory) when it was deleted with a folder (docs/decisions/050).
    Hidden files and folders (`.DS_Store`, `.obsidian`, the clash index) are not listed, as the tree
    does not list them; emptying the bin still removes them. Scoped to the persona: an entry whose
    original location sits outside `allowed_dirs` is omitted."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    if not os.path.isdir(troot):
        return []
    # Loaded once for the whole listing — `original_relpath` alone would
    # re-read the index file from disk once per trashed item.
    index = load_index(troot)
    group_of = vault_trash_folders.members(troot)
    rows: list[dict[str, Any]] = []
    for cur, dirs, files in os.walk(troot):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if fn.startswith("."):
                continue
            fp = os.path.join(cur, fn)
            if not is_safe_path(fp, troot):
                continue
            trash_rel = os.path.relpath(fp, troot).replace(os.sep, "/")
            orig_rel = index.get(trash_rel, trash_rel)
            orig_abs = os.path.join(mv, orig_rel)
            if not is_within_any(orig_abs, allowed_dirs):
                continue
            try:
                st = os.stat(fp)
            except OSError:
                continue
            rows.append(
                {
                    "trash_path": trash_rel,
                    "original_path": orig_rel,
                    "deleted_at": st.st_mtime,
                    "size": st.st_size,
                    **({"folder": group_of[trash_rel]} if trash_rel in group_of else {}),
                }
            )
    rows.sort(key=lambda r: r["deleted_at"], reverse=True)
    return rows


def _resolve_in_trash(mv: str, trash_rel: str) -> str:
    """Absolute path of `trash_rel` under `<mv>/.trash`, or a `NOTE_DENIED` /
    `NOTE_NOT_FOUND` sentinel."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = os.path.normpath(os.path.join(troot, (trash_rel or "").lstrip("/\\")))
    if not is_safe_path(src, troot):
        return NOTE_DENIED
    if not os.path.isfile(src):
        return NOTE_NOT_FOUND
    return src


def _resolve_trash_entry(
    mv: str, trash_rel: str
) -> tuple[str, str, str, str] | str:
    """Resolves a trash-relative path to (`src`, `troot`, `trash_rel_actual`,
    `orig_rel`) — the trashed file's absolute path, the trash root, its
    actual trash-relative path, and its recorded original vault-relative
    path — or a `NOTE_DENIED`/`NOTE_NOT_FOUND` sentinel."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    src = _resolve_in_trash(mv, trash_rel)
    if src in (NOTE_DENIED, NOTE_NOT_FOUND):
        return src
    trash_rel_actual = os.path.relpath(src, troot).replace(os.sep, "/")
    orig_rel = original_relpath(troot, trash_rel_actual)
    return src, troot, trash_rel_actual, orig_rel


def restore(mv: str, allowed_dirs: list[str], trash_rel: str) -> tuple[str, str | None]:
    """Move a trashed note back to its original vault-relative path. Returns
    `(result, path)`: on success a message and that path; otherwise `NOTE_NOT_FOUND` /
    `NOTE_EXISTS` (something occupies the original spot now) / `NOTE_DENIED` / `"Error: …"`
    and `None`. The path is its own value, not the result, because a note may be called
    `Error: …` and the caller reads a result that starts that way as a failure."""
    entry = _resolve_trash_entry(mv, trash_rel)
    if isinstance(entry, str):
        return entry, None
    src, troot, trash_rel_actual, orig_rel = entry
    dst = os.path.normpath(os.path.join(mv, orig_rel))
    if not is_within_any(dst, allowed_dirs):
        return NOTE_DENIED, None
    # Locks both ends: `src` against a concurrent restore/purge of the same
    # trash entry, `dst` against a concurrent create/restore landing on the
    # same original path — the same double-lock shape `overwrite_note` uses.
    with get_file_locks(src, dst):
        if os.path.exists(dst):
            return NOTE_EXISTS, None
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
        except OSError as e:
            return f"Error: Failed to restore note: {e}", None
    forget_clash(troot, trash_rel_actual)
    _prune_empty_dirs(troot, os.path.dirname(src))
    restored = os.path.relpath(dst, mv).replace(os.sep, "/")
    return f"Restored to `{restored}`", restored


def purge(mv: str, allowed_dirs: list[str], trash_rel: str) -> str:
    """Permanently unlink one trashed note. Returns `""` on success, or
    `NOTE_NOT_FOUND` / `NOTE_DENIED` / `"Error: …"`. Scoped: an entry whose
    original location is outside `allowed_dirs` cannot be purged through
    this persona."""
    entry = _resolve_trash_entry(mv, trash_rel)
    if isinstance(entry, str):
        return entry
    src, troot, trash_rel_actual, orig_rel = entry
    if not is_within_any(os.path.join(mv, orig_rel), allowed_dirs):
        return NOTE_DENIED
    try:
        with get_file_lock(src):
            os.remove(src)
    except OSError as e:
        return f"Error: Failed to delete note: {e}"
    forget_clash(troot, trash_rel_actual)
    _prune_empty_dirs(troot, os.path.dirname(src))
    return ""


def _prune_empty_folders(mv: str, troot: str, allowed_dirs: list[str]) -> None:
    """Removes every empty folder left under the bin (a deleted folder's empty sub-folders never held a
    file to purge), bottom-up, inside the persona's scope only."""
    for cur, _, _ in os.walk(troot, topdown=False):
        if cur == troot or not is_within_any(os.path.join(mv, os.path.relpath(cur, troot)), allowed_dirs):
            continue
        try:
            os.rmdir(cur)  # refuses a folder that still holds something
        except OSError:
            pass


def purge_all(mv: str, allowed_dirs: list[str]) -> int:
    """Empty the bin: every in-scope file is removed, the ones the list shows and the hidden ones it
    does not, and the folders that leave empty are pruned. Files outside `allowed_dirs` stay. Links are
    never followed out of the bin. Returns how many listed (non-hidden) files were removed."""
    troot = os.path.join(mv, TRASH_DIRNAME)
    found = []
    for cur, _, files in os.walk(troot):
        for fn in files:
            rel = os.path.relpath(os.path.join(cur, fn), troot).replace(os.sep, "/")
            if rel not in (INDEX_FILENAME, vault_trash_folders.FOLDERS_FILENAME):  # bookkeeping, not files the user deleted
                found.append((rel, any(part.startswith(".") for part in rel.split("/"))))
    removed = 0
    for rel, hidden in found:
        if purge(mv, allowed_dirs, rel) == "" and not hidden:
            removed += 1
    _prune_empty_folders(mv, troot, allowed_dirs)
    vault_trash_folders.prune(troot)
    return removed
