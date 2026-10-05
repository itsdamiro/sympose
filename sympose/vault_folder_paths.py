"""Resolving the folder a folder operation names, inside the asking persona's sandbox (docs/decisions/073, 074): the
checks a rename and a move share, so the two cannot drift apart."""

import os
from typing import Any

from sympose import vault_paths
from sympose.security import is_safe_path
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND

OK = "ok"


def resolve_folder(profile: dict[str, Any], name: str, *, root: bool = False) -> tuple[str, tuple[str, list[str], str, str] | None]:
    """`(OK, (vault, allowed_dirs, absolute path, vault-relative path))` for an existing folder the persona may touch,
    else `(NOTE_DENIED | NOTE_NOT_FOUND, None)`. Never the bin or another dot folder (`.obsidian`, `.git`): they are not
    folders of notes. With `root`, an empty name is the vault's own root (a destination), if the persona may touch it."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED, None
    mv, allowed_dirs = scope
    clean = name.strip().strip("\"'").strip("/\\")
    path = os.path.normpath(os.path.join(mv, clean))
    rel = "" if path == os.path.normpath(mv) else os.path.relpath(path, mv).replace(os.sep, "/")
    if (not rel and not root) or any(part.startswith(".") for part in rel.split("/")) or not is_safe_path(path, mv):
        return NOTE_DENIED, None
    if not vault_paths.is_within_any(path, allowed_dirs):
        return NOTE_DENIED, None
    if not os.path.isdir(path):
        return NOTE_NOT_FOUND, None
    return OK, (mv, allowed_dirs, path, rel)
