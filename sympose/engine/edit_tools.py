"""The persona's edit tool (docs/decisions/072), in two shapes and one parser, the pattern of `memory_tools`
(ADR 041): `propose_edit(find, replace, say)` and `propose_note(text, title, say)` for a model that can call tools,
and for one that cannot, the same arguments as a marked block in its reply,

    <!-- propose_edit: {"find": "...", "replace": "...", "say": "..."} -->
    <!-- propose_note: {"text": "...", "title": "...", "say": "..."} -->
    <!-- comment_on: {"find": "...", "text": "..."} -->
    <!-- show_note: {"path": "..."} -->

which is read, filed and removed from what is shown. They end in `note_changes.propose_edit` / `propose_create` /
`annotate` (ADR 070, 069), which refuse a passage not found exactly once. A comment is hers on a passage, kept apart
from the note's text like the user's own. Nothing here writes the vault: a proposal waits for the
user's Accept. `show_note(path)` writes nothing at all: it only tells the web app to open a note of the persona's scope
in the editor (the path is returned in the record). A change that could not be placed is told to the user, in the open, never dropped silently."""

import json
import re
from typing import Any

from sympose import note_changes
from sympose.engine import lookup_scope
from sympose.engine.lookup_result import Result

EDIT, NOTE, COMMENT, SHOW = "propose_edit", "propose_note", "comment_on", "show_note"
_NO_NOTE = "No note is open in the editor, so there is nothing to change; ask the user to open it."
_BAD = "The arguments of {name} could not be read: give {fields} as text."
_NO_SUCH_NOTE = "No note called {path} was found in the vault, so nothing was opened."  # a marker's failure is shown to the user as it is
_ASK_WHICH = " Ask the user which note they mean."  # said to a model that called the tool, not to the user
_DONE = {COMMENT: "Commented.", SHOW: "Opened."}
_FIELDS = {EDIT: ("find", "replace", "say"), NOTE: ("text", "say"), COMMENT: ("find", "text"), SHOW: ("path",)}


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
        {"text": "The whole text of the new note.", "title": "A name of three to five words.", "say": "One sentence telling the user what it is.",
         "folder": "Only if the user asked for a place: the folder to make it in, as a path of the vault such as Projects/Sympose (it is made there "
                   "when they accept, and the folder with it if it is not there yet). Leave it out to make it in the folder the user is in."},
        ["text", "say"],
    ),
    _tool(
        COMMENT,
        "Leave a comment on one passage of the note open in the editor, without changing it: a question, a doubt or a "
        "pointer the user should see beside those words. It is kept apart from the note's text.",
        {"find": "The passage, copied from the note exactly, and found in it exactly once (add a neighbouring word if it is not).",
         "text": "What you want to say about it, in a sentence or two."},
        ["find", "text"],
    ),
    _tool(
        SHOW,
        "Open a note in the editor beside this conversation, for the user to read or edit. Use it when the user asks you to "
        "open or show a note. It does not change anything.",
        {"path": "The note's path in the vault, as it was given to you (for example Projects/Sympose/Plan.md), or its name."},
        ["path"],
    ),
]

_MARKER = re.compile(r"<!--\s*(propose_edit|propose_note|comment_on|show_note):\s*(\{.*?\})\s*-->", re.IGNORECASE | re.DOTALL)


def _arguments(name: str, raw: str | dict[str, Any] | None) -> dict[str, str] | None:
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) for k in _FIELDS[name]):
        return None
    title, folder = data.get("title"), data.get("folder")
    return {**{k: data[k] for k in _FIELDS[name]}, "title": title if isinstance(title, str) else "", "folder": folder if isinstance(folder, str) else ""}


