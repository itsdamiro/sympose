"""The persona's tool for proposing a new persona (docs/decisions/078): `propose_persona(...)`, for a model that can call
tools. A model without tools is not given it (measured: `gemma2:9b` answered every request with questions, never an attempt,
with or without the soul skill), so there is no marked-block form as there is for a note's proposal (ADR 072).

A call ends in `persona_create.problem` (the checks, answered with the first thing wrong so she can fix it) and
`confirmations.propose_persona` (a request the user sees as a card). Nothing here makes a persona: that waits for the
user's Accept."""

import json
from typing import Any

from sympose import look, persona_create
from sympose.engine import confirmations, edit_mode
from sympose.engine.lookup_result import Result

PROPOSE = "propose_persona"
_STRINGS = ("name", "title", "soul", "icon", "accent", "accent_dark", "edit_mode")
_BAD = "The arguments of propose_persona could not be read: give name, title, soul, icon, accent, accent_dark and edit_mode as text and folders as a list of folder names."
_DONE = "Shown to the user as a card; nothing is made until they accept. Tell them in a sentence what you proposed."


def offered(persona: dict[str, Any]) -> bool:
    """Whether this persona may propose personas: the one that has the Sympose reference library (ADR 078)."""
    return bool(persona.get("sympose_reference"))


def tool(persona: dict[str, Any], share_folders: bool = True) -> dict[str, Any]:
    """The tool as this persona is given it: the icon names and the folders she can read are listed in its description,
    the folders only when the model may be told the vault's folders (`share_folders`); otherwise she leaves them out and
    the user chooses them on the card."""
    folders = persona_create.readable_folders(persona) if share_folders else []
    text = {k: {"type": "string", "description": v} for k, v in {
        "name": "The new persona's name, as it is shown.",
        "title": "A few words on what it is, such as 'Patient mathematics tutor'.",
        "soul": "How it talks and what it is like to talk to: voice and temperament only, about 1,500 characters, written to it "
                "('You are ...'). Never rules for the vault, never what it can do or which tools it has, never anything about the user.",
        "icon": "Its icon, the one that suits its character. One of: " + ", ".join(look.ICON_NAMES) + ".",
        "accent": "Its colour in light mode, suited to its character, such as #3366cc.",
        "accent_dark": "Its colour in dark mode, a lighter version of the same hue.",
        "edit_mode": "How far it acts on notes: " + ", ".join(edit_mode.MODES) + ". plan talks only; manual proposes changes the user accepts.",
    }.items()}
    return {"type": "function", "function": {
        "name": PROPOSE,
        "description": "Propose a new persona. The user sees it as a card and accepts or declines it; nothing is made before that. "
                       "Everything in it is your suggestion from the character the user described: choose each detail to suit it. "
                       "Ask the user only for what you cannot work out from their request.",
        "parameters": {"type": "object", "properties": {**text, "folders": {
            "type": "array", "items": {"type": "string"},
            "description": (
                "The folders of the vault it may read, chosen to suit its character (a persona to talk with may need only a few). "
                "From: " + ", ".join(folders) + "."
            ) if share_folders else "Leave this empty: the user chooses the folders on the card.",
        }}, "required": [*_STRINGS, "folders"]},
    }}


def _draft(raw: str | dict[str, Any] | None) -> persona_create.Draft | None:
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return None
    folders = data.get("folders") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in _STRINGS) or not (
        isinstance(folders, list) and all(isinstance(f, str) for f in folders)
    ):
        return None
    return persona_create.Draft(**{k: data[k] for k in _STRINGS}, folders=tuple(folders))


def tool_names() -> tuple[str, ...]:
    """The engine's real tool names, which a soul must not mention."""
    from sympose.engine import chat_tools, edit_tools, lookup_tools, memory_tools

    names = {t["function"]["name"] for group in (lookup_tools.TOOLS, memory_tools.TOOLS, chat_tools.TOOLS, edit_tools.TOOLS) for t in group}
    return tuple(sorted(names | {PROPOSE}))


def _file(
    handle: str, session_id: str, persona: dict[str, Any], raw: str | dict[str, Any] | None, share_folders: bool,
) -> tuple[bool, str, str | None]:
    """`(filed, what happened, the request's id)`."""
    draft = _draft(raw)
    if draft is None:
        return False, _BAD, None
    problem = persona_create.problem(draft, persona, tool_names(), share_folders)
    if problem is not None:
        return False, problem, None
    return True, _DONE, confirmations.propose_persona(handle, session_id, draft)["id"]


def run(
    handle: str, session_id: str, persona: dict[str, Any], name: str, raw: str | dict[str, Any] | None, share_folders: bool = True,
) -> Result | None:
    """The tool's result, or `None` for a name that is not ours so it composes in `persona_tools`."""
    if name != PROPOSE:
        return None
    filed, said, request_id = _file(handle, session_id, persona, raw, share_folders)
    return Result(said, lookup={"tool": PROPOSE, "saved": filed, **({"request": request_id} if request_id else {})})
