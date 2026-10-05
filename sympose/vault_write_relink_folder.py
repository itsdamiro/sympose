"""
Rewriting the `[[wikilinks]]` that name a renamed folder (docs/decisions/073) -- the folder's counterpart of
`vault_write_relink.py`, which retargets the links to one renamed note. A link by name alone (`[[Anna]]`) does not care
where its note lives and is never touched; a link whose path qualifier names the folder (`[[People/Anna]]`,
`![[People/Photos/anna.png]]`) breaks when the folder is renamed, so its folder segment is rewritten.
"""

import logging
import os
import re

from sympose.security import is_safe_path
from sympose.vault_write import get_file_lock, write_atomic_text
from sympose.vault_write_relink import _WIKILINK_RE

log = logging.getLogger(__name__)


def _segments(path: str) -> list[str]:
    return [s.strip().lower() for s in path.replace("\\", "/").split("/") if s.strip()]


def rewrite_folder_links(text: str, old_folder: str, new_name: str, inside: set[str]) -> tuple[str, int]:
    """Retarget every wikilink or embed whose qualifier names `old_folder` (the vault-relative path it had) and that,
    read against `inside` (the lower-cased paths of the files that were in it, a note both with and without `.md`), resolves to
    one of them: the qualifier before the folder's name must be a tail of the folder's parent path, and what follows it
    must be a path inside the folder. `#heading` and `|alias` stay. Returns the new text and the hit count."""
    old = _segments(old_folder)
    name_l, parent = old[-1], old[:-1]
    rewritten = 0

    def repl(m: "re.Match[str]") -> str:
        nonlocal rewritten
        bang, inner = m.group(1), m.group(2)
        head = re.match(r"^([^#|]*)(.*)$", inner)
        target, tail = head.group(1), head.group(2)
        segs = target.split("/")
        qualifier, leaf = segs[:-1], segs[-1]
        for i, segment in enumerate(qualifier):
            if segment.strip().lower() != name_l:
                continue
            before = [s.strip().lower() for s in qualifier[:i]]
            if before != parent[len(parent) - len(before):] or len(before) > len(parent):
                continue
            inner_path = "/".join([*old, *[s.strip().lower() for s in qualifier[i + 1 :]], leaf.strip().lower()])
            if inner_path in inside:
                segs[i] = new_name
                rewritten += 1
                return f"{bang}[[{'/'.join(segs)}{tail}]]"
        return m.group(0)

    return _WIKILINK_RE.sub(repl, text), rewritten


def _notes(root: str):
    """Every `.md` file under `root`, leaving out the dot folders (`.obsidian`, `.git`, `.trash`) that are not notes."""
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.endswith(".md"):
                yield os.path.join(folder, name)


def relink_folder(mv: str, allowed_dirs: list[str], old_folder: str, new_name: str, inside: set[str]) -> tuple[int, int]:
    """Rewrite the folder links in every note of the vault inside the sandbox (those now in the renamed folder
    included). Returns `(updated, failed)`: `failed` counts a note whose rewrite was lost to an `OSError`, so a caller
    can tell "nothing needed relinking" from "some relinks silently did not happen"."""
    needle = old_folder.replace("\\", "/").rstrip("/").split("/")[-1].lower()
    updated = failed = 0
    for fp in _notes(mv):
        if not any(is_safe_path(fp, allowed) for allowed in allowed_dirs):
            continue
        try:
            with get_file_lock(fp):
                # Exactly as it is on disk: line endings kept and bytes that are not valid UTF-8 carried through.
                with open(fp, "r", encoding="utf-8", errors="surrogateescape", newline="") as f:
                    content = f.read()
                if needle not in content.lower():
                    continue
                rewritten, hits = rewrite_folder_links(content, old_folder, new_name, inside)
                if not hits:
                    continue
                write_atomic_text(fp, rewritten, newline="", errors="surrogateescape")
            updated += 1
        except OSError as error:
            log.warning("[vault] relink failed for %s after renaming folder %s: %s", fp, old_folder, error)
            failed += 1
    return updated, failed
