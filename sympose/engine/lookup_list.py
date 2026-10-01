"""`list_notes`, the third tool of `ask` (docs/decisions/040, amendment of 2026-10-02): which notes are in one
folder, so a request by position ("the 5th note in my movies folder") or by folder ("what is in Projects?")
has something to work from. Read-only and inside the persona's scope, like the other two: it reads the same
snapshot, and a folder outside the scope or one that does not exist is "not found", the two not told apart.

The order is stated in the result and never assumed: alphabetical by file name, ignoring case. What it
returns are note names, so a cloud model gets them only when the user allows `notes` (ADR 031)."""

from typing import Any

from sympose import vault_paths
from sympose.engine import sharing
from sympose.engine.lookup_result import Result
from sympose.engine.prompt_text import WITHHELD_NOTES
from sympose.vault_snapshot import get_vault_snapshot

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


def _title(note: dict[str, Any]) -> str:
    meta = note.get("meta") or {}
    return str(meta.get("title") or meta.get("name") or note["file_name"][:-3])


def list_notes(profile: dict[str, Any], model: str, folder: str) -> Result:
    scope = vault_paths.resolve_sandbox(profile)
    wanted = folder.strip().strip("/")
    shown = repr(folder) if wanted else "the top of the vault"
    notes = get_vault_snapshot(*scope) if scope is not None else []
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
        lines.append(f"{number}. {_title(note)} ({note['rel_path']})")
    if len(here) > MAX_NAMES:
        lines.append(f"...and {len(here) - MAX_NAMES} more; search or open one by name to reach them.")
    if folders:
        lines.append("Folders inside it: " + ", ".join(f"{name} ({n} notes)" for name, n in sorted(folders.items(), key=lambda kv: kv[0].casefold())))
    return Result("\n".join(lines), lookup={"folder": wanted, "found": count})
