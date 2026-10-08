"""Route handlers for a persona's requests for the user's yes (docs/decisions/078): list the ones of a conversation, and
answer one. Accepting runs the check again in the engine (`confirmations.resolve`); nothing here makes a persona."""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from sympose import persona_create
from sympose.engine import confirmations, edit_mode, persona_proposal, setting_targets
from sympose.server_handlers import require_profile


class ConfirmationAnswer(BaseModel):
    """Body of `POST /api/chat/confirmations/{id}`: whose request it is, the decision, and the folders as the user's pills
    were left (`null` keeps the persona's own proposal)."""

    persona: str | None = None
    accept: bool
    folders: list[str] | None = None
    edit_mode: str | None = None


def _setting_view(profile: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """A request to change a setting as its card needs it (docs/decisions/080): what it is, from and to in words, and the
    extra line where the consequence is not in the change itself. A decided request keeps the value it replaced."""
    draft = request["draft"]
    target = setting_targets.find(draft["setting"])
    base = {"id": request["id"], "kind": request["kind"], "state": request["state"], "reason": request.get("reason"), "created_at": request["created_at"]}
    if target is None:
        return {**base, "setting": {"name": draft["setting"], "label": draft["setting"], "summary": "", "from": "", "to": "", "note": None}}
    return {**base, "setting": {
        "name": target.name, "label": target.label, "summary": target.summary,
        "from": draft.get("was") or setting_targets.current_text(target, profile), "to": setting_targets.value_text(target, draft["value"]),
        "note": setting_targets.consequence(target, draft["value"]),
    }}


def _view(profile: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """A request as the card needs it: the proposal, its state, and the folders the pills offer (those the proposer reads)."""
    if request["kind"] == confirmations.SETTING:
        return _setting_view(profile, request)
    return {
        "id": request["id"], "kind": request["kind"], "state": request["state"], "handle": request["handle"],
        "draft": request["draft"], "reason": request.get("reason"), "created_at": request["created_at"],
        "folder_choices": persona_create.readable_folders(profile),
        "edit_modes": [{"id": m, "summary": edit_mode.SUMMARIES[m]} for m in edit_mode.MODES],
    }


def list_requests(persona: str | None, session: str) -> dict[str, Any]:
    profile = require_profile(persona)
    return {"requests": [_view(profile, r) for r in confirmations.for_session(profile["handle"], session)]}


def answer(request_id: str, body: ConfirmationAnswer) -> dict[str, Any]:
    profile = require_profile(body.persona)
    try:
        done = confirmations.resolve(
            profile["handle"], request_id, body.accept, body.folders, persona_proposal.tool_names(), body.edit_mode,
        )
    except confirmations.Refused as error:
        current = confirmations.read(profile["handle"], request_id)
        if current is None:
            raise HTTPException(status_code=404, detail=str(error))
        # Already answered is a conflict; a proposal that fails a check (no folder on, say) can be put right and sent again.
        raise HTTPException(status_code=409 if current["state"] != confirmations.WAITING else 422, detail=str(error))
    return _view(profile, done)
