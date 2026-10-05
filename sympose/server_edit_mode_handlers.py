"""The edit-mode routes' handlers (docs/decisions/072): which mode counts for a persona and where it comes from, the
note to show for the more autonomous modes (about the model she uses, so the screen holds no figures of its own), and
saving her own choice into her untracked local file (`persona_model`), the file her model pick lives in too."""

from typing import Any

from fastapi import HTTPException

from sympose import persona_model, profile as profile_mod
from sympose.engine import edit_mode, model as model_mod
from sympose.server_handlers import require_profile
from sympose.server_models import EditModeChoice


def _state(persona: str) -> dict[str, Any]:
    profile = require_profile(persona)
    model = model_mod.resolve_model(profile.get("model") or None)
    return {
        "mode": edit_mode.for_persona(profile),
        "source": "persona" if edit_mode.valid(profile.get("edit_mode")) else "global",
        "modes": [{"id": m, "summary": edit_mode.SUMMARIES[m]} for m in edit_mode.MODES],
        "notes": {m: edit_mode.note(m, model) for m in (edit_mode.ACCEPT, edit_mode.AUTO)},
        "model": model,
    }


def get_edit_mode(persona: str) -> dict[str, Any]:
    return _state(persona)


def put_edit_mode(persona: str, body: EditModeChoice) -> dict[str, Any]:
    profile = require_profile(persona)
    if body.mode is not None and edit_mode.valid(body.mode) is None:
        raise HTTPException(status_code=422, detail=f"{body.mode} is not one of the modes: {', '.join(edit_mode.MODES)}.")
    if not persona_model.set_edit_mode(profile["handle"], body.mode):
        raise HTTPException(status_code=500, detail=f"Couldn't save the edit mode for {profile['handle']}.")
    return _state(persona)


_NO_FOLLOWER = (
    "No persona follows this setting right now: each has a mode of her own, chosen on the Persona page. "
    "It applies to a persona that has none."
)


def get_global_edit_mode() -> dict[str, Any]:
    """The global mode and who it reaches: the personas with no mode of their own, each with the model she uses, and the
    note for `accept` and `auto` listing one line per follower (the global setting has no one model to quote)."""
    following = [
        {"handle": p["handle"], "name": p["name"], "model": model_mod.resolve_model(p.get("model") or None)}
        for p in profile_mod.list_profiles()
        if not edit_mode.valid(p.get("edit_mode"))
    ]
    notes = {
        m: "\n".join(f"{f['name']} ({f['model']}): {edit_mode.note(m, f['model'])}" for f in following) or _NO_FOLLOWER
        for m in (edit_mode.ACCEPT, edit_mode.AUTO)
    }
    return {"mode": edit_mode.mode(), "following": following, "notes": notes}
