"""A note's properties, riding along with the note when it is found (docs/decisions/030, "Stage 2").

The frontmatter of a note that a turn attaches goes with it as one passage of its own, so a question
about `status` or `email` can be answered from the note that was found. Nothing here searches:
properties are not in the index's terms, so which notes are found is decided exactly as before, and a
note's properties come along only because the note did."""

import re
from datetime import date, datetime
from typing import Any

from sympose.engine.grounding_split import MAX_PASSAGE_CHARS

KIND = "properties"
HEADING = "Properties"
# The note a link names, without its heading or its shown text: `[[Anna Ruiz#Bio|Anna]]` is Anna Ruiz.
_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def _value_text(value: Any) -> str:
    """One property's value as plain text: a list joined with commas (an unquoted `[[Anna Ruiz]]` is read by
    the YAML parser as a list inside a list, and comes out as the name), a link as the name of its note, a
    date as a date."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return ", ".join(text for text in map(_value_text, value) if text)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {text}" for key, item in value.items() if (text := _value_text(item)))
    return _LINK.sub(r"\1", str(value)).strip()


def properties_text(meta: dict[str, Any]) -> str:
    """One `key: value` line for every property that has a value, cut at a line boundary at the size of one
    passage; `""` for a note with none. The key stays with its value: it is what says what the value means."""
    lines: list[str] = []
    for key, value in meta.items():
        text = _value_text(value)
        if not text:
            continue
        line = f"{key}: {text}"
        if len("\n".join([*lines, line])) > MAX_PASSAGE_CHARS:
            if not lines:
                lines.append(line[:MAX_PASSAGE_CHARS].rstrip())  # one huge value, and nothing before it
            break
        lines.append(line)
    return "\n".join(lines)


def for_hits(properties: dict[str, str], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One properties passage for each note among `hits` (the passages that were found) that has properties
    (`properties`: note path to its text, as the index keeps it), in the order the notes were found. They go
    after all the text and do not count toward the passages of a turn: they cannot push a body passage out,
    and they are the first left out when the prompt does not fit (docs/decisions/015)."""
    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    for hit in hits:
        path = hit["rel_path"]
        if path in seen:
            continue
        seen.add(path)
        if text := properties.get(path):
            found.append(
                {
                    "rel_path": path,
                    "title": hit["title"],
                    "heading": HEADING,
                    "text": text,
                    "tags": list(hit.get("tags", [])),
                    "kind": KIND,
                    "index": len(hits) + len(found) + 1,
                }
            )
    return found
