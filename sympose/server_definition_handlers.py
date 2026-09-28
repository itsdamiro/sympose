"""Route handler logic for setting up a new root folder (docs/decisions/038): the generic template's property lines
to start from, and writing the definition note the user typed."""

from typing import Any

from fastapi import HTTPException

from sympose import folder_definitions_write, generic_template, vault_paths
from sympose.server_handlers import require_profile, sandbox_denied, translate_vault_result
from sympose.server_models import FolderDefinition
from sympose.vault_write_status import NOTE_NOT_FOUND


def get_note_template(folder: str | None, persona: str | None) -> dict[str, Any]:
    """The generic template's lines and where they came from; with `folder`, also whether that folder can be given
    a definition now (`definable`), so the web app opens its setup step only when saving can work."""
    vault = vault_paths.get_master_vault()
    if not vault:
        raise HTTPException(status_code=409, detail="No vault is configured.")
    lines, source = generic_template.lines_for(vault)
    answer: dict[str, Any] = {"lines": lines, "source": source}
    if folder is not None:
        answer["definable"] = folder_definitions_write.definable(require_profile(persona), folder)
    return answer


def write_definition(body: FolderDefinition) -> dict[str, Any]:
    profile = require_profile(body.persona)
    try:
        result = folder_definitions_write.write_own(profile, body.path, body.purpose, body.template)
    except folder_definitions_write.Refused as reason:
        raise HTTPException(status_code=400, detail=str(reason)) from reason
    if result == NOTE_NOT_FOUND:
        raise HTTPException(status_code=404, detail=f"Folder `{body.path}` not found in the vault.")
    translate_vault_result(
        result,
        exists=f"`{body.path}` already has a definition.",
        denied=sandbox_denied(body.path),
    )
    return {"path": body.path, "detail": result}
