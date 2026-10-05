"""The checks behind `sympose vault --health` (docs/decisions/034): a read-only look at the notes.

Each check is one function from what a persona can read to a list of findings, and a later check is one more entry
in `CHECKS`. Nothing here writes, renames or deletes a note, and no check calls a model."""

import os
import re
import shlex
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import folder_looks
from sympose import vault_graph, vault_health_moves, vault_paths
from sympose.vault_defaults import ATTACHMENT_EXTENSIONS, IGNORE_FOLDERS, NOTE_EXTENSIONS
from sympose.vault_snapshot import get_vault_snapshot

_EMPTY_FRONTMATTER = re.compile(r"---\s*---")
_UNSAFE_IN_A_NAME = re.compile(r'[\\/:*?"<>|]')
_LONGEST_NAME = 250  # bytes a file name may have, less its `.md`
_SHOWN_TITLE = 60
OBSIDIAN_OWN = frozenset({".canvas", ".base"})  # file types Obsidian makes itself, so not clutter


@dataclass(frozen=True)
class Finding:
    folder: str  # the note's top-level folder, "" at the vault root
    note: str  # the note's path in the vault (the folder's name for an offer)
    message: str
    fix: tuple[str, ...] = ()  # the property lines the offered fix would add to `note`; empty when there is no fix


@dataclass(frozen=True)
class Scope:
    profile: dict[str, Any]
    notes: list[dict[str, Any]]  # every note the persona can read (`get_vault_snapshot`)
    vault: str  # the vault's root
    allowed: list[str]  # the folders the persona may read, as paths


@dataclass(frozen=True)
class Check:
    heading: str
    run: Callable[[Scope], list[Finding]]
    problem: bool = True  # False: an offer or an observation, not a fault, so it never changes the exit code
    of_notes: bool = True  # False: the findings are files, so a folder's line counts them and not "of N notes"
    per_folder: bool = True  # False: a finding is already about a whole folder, so it needs no folder-count header


