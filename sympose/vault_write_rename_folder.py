"""
Renaming a vault folder (docs/decisions/073): the directory, the wikilinks that name it, and its definition note.
What lives outside the vault's files (the personas' scopes, the hidden list, the persona's pending changes) follows in
the route, which knows about them; this module is the part that reads and writes the vault.
"""

import os
from dataclasses import dataclass
from typing import Any

from sympose import folder_definitions, vault_paths
from sympose.security import is_safe_path
from sympose.vault_write import get_file_locks
from sympose.vault_write_rename import _dst_already_taken, rename_note_to_path
from sympose.vault_write_relink import WIKILINK_UNSAFE_CHARS
from sympose.vault_write_relink_folder import relink_folder
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_INVALID_NAME, NOTE_NOT_FOUND

OK = "ok"


@dataclass(frozen=True)
class FolderRenamed:
    path: str  # the folder's new vault-relative path
    relinked: int  # notes whose links to the folder were rewritten
    failed: int  # notes whose links could not be rewritten
    definition: bool  # the folder's definition note was renamed with it


def _new_name_error(new_name: str) -> str | None:
    """A new name is one plain path segment: not empty, not `.` or `..`, no separator, not starting with a dot (that
    would hide the folder from the vault) and none of the characters that break a wikilink naming it."""
    if not new_name:
        return NOTE_DENIED
    if new_name in (".", "..") or "/" in new_name or "\\" in new_name or new_name.startswith("."):
        return NOTE_INVALID_NAME
    if WIKILINK_UNSAFE_CHARS.intersection(new_name):
        return NOTE_INVALID_NAME
    return None


def _files_inside(mv: str, src: str) -> set[str]:
    """The lower-cased vault-relative paths of every file in `src`, a note both with and without `.md`: what a link
    that names the folder can point at, read before the folder moves."""
    inside: set[str] = set()
    for folder, _dirs, files in os.walk(src):
        for name in files:
            rel = os.path.relpath(os.path.join(folder, name), mv).replace(os.sep, "/").lower()
            inside.add(rel)
            if rel.endswith(".md"):
                inside.add(rel[:-3])
    return inside


def rename_folder_to_path(profile: dict[str, Any], old_name: str, new_name: str) -> tuple[str, FolderRenamed | None]:
    """Rename a vault folder, keeping its parent, and rewrite the links that name it. `(OK, details)` or `(error, None)`,
    the error being `NOTE_NOT_FOUND` / `NOTE_EXISTS` / `NOTE_DENIED` / `NOTE_INVALID_NAME` or an `Error: ...` message."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED, None
    mv, allowed_dirs = scope
    clean = old_name.strip().strip("\"'").strip("/\\")
    new = new_name.strip().strip("\"'")
    if not clean:
        return NOTE_DENIED, None
    src = os.path.normpath(os.path.join(mv, clean))
    rel_parts = os.path.relpath(src, mv).replace(os.sep, "/").split("/")
    # Never the vault root (its relative path is `.`), the bin or another dot folder (`.obsidian`, `.git`): they are not
    # folders of notes.
    if any(part.startswith(".") for part in rel_parts) or not is_safe_path(src, mv):
        return NOTE_DENIED, None
    if not vault_paths.is_within_any(src, allowed_dirs):
        return NOTE_DENIED, None
    if not os.path.isdir(src):
        return NOTE_NOT_FOUND, None
    if (error := _new_name_error(new)) is not None:
        return error, None
    dst = os.path.join(os.path.dirname(src), new)
    if new == os.path.basename(src) or _dst_already_taken(dst, src):
        return NOTE_EXISTS, None
    if not vault_paths.is_within_any(dst, allowed_dirs):
        return NOTE_DENIED, None

    old_rel = os.path.relpath(src, mv).replace(os.sep, "/")
    new_rel = os.path.relpath(dst, mv).replace(os.sep, "/")
    inside = _files_inside(mv, src)
    with get_file_locks(src, dst):
        if _dst_already_taken(dst, src):  # re-checked under the lock: something may have landed there meanwhile
            return NOTE_EXISTS, None
        try:
            os.rename(src, dst)
        except OSError as error:
            return f"Error: Failed to rename folder: {error}", None

    relinked, failed = relink_folder(mv, allowed_dirs, old_rel, new, inside)
    renamed_definition = False
    old_stem = os.path.basename(old_rel)
    if folder_definitions.can_have_definition(old_rel):  # a top-level folder of the user's content (ADR 033)
        result, _ = rename_note_to_path(profile, f"{new_rel}/{old_stem}.md", new)  # refuses when there is none, or the name is taken
        renamed_definition = result.startswith("Renamed")
    return OK, FolderRenamed(new_rel, relinked, failed, renamed_definition)
