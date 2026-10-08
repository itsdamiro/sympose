"""The persona's tool for proposing a change to one setting (docs/decisions/080): `propose_setting(setting, value)`, for a
model that can call tools. A call ends in a request the user sees as a card (`confirmations.propose_setting`); nothing is
changed until the user accepts. The checks here are the ones that can be made without trying (the name, the value's shape, a
model on the list); the owning module's own rules run when the user accepts."""

import json
from typing import Any

from sympose.engine import confirmations, setting_targets
from sympose.engine.lookup_result import Result

PROPOSE = "propose_setting"
_BAD = "The arguments of propose_setting could not be read: give setting as text and value as true or false, a number or text."
_DONE = "Shown to the user as a card; nothing changes until they accept. Tell them in a sentence what you proposed."


def tool() -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": PROPOSE,
        "description": (
            "Propose changing one setting. The user sees it as a card showing the change and accepts or declines it; nothing changes before "
            "that. Use it when the user asks for something a setting does (faster replies, no notes sent to a cloud model, another model), "
            "after you have checked in the reference what the setting does. One setting per call. The setting is one of: "
            + ", ".join(setting_targets.names()) + ". `model` is the model this persona answers with; `cloud_share:<category>` is whether a "
            "cloud model may receive that category of the user's vault (true or false)."
        ),
        "parameters": {"type": "object", "properties": {
            "setting": {"type": "string", "description": "The setting's name, exactly as listed."},
            "value": {"description": "true or false for an on/off setting and a cloud_share one, one of its values for a choice, a number, or a model id; "
                                     "null puts a number setting back to its default."},
        }, "required": ["setting", "value"]},
    }}


def _read(raw: str | dict[str, Any] | None) -> tuple[str, Any] | None:
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("setting"), str) or "value" not in data:
        return None
    return data["setting"].strip(), data["value"]


def _file(handle: str, session_id: str, persona: dict[str, Any], raw: str | dict[str, Any] | None) -> tuple[bool, str, str | None]:
    """`(filed, what happened, the request's id)`."""
    read = _read(raw)
    if read is None:
        return False, _BAD, None
    name, value = read
    target = setting_targets.find(name)
    if target is None:
        return False, f"There is no setting called {name!r}. The settings are: {', '.join(setting_targets.names())}.", None
    value, why = setting_targets.parse(target, value, persona)
    if why is not None:
        return False, why, None
    return True, _DONE, confirmations.propose_setting(handle, session_id, name, value)["id"]


def run(handle: str, session_id: str, persona: dict[str, Any], name: str, raw: str | dict[str, Any] | None) -> Result | None:
    """The tool's result, or `None` for a name that is not ours so it composes in `persona_tools`."""
    if name != PROPOSE:
        return None
    filed, said, request_id = _file(handle, session_id, persona, raw)
    return Result(said, lookup={"tool": PROPOSE, "saved": filed, **({"request": request_id} if request_id else {})})
