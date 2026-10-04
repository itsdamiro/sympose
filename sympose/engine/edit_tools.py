"""The persona's edit tool (docs/decisions/072), in two shapes and one parser, the pattern of `memory_tools`
(ADR 041): `propose_edit(find, replace, say)` and `propose_note(text, title, say)` for a model that can call tools,
and for one that cannot, the same arguments as a marked block in its reply,

    <!-- propose_edit: {"find": "...", "replace": "...", "say": "..."} -->
    <!-- propose_note: {"text": "...", "title": "...", "say": "..."} -->

which is read, filed and removed from what is shown. Both end in `note_changes.propose_edit` / `propose_create`
(ADR 070), which refuse a passage not found exactly once. Nothing here writes the vault: a proposal waits for the
user's Accept. A change that could not be placed is told to the user, in the open, never dropped silently."""

import json
import re
from typing import Any

from sympose import note_changes
from sympose.engine.lookup_result import Result

EDIT, NOTE = "propose_edit", "propose_note"
_NO_NOTE = "No note is open in the editor, so there is nothing to change; ask the user to open it."
_BAD = "The arguments of {name} could not be read: give {fields} as text."
_FIELDS = {EDIT: ("find", "replace", "say"), NOTE: ("text", "say")}


def _tool(name: str, description: str, properties: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in properties.items()}, "required": required},
    }}


TOOLS: list[dict[str, Any]] = [
    _tool(
        EDIT,
        "Propose one change to the note open in the editor. The user sees it as a tracked change and accepts or declines it; "
        "nothing is saved before that. Use it when the user asks you to change the note.",
        {"find": "The passage to replace, copied from the note exactly, character for character, and found in it exactly once "
                 "(add a neighbouring word if it is not).",
         "replace": "What replaces it.", "say": "One sentence telling the user what you changed."},
        ["find", "replace", "say"],
    ),
    _tool(
        NOTE,
        "Propose a new note. The user reads it as a draft and accepts or declines it; no file exists before that.",
        {"text": "The whole text of the new note.", "title": "A name of three to five words.", "say": "One sentence telling the user what it is."},
        ["text", "say"],
    ),
]

_MARKER = re.compile(r"<!--\s*(propose_edit|propose_note):\s*(\{.*?\})\s*-->", re.IGNORECASE | re.DOTALL)


def _arguments(name: str, raw: str | dict[str, Any] | None) -> dict[str, str] | None:
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in _FIELDS[name]):
        return None
    title = data.get("title")
    return {**{k: data[k] for k in _FIELDS[name]}, "title": title if isinstance(title, str) else ""}


def _propose(handle: str, path: str | None, text: str | None, name: str, raw: str | dict[str, Any] | None) -> tuple[bool, str]:
    """`(saved, what happened)`: the one place a tool call and a marker both end."""
    args = _arguments(name, raw)
    if args is None:
        return False, _BAD.format(name=name, fields=", ".join(_FIELDS[name]))
    try:
        if name == NOTE:
            note_changes.propose_create(handle, f"new/{note_changes._id()}", args["text"], say=args["say"], title=args["title"] or None)
        elif path is None or text is None:
            return False, _NO_NOTE
        else:
            note_changes.propose_edit(handle, path, text, find=args["find"], replace=args["replace"], say=args["say"])
    except note_changes.CannotAnchor as error:
        return False, str(error)
    return True, "Proposed; the user decides."


def run(handle: str, note_path: str | None, note_text: str | None, name: str, raw: str | dict[str, Any] | None) -> Result | None:
    """The tool's result, or `None` for a name that is not ours so it composes in `persona_tools`."""
    if name not in (EDIT, NOTE):
        return None
    saved, said = _propose(handle, note_path, note_text, name, raw)
    return Result(said, lookup={"tool": name, "saved": saved})


def apply_marker(handle: str, note_path: str | None, note_text: str | None, reply: str) -> tuple[str, list[dict[str, Any]]]:
    """`reply` with every marker removed and filed as a proposal, and a record per marker (the same shape a tool
    call leaves). A marker that could not be placed adds one line saying so to what is shown. A reply with no marker
    is returned exactly as given."""
    matches = list(_MARKER.finditer(reply))
    if not matches:
        return reply, []
    records, failures = [], []
    for found in matches:
        name = found.group(1).lower()
        saved, said = _propose(handle, note_path, note_text, name, found.group(2))
        record: dict[str, Any] = {"tool": name, "saved": saved}
        if not saved:
            record["reason"] = said
            failures.append(said)
        records.append(record)
    shown = re.sub(r"\n{3,}", "\n\n", _MARKER.sub("", reply)).strip()
    if not shown and len(failures) < len(matches):
        shown = next((m for m in (_say(f.group(2)) for f in matches) if m), "Proposed.")
    if failures:
        shown = "\n\n".join(filter(None, [shown, *(f"A change could not be placed: {why}" for why in failures)]))
    return shown, records


def _say(raw: str) -> str:
    try:
        value = json.loads(raw).get("say")
    except (json.JSONDecodeError, AttributeError):
        return ""
    return value.strip() if isinstance(value, str) else ""
