"""What moving or merging a folder leaves behind (docs/decisions/074): two observations for `sympose vault --health`,
never faults and never fixed from here (the fix belongs to the future `vault --fix`, #101). Each reads the notes a
persona can read and returns `(note path, message)` pairs; `vault_health` turns them into findings."""

import posixpath
import re
from typing import Any

_NUMBERED = re.compile(r"^(?P<stem>.+) \((?P<n>\d+)\)$")


def stale_definitions(notes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """A note named after its folder inside a folder that is not top-level (`Projects/Garden/Garden.md`): it looks like
    a folder description that stopped applying, since only a top-level folder's is read (ADR 033). Moving the folder
    back to the top would make it one again."""
    found = []
    for note in notes:
        rel = note["rel_path"].replace("\\", "/")
        parts = rel.split("/")
        if len(parts) >= 3 and posixpath.splitext(parts[-1])[0].lower() == parts[-2].lower():
            found.append((rel, f"is named after its folder, but `{parts[-2]}` is not a top-level folder, so it is not read as its description"))
    return found


def numbered_twins(notes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """`Anna (2).md` beside `Anna.md` in one folder: what a merge makes of two notes with one name, so it may be a
    duplicate to combine."""
    names = {n["rel_path"].replace("\\", "/").lower() for n in notes}
    found = []
    for note in notes:
        rel = note["rel_path"].replace("\\", "/")
        folder, name = posixpath.split(rel)
        stem, extension = posixpath.splitext(name)
        twin = _NUMBERED.match(stem)
        if twin and int(twin["n"]) >= 2 and posixpath.join(folder, twin["stem"] + extension).lower() in names:
            found.append((rel, f"has the same name as `{twin['stem']}{extension}` in its folder with a number added: it may be a duplicate to combine"))
    return found
