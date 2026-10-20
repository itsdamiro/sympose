"""The look of folders below a top-level folder, kept in that top-level folder's own definition note
(docs/decisions/090): `Projects/Projects.md` holds a `subfolders` property, a map from a path below `Projects` to the
folder's `accent` and `accent_dark` (and its `icon`), so `Projects/sympose` and `Projects/stylo` can be told apart in
the Knowledge Nebula and the tree without a note of their own for each. A note takes the colour of its nearest coloured
folder; an icon belongs to its own folder only.

Reading is `of_note`, `colors` and `nearest`; writing is `with_entries` (text in, text out), `set_color` (the one save the
Folder look dialog makes) and `follow` (a renamed or moved folder takes its entries with it). A colour here is a
six-digit hex, as for a top-level folder (ADR 064): it comes from a note that may be from a shared vault."""

import os
from typing import Any

import yaml

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import folder_looks, folder_settings_text, vault_paths
from sympose.look import ICON_NAME, ICON_NAMES
from sympose.look import clean as clean_value
from sympose.folder_looks_write import Failed, Missing, Refused, rewrite_note
from sympose.vault_snapshot import get_vault_snapshot, parse_frontmatter
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

KEY = "subfolders"
COLOR_KEYS = ("accent", "accent_dark")
LOOK_KEYS = (*COLOR_KEYS, "icon")
_CREATED = "Created note:"


def clean_path(path: object) -> str | None:
    """A path below a top-level folder as the property writes it (`sympose/decisions`): plain names joined by `/`,
    none empty, hidden or `..`. `None` for anything else, so a hand-written key that is not a folder is left out."""
    if not isinstance(path, str):
        return None
    parts = path.strip().replace("\\", "/").strip("/").split("/")
    if not all(part.strip() and not part.startswith(".") and part == part.strip() for part in parts):
        return None
    return "/".join(parts)


def of_note(meta: dict[str, Any]) -> dict[str, dict[str, str]]:
    """`{path below the folder: {accent, accent_dark, icon}}` from one definition note's properties: each entry that is
    a folder path and sets at least one colour or icon of the safe shape. The rest is left out, so a bad value is the
    same as none."""
    raw = meta.get(KEY)
    if not isinstance(raw, dict):
        return {}
    found: dict[str, dict[str, str]] = {}
    for key, value in raw.items():
        path = clean_path(key if isinstance(key, str) else str(key))
        if path is None or not isinstance(value, dict):
            continue
        look = {k: v for k in LOOK_KEYS if (v := clean_value(value.get(k), ICON_NAME if k == "icon" else folder_looks.HEX_COLOR))}
        if look:
            found[path] = look
    return found


