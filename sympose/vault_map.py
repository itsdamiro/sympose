"""The vault map (docs/decisions/035): a small, always-present summary of the vault's shape — its
top-level folders, their definitions and note counts, and its most common tags — read fresh from the
same mtime-cached snapshot the tree, the Knowledge Nebula and the health report already use. It goes
in the prompt ahead of the sacrifice loop (docs/decisions/015) and is never left out to make room, unlike
the notes found for a message, so it is kept deliberately small. Everything in it is a count or a fact
read off the vault; nothing here calls a model."""

import os
from collections import Counter
from typing import Any

from sympose import folder_definitions, vault_paths
from sympose.vault_manifest_build import _tags_of
from sympose.vault_snapshot import get_vault_snapshot

MAX_FOLDERS_SHOWN = 20
MAX_TAGS_SHOWN = 8

# `(the snapshot list object, the map text built from it)` per scope: the snapshot is already mtime-cached
# and returns the very same list until the vault changes, so an identity check is enough to know the map
# is still current (the same trick `grounding._index_for` uses).
_MAP_CACHE: dict[tuple[str, ...], tuple[list[dict[str, Any]], str]] = {}


def _purpose_of(vault: str, folder: str, allowed_dirs: list[str]) -> str | None:
    """The purpose paragraph of `folder`'s definition note, or `None`: no definition, no purpose written
    (ADR 033 stage 2), or a definition the persona may not read (a scoped persona, ADR 010). `folder` is
    already the exact on-disk name (it came from a real note's path via `top_folder`), so unlike
    `template_for_folder` this needs no case-insensitive `folder_named` lookup."""
    path = os.path.join(vault, folder_definitions.definition_path(folder))
    if not vault_paths.is_within_any(path, allowed_dirs):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return folder_definitions.read_purpose(f.read())
    except (OSError, ValueError):  # ValueError: not valid UTF-8
        return None


def _build(vault: str, allowed_dirs: list[str], notes: list[dict[str, Any]]) -> str:
    all_folders = sorted({folder_definitions.top_folder(n["rel_path"].replace("\\", "/")) for n in notes})
    shown_folders = [f for f in all_folders if folder_definitions.can_have_definition(f)]
    counts = {f: len(folder_definitions.notes_in(notes, f)) for f in shown_folders}
    shown_folders = [f for f in shown_folders if counts[f] > 0]
    shown_folders.sort(key=lambda f: (-counts[f], f.lower()))

    tags: Counter[str] = Counter()
    for note in notes:
        tags.update(_tags_of(note.get("meta") or {}))

    top, rest = shown_folders[:MAX_FOLDERS_SHOWN], shown_folders[MAX_FOLDERS_SHOWN:]
    lines = [
        f"{len(notes)} notes in {len(shown_folders)} top-level folders." if shown_folders else f"{len(notes)} notes."
    ]
    for folder in top:
        count_text = f"{counts[folder]} note" + ("" if counts[folder] == 1 else "s")
        purpose = _purpose_of(vault, folder, allowed_dirs)
        lines.append(f"- {folder} ({count_text}): {purpose}" if purpose else f"- {folder} ({count_text}).")
    if rest:
        lines.append(f"({len(rest)} more folders not shown.)")
    if tags:
        lines.append("Most common tags: " + ", ".join(tag for tag, _ in tags.most_common(MAX_TAGS_SHOWN)) + ".")
    return "\n".join(lines)


def build(profile: dict[str, Any]) -> str:
    """The map as text for the prompt, or `""` with no vault or no notes (nothing is said about an empty
    vault; `NO_NOTES`-style wording belongs to the notes found for a message, not to this)."""
    sandbox = vault_paths.resolve_sandbox(profile)
    if sandbox is None:
        return ""
    vault, allowed_dirs = sandbox
    notes = get_vault_snapshot(vault, allowed_dirs)
    if not notes:
        return ""
    key = tuple(sorted(allowed_dirs))
    cached = _MAP_CACHE.get(key)
    if cached is not None and cached[0] is notes:
        return cached[1]
    text = _build(vault, allowed_dirs, notes)
    _MAP_CACHE[key] = (notes, text)
    return text
