"""
Trash-recovery route handlers — split out of `server_handlers.py` (project's
200-LOC-per-file guideline).
"""

from typing import Any

from fastapi import HTTPException

from sympose import vault_paths, vault_trash, vault_trash_unit
from sympose.server_handlers import require_profile, sandbox_denied, translate_vault_result
from sympose.server_models import TrashEmpty, TrashRestore


def _not_in_bin(path: str) -> str:
    return f"`{path}` is not in the bin."


def _trash_scope(persona: str | None) -> tuple[str | None, list[str]]:
    profile = require_profile(persona)
    return vault_paths.get_master_vault(), vault_paths.get_allowed_dirs(profile)


def _require_trash_scope(persona: str | None) -> tuple[str, list[str]]:
    """Same as `_trash_scope`, but raises 403 instead of returning an
    empty/falsy scope — for the mutating routes, where "nothing configured"
    is an error, not an empty result."""
    mv, allowed_dirs = _trash_scope(persona)
    if not mv or not allowed_dirs:
        raise HTTPException(status_code=403, detail="No vault configured for this persona.")
    return mv, allowed_dirs


def list_trash(persona: str | None) -> dict[str, Any]:
    mv, allowed_dirs = _trash_scope(persona)
    if not mv or not allowed_dirs:
        return {"items": [], "folders": []}
    rows = vault_trash.list_trashed(mv, allowed_dirs)
    return {"items": rows, "folders": vault_trash_unit.summarize(mv, rows)}


def restore_trash(body: TrashRestore) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(body.persona)
    result, restored = vault_trash.restore(mv, allowed_dirs, body.path)
    translate_vault_result(
        result,
        not_found=_not_in_bin(body.path),
        exists="Something already occupies that file's original location.",
        denied=sandbox_denied(body.path),
    )
    return {"path": restored, "detail": result}


def restore_trash_folder(body: TrashRestore) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(body.persona)
    result = vault_trash_unit.restore_folder(mv, allowed_dirs, body.path)
    if isinstance(result, str):
        raise HTTPException(status_code=404, detail=f"`{body.path}` is not a deleted folder in the bin.")
    restored, skipped = result
    total = len(restored) + len(skipped)
    detail = f"Restored {len(restored)} of {total} file{'' if total == 1 else 's'}."
    if skipped:
        names = ", ".join(s["path"].rsplit("/", 1)[-1] for s in skipped[:5])
        more = f" and {len(skipped) - 5} more" if len(skipped) > 5 else ""
        detail += f" Skipped {len(skipped)}: {names}{more}."
    return {"restored": restored, "skipped": skipped, "detail": detail}


def purge_trash(path: str, persona: str | None) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(persona)
    result = vault_trash.purge(mv, allowed_dirs, path)
    translate_vault_result(
        result,
        not_found=_not_in_bin(path),
        denied=sandbox_denied(path),
    )
    return {"path": path, "detail": "Deleted permanently."}


def empty_trash(body: TrashEmpty) -> dict[str, Any]:
    mv, allowed_dirs = _require_trash_scope(body.persona)
    count = vault_trash.purge_all(mv, allowed_dirs)
    return {
        "count": count,
        "detail": f"Emptied the bin ({count} item{'' if count == 1 else 's'}).",
    }
