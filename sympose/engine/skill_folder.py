"""The folder a skill that drafts a note takes its shape from (docs/decisions/077, amendment of 2026-10-09): the
folder's definition note and one note already in it, exactly as stored, so a model copies the shape instead of recalling
or inventing it. Real vault content only, chosen without a model call: the folder is the one the message names, by its
name or by a constant of its template (`type: recipe` for "a recipe"), and none when two folders fit equally or none
does, so the skill's own step (ask which) applies."""

import re
from typing import Any

from sympose import folder_definitions as defs
from sympose import vault_paths
from sympose.vault_snapshot import get_vault_snapshot

MAX_DEFINITION = 1500  # characters of the definition note that are sent
MAX_EXAMPLE = 1800  # characters of the example note
CUT = "[The rest of this note was left out to fit.]"
_WORD = re.compile(r"[a-z0-9]+")
_HEADING = re.compile(r"^##[ \t]+\S", re.MULTILINE)


def _words(text: str) -> set[str]:
    """The lowercase words of `text` without a plural `s`, so that `recipes` and `recipe` are one word."""
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in _WORD.findall(text.lower())}


def _constants(template: str) -> set[str]:
    """The words of the values the template gives a property outright (`type: recipe`)."""
    words: set[str] = set()
    for line in template.splitlines():
        key, sep, value = line.partition(":")
        if sep and value.strip():
            words |= _words(value)
    return words


def _score(folder: str, template: str, message: set[str]) -> int:
    return len(_words(folder) & message) * 2 + len(_constants(template) & message)


def _cut(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if text[limit] != "\n":
        cut = cut.rsplit("\n", 1)[0]
    return f"{cut.rstrip()}\n{CUT}"


def _example(notes: list[dict[str, Any]], definition: str) -> dict[str, Any] | None:
    """The note of the folder that shows its sections best: the most `##` headings, then the shortest."""
    siblings = [n for n in notes if n["rel_path"] != definition]
    return min(siblings, key=lambda n: (-len(_HEADING.findall(n["body"])), len(n["full_content"]))) if siblings else None


def shape_for(persona: dict[str, Any], message: str) -> str | None:
    """The text for the prompt: the definition note and an example note of the folder `message` names, or `None` when
    there is no vault, no folder with a template, or not exactly one best match."""
    sandbox = vault_paths.resolve_sandbox(persona)
    if sandbox is None:
        return None
    vault, allowed_dirs = sandbox
    snapshot = get_vault_snapshot(vault, allowed_dirs)
    by_path = {n["rel_path"].replace("\\", "/"): n for n in snapshot}
    words = _words(message)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for folder in sorted({defs.top_folder(p) for p in by_path}):
        if not defs.can_have_definition(folder):
            continue
        definition = by_path.get(defs.definition_path(folder))
        template = defs.read_template(definition["body"]) if definition else None
        if definition and template and (score := _score(folder, template, words)):
            scored.append((score, folder, definition))
    scored.sort(key=lambda s: -s[0])
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return None
    _, folder, definition = scored[0]
    parts = [
        f"The folder {folder} and the shape its notes take. Its definition, `{definition['rel_path']}`, exactly as stored:",
        _cut(definition["full_content"], MAX_DEFINITION),
    ]
    example = _example([n for n in defs.notes_in(snapshot, folder)], definition["rel_path"])
    if example:
        parts += [f"A note already in the folder, `{example['rel_path']}`, exactly as stored:", _cut(example["full_content"], MAX_EXAMPLE)]
    return "\n\n".join(parts)
