"""How much a persona may do on the user's notes before the user's Accept (docs/decisions/072). In every mode the file
changes only when the user clicks Accept; the modes differ in how much she does before that:

    plan     she talks about a change and proposes nothing
    manual   she proposes tracked changes when asked (the default)
    accept   her edits are applied in the editor, and reach the file only through the user's save
    auto     she acts on her own initiative; everything still waits for the user's Accept

The mode that counts for a persona is her own `edit_mode` (the user's untracked `persona.local.yaml`, then her shipped
`persona.yaml`, both read by `profile`), then the global `edit_mode` setting, then `manual`. `note` is what the user is
shown when choosing `accept` or `auto`: how faithfully the model the persona uses edited, when it was measured."""

from typing import Any

from sympose import settings_store

SETTING = "edit_mode"
PLAN, MANUAL, ACCEPT, AUTO = "plan", "manual", "accept", "auto"
MODES = (PLAN, MANUAL, ACCEPT, AUTO)
DEFAULT = MANUAL

# One line each, for a screen that lists the modes (the persona page, docs/decisions/072).
SUMMARIES = {
    PLAN: "She talks about a change and proposes nothing.",
    MANUAL: "She proposes changes when you ask, and you accept or decline each.",
    ACCEPT: "Her edits are applied in the editor as she makes them; your save is what keeps them.",
    AUTO: "She acts on her own initiative; everything waits for your Accept.",
}
_READ_EACH = "Read each change before you accept it."
_GEMMA = (
    "On this model, measured on invented notes with her real prompt, a change was right 18 times out of 36 and "
    "placed but wrong 3 times out of 36; most of the others she talked about the change instead of proposing it. "
    "In an earlier, shorter test it invented a price the note did not hold once in 4. " + _READ_EACH
)
# What was measured, by model (docs/decisions/072, Measured). A model joins by a measurement and a line here.
MEASURED = {
    "ollama_chat/gemma2:9b": _GEMMA,
    "ollama/gemma2:9b": _GEMMA,
    "gemini/gemini-flash-latest": (
        "Measured on a small set of invented notes only, with her real prompt: a change was right 35 times out of 36 (once it "
        "added a list item without its marker). " + _READ_EACH
    ),
}
_UNMEASURED = (
    "This model has not been measured for editing notes. Models smaller than gemma2:9b are expected to be worse, "
    "not better. " + _READ_EACH
)


def valid(value: Any) -> str | None:
    """`value` when it is one of the modes, else `None` (a hand-edited file may hold anything)."""
    return value if isinstance(value, str) and value in MODES else None


def mode() -> str:
    """The global mode: the setting when it is one of the modes, else `manual`."""
    return valid(settings_store.get(SETTING)) or DEFAULT


def for_persona(persona: dict[str, Any] | None) -> str:
    """The mode that counts for a persona's profile: her own, else the global one."""
    return valid((persona or {}).get("edit_mode")) or mode()


def note(chosen: str, model: str | None) -> str | None:
    """What to show beside a chosen mode, or `None` for the two that need no warning."""
    if chosen not in (ACCEPT, AUTO):
        return None
    return MEASURED.get(model or "", _UNMEASURED)
