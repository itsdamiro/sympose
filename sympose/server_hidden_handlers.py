"""Route handler logic for what the user has hidden from view (docs/decisions/037): read the list,
hide a path, unhide one, and the switch that shows folder definition notes. Every call answers with
the whole state, so the web app never has to guess what changed."""

from typing import Any

from fastapi import HTTPException

from sympose import vault_hidden, vault_paths
from sympose.server_models import DefinitionsSwitch, HiddenPath


def _state() -> dict[str, Any]:
    return {"hidden": vault_hidden.hidden_paths(), "showDefinitionNotes": vault_hidden.definitions_shown()}


def _vault() -> str:
    vault = vault_paths.get_master_vault()
    if not vault:
        raise HTTPException(status_code=409, detail="No vault is configured.")
    return vault


def _path(raw: str) -> str:
    path = vault_hidden.normalize(raw)
    if path is None:
        raise HTTPException(status_code=400, detail=f"`{raw}` is not a vault-relative path.")
    return path


def _saved(ok: bool) -> dict[str, Any]:
    if not ok:
        raise HTTPException(status_code=500, detail="Could not save: the settings file could not be written, or `hidden_paths` in it is not one Sympose wrote.")
    return _state()


def get_hidden() -> dict[str, Any]:
    return _state()


def hide(body: HiddenPath) -> dict[str, Any]:
    return _saved(vault_hidden.hide(_vault(), _path(body.path)))


def unhide(path: str) -> dict[str, Any]:
    return _saved(vault_hidden.unhide(_vault(), _path(path)))


def set_definitions(body: DefinitionsSwitch) -> dict[str, Any]:
    return _saved(vault_hidden.set_definitions_shown(body.show))
