"""The notes a lookup tool may see and how a tool names one (docs/decisions/040): always the persona's own scope,
read from the mtime-cached snapshot the search reads, so a name outside the scope or one that is not a note finds
nothing and cannot be told apart from a note that does not exist."""

from typing import Any

from sympose import vault_paths
from sympose.vault_snapshot import get_vault_snapshot


def in_scope(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Every note in the persona's scope; none when it has no vault."""
    scope = vault_paths.resolve_sandbox(profile)
    return get_vault_snapshot(*scope) if scope is not None else []


def title(note: dict[str, Any]) -> str:
    meta = note.get("meta") or {}
    return str(meta.get("title") or meta.get("name") or note["file_name"][:-3])


def find(profile: dict[str, Any], path: str) -> dict[str, Any] | None:
    """The note in the persona's scope that `path` names: its path relative to the vault (with or without
    `.md`, in any case), else its title or file name when only one note has it."""
    notes = in_scope(profile)
    wanted = path.strip().strip("/").lower()
    bare = wanted[:-3] if wanted.endswith(".md") else wanted
    for note in notes:
        rel = note["rel_path"].lower()
        if rel == wanted or rel[:-3] == bare:
            return note
    named = [
        note for note in notes
        if bare in {
            note["file_name"][:-3].lower(),
            str((note.get("meta") or {}).get("title") or (note.get("meta") or {}).get("name") or "").lower(),
        }
    ]
    return named[0] if len(named) == 1 else None