def folder_of(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ""


def check_due_folders(scope: Scope) -> list[Finding]:
    return [
        Finding(folder, folder, f"{folder}: {count} notes and no definition; `sympose vault --draft {shlex.quote(folder)}` drafts one")
        for folder, count in write_defs.due(scope.profile)
    ]


def check_definition_icons(scope: Scope) -> list[Finding]:
    """A definition note with no `icon` for a folder the web app has always drawn with one (ADR 064). An offer, not
    a fault, and the one check with a fix: the property lines are in the finding, and nothing is written until the
    person says yes to that folder."""
    found = []
    for folder in sorted(folder_looks.BUILT_IN):
        lines = folder_looks.offer(folder, scope.notes)
        if lines:
            colours = " and its colours" if len(lines) > 1 else ""
            found.append(Finding(folder, defs.definition_path(folder), f"has no icon; can add {lines[0]}{colours}", tuple(lines)))
    return found


def check_empty_notes(scope: Scope) -> list[Finding]:
    """A note with no text and no properties, so nothing but its file name. A note of only properties or only a title
    is not empty: ADR 030 reads those."""
    found = []
    for note in scope.notes:
        text = (note.get("full_content") or "").strip()
        if not text or _EMPTY_FRONTMATTER.fullmatch(text):
            found.append(Finding(folder_of(note["rel_path"]), note["rel_path"], "has no text and no properties"))
    return found


def check_broken_links(scope: Scope) -> list[Finding]:
    """A `[[link]]` to no note: what the Knowledge Nebula draws as a ghost, so the two never disagree."""
    graph = vault_graph.get_vault_graph(scope.profile)
    missing = {n["id"] for n in graph["nodes"] if not n.get("exists", True)}
    found, seen = [], set()
    for link in graph["links"]:
        pair = (link["source"], link["target"].lower())  # `[[Gone]]` and `[[gone]]` are one link, as in Obsidian
        if link["target"] in missing and pair not in seen:
            seen.add(pair)
            found.append(Finding(folder_of(link["source"]), link["source"], f"links to [[{link['target']}]], which is not a note"))
    return found


def _declared_title(meta: dict[str, Any]) -> str:
    """The `title` (else `name`) property as text, the same choice the graph makes; `""` when neither says anything
    usable (missing, blank or not a plain value). Checked independently, as `folder_purpose._title` does: an
    unusable `title` (a list, say) must not block a usable `name` from being read."""
    for raw in (meta.get("title"), meta.get("name")):
        if isinstance(raw, (str, int, float, date)) and not isinstance(raw, bool):
            text = str(raw).strip()
            if text:
                return text
    return ""


def _same_title(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def check_other_files(scope: Scope) -> list[Finding]:
    """A file that is neither a note nor an attachment Obsidian opens nor one of its own types (`.txt`, `.markdown`,
    a note ending `.MD`, a file with no extension): clutter, by the vault owner's word. Hidden files and the folders
    the snapshot skips are left out, as the snapshot leaves them out. Found by a file walk, since the snapshot only
    holds notes."""
    skipped = {d.lower() for d in IGNORE_FOLDERS}
    found: dict[str, Finding] = {}
    for base in scope.allowed:
        for root, folders, files in os.walk(base):
            folders[:] = [d for d in folders if d.lower() not in skipped and not d.startswith(".")]
            for name in files:
                extension = os.path.splitext(name)[1].lower()
                if name.startswith(".") or name.endswith(NOTE_EXTENSIONS) or extension in ATTACHMENT_EXTENSIONS | OBSIDIAN_OWN:
                    continue
                rel = os.path.relpath(os.path.join(root, name), scope.vault).replace(os.sep, "/")
                found[rel] = Finding(folder_of(rel), rel, f"is not a note (Sympose reads only .md files) or an attachment ({extension or 'no extension'})")
    return list(found.values())


def check_titles(scope: Scope) -> list[Finding]:
    """A declared title that is not the file name (the title wins, ADR 034), ignoring case and spacing. A title that
    cannot be a file name is said so, since renaming cannot make them one."""
    found = []
    for note in scope.notes:
        title = _declared_title(note.get("meta") or {})
        if not title or _same_title(title, os.path.splitext(note["file_name"])[0]):
            continue
        shown = title if len(title) <= _SHOWN_TITLE else title[: _SHOWN_TITLE - 1] + "…"
        message = f'the title "{shown}" is not the file name'
        unsafe = _UNSAFE_IN_A_NAME.search(title)
        if unsafe:
            message += f" and cannot be one: a file name cannot hold {unsafe.group()!r}"
        elif len(title.encode("utf-8")) > _LONGEST_NAME:
            message += " and cannot be one: it is too long for a file name"
        found.append(Finding(folder_of(note["rel_path"]), note["rel_path"], message))
    return found


def check_stale_definitions(scope: Scope) -> list[Finding]:
    return [Finding(folder_of(rel), rel, message) for rel, message in vault_health_moves.stale_definitions(scope.notes)]


def check_numbered_twins(scope: Scope) -> list[Finding]:
    return [Finding(folder_of(rel), rel, message) for rel, message in vault_health_moves.numbered_twins(scope.notes)]


CHECKS: list[Check] = [
    Check("Folders due a definition", check_due_folders, problem=False, per_folder=False),
    Check("Folder definitions with no icon", check_definition_icons, problem=False, of_notes=False),
    Check("Empty notes", check_empty_notes),
    Check("Links to no note", check_broken_links),
    Check("Titles that are not the file name", check_titles),
    Check("Other files (clutter)", check_other_files, problem=False, of_notes=False),
    Check("Notes named after a folder that is not top-level", check_stale_definitions, problem=False),
    Check("Numbered twins of a note", check_numbered_twins, problem=False),
]


def scan(profile: dict[str, Any]) -> tuple[Scope, list[tuple[Check, list[Finding]]]] | None:
    """Every check run over what `profile` can read, or `None` when there is no vault."""
    sandbox = vault_paths.resolve_sandbox(profile)
    if sandbox is None:
        return None
    scope = Scope(profile, get_vault_snapshot(*sandbox), sandbox[0], sandbox[1])
    return scope, [(check, sorted(check.run(scope), key=lambda f: (f.note.lower(), f.message))) for check in CHECKS]