def _propose(
    handle: str, path: str | None, text: str | None, name: str, raw: str | dict[str, Any] | None, scope: tuple[tuple[int, int], ...] = (),
) -> tuple[bool, str]:
    """`(saved, what happened)`: the one place a tool call and a marker both end."""
    args = _arguments(name, raw)
    if args is None:
        return False, _BAD.format(name=name, fields=", ".join(_FIELDS[name]))
    try:
        if name == COMMENT:
            if path is None or text is None:
                return False, _NO_NOTE
            note_changes.comment_on(handle, path, text, quote=args["find"], text=args["text"], author="persona", within=scope)
        elif name == NOTE:
            note_changes.propose_create(handle, f"new/{note_changes._id()}", args["text"], say=args["say"], title=args["title"] or None, folder=args["folder"] or None)
        elif path is None or text is None:
            return False, _NO_NOTE
        else:
            note_changes.propose_edit(handle, path, text, find=args["find"], replace=args["replace"], say=args["say"], within=scope)
    except note_changes.CannotAnchor as error:
        return False, str(error)
    return True, "Commented." if name == COMMENT else "Proposed; the user decides."


def _show(profile: dict[str, Any] | None, raw: str | dict[str, Any] | None) -> tuple[bool, str, str | None]:
    """`(opened, what happened, the note's path in the vault)`: the note `path` names within the persona's scope."""
    args = _arguments(SHOW, raw)
    if args is None:
        return False, _BAD.format(name=SHOW, fields="path"), None
    note = lookup_scope.find(profile, args["path"]) if profile is not None else None
    if note is None:
        return False, _NO_SUCH_NOTE.format(path=repr(args["path"])), None
    return True, f"Opened {note['rel_path']} in the editor for the user.", note["rel_path"]


def run(
    handle: str, note_path: str | None, note_text: str | None, name: str, raw: str | dict[str, Any] | None,
    profile: dict[str, Any] | None = None, scope: tuple[tuple[int, int], ...] = (),
) -> Result | None:
    """The tool's result, or `None` for a name that is not ours so it composes in `persona_tools`."""
    if name not in _FIELDS:
        return None
    if name == SHOW:
        opened, said, path = _show(profile, raw)
        return Result(said if opened else said + _ASK_WHICH, lookup={"tool": name, "saved": opened, **({"path": path} if path else {})})
    saved, said = _propose(handle, note_path, note_text, name, raw, scope)
    return Result(said, lookup={"tool": name, "saved": saved})


def apply_marker(
    handle: str, note_path: str | None, note_text: str | None, reply: str, profile: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """`reply` with every marker removed and filed as a proposal, and a record per marker (the same shape a tool
    call leaves). A marker that could not be placed adds one line saying so to what is shown. A reply with no marker
    is returned exactly as given."""
    matches = list(_MARKER.finditer(reply))
    if not matches:
        return reply, []
    records, failures = [], []
    for found in matches:
        name = found.group(1).lower()
        if name == SHOW:
            saved, said, shown_path = _show(profile, found.group(2))
            record: dict[str, Any] = {"tool": name, "saved": saved, **({"path": shown_path} if shown_path else {})}
        else:
            saved, said = _propose(handle, note_path, note_text, name, found.group(2))
            record = {"tool": name, "saved": saved}
        if not saved:
            record["reason"] = said
            failures.append(said if name == SHOW else f"A change could not be placed: {said}")
        records.append(record)
    shown = re.sub(r"\n{3,}", "\n\n", _MARKER.sub("", reply)).strip()
    if not shown and len(failures) < len(matches):
        kinds = {f.group(1).lower() for f in matches}
        shown = next((m for m in (_say(f.group(2)) for f in matches) if m), _DONE.get(kinds.pop(), "Proposed.") if len(kinds) == 1 else "Proposed.")
    if failures:
        shown = "\n\n".join(filter(None, [shown, *failures]))
    return shown, records


def _say(raw: str) -> str:
    try:
        value = json.loads(raw).get("say")
    except (json.JSONDecodeError, AttributeError):
        return ""
    return value.strip() if isinstance(value, str) else ""
