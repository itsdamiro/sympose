"""A persona's request for the user's yes (docs/decisions/078): stored, shown as a card in the chat, resolved by the
user. One JSON file per request in the persona's own folder (`profiles/<handle>/confirmations/<id>.json`), so a reload
shows it still waiting and a second answer is refused. Nothing a request names has happened until it is accepted, and
accepting checks the whole proposal again: the card is a view, never the authority.

A request for a new persona is the only kind so far; the file's `kind` says what accepting does."""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sympose import persona_create, profile
from sympose.atomic_write import write_atomic_text
from sympose.persona_files import persona_dir

PERSONA = "persona"
WAITING, ACCEPTED, DECLINED, REPLACED, OUTDATED = "waiting", "accepted", "declined", "replaced", "outdated"
_DECIDED = (ACCEPTED, DECLINED, OUTDATED)  # what she is told about (a replaced card is her own doing)
_FIELDS = ("name", "title", "soul", "icon", "accent", "accent_dark", "edit_mode")


class Refused(ValueError):
    """The answer cannot be taken; the text says why, for the user."""


def _folder(handle: str) -> str:
    return os.path.join(persona_dir(handle), "confirmations")


def _file(handle: str, request_id: str) -> str | None:
    return os.path.join(_folder(handle), f"{request_id}.json") if request_id.isalnum() else None


def _save(handle: str, request: dict[str, Any]) -> None:
    os.makedirs(_folder(handle), exist_ok=True)
    write_atomic_text(_file(handle, request["id"]) or "", json.dumps(request, ensure_ascii=False, indent=1))


def read(handle: str, request_id: str) -> dict[str, Any] | None:
    path = _file(handle, request_id)
    try:
        with open(path or "", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("id") == request_id else None


def for_session(handle: str, session_id: str) -> list[dict[str, Any]]:
    """The requests of one conversation, oldest first."""
    try:
        names = os.listdir(_folder(handle))
    except OSError:
        return []
    found = [r for n in names if n.endswith(".json") and (r := read(handle, n[:-5])) and r.get("session_id") == session_id]
    return sorted(found, key=lambda r: (r.get("created_at", ""), r["id"]))


def propose_persona(handle: str, session_id: str, draft: persona_create.Draft) -> dict[str, Any]:
    """File a request for a new persona from `handle`; any request of hers still waiting in this conversation is
    `replaced` by it, so there is one waiting card at a time."""
    for old in for_session(handle, session_id):
        if old["kind"] == PERSONA and old["state"] == WAITING:
            _save(handle, {**old, "state": REPLACED})
    request = {
        "id": uuid.uuid4().hex[:12], "kind": PERSONA, "session_id": session_id, "state": WAITING,
        "created_at": datetime.now(timezone.utc).isoformat(), "told": False,
        "draft": {**{k: getattr(draft, k) for k in _FIELDS}, "folders": list(draft.folders)},
        "handle": persona_create.handle_for(draft.name),
    }
    _save(handle, request)
    return request


def _draft(request: dict[str, Any], folders: list[str] | None, mode: str | None) -> persona_create.Draft:
    data = request["draft"]
    return persona_create.Draft(
        **{k: data[k] if k != "edit_mode" or mode is None else mode for k in _FIELDS},
        folders=tuple(data["folders"] if folders is None else folders),
    )


def resolve(
    handle: str, request_id: str, accept: bool, folders: list[str] | None, tool_names: tuple[str, ...], edit_mode: str | None = None,
) -> dict[str, Any]:
    """Decline or accept a waiting request. Accepting uses `folders` and `edit_mode` as the user left them on the card (`None`
    keeps the proposal's), checks the proposal again as if it had just been made, and creates the persona. A proposal that fails
    the check for the folders alone is refused and stays waiting; one that cannot be made any more (the handle is now
    taken) becomes `outdated`. Raises `Refused` for an unknown or already answered request."""
    request = read(handle, request_id)
    if request is None:
        raise Refused("That request is not there any more.")
    if request["state"] != WAITING:
        raise Refused("That request has already been answered.")
    if not accept:
        result = {**request, "state": DECLINED}
        _save(handle, result)
        return result
    draft = _draft(request, folders, edit_mode)
    if os.path.exists(persona_dir(persona_create.handle_for(draft.name))):
        result = {**request, "state": OUTDATED, "reason": f"A persona called {request['handle']} already exists."}
        _save(handle, result)
        return result
    if not draft.folders:
        raise Refused("Choose at least one folder the new persona may read.")
    problem = persona_create.problem(draft, profile.get_profile(handle) or {"handle": handle}, tool_names)
    if problem is not None:
        raise Refused(problem)
    try:
        persona_create.create(draft)
    except FileExistsError:
        result = {**request, "state": OUTDATED, "reason": f"A persona called {request['handle']} already exists."}
    else:
        result = {**request, "state": ACCEPTED, "draft": {**request["draft"], "folders": list(draft.folders), "edit_mode": draft.edit_mode}}
    _save(handle, result)
    return result


def outcomes(handle: str, session_id: str) -> list[dict[str, Any]]:
    """The requests of this conversation the user has decided and she has not yet been told about."""
    return [r for r in for_session(handle, session_id) if r["state"] in _DECIDED and not r.get("told")]


def lines(requests: list[dict[str, Any]]) -> list[str]:
    """One line each, for her next turn."""
    said = {
        ACCEPTED: "the user accepted it and the persona now exists",
        DECLINED: "the user declined it, so nothing was made",
        OUTDATED: "it could not be made any more",
    }
    return [f"You proposed a persona called {r['draft']['name']}: {said[r['state']]}." for r in requests]


def mark_told(handle: str, requests: list[dict[str, Any]]) -> None:
    for request in requests:
        current = read(handle, request["id"])
        if current is not None and not current.get("told"):
            _save(handle, {**current, "told": True})
