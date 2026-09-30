"""The model routes' handlers (docs/decisions/044): the one list of models both channels offer, and saving
a persona's own model into its `persona.yaml` (`persona_model`), the file the terminal's `/model` writes
too. Whether a model is cloud is the engine's own rule, and only a listed id is accepted, so the browser
cannot make the server call a model the product does not offer."""

from typing import Any

from fastapi import HTTPException

from sympose import persona_model
from sympose.engine import model as model_mod, sharing
from sympose.engine.model_options import MODEL_OPTIONS
from sympose.server_handlers import require_profile
from sympose.server_models import ModelChoice


def _state(persona: str | None) -> dict[str, Any]:
    own = require_profile(persona).get("model") or None
    current = model_mod.resolve_model(own)
    fallback = model_mod.resolve_model(None)
    return {
        "models": [{"id": m.id, "label": m.label, "short": m.short, "cloud": not sharing.is_local(m.id)} for m in MODEL_OPTIONS],
        "current": current,
        "current_cloud": not sharing.is_local(current),  # the model may be one the list does not hold
        "own": own,
        "fallback": fallback,
        "fallback_cloud": not sharing.is_local(fallback),
    }


def get_models(persona: str | None) -> dict[str, Any]:
    return _state(persona)


def put_persona_model(handle: str, body: ModelChoice) -> dict[str, Any]:
    profile = require_profile(handle)
    if body.model is not None and body.model not in {m.id for m in MODEL_OPTIONS}:
        raise HTTPException(status_code=422, detail=f"{body.model} is not one of the models offered.")
    if not persona_model.set_model(profile["handle"], body.model):
        raise HTTPException(status_code=500, detail=f"Couldn't save the model into {profile['handle']}'s persona.yaml.")
    return _state(handle)
