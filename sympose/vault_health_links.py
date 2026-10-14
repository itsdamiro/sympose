"""Links whose folder no longer matches (docs/decisions/084): a `[[Folder/Note]]` that names no note's path but whose
name one note has, which is what a move leaves behind (#101). The graph resolves a link by its last segment, so the
"Links to no note" check never sees these; Obsidian reads the qualifier as a path and does not find the note.
Returns `(note path, message, old target, new target or None)`; `vault_health` turns them into findings."""

import os
import re
from typing import Any

from sympose.vault_defaults import ATTACHMENT_EXTENSIONS, NOTE_EXTENSIONS

_WIKILINK = re.compile(r"!?\[\[([^\[\]\r\n]+?)\]\]")


def _target(inner: str) -> str:
    return re.match(r"^([^#|]*)", inner).group(1).strip()


def stale_folder_links(notes: list[dict[str, Any]]) -> list[tuple[str, str, str, str | None]]:
    paths = {n["rel_path"].replace("\\", "/") for n in notes}
    stripped = {os.path.splitext(p)[0].lower(): p for p in paths}
    by_name: dict[str, list[str]] = {}
    for rel in paths:
        by_name.setdefault(os.path.splitext(os.path.basename(rel))[0].lower(), []).append(rel)
    found = []
    for note in sorted(notes, key=lambda n: n["rel_path"]):
        source, seen = note["rel_path"].replace("\\", "/"), set()
        for match in _WIKILINK.finditer(note.get("full_content") or ""):
            target = _target(match.group(1))
            segments = target.replace("\\", "/").lstrip("/").split("/")
            stem, ext = os.path.splitext(segments[-1])
            if len(segments) < 2 or target in seen or ext.lower() in ATTACHMENT_EXTENSIONS:
                continue
            seen.add(target)
            leaf = stem if ext.lower() in NOTE_EXTENSIONS else segments[-1]
            qualified = "/".join(segments[:-1] + [leaf]).lower()
            if any(path == qualified or path.endswith("/" + qualified) for path in stripped):
                continue
            named = by_name.get(leaf.lower(), [])
            if not named:
                continue  # no note has the name: a link to no note, reported by its own check
            if len(named) > 1:
                found.append((source, f"links to [[{target}]], but no note is at that path and {len(named)} notes have that name", target, None))
                continue
            folders = named[0].split("/")[:-1][-(len(segments) - 1):]
            new = "/".join(folders + [segments[-1]])
            found.append((source, f"links to [[{target}]], but no note is at that path; the note of that name is {named[0]}", target, new))
    return found
