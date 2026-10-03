"""The routes that serve a persona's own files to the web editor (docs/decisions/061): `soul.md`, `profile.md`,
`context.md` and `decisions.md`, by an allow-list of names (`persona_editable`), a save that presents the mtime the
editor opened the file at, the soul's reset to the shipped file, and the review of a rewrite the engine staged."""

from typing import Any

from fastapi import HTTPException

from sympose import persona_editable as pe
from sympose.server_handlers import require_profile
from sympose.server_models import PersonaFileWrite


def _handle(handle: str) -> str:
    return require_profile(handle)["handle"]


def _known(name: str) -> str:
    if name not in pe.FILES:
        raise HTTPException(status_code=404, detail=f"`{name}` is not one of a persona's files.")
    return name


def list_files(handle: str) -> dict[str, Any]:
    return {"files": pe.list_files(_handle(handle))}


def get_file(handle: str, name: str) -> dict[str, Any]:
    try:
        found = pe.read(_handle(handle), _known(name))
    except (OSError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Couldn't read `{name}` as text: {e}")
    if found is None:
        raise HTTPException(status_code=404, detail=f"`{name}` is not one of a persona's files.")
    return found


def put_file(handle: str, name: str, body: PersonaFileWrite) -> dict[str, Any]:
    handle = _handle(handle)
    result = pe.write(handle, _known(name), body.content, body.expected_mtime)
    if result == pe.CONFLICT:
        raise HTTPException(status_code=409, detail=f"`{name}` changed on disk since it was opened — reload before saving.")
    if result != pe.OK:
        raise HTTPException(status_code=500, detail=f"Couldn't save `{name}`.")
    saved = pe.read(handle, name) or {}
    return {"name": name, "mtime": saved.get("mtime"), "local": saved.get("local", False)}


def reset_soul(handle: str) -> dict[str, Any]:
    return {"removed": pe.reset_soul(_handle(handle))}


def get_pending(handle: str, name: str) -> dict[str, str]:
    waiting = pe.pending(_handle(handle), _known(name))
    if waiting is None:
        raise HTTPException(status_code=404, detail=f"No rewrite of `{name}` is waiting.")
    return waiting


def accept_pending(handle: str, name: str) -> dict[str, Any]:
    handle, name = _handle(handle), _known(name)
    if pe.pending(handle, name) is None:
        raise HTTPException(status_code=404, detail=f"No rewrite of `{name}` is waiting.")
    if not pe.accept_pending(handle, name):
        raise HTTPException(status_code=500, detail=f"Couldn't apply the rewrite of `{name}`.")
    return {"ok": True}


def discard_pending(handle: str, name: str) -> dict[str, Any]:
    handle, name = _handle(handle), _known(name)
    if not pe.discard_pending(handle, name):
        raise HTTPException(status_code=404, detail=f"No rewrite of `{name}` is waiting.")
    return {"ok": True}
