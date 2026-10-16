"""Links whose folder no longer matches (docs/decisions/084): a `[[Folder/Note]]` that names no note's path but whose
name one note has, which is what a move leaves behind (#101). The graph resolves a link by its last segment, so the
"Links to no note" check never sees these; Obsidian reads the qualifier as a path and does not find the note.
A link shown as code is a sample and is not read. Returns `(note path, message, old target, new target or None)`;
`vault_health` turns them into findings."""

import os
import re
from typing import Any

from sympose import markdown_code
from sympose.vault_defaults import ATTACHMENT_EXTENSIONS, NOTE_EXTENSIONS
from sympose.wikilinks import WIKILINK_RE


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
        text = note.get("full_content") or ""
        source, seen, in_code = note["rel_path"].replace("\\", "/"), set(), markdown_code.in_code(text)
        for match in WIKILINK_RE.finditer(text):
            target = _target(match.group(2))
            segments = target.replace("\\", "/").lstrip("/").split("/")
            stem, ext = os.path.splitext(segments[-1])
            if len(segments) < 2 or target in seen or ext.lower() in ATTACHMENT_EXTENSIONS:
                continue
            if in_code(match.start()):
                continue  # a link shown as code is a sample, not a link
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
