"""
The `.trash-folders.json` sidecar: which files a deleted folder held (docs/decisions/050).

A folder deleted as a unit is moved whole to `<vault>/.trash/<folder>`, but a note deleted alone
lands in the same place, so the bin's layout cannot say which files went together. `delete_folder`
records the group here, and the listing and "Restore folder" read it back. Like the clash index
(`vault_trash_index`) it is bookkeeping, not a deleted file: hidden, never listed, never counted.
Each record is `{trash_dir: {"original": vault-relative path, "deleted_at": epoch, "files": [paths
inside the folder]}}`.
"""

import json
import os
import time
from typing import Any

from sympose.vault_write import get_file_lock, write_atomic_text

FOLDERS_FILENAME = ".trash-folders.json"


def _path(troot: str) -> str:
    return os.path.join(troot, FOLDERS_FILENAME)


def load(troot: str) -> dict[str, dict[str, Any]]:
    try:
        with open(_path(troot), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if _well_formed(v)} if isinstance(data, dict) else {}


def _well_formed(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(record.get("original"), str)
        and isinstance(record.get("files"), list)
        and all(isinstance(f, str) for f in record["files"])
    )


def _save(troot: str, records: dict[str, dict[str, Any]]) -> None:
    try:
        if records:
            write_atomic_text(_path(troot), json.dumps(records, ensure_ascii=False))
        elif os.path.exists(_path(troot)):
            os.remove(_path(troot))
    except OSError:
        pass  # bookkeeping: losing it leaves the files as loose rows, never loses a file


def record(troot: str, trash_dir: str, original: str, files: list[str]) -> None:
    """Notes that `trash_dir` (bin-relative) is the folder `original` with `files` (paths inside it), deleted now.
    Replaces any earlier record for the same directory. Drops records whose directory has gone."""
    with get_file_lock(_path(troot)):
        records = _without_gone(troot, load(troot))
        records[trash_dir] = {"original": original, "deleted_at": time.time(), "files": sorted(files)}
        _save(troot, records)


def prune(troot: str) -> None:
    """Drops the records whose bin directory no longer exists (all restored or deleted)."""
    with get_file_lock(_path(troot)):
        records = load(troot)
        kept = _without_gone(troot, records)
        if kept != records or (not kept and os.path.exists(_path(troot))):
            _save(troot, kept)


def _without_gone(troot: str, records: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {d: r for d, r in records.items() if os.path.isdir(os.path.join(troot, d))}


def members(troot: str) -> dict[str, str]:
    """`{bin-relative file path: its folder's bin directory}` for every recorded file still in the bin."""
    found: dict[str, str] = {}
    for trash_dir, rec in load(troot).items():
        for inside in rec["files"]:
            rel = f"{trash_dir}/{inside}"
            if os.path.isfile(os.path.join(troot, rel)):
                found[rel] = trash_dir
    return found
