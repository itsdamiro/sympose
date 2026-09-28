"""Drafting and writing a folder's definition note (docs/decisions/033).

Two steps on purpose. `draft` reads the vault and returns the text that would be written, and writes nothing.
`write` creates the note from a draft. It does not ask: the caller (the vault health report, later the agent)
shows the draft and calls `write` only on the user's yes. A definition that exists is never replaced, because the
note is created through `create_note`, which refuses to overwrite."""

import os
from dataclasses import dataclass
from typing import Any

from sympose import folder_definitions as defs
from sympose import generic_template, vault_paths, vault_write_create
from sympose.vault_snapshot import get_vault_snapshot
from sympose.vault_write_status import NOTE_DENIED, NOTE_NOT_FOUND


MAX_LINES, MAX_LINE, MAX_PURPOSE = 40, 200, 500  # what a typed definition may hold (docs/decisions/038)


class Refused(ValueError):
    """A typed definition that cannot be written, with the reason a person can read."""


@dataclass(frozen=True)
class Draft:
    folder: str
    rel_path: str
    text: str
    template: list[str]  # the property lines, as they are in the text
    notes: int  # how many notes the template was counted from (0 when it is the user's own Templates file)
    from_templates_file: bool  # the template is the property lines of the user's `Templates/` file for the folder


def due(profile: dict[str, Any]) -> list[tuple[str, int]]:
    """`(folder, number of notes)` for the folders `profile` can see that are due a definition (`due_folders`),
    leaving out one whose definition exists on disk although the persona cannot see it (a persona scoped below the
    folder), so nothing is offered that `draft` would refuse."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return []
    vault, allowed = scope
    return [(f, n) for f, n in defs.due_folders(get_vault_snapshot(vault, allowed)) if not _defined(vault, f)]


def _defined(vault: str, folder: str) -> bool:
    return os.path.exists(os.path.join(vault, defs.definition_path(folder)))


def draft(profile: dict[str, Any], folder: str, purpose: str = "") -> Draft | None:
    """The definition `folder` would get, or `None` when it cannot have one (not the user's content, out of the
    persona's scope, no notes in it, or it already has one). See `draft_from`."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return None
    vault, allowed = scope
    return draft_from(vault, get_vault_snapshot(vault, allowed), folder, purpose)


def draft_from(vault: str, notes: list[dict[str, Any]], folder: str, purpose: str = "") -> Draft | None:
    """`draft` for a caller that already has the notes it may read (`notes`, of the vault at `vault`), so a
    request built from them and the template counted from them are the same read. The template is the property
    lines of the user's own `Templates/` file for the folder when there is one, so the two say the same thing, and
    otherwise what the folder's notes carry (`template_lines`). `purpose` is written as given; without one the
    note has none."""
    counted = defs.notes_in(notes, folder)
    if not defs.can_have_definition(folder) or not counted or _defined(vault, folder):
        return None  # asked on disk, not in the snapshot: a definition out of the persona's scope is still there
    file = vault_write_create.dedicated_template_file(vault, folder)
    own = generic_template.frontmatter_lines(vault_write_create.read_text_file(file) or "") if file else []
    lines = own or defs.template_lines(notes, folder)
    return Draft(folder, defs.definition_path(folder), defs.render(folder, lines, purpose), lines, 0 if own else len(counted), bool(own))


def write(profile: dict[str, Any], made: Draft) -> str:
    """Creates the note of `made`; the message `create_note` gives (`Created note: ...`, or that it exists or is
    not allowed). Only a definition of a top-level folder, at its own path, is written."""
    if not defs.can_have_definition(made.folder) or made.rel_path != defs.definition_path(made.folder):
        return NOTE_DENIED
    return vault_write_create.create_note(profile, made.rel_path, made.text)


def property_lines(template: list[str]) -> list[str]:
    """The non-blank lines of a typed template, trailing space dropped."""
    return [line.rstrip() for text in template for line in text.splitlines() if line.strip()]


def refusal(purpose: str, template: list[str]) -> str | None:
    """Why a typed definition cannot be written, or `None`. The limits keep the note readable by `read_template` and
    `read_purpose`: a line that starts a code fence would close the block early, a `---` line would close a note's
    frontmatter early, a purpose line that starts a heading would be read as the note's own structure. A definition
    with neither a purpose nor a property line says nothing, and would only stop the folder being offered one."""
    lines = property_lines(template)
    if not lines and not purpose.strip():
        return "Give a purpose or at least one property line."
    if len(lines) > MAX_LINES or any(len(line) > MAX_LINE for line in lines):
        return f"The template holds at most {MAX_LINES} lines of {MAX_LINE} characters."
    if any(line.strip().startswith(("```", "~~~")) for line in lines):
        return "A template line cannot start a code fence."
    if any(line.strip() == "---" for line in lines):
        return "Leave the `---` lines out: only the properties go here."
    if len(purpose.strip()) > MAX_PURPOSE:
        return f"The purpose holds at most {MAX_PURPOSE} characters."
    if any(line.strip().startswith("#") for line in purpose.splitlines()):
        return "A line of the purpose cannot start with `#` (it would read as a heading)."
    return None


def _reachable(scope: tuple[str, list[str]] | None, folder: str) -> bool:
    """Whether `folder` is a folder at the vault's root that the persona of `scope` may write to. A folder outside
    the persona's scope is answered like one that is not there, so the answer does not say which exist."""
    if scope is None:
        return False
    path = os.path.join(scope[0], folder)
    return os.path.isdir(path) and vault_paths.is_within_any(path, scope[1])


def definable(profile: dict[str, Any], folder: str) -> bool:
    """Whether `folder` can be given a definition now: a folder of the user's content at the vault's root, in the
    persona's scope, without one. The web app asks before it opens its setup step, so the step opens only when
    saving can work."""
    scope = vault_paths.resolve_sandbox(profile)
    return defs.can_have_definition(folder) and _reachable(scope, folder) and not _defined(scope[0], folder)


def write_own(profile: dict[str, Any], folder: str, purpose: str, template: list[str]) -> str:
    """Creates the definition of an existing top-level `folder` from what the user typed (docs/decisions/038): no
    notes are counted and no model is asked, the words are theirs. Raises `Refused` with the reason when the text
    (`refusal`) or the folder (not one that can have a definition) is not allowed; otherwise the message `write`
    gives, or `NOTE_NOT_FOUND` when the folder is not there for this persona."""
    if reason := refusal(purpose, template):
        raise Refused(reason)
    if not defs.can_have_definition(folder):
        raise Refused(f"`{folder}` is not a folder that can have a definition.")
    if not _reachable(vault_paths.resolve_sandbox(profile), folder):
        return NOTE_NOT_FOUND
    lines = property_lines(template)
    made = Draft(folder, defs.definition_path(folder), defs.render(folder, lines, purpose), lines, 0, False)
    return write(profile, made)
