"""The cloud-sharing route handlers (docs/decisions/044, 031): what the persona's model may receive from
the user's vault, read and changed through the one `cloud_share` list the terminal's `/share` uses, so the
two channels cannot disagree. Whether a model is a cloud one is the engine's own rule, not a copy of it."""

from typing import Any

from fastapi import HTTPException

from sympose.engine import model as model_mod, sharing
from sympose.server_handlers import require_profile
from sympose.server_models import SharingChange


def _state(persona: str | None) -> dict[str, Any]:
    model = model_mod.resolve_model(require_profile(persona).get("model"))
    approved = sharing.approved()
    return {
        "model": model,
        "cloud": not sharing.is_local(model),
        "categories": [
            {"name": name, "description": sharing.DESCRIPTIONS[name], "shared": name in approved}
            for name in sharing.CATEGORIES
        ],
    }


def get_sharing(persona: str | None) -> dict[str, Any]:
    return _state(persona)


def put_sharing(category: str, persona: str | None, body: SharingChange) -> dict[str, Any]:
    if category not in sharing.CATEGORIES:
        raise HTTPException(status_code=404, detail=f"There is no category called {category}.")
    if not sharing.set_approved(category, body.shared):
        raise HTTPException(status_code=500, detail="Couldn't save your cloud-sharing choice. Check that settings.json can be written to.")
    return _state(persona)
