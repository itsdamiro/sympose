"""Moving a vault folder into another folder or the vault root (docs/decisions/074): the directory, and the wikilinks that
name it, rewritten to its full new path; when a folder of that name is already there, the user's choice of renaming the
moved folder or merging it into the one there. What lives outside the vault's files (the personas' scopes, the hidden
list, the pending changes) follows in the route, as for a rename."""

import os
import posixpath
from dataclasses import dataclass
from typing import Any, Callable

from sympose.vault_folder_paths import OK, resolve_folder
from sympose.vault_move_folder_plan import clashes
from sympose.vault_write import get_file_locks
from sympose.vault_write_relink_folder import relink_folder
from sympose.vault_write_rename import _dst_already_taken
from sympose.vault_write_merge_folder import merge_files, rename_clashes
from sympose.vault_write_rename_folder import _files_inside, _new_name_error
from sympose.vault_write_status import NOTE_EXISTS, NOTE_INVALID_NAME


@dataclass(frozen=True)
class FolderMoved:
    path: str  # the folder's new vault-relative path
    relinked: int  # notes whose links to the folder were rewritten
    failed: int  # notes whose links could not be rewritten
    merged: bool = False  # the folder went into one that was there
    renamed_notes: tuple[tuple[str, str], ...] = ()  # notes renamed to avoid a clash, as `(old, new)` vault paths, before the move
    renamed_others: int = 0  # other files or folders renamed the same way
    left_behind: int = 0  # files a merge left where they were (hidden, or taken meanwhile), keeping the folder


def move_folder_to_path(
    profile: dict[str, Any], path: str, destination: str, *, if_exists: str | None = None, new_name: str = "",
    rename_clashing_notes: bool = False, on_note_renamed: Callable[[str, str], None] | None = None,
) -> tuple[str, FolderMoved | None]:
    """Move the folder `path` into `destination` (a folder, or `""` for the vault root) and rewrite the links that name
    it. When a folder of that name is there, `if_exists` says `"merge"` (its contents go into it; what is in both is
    renamed first when `rename_clashing_notes`, else nothing is done) or `"rename"` (it goes in as `new_name`).
    `(OK, details)` or `(error, None)`, the error being `NOTE_NOT_FOUND` / `NOTE_DENIED` / `NOTE_INVALID_NAME` (into
    itself, into one of its own folders, where it already is, or a bad new name) / `NOTE_EXISTS` (something already has
    that name there, and the user has not said what to do) or an `Error: ...` message. `on_note_renamed(old, new)` hears
    of each note a merge renamed to avoid a clash, as it happens."""
    status, source = resolve_folder(profile, path)
    if source is None:
        return status, None
    status, dest = resolve_folder(profile, destination, root=True)
    if dest is None:
        return status, None
    mv, allowed_dirs, src, old_rel = source  # the destination is in the persona's scope, so what goes into it is too
    _, _, dst_dir, into = dest
    if into == old_rel or into.startswith(old_rel + "/") or into == posixpath.dirname(old_rel):
        return NOTE_INVALID_NAME, None
    name = posixpath.basename(old_rel)
    if if_exists == "rename":
        name = new_name.strip().strip("\"'")
        if _new_name_error(name) is not None:
            return NOTE_INVALID_NAME, None
    dst = os.path.join(dst_dir, name)
    new_rel = posixpath.join(into, name)
    merging = if_exists == "merge" and os.path.isdir(dst)
    if not merging and _dst_already_taken(dst, src):
        return NOTE_EXISTS, None
    clashing = clashes(src, dst) if merging else ()
    if clashing and not rename_clashing_notes:
        return NOTE_EXISTS, None

    renamed: list[tuple[str, str]] = []
    others = left = 0
    if merging:
        renamed, error = rename_clashes(profile, mv, src, dst, clashing, on_note_renamed)
        if error:
            return error, None
        others = len(clashing) - len(renamed)
        inside = _files_inside(mv, src)  # after the renames: a link to a note now numbered follows it, not the one there
        left = merge_files(src, dst)
    else:
        inside = _files_inside(mv, src)
        with get_file_locks(src, dst):
            if _dst_already_taken(dst, src):  # re-checked under the lock: something may have landed there meanwhile
                return NOTE_EXISTS, None
            try:
                os.rename(src, dst)
            except OSError as error:
                return f"Error: Failed to move folder: {error}", None

    relinked, failed = relink_folder(mv, allowed_dirs, old_rel, posixpath.basename(old_rel), inside, new_rel)
    return OK, FolderMoved(new_rel, relinked, failed, merging, tuple(renamed), others, left)
