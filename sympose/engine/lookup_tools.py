"""The two tools a persona has when it looks up notes itself (docs/decisions/040): `search_notes`, the
same retriever as the automatic search on a query the persona writes, and `open_note`, the whole of one
note. Both are read-only and inside the persona's own scope.

A tool never opens a path it was given: `open_note` looks the name up among the notes the persona's scope
already holds (the mtime-cached snapshot the search reads), so a name outside the scope, or one that is not
a note, finds nothing and cannot be told apart from a note that does not exist. What a tool finds is
returned as passages, gated by `sharing` like the automatic search's, before any of it reaches a model."""

import json
from dataclasses import dataclass, field
from typing import Any

from sympose import vault_paths
from sympose.engine import connections, grounding, grounding_properties, sharing
from sympose.engine.prompt_blocks import passage_text
from sympose.engine.prompt_text import WITHHELD_CONNECTIONS, WITHHELD_NOTES, WITHHELD_PROPERTIES
from sympose.vault_snapshot import get_vault_snapshot

SEARCH, OPEN = "search_notes", "open_note"
# A note's body is cut here, with a marker: the prompt budget then fits what is left (docs/decisions/015).
MAX_NOTE_CHARS = 12000
_CUT = "\n[The note continues; the rest was left out because it is long.]"

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": SEARCH,
            "description": (
                "Search the user's notes (their vault) for a topic, a name or a question and get back the "
                "best matching passages, with the note each one is from. Each passage is already the text "
                "of the note, so answer from it and open the whole note only when the passages don't "
                "say enough. Use it whenever the user asks about, or refers to, something they wrote "
                "or keep in their notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look for, in a few words."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": OPEN,
            "description": (
                "Open one note in full, by its path as given by a search (for example \"Projects/Atlas.md\") "
                "or by its title. Use it when the user names a note, or a search found a note you need to "
                "read all of."
            ),
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "The note's path or its title."}},
                "required": ["path"],
            },
        },
    },
]

_UNKNOWN_TOOL = "There is no tool called {name}. The tools are {names}."
_BAD_ARGUMENTS = "The arguments of {name} could not be read: give {argument} as text."
_NOT_FOUND = "No note called {path} was found in the vault."
_NOTHING = "The search for {query} found no notes."


@dataclass(frozen=True)
class Result:
    """What one tool call gives back: `text` for the model, `hits` (the passages it was sent, as the
    turn record keeps them), `withheld` (what a cloud model was not sent, by category) and `lookup`,
    the entry the turn record keeps for the call (a count, never text)."""

    text: str
    hits: list[dict[str, Any]] = field(default_factory=list)
    withheld: dict[str, int] = field(default_factory=dict)
    lookup: dict[str, Any] = field(default_factory=dict)


def _arguments(raw: str | dict[str, Any] | None, name: str, argument: str) -> tuple[str | None, str | None]:
    """`(the argument's text, None)` or `(None, what to tell the model)`."""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        parsed = None
    value = parsed.get(argument) if isinstance(parsed, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip(), None
    return None, _BAD_ARGUMENTS.format(name=name, argument=argument)


def _with_extras(profile: dict[str, Any], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`hits` with each note's connections and, after all the text, its properties, as a turn's own
    search adds them (docs/decisions/030 and 035), so the two ways of finding notes give the same passages."""
    with_connections = connections.for_hits(profile, hits)
    index = grounding.scope_index(profile) if hits else None
    if index is None:
        return with_connections
    return with_connections + grounding_properties.for_hits(index.properties, with_connections)


_WITHHELD_TEXT = {
    sharing.NOTES: WITHHELD_NOTES,
    sharing.PROPERTIES: WITHHELD_PROPERTIES,
    sharing.CONNECTIONS: WITHHELD_CONNECTIONS,
}


def _describe(model: str, profile: dict[str, Any], hits: list[dict[str, Any]], heading: str, nothing: str) -> Result:
    """The passages `model` may receive, worded for a tool result, and what was held back. A search that
    found notes none of which may be sent says so, so the persona does not report an empty vault."""
    found = _with_extras(profile, hits)
    gated = sharing.gate(model, found, [])
    held = [text for category, text in _WITHHELD_TEXT.items() if gated.withheld.get(category)]
    if not gated.grounding:
        return Result("\n".join(held) or nothing, [], gated.withheld, {"found": 0})
    lines = [heading]
    for hit in gated.grounding:
        where = hit["rel_path"]
        if hit.get("heading") and hit["heading"] != hit["title"]:
            where += f" › {hit['heading']}"
        lines.append(f"- {hit['title']} ({where}): {passage_text(hit)}")
    notes = {hit["rel_path"] for hit in gated.grounding}
    return Result("\n".join([*lines, *held]), gated.grounding, gated.withheld, {"found": len(notes)})


def search_notes(profile: dict[str, Any], model: str, query: str) -> Result:
    hits = [{**hit, "via": hit.get("via", "search")} for hit in grounding.ground(profile, query)]
    return _describe(model, profile, hits, f"Notes found for the search {query!r}:", _NOTHING.format(query=repr(query)))


def _cut(text: str) -> str:
    return text if len(text) <= MAX_NOTE_CHARS else text[:MAX_NOTE_CHARS].rstrip() + _CUT


def _find(profile: dict[str, Any], path: str) -> dict[str, Any] | None:
    """The note in the persona's scope that `path` names: its path relative to the vault (with or without
    `.md`, in any case), else its title or file name when only one note has it."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return None
    notes = get_vault_snapshot(*scope)
    wanted = path.strip().strip("/").lower()
    bare = wanted[:-3] if wanted.endswith(".md") else wanted
    for note in notes:
        rel = note["rel_path"].lower()
        if rel == wanted or rel[:-3] == bare:
            return note
    named = [
        note for note in notes
        if bare in {
            note["file_name"][:-3].lower(),
            str((note.get("meta") or {}).get("title") or (note.get("meta") or {}).get("name") or "").lower(),
        }
    ]
    return named[0] if len(named) == 1 else None


def open_note(profile: dict[str, Any], model: str, path: str) -> Result:
    note = _find(profile, path)
    if note is None:
        return Result(_NOT_FOUND.format(path=repr(path)), lookup={"found": 0})
    meta = note.get("meta") or {}
    title = str(meta.get("title") or meta.get("name") or note["file_name"][:-3])
    body = note["body"].strip()
    base = {"rel_path": note["rel_path"], "title": title, "heading": "", "tags": [], "via": "opened"}
    hit = {**base, "text": _cut(body), "kind": "text"} if body else {**base, "text": "", "kind": "title"}
    return _describe(model, profile, [hit], f"The note {title} ({note['rel_path']}):", _NOT_FOUND.format(path=repr(path)))


def run(profile: dict[str, Any], model: str, name: str, raw_arguments: str | dict[str, Any] | None) -> Result:
    """Run the tool `name` and give back what the model is told. An unknown tool, or arguments that are
    not readable, is a result like any other (the model can try again), never an exception that ends the turn."""
    tool = {SEARCH: ("query", search_notes), OPEN: ("path", open_note)}.get(name)
    if tool is None:
        return Result(_UNKNOWN_TOOL.format(name=name, names=" and ".join((SEARCH, OPEN))), lookup={"tool": name, "found": 0})
    argument, problem = _arguments(raw_arguments, name, tool[0])
    if argument is None:
        return Result(problem or "", lookup={"tool": name, "found": 0})
    result = tool[1](profile, model, argument)
    return Result(result.text, result.hits, result.withheld, {"tool": name, tool[0]: argument, **result.lookup})
