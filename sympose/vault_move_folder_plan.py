"""What moving a folder would do and what it needs the user's word for (docs/decisions/074, slice 1): the same checks
the move itself will make, and what it found: a folder of that name already at the destination (a merge), the files that
are in both, the personas whose reach would change, whether a definition note stops or starts applying. Read only:
nothing here moves, renames or writes a file."""

import os
import posixpath
from dataclasses import dataclass
from typing import Any

from sympose import folder_definitions
from sympose.vault_folder_paths import OK, resolve_folder
from sympose.vault_move_reach import Reach, notes_in, reach_changes
from sympose.vault_write_rename_folder import _new_name_error
from sympose.vault_write_status import NOTE_EXISTS, NOTE_INVALID_NAME


@dataclass(frozen=True)
class MovePlan:
    path: str  # the folder, vault-relative
    destination: str  # the folder it goes into, "" for the vault root
    new_path: str  # where it will be, before any rename the user chooses for a clash
    clash: bool  # a folder of that name is already there: the user chooses to rename or merge
    note_clashes: tuple[str, ...]  # on a merge, what is in both, relative to the folder (hidden files left out)
    reach: tuple[Reach, ...]  # the personas who would read more or less
    definition: str | None  # "stops" or "starts" when a definition note's folder changes between top level and below


def clashes(src: str, target: str) -> tuple[str, ...]:
    """What the folder holds that is already at `target`: a file where there is a file or a folder, a folder where there
    is a file. A folder in both is merged, not a clash. Hidden names are left out. Nothing is already at a `target`
    that is not there, so a move with no folder of that name has none."""
    found = []
    for folder, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        rel = os.path.relpath(folder, src)
        there = target if rel == "." else os.path.join(target, rel)
        for name in files:
            if not name.startswith(".") and os.path.lexists(os.path.join(there, name)):
                found.append(posixpath.join(*([] if rel == "." else rel.split(os.sep)), name))
        for name in dirs:
            if os.path.lexists(os.path.join(there, name)) and not os.path.isdir(os.path.join(there, name)):
                found.append(posixpath.join(*([] if rel == "." else rel.split(os.sep)), name))
    return tuple(sorted(found))


def _definition(mv: str, old: str, new: str) -> str | None:
    """A definition note is read only on a top-level folder (ADR 033), so a folder that has one stops having it below
    the top and starts again when it comes back."""
    name = posixpath.basename(old)
    if folder_definitions.can_have_definition(old) and "/" in new and os.path.exists(os.path.join(mv, folder_definitions.definition_path(old))):
        return "stops"
    if folder_definitions.can_have_definition(new) and os.path.exists(os.path.join(mv, old, name + ".md")):
        return "starts"
    return None


def plan_move(profile: dict[str, Any], path: str, destination: str, new_name: str = "") -> tuple[str, MovePlan | None]:
    """`(OK, plan)` or `(error, None)`, the error being `NOTE_NOT_FOUND`, `NOTE_DENIED`, `NOTE_INVALID_NAME` (into itself,
    into its own subfolder, or where it already is, or a `new_name` that is not one plain name) or `NOTE_EXISTS`
    (something that is not a folder has its name there). With a `new_name`, the plan is for the folder going in under
    that name, as the user may choose when a folder of its name is already there."""
    status, source = resolve_folder(profile, path)
    if source is None:
        return status, None
    status, dest = resolve_folder(profile, destination, root=True)
    if dest is None:
        return status, None
    mv, _, src, old = source
    _, _, dst, into = dest
    if into == old or into.startswith(old + "/") or into == posixpath.dirname(old):
        return NOTE_INVALID_NAME, None
    name = new_name.strip().strip("\"'") or os.path.basename(src)
    if new_name and _new_name_error(name) is not None:
        return NOTE_INVALID_NAME, None
    target = os.path.join(dst, name)
    if os.path.lexists(target) and not os.path.isdir(target):
        return NOTE_EXISTS, None
    new = posixpath.join(into, name)
    clash = os.path.isdir(target)
    return OK, MovePlan(
        path=old,
        destination=into,
        new_path=new,
        clash=clash,
        note_clashes=clashes(src, target),
        reach=reach_changes(mv, old, new, notes_in(mv, src)),
        definition=_definition(mv, old, new),
    )
