"""What the CLI offers to choose from: the personas (a real read through
`sympose/profile.py` and `profiles/*.yaml`, the one roster the web app's persona
picker also builds on) and the models (the list itself is the engine's, `engine/model_options.py`, shared with
the web chat, docs/decisions/044). `active_model` says which one actually runs."""

__all__ = ["MODEL_OPTIONS", "ModelOption", "PersonaOption", "active_model", "list_personas", "model_option_for"]

from dataclasses import dataclass

from sympose.engine.model import resolve_model
from sympose.engine.model_options import MODEL_OPTIONS, ModelOption, model_option_for
from sympose.profile import list_profiles


@dataclass(frozen=True)
class PersonaOption:
    handle: str
    name: str
    title: str
    # The persona's own `model` from its profile, or `None` (docs/decisions/010).
    model: str | None = None


def list_personas() -> list[PersonaOption]:
    """The CLI's narrower projection of `profile.list_profiles()` — the
    one canonical roster the web app's `GET /api/personas` also builds
    on (docs/decisions/009), so a malformed/unsafe profile file is
    already handled and handles are already lowercased/deduped there."""
    return [
        PersonaOption(
            handle=p["handle"], name=p["name"], title=p["title"], model=p["model"]
        )
        for p in list_profiles()
    ]


def active_model(persona: PersonaOption, override: ModelOption | None) -> ModelOption:
    """What actually runs for `persona`: the user's explicit `/model` pick if
    there is one, else the persona's model / setting / default, in the
    engine's own order (`resolve_model`, docs/decisions/010) — the same
    function `run_turn` uses, so the header can't show something else."""
    return override or model_option_for(resolve_model(persona.model))
