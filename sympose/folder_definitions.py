"""Folder definitions (docs/decisions/033): a note per top-level folder, `People/People.md`, that says what the folder
is for and holds a `## Template` block of the properties its notes carry.

Everything here reads and computes; nothing writes (`folder_definitions_write.py` does, from a draft a caller has
shown). The template is a count of the folder's real notes, never something a model was asked to make up."""

import math
import os
import re
from collections import Counter
from typing import Any

import yaml

from sympose import generic_template, settings_store, vault_paths
from sympose.vault_defaults import IGNORE_FOLDERS

MIN_NOTES_SETTING = "folder_definition_min_notes"
DEFAULT_MIN_NOTES = 5
SHARE_SETTING = "folder_template_share"
DEFAULT_SHARE = 0.5
_NOT_FOLDERS = {name.lower() for name in IGNORE_FOLDERS} | {"templates"}  # not the user's content: no definition
_MAX_CONSTANT = 60  # a value longer than this is not a constant of the folder, it is a sentence
_KEY = generic_template.KEY
_HEADING = re.compile(r"^#{1,6}[ \t]+template[ \t]*#*[ \t]*$", re.IGNORECASE)  # `#template` is a tag, not a heading
_ANY_HEADING = re.compile(r"^#{1,6}[ \t]+\S")  # a heading needs a space after the hashes: `#todo` is prose
_FENCE = re.compile(r"^[ \t]*(```|~~~)")


def min_notes() -> int:
    """The user's `folder_definition_min_notes`, else 5. Only a whole number of at least 1 that is not a bool counts."""
    value = settings_store.get(MIN_NOTES_SETTING)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else DEFAULT_MIN_NOTES


def template_share() -> float:
    """The user's `folder_template_share`, else 0.5: the share of a folder's notes that must carry a property for
    it to be in the template. Only a number above 0 and at most 1 that is not a bool counts."""
    value = settings_store.get(SHARE_SETTING)
    usable = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 < value <= 1
    return float(value) if usable else DEFAULT_SHARE


def top_folder(rel_path: str) -> str:
    """The top-level folder of a note's path, `""` for a note at the vault's root."""
    head, sep, _ = rel_path.replace("\\", "/").partition("/")
    return head if sep else ""


def definition_path(folder: str) -> str:
    return f"{folder}/{folder}.md"


def can_have_definition(folder: str) -> bool:
    """A top-level folder of the user's content: one name, not hidden, not `Templates` or an ignored folder."""
    return bool(folder) and not folder.startswith(".") and "/" not in folder and "\\" not in folder and folder.lower() not in _NOT_FOLDERS


def notes_in(notes: list[dict[str, Any]], folder: str) -> list[dict[str, Any]]:
    """The notes under `folder` at any depth, not counting its definition note."""
    own = definition_path(folder)
    return [n for n in notes if top_folder(n["rel_path"]) == folder and n["rel_path"].replace("\\", "/") != own]


def due_folders(notes: list[dict[str, Any]], minimum: int | None = None) -> list[tuple[str, int]]:
    """`(folder, number of notes)` for each top-level folder that has no definition and at least `minimum` notes
    (the setting when omitted), the fullest first. A folder that is not due is not mentioned: nothing is written
    for an empty folder, and a placeholder is not nagged about."""
    minimum = min_notes() if minimum is None else minimum
    counts: Counter[str] = Counter()
    defined: set[str] = set()
    for note in notes:
        rel = note["rel_path"].replace("\\", "/")
        folder = top_folder(rel)
        if not can_have_definition(folder):
            continue
        if rel == definition_path(folder):
            defined.add(folder)
        else:
            counts[folder] += 1
    due = [(folder, count) for folder, count in counts.items() if folder not in defined and count >= minimum]
    return sorted(due, key=lambda item: (-item[1], item[0].lower()))


def _constant(values: list[Any]) -> str:
    """`value` as a property line's text when every note holds the same short plain value, else `""`."""
    first = values[0]
    if not isinstance(first, (str, int, float, bool)) or any(v != first or type(v) is not type(first) for v in values):
        return ""
    text = yaml.safe_dump(first, allow_unicode=True, default_flow_style=True, width=1000).strip().removesuffix("...").strip()
    return text if 0 < len(text) <= _MAX_CONSTANT and "\n" not in text else ""


