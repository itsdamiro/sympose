"""What a persona may ask the user to change, and how it is read, shown and applied (docs/decisions/080): the engine settings of
the registry, the model of the persona that is talking, and one `cloud_share` category at a time. Every rule about a value
stays with the module that owns the setting; this file only names the three kinds of target in one shape, so the tool, the
card and Accept agree."""

from dataclasses import dataclass
from typing import Any

from sympose import persona_model
from sympose.engine import model as model_mod, settings_apply, settings_registry as registry, sharing
from sympose.engine.model_options import offered

MODEL = "model"
SHARE = "cloud_share:"
SETTING, SHARING, PERSONA_MODEL = "setting", "sharing", "model"  # a target's `kind`


@dataclass(frozen=True)
class Target:
    name: str  # what she writes in the tool: a registry key, `model`, or `cloud_share:<category>`
    kind: str
    label: str  # what the card calls it
    summary: str  # what it does, in a line; empty for a registry setting, whose label already says it
    registry_setting: registry.Setting | None = None


def find(name: str) -> Target | None:
    if name == MODEL:
        return Target(MODEL, PERSONA_MODEL, "Model", "the model this persona answers with")
    if name.startswith(SHARE):
        category = name[len(SHARE):]
        if category in sharing.CATEGORIES:
            return Target(name, SHARING, f"Cloud models may receive: {category}", sharing.DESCRIPTIONS[category])
        return None
    setting = registry.find(name)
    return Target(name, SETTING, settings_apply.label(setting), "", setting) if setting else None


def names() -> list[str]:
    """Every name she may use, for the tool's description."""
    return [s.key for s in registry.SETTINGS] + [MODEL] + [SHARE + c for c in sharing.CATEGORIES]


def parse(target: Target, value: Any, persona: dict[str, Any]) -> tuple[Any, str | None]:
    """`(the value as it will be applied, None)`, or `(None, why not)` in words she can act on."""
    if target.kind == SHARING:
        return (value, None) if isinstance(value, bool) else (None, f"{target.name} takes true or false.")
    if target.kind == PERSONA_MODEL:
        ids = [m.id for m in offered(model_mod.resolve_model(persona.get("model") or None))]
        return (value, None) if isinstance(value, str) and value in ids else (None, "The model must be one of: " + ", ".join(ids) + ".")
    setting = target.registry_setting
    assert setting is not None
    if setting.kind == registry.TOGGLE:
        return (value, None) if isinstance(value, bool) else (None, f"{target.name} takes true or false.")
    if setting.kind == registry.CHOICE:
        return (value, None) if value in setting.choices else (None, f"{target.name} takes one of: {', '.join(setting.choices)}.")
    if value is None or value == "":
        return None, None  # the default again
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None, f"{target.name} takes a number: {setting.hint}."
    parsed = settings_apply.parse_number(setting, str(value))
    return (parsed, None) if parsed is not None else (None, f"{value!r} is not {'a whole number' if setting.whole else 'a number'}: {setting.hint}.")


def current_text(target: Target, persona: dict[str, Any]) -> str:
    """The value in force, in words."""
    if target.kind == SHARING:
        return "yes" if target.name[len(SHARE):] in sharing.approved() else "no"
    if target.kind == PERSONA_MODEL:
        return _model_label(model_mod.resolve_model(persona.get("model") or None))
    return settings_apply.value_text(target.registry_setting)  # type: ignore[arg-type]


def value_text(target: Target, value: Any) -> str:
    """A proposed value, in words."""
    if target.kind == SHARING:
        return "yes" if value else "no"
    if target.kind == PERSONA_MODEL:
        return _model_label(value)
    setting = target.registry_setting
    assert setting is not None
    if setting.kind == registry.TOGGLE:
        return "on" if value else "off"
    return "automatic" if value is None and setting.default() is None else str(setting.default() if value is None else value)


def _model_label(model_id: str) -> str:
    return next((m.label for m in offered(model_id) if m.id == model_id), model_id)


def consequence(target: Target, value: Any) -> str | None:
    """A line for the card where what accepting does is not clear from the change: a cloud model gets the conversation, and
    only what the user allows of their vault (ADR 031)."""
    if target.kind == PERSONA_MODEL and not sharing.is_local(value):
        return "Your messages go to this cloud model, with any earlier replies in this chat that quote your notes. Other parts of your vault go only where Settings allows."
    if target.kind == SHARING and value:
        return "A cloud model may then receive this from your vault; a local model is not affected."
    return None


def apply(target: Target, value: Any, handle: str) -> tuple[bool, str]:
    """Save it through the module that owns it; `(saved, what happened)`. A value the owner refuses leaves the setting as it was."""
    if target.kind == SHARING:
        saved = sharing.set_approved(target.name[len(SHARE):], bool(value))
        return saved, "Saved." if saved else f"Couldn't save {target.label}."
    if target.kind == PERSONA_MODEL:
        saved = persona_model.set_model(handle, value)
        return saved, "Saved." if saved else f"Couldn't save the model for {handle}."
    setting = target.registry_setting
    assert setting is not None
    if setting.kind == registry.NUMBER:
        return _number(setting, value)
    message, ok = settings_apply.set_value(setting, value)
    return ok, message


def _number(setting: registry.Setting, value: Any) -> tuple[bool, str]:
    message, ok = settings_apply.set_number(setting, "" if value is None else str(value))
    return ok, message
