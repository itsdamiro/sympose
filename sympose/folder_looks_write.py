"""Writing to a folder definition note that exists: `rewrite_note`, the one read, change and save of it (the Folder
settings dialog, docs/decisions/087, and the vault health's icon fix both use it), and `add_look` (docs/decisions/064),
the one write the vault health makes.

`add_look` adds property lines (`folder_looks.offer`) to the note's frontmatter and changes no other line of the note: the
purpose, the `## Template` block and the user's own properties stay as they were. The save is the editor's own
(`overwrite_note`), so it also ends the file with one line break and, in a file that is mostly CRLF, gives every line
CRLF. It is called only on the user's yes, one folder at a time, and refuses when the note changed since it was read."""

from collections.abc import Callable
from typing import Any

from sympose import folder_definitions as defs
from sympose import folder_looks, vault_paths, vault_write
from sympose.vault_snapshot import get_vault_snapshot
from sympose.vault_write_concurrency import NOTE_CONFLICT, current_mtime
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND, NOTE_NOT_TEXT

_SAVED = "Saved note:"  # what `overwrite_note` starts its answer with when it wrote the file


def insert_properties(text: str, lines: list[str]) -> str | None:
    """`text` with the property `lines` added at the end of its frontmatter (a block is made when it has none), or
    `None` when it opens a frontmatter block it never closes, which is not for this function to repair.
    The lines added end in LF (the writer gives them CRLF when most of the file has it); no other line is touched."""
    added = "".join(f"{line}\n" for line in lines)
    opening = defs.FRONT_OPEN.match(text)
    if opening is None:
        return f"---\n{added}---\n{text}"
    closing = defs.FRONT_CLOSE.search(text, opening.end())
    if closing is None:
        return None
    return text[: closing.start()] + added + text[closing.start() :]


class Refused(ValueError):
    """A look or a definition that cannot be written, with the reason a person can read."""


class Missing(Refused):
    """The note or folder is not there for this persona."""


class Changed(Refused):
    """The note changed while it was being read, so nothing was written."""


class Failed(Refused):
    """The disk or the writer failed: not a refusal of what was asked, so a server answers it as its own fault."""


def rewrite_note(profile: dict[str, Any], note: str, change: Callable[[str], str]) -> bool:
    """Reads the existing `note`, writes back what `change` makes of its text, and says whether it wrote (not when
    `change` leaves the text as it was, so a save that changes nothing does not even normalise the line breaks).
    `change` raises `Refused` for a text it cannot handle. Raises `Refused` (`Missing`, `Changed` among them) with a
    reason when the note cannot be read or written, the persona may not write there, or the note changed meanwhile:
    the save is the editor's own, so it refuses on a newer mtime than the one read."""
    path = resolve_existing_note(profile, note)
    if path is None:
        raise Missing(f"`{note}` was not found.")
    mtime = current_mtime(path)
    try:
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
    except UnicodeDecodeError as reason:
        raise Refused(f"`{note}` is not plain UTF-8 text, so nothing was changed.") from reason
    except OSError as reason:
        raise Refused(f"`{note}` could not be read ({reason.strerror or reason}), so nothing was changed.") from reason
    updated = change(text)
    if updated == text:
        return False
    result = vault_write.overwrite_note(profile, note, updated, expected_mtime=mtime)
    if result.startswith(_SAVED):
        return True
    if result == NOTE_CONFLICT:
        raise Changed(f"`{note}` changed while it was being read, so nothing was written. Try again.")
    if result == NOTE_NOT_FOUND:
        raise Missing(f"`{note}` was not found.")
    if result == NOTE_DENIED:
        raise Refused("This persona may not write there, so nothing was written.")
    if result == NOTE_NOT_TEXT:
        raise Refused(f"`{note}` is not plain text, so nothing was changed.")
    raise Failed(f"`{note}` could not be written, so nothing was changed. {result.removeprefix('Error: ')}")


def add_look(profile: dict[str, Any], folder: str) -> list[str]:
    """Adds the built-in look to `folder`'s definition note and returns the property lines written. Raises
    `Refused` (with a reason) when there is nothing to add, the note cannot be read or written, the persona may not
    write there, or the note changed while it was being read."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        raise Refused("No vault is set up.")
    lines = folder_looks.offer(folder, get_vault_snapshot(*scope))
    if not lines:
        raise Refused(f"`{folder}` has no definition to add an icon to, or already has an icon.")
    note = defs.definition_path(folder)

    def change(text: str) -> str:
        updated = insert_properties(text, lines)
        if updated is None:
            raise Refused(f"`{note}` opens a properties block it does not close, so nothing was changed.")
        return updated

    rewrite_note(profile, note, change)
    return lines
