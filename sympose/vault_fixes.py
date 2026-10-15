"""The repairs `sympose vault --fix` offers (docs/decisions/084). A `Repair` says what would change, in words, and
`apply` makes the change through the layer that already owns it: the rename layer for a title, `retarget_link` for a
stale link, `folder_looks_write` for an icon. Nothing here asks; the walk in `vault_command` asks before each call."""

import os
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sympose import folder_looks_write, note_changes
from sympose.folder_definitions import definition_path
from sympose.vault_file_names import why_not_a_file_name
from sympose.vault_write_relink import retarget_link
from sympose.vault_write_rename import rename_note_to_path
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_INVALID_NAME, NOTE_NOT_FOUND

ICON, RENAME, RELINK = "icon", "rename", "relink"


@dataclass(frozen=True)
class Repair:
    kind: str
    show: tuple[str, ...]  # what would change, one line each
    path: str  # the icon's folder, or the note to rename or to rewrite a link in
    old: str = ""  # a relink: the link's target as written
    new: str = ""  # a rename: the new file name; a relink: the new target

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.kind, self.path, self.old, self.new)


_REFUSED = {
    NOTE_NOT_FOUND: "The note is not there any more, so nothing was changed.",
    NOTE_EXISTS: "A note with that name exists already, so nothing was changed.",
    NOTE_DENIED: "This persona may not write there, so nothing was changed.",
    NOTE_INVALID_NAME: "That name cannot be used in a link, so nothing was changed.",
}


def apply(profile: dict[str, Any], repair: Repair) -> tuple[bool, str]:
    """Makes the repair; returns whether it was made and a sentence to show."""
    if repair.kind == ICON:
        try:
            folder_looks_write.add_look(profile, repair.path)
        except folder_looks_write.Refused as reason:
            return False, str(reason)
        return True, f"Added to {definition_path(repair.path)}."
    if repair.kind == RENAME:
        result, new_path = rename_note_to_path(profile, repair.path, repair.new)
        if not new_path:
            return False, _REFUSED.get(result, result)
        note_changes.rename_everywhere(repair.path, new_path)  # a persona's pending changes follow the note (ADR 070)
        return True, result
    hits = retarget_link(profile, repair.path, repair.old, repair.new)
    if isinstance(hits, str):
        return False, _REFUSED.get(hits, hits)
    if not hits:
        return False, "The link is not in the note any more, so nothing was changed."
    return True, f"Changed {hits} link{'s' if hits != 1 else ''} in {repair.path}."


def icon_repair(folder: str, lines: list[str]) -> Repair:
    """Adding the icon's property lines to the folder's definition note; what is shown is made here from the lines."""
    return Repair(ICON, (f"Add to {definition_path(folder)}:", *(f"  {line}" for line in lines)), folder)


def title_rename(rel_path: str, title: str, stems: Counter[str]) -> Repair | None:
    """Renaming the note to its title, or `None` when that cannot be done without risk: the title is not safe as a file
    name and as a wikilink, another note already has the new name, or another note has the old one. In the last two a
    bare `[[link]]` names more than one note and a rename changes which one it reaches, so it is left to the person.
    `stems` counts every note's file name without `.md`, lower case."""
    if why_not_a_file_name(title):
        return None
    if stems[title.lower()] or stems[os.path.splitext(os.path.basename(rel_path))[0].lower()] > 1:
        return None
    return Repair(RENAME, (f"Rename {rel_path} to {title}.md (links to it are updated)",), rel_path, new=f"{title}.md")
