"""
Resolving an *existing* note to its absolute path. A name is always a path from
the vault's root, resolved only as that path and never by searching for a note
of the same name elsewhere (docs/decisions/047).
"""

import os
from typing import Any

from sympose import vault_paths
from sympose.security import is_safe_path


def _resolve_note_direct(mv: str, allowed_dirs: list[str], clean: str) -> str | None:
    """An exact path under the master vault."""
    direct = os.path.join(mv, clean)
    for allowed in allowed_dirs:
        if is_safe_path(direct, allowed) and os.path.isfile(direct):
            return direct
    return None


def resolve_existing_note(profile: dict[str, Any], note_name: str) -> str | None:
    """Absolute path of the file for `note_name`, a path from the vault's root (`A/Note`, or `Note` for the top
    of the vault, `.md` optional), or `None`. It resolves only to that file, never to a same-named note
    elsewhere: a request from a stale tree or a double click must not act on a different note."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return None
    mv, allowed_dirs = scope
    clean = note_name.strip().strip("\"'")
    if not clean.endswith(".md"):
        clean += ".md"
    return _resolve_note_direct(mv, allowed_dirs, clean)
