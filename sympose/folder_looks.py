"""A top-level folder's look, read from its definition note's own properties (docs/decisions/064): `icon` (the
name of an icon in the app's set) and `accent` / `accent_dark` (its colour in the Knowledge Nebula, light and
dark). The same keys as a persona's look (ADR 062), but a colour here is a six-digit hex only: it comes from a note
(which may be from a shared vault, not a file the user owns) and the nebula's renderers parse a hex. Read-only:
nothing here writes a note."""

import re
from typing import Any

from sympose import folder_definitions as defs
from sympose import look

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
KEYS = {"icon": look.ICON_NAME, "accent": HEX_COLOR, "accent_dark": HEX_COLOR}


def of_note(meta: dict[str, Any]) -> dict[str, str]:
    """The look keys of one definition note's properties that hold a value of the safe shape; the rest are left
    out, so a bad value is the same as none."""
    found = {key: look.clean(meta.get(key), pattern) for key, pattern in KEYS.items()}
    return {key: value for key, value in found.items() if value}


def _is_definition(note: dict[str, Any], folder: str) -> bool:
    return (note.get("rel_path") or "").replace("\\", "/") == defs.definition_path(folder)


def looks(notes: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """`{folder: look}` for each top-level folder whose definition note (`<Folder>/<Folder>.md`) is among `notes`
    and sets at least one look key."""
    found = {}
    for note in notes:
        folder = defs.top_folder(note.get("rel_path") or "")
        if not defs.can_have_definition(folder) or not _is_definition(note, folder):
            continue
        if folder_look := of_note(note.get("meta") or {}):
            found[folder] = folder_look
    return found


# The look the web app has always drawn these folder names with (`VAULT_FOLDERS` and the nebula's colour tables in
# `ui/src/lib`, which a test keeps equal to this): `folder: (icon, accent, accent_dark)`. It exists so the vault
# health can offer to write it into a definition that has none (ADR 064); once that is done the lists can go.
BUILT_IN = {
    "Projects": ("folder-library", "#0284c7", "#56c9e0"),
    "Code": ("source-code", "#059669", "#6fdcb0"),
    "Daily": ("calendar", "#b45309", "#e7c14a"),
    "Drawings": ("paintbrush-2", "#7c3aed", "#b98cff"),
    "General": ("folder", "#334155", "#9aa7bd"),
    "Limbo": ("hourglass", "#475569", "#6b7280"),
    "Movies": ("film-roll", "#be123c", "#f2889b"),
    "People": ("users", "#c2410c", "#f0a35a"),
    "Quotes": ("quote", "#92400e", "#d9c169"),
    "Reading": ("book-open", "#1d4ed8", "#7aa7e0"),
    "Recipes": ("chef-hat", "#b45309", "#e78a5c"),
    "Templates": ("copy", "#0f766e", "#5fc7c7"),
    "Writing": ("pencil-edit", "#a21caf", "#e07ac0"),
}


def offer(folder: str, notes: list[dict[str, Any]]) -> list[str]:
    """The property lines to add to `folder`'s definition note: its built-in icon, and its built-in colours where
    the note sets none. Empty when the folder has no definition among `notes`, the folder is not in `BUILT_IN`, or
    the note already has an `icon` property (whatever it holds: a chosen icon is never changed, ADR 064)."""
    built_in = BUILT_IN.get(folder)
    definition = next((n for n in notes if _is_definition(n, folder)), None)
    if built_in is None or not defs.can_have_definition(folder) or definition is None:
        return []
    meta = definition.get("meta") or {}
    if "icon" in meta:
        return []
    icon, accent, accent_dark = built_in
    lines = [f"icon: {icon}"]
    if "accent" not in meta:
        lines.append(f"accent: '{accent}'")
    if "accent_dark" not in meta:
        lines.append(f"accent_dark: '{accent_dark}'")
    return lines
