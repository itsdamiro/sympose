"""The two tools a persona has when it looks up notes itself (docs/decisions/040): `search_notes`, the
same retriever as the automatic search on a query the persona writes, and `open_note`, the whole of one
note. Both are read-only and inside the persona's own scope.

A tool never opens a path it was given: `open_note` looks the name up among the notes the persona's scope
already holds (the mtime-cached snapshot the search reads), so a name outside the scope, or one that is not
a note, finds nothing and cannot be told apart from a note that does not exist. What a tool finds is
returned as passages, gated by `sharing` like the automatic search's, before any of it reaches a model."""

import json
from typing import Any

from sympose.engine import connections, grounding, grounding_properties, lookup_find, lookup_list, lookup_scope, related, sharing
from sympose.engine.lookup_result import Result
from sympose.engine.prompt_blocks import passage_text
from sympose.engine.prompt_text import WITHHELD_CONNECTIONS, WITHHELD_NOTES, WITHHELD_PROPERTIES

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
    lookup_list.TOOL,
    lookup_find.TOOL,
]

_UNKNOWN_TOOL = "There is no tool called {name}. The tools are {names}."
_BAD_ARGUMENTS = "The arguments of {name} could not be read: give {argument} as text."
_NOT_FOUND = "No note called {path} was found in the vault."
_NOTHING = "The search for {query} found no notes."


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


def _no_folder_named(raw: str | dict[str, Any] | None) -> bool:
    """Whether `raw` is readable arguments that name no folder (nothing, or an empty text)."""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    folder = parsed.get("folder")
    return folder is None or (isinstance(folder, str) and not folder.strip())


def _with_extras(profile: dict[str, Any], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`hits` with each note's connections and, after all the text, its properties, as a turn's own
    search adds them (docs/decisions/030 and 035), so the two ways of finding notes give the same passages."""
    with_connections = related.for_hits(profile, connections.for_hits(profile, hits))
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


def open_note(profile: dict[str, Any], model: str, path: str) -> Result:
    note = lookup_scope.find(profile, path)
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
    if name == lookup_find.FIND:
        filters, problem = lookup_find.parse(raw_arguments)
        if filters is None:
            return Result(problem or "", lookup={"tool": name, "found": 0})
        result = lookup_find.find_notes(profile, model, filters)
        return Result(result.text, result.hits, result.withheld, {"tool": name, **result.lookup})
    tool = {
        SEARCH: ("query", search_notes), OPEN: ("path", open_note), lookup_list.LIST: ("folder", lookup_list.list_notes),
    }.get(name)
    if tool is None:
        names = ", ".join((SEARCH, OPEN, lookup_list.LIST, lookup_find.FIND))
        return Result(_UNKNOWN_TOOL.format(name=name, names=names), lookup={"tool": name, "found": 0})
    argument, problem = _arguments(raw_arguments, name, tool[0])
    if argument is None and name == lookup_list.LIST and _no_folder_named(raw_arguments):
        argument, problem = "", None  # no folder, or an empty one, is the top of the vault
    if argument is None:
        return Result(problem or "", lookup={"tool": name, "found": 0})
    result = tool[1](profile, model, argument)
    return Result(result.text, result.hits, result.withheld, {"tool": name, tool[0]: argument, **result.lookup})
