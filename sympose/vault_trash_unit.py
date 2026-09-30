"""
Folders in the bin (docs/decisions/050): the summary of each deleted folder for the listing, and
restoring one as a unit. Split out of `vault_trash` to keep it small.
"""

import os
from typing import Any

from sympose import vault_trash, vault_trash_folders
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND


def summarize(mv: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per deleted folder that has files in `rows` (the listing, already in the persona's scope):
    `{trash_dir, original_path, deleted_at, count}`, newest deletion first."""
    records = vault_trash_folders.load(os.path.join(mv, vault_trash.TRASH_DIRNAME))
    counts: dict[str, int] = {}
    for row in rows:
        if "folder" in row:
            counts[row["folder"]] = counts.get(row["folder"], 0) + 1
    folders = [
        {
            "trash_dir": d,
            "original_path": records[d]["original"],
            "deleted_at": records[d].get("deleted_at") or 0,
            "count": n,
        }
        for d, n in counts.items()
        if d in records
    ]
    return sorted(folders, key=lambda f: f["deleted_at"], reverse=True)


def restore_folder(mv: str, allowed_dirs: list[str], trash_dir: str) -> tuple[list[str], list[dict[str, str]]] | str:
    """Puts back every file a deleted folder held that is still in the bin and whose place is free, through the
    same restore a single file uses (it never overwrites). Returns `(restored paths, skipped)` where each skipped
    entry is `{path, reason}`, or `NOTE_NOT_FOUND` when `trash_dir` is not a recorded folder."""
    troot = os.path.join(mv, vault_trash.TRASH_DIRNAME)
    record = vault_trash_folders.load(troot).get(trash_dir)
    if record is None:
        return NOTE_NOT_FOUND
    restored: list[str] = []
    skipped: list[dict[str, str]] = []
    for inside in record["files"]:
        trash_rel = f"{trash_dir}/{inside}"
        if not os.path.isfile(os.path.join(troot, trash_rel)):
            continue  # already restored or deleted on its own
        result, path = vault_trash.restore(mv, allowed_dirs, trash_rel)
        if path is not None:
            restored.append(path)
        else:
            skipped.append({"path": f"{record['original']}/{inside}", "reason": _reason(result)})
    vault_trash_folders.prune(troot)
    return restored, skipped


def _reason(result: str) -> str:
    if result == NOTE_EXISTS:
        return "already exists"
    if result == NOTE_DENIED:
        return "outside this persona's folders"
    if result == NOTE_NOT_FOUND:
        return "no longer in the bin"
    return result.removeprefix("Error: ")
