"""`list_notes`, the third tool of `ask` (docs/decisions/040, amendment of 2026-10-02): which notes are in one
folder, so a request by position ("the 5th note in my movies folder") or by folder ("what is in Projects?")
has something to work from. Read-only and inside the persona's scope, like the other two: it reads the same
snapshot, and a folder outside the scope or one that does not exist is "not found", the two not told apart.

The order is stated in the result and never assumed: alphabetical by file name, ignoring case. What it
returns are note names, so a cloud model gets them only when the user allows `notes` (ADR 031)."""

from typing import Any

from sympose.engine import lookup_scope, sharing
from sympose.engine.lookup_result import Result
from sympose.engine.prompt_text import WITHHELD_NOTES

LIST = "list_notes"
MAX_NAMES = 100

TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": LIST,
        "description": (
            "List the notes in one folder of the user's vault, numbered, and the folders inside it. Use it "
            "when the user asks what is in a folder, or asks for a note by its place in a folder (the 5th "
            "note, the first one). The notes are listed alphabetically by file name; say so when you give "
            "a position, as the user's own order may differ. Give an empty folder for the top of the vault."
        ),
        "parameters": {
            "type": "object",
            "properties": {"folder": {"type": "string", "description": "The folder's path, for example \"Movies\"."}},
            "required": ["folder"],
        },
    },
}

_NOT_FOUND = "No folder called {folder} was found in the vault."
_EMPTY = "The folder {folder} has no notes in it."


MAX_PROPERTIES = 12


def property_names(notes: list[dict[str, Any]]) -> str:
    """The property names the notes use, most used first, with how many notes have each: what tells the persona
    that a filter on one exists, so it does not open the notes one by one to find out (docs/decisions/058)."""
    counts: dict[str, int] = {}
    for note in notes:
        for key in note.get("meta") or {}:
            counts[str(key)] = counts.get(str(key), 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))[:MAX_PROPERTIES]
    return ", ".join(f"{key} ({count})" for key, count in ranked)


def list_notes(profile: dict[str, Any], model: str, folder: str) -> Result:
    wanted = folder.strip().strip("/")
    shown = repr(folder) if wanted else "the top of the vault"
    notes = lookup_scope.in_scope(profile)
    prefix = wanted.lower() + "/" if wanted else ""
    inside = [note for note in notes if note["rel_path"].lower().startswith(prefix)]
    if not inside:
        return Result(_NOT_FOUND.format(folder=repr(folder)), lookup={"folder": wanted, "found": 0})
    here = sorted(
        (note for note in inside if "/" not in note["rel_path"][len(prefix):]),
        key=lambda note: note["file_name"].casefold(),
    )
    folders: dict[str, int] = {}
    for note in inside:
        rest = note["rel_path"][len(prefix):]
        if "/" in rest:
            name = rest.split("/", 1)[0]
            folders[name] = folders.get(name, 0) + 1
    count = len(here) + len(folders)
    if sharing.NOTES not in sharing.allowed(model):
        return Result(WITHHELD_NOTES, withheld={sharing.NOTES: count}, lookup={"folder": wanted, "found": 0})
    lines = [f"Notes in {shown}, {len(here)} in alphabetical order by file name:"] if here else [_EMPTY.format(folder=shown)]
    for number, note in enumerate(here[:MAX_NAMES], 1):
        lines.append(f"{number}. {lookup_scope.title(note)} ({note['rel_path']})")
    if len(here) > MAX_NAMES:
        lines.append(f"...and {len(here) - MAX_NAMES} more; search or open one by name to reach them.")
    keys = property_names(here) if sharing.PROPERTIES in sharing.allowed(model) else ""
    if keys:
        lines.append(f"Properties these notes have: {keys}. find_notes can filter on them in one call.")
    if folders:
        lines.append("Folders inside it: " + ", ".join(f"{name} ({n} notes)" for name, n in sorted(folders.items(), key=lambda kv: kv[0].casefold())))
    return Result("\n".join(lines), lookup={"folder": wanted, "found": count})
