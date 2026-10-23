"""The persona offering a folder's definition while she talks (docs/decisions/033, 087): `propose_folder_definition(folder,
purpose, say)`. The template is counted from the folder's real notes by `folder_definitions_write.draft`, never written by the
model, so nothing in it can be invented (the zero-hallucination rule); only the purpose sentence is hers, and she leaves it out
when the note titles do not show one. The draft is filed as a new note at `<Folder>/<Folder>.md`, and the file exists only when
the user accepts it. What is told back to her holds counts and no property or value, so nothing of the notes' content goes to a
cloud model through this call."""

from typing import Any

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import draft_limit, note_changes, vault_paths

_NOT_FOLDER = "{folder!r} is not a folder of the user's notes that can have a definition, so nothing was proposed."
_NO_NOTES = "{folder} holds no notes yet, so there is nothing to count a template from. Nothing was proposed."
_EXISTS = "{folder} already has a definition note, so nothing was proposed; the user can change it in Folder settings."
_NO_PROFILE = "No vault is open, so nothing was proposed."


def propose(handle: str, profile: dict[str, Any] | None, folder: str, purpose: str, say: str, filing: draft_limit.Filing | None = None) -> tuple[bool, str]:
    """`(filed, what happened)`: the definition of `folder` as a draft the user accepts or declines."""
    scope = vault_paths.resolve_sandbox(profile) if profile is not None else None
    if scope is None:
        return False, _NO_PROFILE
    vault = scope[0]
    name = defs.folder_named(vault, folder.strip().strip("/\\"))
    if not defs.can_have_definition(name) or not write_defs.reachable(scope, name):
        return False, _NOT_FOLDER.format(folder=folder.strip())  # the same words for a folder out of her scope: the answer does not say which exist
    if write_defs.defined(vault, name):
        return False, _EXISTS.format(folder=name)
    if (why := write_defs.purpose_refusal(purpose)) is not None:
        return False, why
    made = write_defs.draft(profile, name, " ".join(purpose.split()))
    if made is None:
        return False, _NO_NOTES.format(folder=name)
    try:
        note_changes.propose_create(handle, note_changes.new_note_path(), made.text, say=say, title=name, folder=name, filing=filing)
    except note_changes.CannotAnchor as error:
        return False, str(error)
    counted = "the property lines of the user's own Templates file" if made.from_templates_file else f"counted from {made.notes} of its notes"
    written = "with your purpose sentence" if purpose.strip() else "with no purpose sentence"
    return True, f"Proposed {made.rel_path}, {written}; its template has {len(made.template)} property lines, {counted}. The user decides."