def template_lines(notes: list[dict[str, Any]], folder: str, share: float | None = None) -> list[str]:
    """The property lines a note of `folder` usually carries: each property that at least `share` of the folder's
    notes have (the setting when omitted), the most common first and the first seen among equals. The value is left
    empty unless every note of the folder holds the same one (`type: person`): a value that only some notes carry is
    theirs, not the folder's. `[]` for a folder whose notes do not agree."""
    share = template_share() if share is None else share
    metas = [n.get("meta") or {} for n in notes_in(notes, folder)]
    seen: dict[str, list[Any]] = {}
    for meta in metas:
        for key, value in meta.items():
            if isinstance(key, str) and _KEY.fullmatch(key):
                seen.setdefault(key, []).append(value)
    common = sorted((k for k, v in seen.items() if len(v) / len(metas) >= share), key=lambda k: -len(seen[k])) if metas else []
    return [f"{key}: {_constant(seen[key]) if len(seen[key]) == len(metas) else ''}".rstrip() for key in common]


def read_template(body: str) -> str | None:
    """The property lines of a definition's `## Template` section: the first fenced block under a heading called
    Template (any level, any case) with no other heading between them. Every such heading is tried, so a note
    that has a title called Template (a folder of that name) or a stray heading first still has its section found.
    `None` when there is none or the block is empty; the rest of the note is not read."""
    lines = body.splitlines()
    for start, line in enumerate(lines):
        if not _HEADING.match(line.strip()):
            continue
        fence = next((i for i in range(start + 1, len(lines)) if _FENCE.match(lines[i])), None)
        if fence is None or any(_ANY_HEADING.match(text.strip()) for text in lines[start + 1 : fence]):
            continue  # this heading has no block of its own: the next one may
        marker = _FENCE.match(lines[fence]).group(1)
        end = next((i for i in range(fence + 1, len(lines)) if lines[i].strip().startswith(marker)), len(lines))
        return "\n".join(lines[fence + 1 : end]).strip() or None
    return None


def read_purpose(body: str) -> str | None:
    """The purpose paragraph of a definition (`render`'s own shape, docs/decisions/035): everything before
    its `## Template` section, minus the note's own `# <Folder>` title line. `None` when there is none — an
    empty note, or a purpose the vault owner never wrote (ADR 033 stage 2's `unclear`, `withheld` or
    `failed`, where the draft has the template and no purpose)."""
    lines = body.splitlines()
    end = next((i for i, line in enumerate(lines) if _HEADING.match(line.strip())), len(lines))
    before = [line for line in lines[:end] if not line.strip().startswith("# ")]
    text = "\n".join(before).strip()
    return text or None


def as_template(block: str) -> str:
    """A block of property lines as the frontmatter a new note starts with (rendered like a `Templates/` file)."""
    block = block.strip()
    return block if block.startswith("---") else f"---\n{block}\n---"


def folder_named(vault: str, name: str) -> str:
    """The top-level folder of `vault` that `name` means, whatever its case (as the `Templates/` match is): `name`
    itself when a folder is called exactly that or none matches."""
    try:
        entries = os.listdir(vault)
    except OSError:
        return name
    if name in entries:
        return name
    return next((e for e in entries if e.lower() == name.lower() and os.path.isdir(os.path.join(vault, e))), name)


def template_for_folder(vault: str, folder: str, allowed_dirs: list[str] | None = None) -> str | None:
    """The template of `folder`'s definition in the vault at `vault`, as frontmatter, or `None` (no definition,
    no template in it, or it cannot be read). Looks at that one file only, and, when `allowed_dirs` is given, only
    if the persona may read it (the same scope `draft` keeps)."""
    if not vault or not can_have_definition(folder):
        return None
    folder = folder_named(vault, folder)
    path = os.path.join(vault, definition_path(folder))
    if allowed_dirs is not None and not vault_paths.is_within_any(path, allowed_dirs):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            block = read_template(f.read())
    except (OSError, ValueError):  # ValueError: not valid UTF-8
        return None
    return as_template(block) if block else None


def render(folder: str, template: list[str], purpose: str = "") -> str:
    """The text of a definition: the purpose paragraph when there is one (never a made-up one), then the template."""
    parts = [f"# {folder}"]
    if purpose.strip():
        parts.append(purpose.strip())
    parts.append("## Template\n\n```yaml\n" + "\n".join(template) + ("\n" if template else "") + "```")
    return "\n\n".join(parts) + "\n"
