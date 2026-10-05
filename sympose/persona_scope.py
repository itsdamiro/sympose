"""A renamed folder in the personas' own folder scopes (docs/decisions/073). A persona can be limited to folders
(`vault_folders`, or the older `vault_folder`, in her own `persona.yaml`); rename a folder one of them names and she
would silently stop seeing it. Each such entry is rewritten in the file, only that entry: comments, quotes and layout
stay. The file is read again afterwards and, if it does not say what it should, it is put back and the persona is
reported as needing a manual edit."""

import logging
import os
import re
from typing import Any

import yaml

from sympose.atomic_write import write_atomic_text
from sympose.persona_files import PERSONA_FILENAME, profiles_dir

log = logging.getLogger(__name__)

_KEYS = ("vault_folders", "vault_folder")


def _entries(data: Any) -> list[str]:
    """The folders a persona's data limits her to, as written (a string or a list), non-strings left out."""
    found = []
    for key in _KEYS:
        value = data.get(key) if isinstance(data, dict) else None
        found.extend([value] if isinstance(value, str) else value if isinstance(value, list) else [])
    return [e for e in found if isinstance(e, str)]


def _clean(entry: str) -> str:
    return entry.strip().replace("\\", "/").strip("/")


def _follows(entry: str, old: str) -> bool:
    return _clean(entry) == old or _clean(entry).startswith(old + "/")


def _rewritten(text: str, affected: dict[str, str]) -> str:
    """`text` with each affected entry replaced inside the lines of the scope keys (the key's own line and the block
    list under it), matched whole: not inside a longer name."""
    out, inside = [], False
    for line in text.split("\n"):
        key = re.match(r"^(vault_folders|vault_folder)\s*:", line)
        if key:
            inside = True
        elif inside and line.strip() and not line.startswith((" ", "\t", "-")):
            inside = False
        if inside:
            for entry, replacement in affected.items():
                line = re.sub(rf"(?<![\w/.-]){re.escape(entry)}(?![\w/.-])", lambda _m, r=replacement: r, line)
        out.append(line)
    return "\n".join(out)


def rename_folder(old: str, new: str) -> tuple[list[str], list[str]]:
    """Follow the rename `old` -> `new` (vault-relative paths) in every persona's scope. Returns `(changed, stuck)`:
    the names of the personas whose file was rewritten, and of those that name the folder but could not be (the edit
    did not read back as expected, or the file could not be written), for the user to edit by hand."""
    old, new = _clean(old), _clean(new)
    changed, stuck = [], []
    base = profiles_dir()
    try:
        handles = sorted(h for h in os.listdir(base) if os.path.isfile(os.path.join(base, h, PERSONA_FILENAME)))
    except OSError:
        return changed, stuck
    for handle in handles:
        path = os.path.join(base, handle, PERSONA_FILENAME)
        try:
            with open(path, encoding="utf-8", newline="") as f:
                text = f.read()
            data = yaml.safe_load(text)
        except (OSError, yaml.YAMLError, UnicodeDecodeError):
            continue
        affected = {e: new + _clean(e)[len(old):] for e in _entries(data) if _follows(e, old)}
        if not affected:
            continue
        name = str(data.get("name") or handle) if isinstance(data, dict) else handle
        edited = _rewritten(text, affected)
        expected = [_clean(affected.get(e, e)) for e in _entries(data)]
        try:
            ok = edited != text and [_clean(e) for e in _entries(yaml.safe_load(edited))] == expected
        except yaml.YAMLError:
            ok = False
        if ok:
            try:
                write_atomic_text(path, edited, newline="")
            except OSError as error:
                log.warning("[vault] could not follow the rename of %s in %s: %s", old, path, error)
                ok = False
        (changed if ok else stuck).append(name)
    return changed, stuck
