"""The file behind a note's pending changes (docs/decisions/070): one JSON file per note, in the persona's own
folder (`profiles/<handle>/notes/`), never in the vault the user browses.

A note's entry holds that persona's proposals and annotations for it, and the note's path is kept inside the file
as well as in its name, so a name that had to be shortened still says which note it is. A whole load-change-save
cycle runs under one lock (the same per-path lock the vault writes use), so two writers at the same moment cannot
lose each other's change; an entry with nothing left in it is removed rather than kept empty."""

import hashlib
import json
import os
import posixpath
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from sympose.atomic_write import write_atomic_text
from sympose.persona_files import persona_dir
from sympose.vault_write import get_file_lock, get_file_locks

NOTES_DIR = "notes"
VERSION = 1
_NAME_LIMIT = 180  # a file name is limited to 255 bytes on most file systems; stay well under


def _folder(handle: str) -> str:
    return os.path.join(persona_dir(handle), NOTES_DIR)


def key(note_path: str) -> str:
    """The one form a note's path is kept under, whichever way it was written: the vault accepts `A/Note` and
    `A/Note.md`, stray quotes and spaces, `./A/Note` and `A/../A/Note` for the same note, and two forms must not make
    two entries. A path that leaves the vault, or names nothing, is refused."""
    clean = note_path.strip().strip("\"'")
    if not clean.endswith(".md"):
        clean += ".md"
    clean = posixpath.normpath(clean)
    if clean in (".", ".md") or clean.startswith(("/", "..")) or clean.endswith("/.md"):
        raise ValueError(f"Not a path to a note in the vault: {note_path!r}")
    return clean


def _file(handle: str, note_path: str) -> str:
    note_path = key(note_path)
    name = quote(note_path, safe="")  # one component: a slash becomes %2F, so the path cannot leave the folder
    if len(name) > _NAME_LIMIT:
        name = quote(note_path[-30:], safe="")[:60] + "-" + hashlib.sha1(note_path.encode("utf-8")).hexdigest()[:16]
    return os.path.join(_folder(handle), name + ".json")


def _empty(note_path: str) -> dict[str, Any]:
    return {"version": VERSION, "path": note_path, "proposals": [], "annotations": []}


def _load(file: str, note_path: str) -> dict[str, Any]:
    """The entry in `file`; an entry with nothing in it when the file is missing or damaged."""
    entry = _empty(note_path)
    try:
        with open(file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return entry
    if isinstance(data, dict):
        if isinstance(data.get("path"), str) and data["path"]:
            entry["path"] = data["path"]
        for key in ("proposals", "annotations"):
            if isinstance(data.get(key), list):
                entry[key] = [item for item in data[key] if isinstance(item, dict)]
    return entry


def _save(file: str, entry: dict[str, Any]) -> None:
    if not (entry["proposals"] or entry["annotations"]):
        try:
            os.unlink(file)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(file), exist_ok=True)
    write_atomic_text(file, json.dumps(entry, ensure_ascii=False, indent=1) + "\n")


def read(handle: str, note_path: str) -> dict[str, Any]:
    return _load(_file(handle, note_path), key(note_path))


def update(handle: str, note_path: str, change: Callable[[dict[str, Any]], Any]) -> Any:
    """Runs `change(entry)` on the note's entry under its lock and saves the result; what `change` returns is
    returned. If `change` raises, nothing is saved."""
    file, note_path = _file(handle, note_path), key(note_path)
    with get_file_lock(file):
        entry = _load(file, note_path)
        result = change(entry)
        _save(file, entry)
        return result


def entries(handle: str) -> list[dict[str, Any]]:
    """Every note's entry for this persona, skipping any file that cannot be read."""
    folder = _folder(handle)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    found = []
    for name in names:
        if name.endswith(".json"):
            entry = _load(os.path.join(folder, name), "")
            if entry["path"] and (entry["proposals"] or entry["annotations"]):
                found.append(entry)
    return found


def move(handle: str, old: str, new: str) -> None:
    """A note was renamed or moved: its entry follows it (joining any entry already at the new path)."""
    old_file, new_file, old, new = _file(handle, old), _file(handle, new), key(old), key(new)
    if old_file == new_file:
        return
    with get_file_locks(old_file, new_file):
        if not os.path.exists(old_file):
            return
        moved = _load(old_file, old)
        if os.path.exists(new_file) and os.path.samefile(old_file, new_file):
            # A change of case only, on a file system that reads both names as one file: the entry stays where it is
            # and says its new path (loading it as the target and then deleting the old file would delete it).
            moved["path"] = new
            _save(old_file, moved)
            return
        target = _load(new_file, new)
        target["path"] = new
        target["proposals"] += moved["proposals"]
        target["annotations"] += moved["annotations"]
        _save(new_file, target)
        os.unlink(old_file)


def move_prefix(handle: str, old_folder: str, new_folder: str) -> None:
    """A folder was renamed: every entry under it follows its note to the new path (docs/decisions/073). Only notes
    inside the folder: `People and Pets/` and `Other/People/` are not under `People/`."""
    prefix = old_folder.strip("/") + "/"
    for entry in entries(handle):
        if entry["path"].startswith(prefix):
            move(handle, entry["path"], new_folder.strip("/") + "/" + entry["path"][len(prefix):])


def drop(handle: str, note_path: str) -> None:
    file, note_path = _file(handle, note_path), key(note_path)
    with get_file_lock(file):
        _save(file, _empty(note_path))
