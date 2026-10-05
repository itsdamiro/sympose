"""Moving a vault folder into another folder or the vault root (docs/decisions/074, slice 2: no folder of that name
there yet): the directory, and the wikilinks that name it, rewritten to its full new path. What lives outside the vault's
files (the personas' scopes, the hidden list, the pending changes) follows in the route, as for a rename."""

import os
import posixpath
from dataclasses import dataclass
from typing import Any

from sympose.vault_folder_paths import OK, resolve_folder
from sympose.vault_write import get_file_locks
from sympose.vault_write_relink_folder import relink_folder
from sympose.vault_write_rename import _dst_already_taken
from sympose.vault_write_rename_folder import _files_inside
from sympose.vault_write_status import NOTE_EXISTS, NOTE_INVALID_NAME


@dataclass(frozen=True)
class FolderMoved:
    path: str  # the folder's new vault-relative path
    relinked: int  # notes whose links to the folder were rewritten
    failed: int  # notes whose links could not be rewritten


def move_folder_to_path(profile: dict[str, Any], path: str, destination: str) -> tuple[str, FolderMoved | None]:
    """Move the folder `path` into `destination` (a folder, or `""` for the vault root), keeping its name, and rewrite
    the links that name it. `(OK, details)` or `(error, None)`, the error being `NOTE_NOT_FOUND` / `NOTE_DENIED` /
    `NOTE_INVALID_NAME` (into itself, into one of its own folders, or where it already is) / `NOTE_EXISTS` (something
    already has that name there) or an `Error: ...` message."""
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
    dst = os.path.join(dst_dir, os.path.basename(src))
    if _dst_already_taken(dst, src):
        return NOTE_EXISTS, None

    new_rel = posixpath.join(into, posixpath.basename(old_rel))
    inside = _files_inside(mv, src)
    with get_file_locks(src, dst):
        if _dst_already_taken(dst, src):  # re-checked under the lock: something may have landed there meanwhile
            return NOTE_EXISTS, None
        try:
            os.rename(src, dst)
        except OSError as error:
            return f"Error: Failed to move folder: {error}", None

    relinked, failed = relink_folder(mv, allowed_dirs, old_rel, posixpath.basename(old_rel), inside, new_rel)
    return OK, FolderMoved(new_rel, relinked, failed)
