"""`find_notes`, the fourth tool of `ask` (docs/decisions/058, ADR 035's layer 4): the notes that match filters
on the vault's structure, so "which notes link to Atlas?", "everything tagged idea", "the films not watched yet"
or "how many notes mention backups?" return only the matches and only they use tokens. Read-only, inside the
persona's scope, and mechanical: every filter is an exact test of data the snapshot and the link graph already
hold, none is a search by meaning. Filters are combined (all must match). What comes back is names, so a cloud
model gets it only as `notes` allows, and a filter on a tag or a property also needs `properties` (ADR 031)."""

import json
from typing import Any

from sympose.engine import connections, lookup_list, lookup_scope, sharing
from sympose.engine.grounding_properties import _value_text
from sympose.engine.lookup_result import Result
from sympose.engine.prompt_text import WITHHELD_NOTES, WITHHELD_PROPERTIES
from sympose.vault_manifest_build import _tags_of

FIND = "find_notes"
MAX_NAMES = 100
FILTERS = ("folder", "tag", "property", "value", "links_to", "linked_from", "text")

TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": FIND,
        "description": (
            "Find the user's notes by what they hold, not by topic: all notes in a folder, with a tag, with a "
            "property (and a value, such as watched: no), that link to a note or are linked from one, or whose "
            "text contains some words exactly. Filters are combined. You get the count and the matching notes. "
            "Use it for questions such as which notes link to X, what is tagged Y, which films are not watched, "
            "or how many notes mention Z. Use it instead of opening notes one by one to check a tag, a property or a "
            "link: one call gives the whole answer. At least one filter is needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "A folder's path, for example \"Movies\"."},
                "tag": {"type": "string", "description": "A tag, with or without the #."},
                "property": {"type": "string", "description": "A property name, for example \"status\"."},
                "value": {"type": "string", "description": "The value that property must have (needs property)."},
                "links_to": {"type": "string", "description": "A note's title or path: notes that link to it."},
                "linked_from": {"type": "string", "description": "A note's title or path: notes it links to."},
                "text": {"type": "string", "description": "Words the note's text must contain, exactly."},
            },
        },
    },
}

_BAD_ARGUMENTS = "The arguments of find_notes could not be read: give at least one filter ({names}), each as text."
_VALUE_NEEDS_PROPERTY = "A value is only a filter together with the property it belongs to: add the property."
_NOT_FOUND = "No note called {name} was found in the vault."
_YES_NO = {"yes": "true", "no": "false"}  # YAML reads an unquoted yes or no as a boolean, written back as true or false


def parse(raw: str | dict[str, Any] | None) -> tuple[dict[str, str] | None, str | None]:
    """`(the filters given, None)` or `(None, what to tell the model)`: only known filters, only text, at
    least one non-empty."""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        return None, _BAD_ARGUMENTS.format(names=", ".join(FILTERS))
    given: dict[str, str] = {}
    for key in FILTERS:
        value = parsed.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            return None, _BAD_ARGUMENTS.format(names=", ".join(FILTERS))
        if value.strip():
            given[key] = value.strip()
    if "value" in given and "property" not in given:
        return None, _VALUE_NEEDS_PROPERTY
    if not given:
        return None, _BAD_ARGUMENTS.format(names=", ".join(FILTERS))
    return given, None


def _forms(value: Any) -> list[str]:
    """The texts one property value can be compared by: each entry of a list on its own, a yes or no as true or false."""
    items = value if isinstance(value, (list, tuple)) else [value]
    return [_YES_NO.get(text.lower(), text.lower()) for text in (_value_text(item) for item in items) if text]


def _property_of(meta: dict[str, Any], name: str) -> tuple[bool, Any]:
    for key, value in meta.items():
        if str(key).lower() == name.lower():
            return True, value
    return False, None


def _has_tag(note: dict[str, Any], tag: str) -> bool:
    wanted = tag.lower().lstrip("#")
    return any(have == wanted or have.startswith(wanted + "/") for have in (t.lower() for t in _tags_of(note.get("meta") or {})))


def _matches(profile: dict[str, Any], filters: dict[str, str]) -> tuple[list[dict[str, Any]], str | None]:
    """The notes that pass every filter, in the order the snapshot holds them, or `(…, the name that was not found)`."""
    notes = lookup_scope.in_scope(profile)
    folder = filters.get("folder", "").strip("/").lower()
    if folder:
        notes = [n for n in notes if n["rel_path"].lower().startswith(folder + "/")]
    if "tag" in filters:
        notes = [n for n in notes if _has_tag(n, filters["tag"])]
    if "property" in filters:
        wanted = _YES_NO.get(filters["value"].lower(), filters["value"].lower()) if "value" in filters else None
        kept = []
        for note in notes:
            has, value = _property_of(note.get("meta") or {}, filters["property"])
            if has and (wanted is None or wanted in _forms(value)):
                kept.append(note)
        notes = kept
    if "text" in filters:
        needle = filters["text"].lower()
        notes = [n for n in notes if needle in n["body"].lower()]
    for key in ("links_to", "linked_from"):
        if key not in filters:
            continue
        other = lookup_scope.find(profile, filters[key])
        if other is None:
            return [], filters[key]
        out, into = connections.link_graph(profile)
        linked = (into if key == "links_to" else out).get(other["rel_path"].replace("\\", "/"), set())
        notes = [n for n in notes if n["rel_path"].replace("\\", "/") in linked]
    return notes, None


def _shown(filters: dict[str, str]) -> str:
    return ", ".join(f"{key} {value!r}" for key, value in filters.items())


def find_notes(profile: dict[str, Any], model: str, filters: dict[str, str]) -> Result:
    matched, missing = _matches(profile, filters)
    recorded = {"filters": sorted(filters)}
    if missing is not None:
        return Result(_NOT_FOUND.format(name=repr(missing)), lookup={**recorded, "found": 0})
    ok = sharing.allowed(model)
    withheld = {category: len(matched) for category, needed in (
        (sharing.NOTES, True), (sharing.PROPERTIES, bool({"tag", "property"} & filters.keys()))
    ) if needed and category not in ok}
    if withheld:
        text = WITHHELD_NOTES if sharing.NOTES in withheld else WITHHELD_PROPERTIES
        return Result(text, withheld=withheld, lookup={**recorded, "found": 0})
    if not matched:
        return Result(f"No notes match {_shown(filters)}.", lookup={**recorded, "found": 0})
    ordered = sorted(matched, key=lambda note: note["file_name"].casefold())
    lines = [f"{len(ordered)} notes match {_shown(filters)}, alphabetical by file name:"]
    for number, note in enumerate(ordered[:MAX_NAMES], 1):
        extra = ""
        if "property" in filters:
            _, value = _property_of(note.get("meta") or {}, filters["property"])
            extra = f", {filters['property']}: {_value_text(value)[:60]}"
        lines.append(f"{number}. {lookup_scope.title(note)} ({note['rel_path']}){extra}")
    if len(ordered) > MAX_NAMES:
        lines.append(f"...and {len(ordered) - MAX_NAMES} more; add a filter to narrow it.")
    keys = lookup_list.property_names(ordered) if "property" not in filters and sharing.PROPERTIES in ok else ""
    if keys:
        lines.append(f"Properties these notes have: {keys}. Filter on one with property and value.")
    return Result("\n".join(lines), lookup={**recorded, "found": len(ordered)})
