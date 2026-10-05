"""The folder rename route's handler (docs/decisions/073): the vault write itself is `vault_write_rename_folder`; what
follows it outside the vault's files (the personas' own scopes, the hidden list, every persona's pending changes) is done
here, after the directory has moved, best effort and reported."""

from typing import Any

from fastapi import HTTPException

from sympose import note_changes, persona_scope, vault_hidden, vault_paths
from sympose.server_handlers import require_profile, sandbox_denied, translate_vault_result
from sympose.server_models import FolderMovePlan, FolderRename
from sympose.vault_move_folder_plan import plan_move
from sympose.vault_write_rename_folder import OK, rename_folder_to_path


def rename_folder(body: FolderRename) -> dict[str, Any]:
    profile = require_profile(body.persona)
    status, got = rename_folder_to_path(profile, body.path, body.new_name)
    if status != OK:
        translate_vault_result(
            status,
            not_found=f"No folder `{body.path}` in the vault.",
            exists=f"`{body.new_name.strip()}` is already taken in that folder.",
            denied=sandbox_denied(body.path),
            invalid_name="A folder name is one plain name: no `/` or `\\`, not starting with a dot, and none of `[`, `]`, `|` or `#`, which break the links that name it.",
        )
        raise HTTPException(status_code=500, detail=status)
    old = body.path.strip().strip("\"'").strip("/\\")
    changed, unchanged = persona_scope.rename_folder(old, got.path)
    vault = vault_paths.get_master_vault()
    if vault:
        vault_hidden.rename_folder(vault, old, got.path)
    note_changes.rename_folder_everywhere(old, got.path)  # a persona's pending changes follow the notes (docs/decisions/070)
    bits = []
    if got.relinked:
        bits.append(f"{got.relinked} note{'s' if got.relinked != 1 else ''} relinked")
    if got.failed:
        bits.append(f"{got.failed} relink{'s' if got.failed != 1 else ''} failed, see the server log")
    if changed:
        bits.append("folder scope updated for " + ", ".join(changed))
    if unchanged:
        bits.append("edit the folder scope by hand for " + ", ".join(unchanged))
    detail = f"Renamed to `{got.path}`" + (f" ({'; '.join(bits)})" if bits else "")
    return {
        "path": got.path, "detail": detail, "relinked": got.relinked, "failed": got.failed,
        "definition": got.definition, "personas": changed, "personas_unchanged": unchanged,
    }


def move_plan(body: FolderMovePlan) -> dict[str, Any]:
    """What the move would do and what needs the user's word first: a folder of that name already there (rename or merge),
    the files in both, the personas whose reach would change, a definition note that stops or starts applying. Moves nothing."""
    profile = require_profile(body.persona)
    status, got = plan_move(profile, body.path, body.destination)
    if got is None:
        translate_vault_result(
            status,
            not_found=f"No folder `{body.path}` or no folder `{body.destination}` in the vault.",
            exists="Something that is not a folder already has that name there.",
            denied=sandbox_denied(body.path),
            invalid_name="A folder cannot go into itself, into one of its own folders, or into the folder it is already in.",
        )
        raise HTTPException(status_code=500, detail=status)
    return {
        "path": got.path, "destination": got.destination, "new_path": got.new_path, "clash": got.clash,
        "note_clashes": list(got.note_clashes), "definition": got.definition,
        "reach": [{"handle": r.handle, "name": r.name, "gains": r.gains, "loses": r.loses} for r in got.reach],
    }
