"""Route handler logic for the Folder settings dialog (docs/decisions/087): what the dialog starts from, and saving
what the user set."""

from typing import Any

from fastapi import HTTPException

from sympose import folder_settings_write, vault_paths
from sympose.folder_looks_write import Changed, Failed, Missing, Refused
from sympose.server_handlers import require_profile
from sympose.server_models import FolderSettings


def get_folder_settings(folder: str, persona: str | None) -> dict[str, Any]:
    """The values the dialog for the top-level `folder` starts from (`folder_settings_write.read`)."""
    if not vault_paths.get_master_vault():
        raise HTTPException(status_code=409, detail="No vault is configured.")
    try:
        return folder_settings_write.read(require_profile(persona), folder)
    except Refused as reason:
        raise HTTPException(status_code=409, detail=str(reason)) from reason


def put_folder_settings(body: FolderSettings) -> dict[str, Any]:
    profile = require_profile(body.persona)
    settings = folder_settings_write.Settings(body.purpose, body.template, body.icon, body.accent, body.accent_dark)
    try:
        created = folder_settings_write.save(profile, body.path, settings)
    except Missing as reason:
        raise HTTPException(status_code=404, detail=str(reason)) from reason
    except Changed as reason:
        raise HTTPException(status_code=409, detail=str(reason)) from reason
    except Failed as reason:
        raise HTTPException(status_code=500, detail=str(reason)) from reason
    except Refused as reason:
        raise HTTPException(status_code=400, detail=str(reason)) from reason
    return {"path": body.path, "created": created}