def colors(notes: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """`{vault path of a folder: look}` (colours and icon, whichever it sets) for every folder below a top-level folder
    that its top-level folder's definition note (`<Top>/<Top>.md`, among `notes`) has an entry for."""
    found: dict[str, dict[str, str]] = {}
    for note in notes:
        top = defs.top_folder(note.get("rel_path") or "")
        if not defs.can_have_definition(top) or (note.get("rel_path") or "").replace("\\", "/") != defs.definition_path(top):
            continue
        for path, look in of_note(note.get("meta") or {}).items():
            found[f"{top}/{path}"] = look
    return found


def nearest(note_path: str, own: dict[str, dict[str, str]]) -> tuple[str, dict[str, str]] | None:
    """The closest coloured folder above a note: `(its vault path, its colour)`, or `None` when no folder between the
    note and the top-level folder (the top-level folder itself not counted) is coloured. An entry with only an icon
    colours nothing, so the search goes on past it."""
    parts = note_path.replace("\\", "/").split("/")[:-1]
    for depth in range(len(parts), 1, -1):
        folder = "/".join(parts[:depth])
        if colour := {k: v for k, v in own.get(folder, {}).items() if k in COLOR_KEYS}:
            return folder, colour
    return None


def _entry_lines(mapping: dict[str, Any]) -> list[str]:
    block = yaml.safe_dump({KEY: mapping}, default_flow_style=False, sort_keys=False, allow_unicode=True, width=1000)
    return block.splitlines(keepends=True)


def with_entries(text: str, changes: dict[str, dict[str, str] | None]) -> str | None:
    """`text`, a definition note, with each path of `changes` set to its look (a dict of `accent`, `accent_dark`
    and/or `icon`) or removed (`None`) in its `subfolders` property. Entries the note holds for other paths stay as they
    are, even ones this module cannot read. The property is written in YAML block style, so a comment inside it is not
    kept; every other line of the note is. `None` when the note opens a properties block it never closes, or when
    `subfolders` is there but is not a map."""
    parts = defs.split_frontmatter(text)
    if parts is None:
        return None
    front, rest = parts
    lines = front.splitlines(keepends=True)
    inner = lines[1:-1] if front else []
    span = folder_settings_text._key_span(inner, KEY)
    mapping: dict[Any, Any] = {}
    if span is not None:
        try:
            loaded = yaml.safe_load("".join(inner[span[0] : span[1]]))
        except yaml.YAMLError:
            return None
        held = loaded.get(KEY) if isinstance(loaded, dict) else None
        if held is not None and not isinstance(held, dict):
            return None
        mapping = dict(held or {})
    for path, look in changes.items():
        existing = next((k for k in mapping if isinstance(k, str) and clean_path(k) == path), path)
        if look is None:
            mapping.pop(existing, None)
        else:
            mapping[existing] = {k: look[k] for k in LOOK_KEYS if k in look}
    if span is not None:
        ending = "\r\n" if inner[span[0]].endswith("\r\n") else "\n"
        new = [line.rstrip("\n") + ending for line in _entry_lines(mapping)] if mapping else []
        inner[span[0] : span[1]] = new
        return (lines[0] + "".join(inner) + lines[-1] + rest) if front else text
    if not mapping:
        return text
    added = "".join(_entry_lines(mapping))
    if front:
        return lines[0] + "".join(inner) + added + lines[-1] + rest
    return f"---\n{added}---\n{rest}"


def _refusal(look: dict[str, str] | None) -> str | None:
    if look is None:
        return None
    if look.get("icon") is not None and look["icon"] not in ICON_NAMES:
        return f"`{look['icon']}` is not an icon Sympose has."
    if not look or any(k not in LOOK_KEYS or (k != "icon" and not folder_looks.HEX_COLOR.fullmatch(v)) for k, v in look.items()):
        return "A colour is six hexadecimal digits after a `#`, like `#be123c`."
    return None


def _split(path: str) -> tuple[str, str]:
    """`(top-level folder, path below it)` of a folder `path`; `Refused` unless it is a folder below a top-level one
    that can have a definition."""
    clean = clean_path(path)
    top, _, below = (clean or "").partition("/")
    if not clean or not below or not defs.can_have_definition(top):
        raise Refused(f"`{path}` is not a folder below one of your own top-level folders, so it has no colour to set.")
    return top, below


def _reachable(profile: dict[str, Any], path: str) -> tuple[str, list[str]] | None:
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return None
    folder = os.path.join(scope[0], *path.split("/"))
    ok = os.path.isdir(folder) and vault_paths.is_within_any(folder, scope[1])
    return scope if ok else None


def read(profile: dict[str, Any], path: str) -> dict[str, Any]:
    """What the Folder look dialog for `path` starts from: `{"editable": False}` when the folder cannot be given a look
    (not below one of the user's own top-level folders, or not there for this persona), otherwise `editable` and the
    colours and icon its own entry sets (`None` for one it does not)."""
    try:
        top, below = _split(path)
    except Refused:
        return {"editable": False}
    scope = _reachable(profile, f"{top}/{below}")
    if scope is None:
        return {"editable": False}
    own = colors(get_vault_snapshot(*scope)).get(f"{top}/{below}", {})
    return {"editable": True, **{key: own.get(key) for key in LOOK_KEYS}}


def set_color(profile: dict[str, Any], path: str, look: dict[str, str] | None) -> bool:
    """Sets the look of the folder `path` (`{accent, accent_dark}` hex values and/or an `icon` name) or clears it
    (`look` is `None`), in its top-level folder's definition note: edited in place, or created with only this property
    when the folder has no definition yet (nothing is created to clear a look). `True` when the note was created. Raises `Refused` with
    the reason a person can read (`Missing` for a folder that is not there, `Changed` when the note changed while it
    was being read, `Failed` when the disk did)."""
    top, below = _split(path)
    if reason := _refusal(look):
        raise Refused(reason)
    scope = _reachable(profile, f"{top}/{below}")
    if scope is None:
        raise Missing(f"Folder `{top}/{below}` not found in the vault.")
    return _write(profile, scope[0], top, {below: look})


def _write(profile: dict[str, Any], vault: str, top: str, changes: dict[str, dict[str, str] | None]) -> bool:
    """`changes` made in `top`'s definition note, which is created with only this property when there is none (and
    nothing is created to clear a colour). `True` when the note was created."""
    note = defs.definition_path(top)

    def edit(text: str) -> str:
        updated = with_entries(text, changes)
        if updated is None:
            raise Refused(f"`{note}` has a `{KEY}` property that is not a list of folders, or a properties block it does not close, so nothing was changed.")
        return updated

    if write_defs.defined(vault, top):
        rewrite_note(profile, note, edit)
        return False
    text = with_entries(f"# {top}\n", changes)
    if text is None or not any(changes.values()):
        return False
    result = write_defs.write(profile, write_defs.Draft(top, note, text, [], 0, False))
    if result == NOTE_EXISTS:
        raise Refused(f"`{top}` got a description while this was open. Close the dialog and open it again.")
    if result == NOTE_DENIED:
        raise Refused("That path is outside the folders this persona can use.")
    if not result.startswith(_CREATED):
        raise Failed(f"`{note}` could not be created. {result.removeprefix('Error: ')}")
    return True


def follow(profile: dict[str, Any], old: str, new: str) -> int:
    """After the folder `old` was renamed or moved to `new` (vault paths): its colour and its subfolders' move to the new
    paths, taken out of the note they were in and put into the one they belong in now (the same note for a rename).
    A folder that is now top-level has no entry of its own, and one already coloured at the new place keeps its
    colour. Silent when there is nothing to carry. Returns how many entries moved; raises `Refused` when a note
    cannot be read or written (the folder has moved by then, so the caller reports it and goes on)."""
    old_top, _, old_below = old.partition("/")
    new_top, _, new_below = new.partition("/")
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None or not old_below or not defs.can_have_definition(old_top):
        return 0
    held = _held(scope[0], old_top)
    moving = {key: look for key, look in held.items() if key == old_below or key.startswith(old_below + "/")}
    if not moving:
        return 0
    carried: dict[str, dict[str, str]] = {}
    if new_below and defs.can_have_definition(new_top):
        carried = {new_below + key[len(old_below) :]: look for key, look in moving.items()}
    leaving: dict[str, dict[str, str] | None] = {key: None for key in moving}
    if new_top == old_top:
        carried = {key: look for key, look in carried.items() if key not in held or key in moving}
        rewrite_note(profile, defs.definition_path(old_top), lambda text: _with(text, {**leaving, **carried}))
        return len(carried)
    # Into another top-level folder's note: its own entries win, and the note is made when it has none.
    there = _held(scope[0], new_top)
    carried = {key: look for key, look in carried.items() if key not in there}
    rewrite_note(profile, defs.definition_path(old_top), lambda text: _with(text, leaving))
    _write(profile, scope[0], new_top, carried)
    return len(carried)


def _held(vault: str, top: str) -> dict[str, dict[str, str]]:
    return of_note(parse_frontmatter(_read_note(vault, defs.definition_path(top)))[0])


def _with(text: str, changes: dict[str, dict[str, str] | None]) -> str:
    updated = with_entries(text, changes)
    if updated is None:
        raise Refused("The `subfolders` property could not be read, so its colours were not carried.")
    return updated


def _read_note(vault: str, rel: str) -> str:
    try:
        with open(os.path.join(vault, *rel.split("/")), encoding="utf-8", newline="") as f:
            return f.read()
    except (OSError, ValueError):
        return ""

