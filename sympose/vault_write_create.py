"""
Creating a brand-new note or empty folder — refuses rather than overwrites;
that's `vault_write.overwrite_note`'s job.
"""

import datetime
import json
import os
from typing import Any

from sympose import folder_definitions, generic_template, vault_paths
from sympose.vault_write import get_file_lock, write_atomic_text
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS


def dedicated_template_file(mv: str, folder: str) -> str | None:
    """The path of the `Templates/` file made for `folder` (its filename minus " template.md", matched against
    the folder's name exactly or as a singular/plural pair, whatever the case), or `None`. "Note template.md"
    is the general fallback, not a dedicated one."""
    tmpl_dir = os.path.join(mv, "Templates") if mv else ""
    if not folder or not os.path.isdir(tmpl_dir):
        return None
    folder = folder.lower()
    for fname in os.listdir(tmpl_dir):
        fname_lower = fname.lower()
        if fname_lower == "note template.md" or not fname_lower.endswith("template.md"):
            continue
        note_type = fname_lower[: -len("template.md")].strip()
        if folder in (note_type, note_type.rstrip("s"), note_type + "s"):
            return os.path.join(tmpl_dir, fname)
    return None


def read_text_file(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def get_template_for_path(mv: str, note_name: str, allowed_dirs: list[str] | None = None) -> str | None:
    """The template a new note starts from, in this order: the user's own Obsidian template made for the note's
    top-level folder (`dedicated_template_file`), else that folder's definition note's `## Template` block
    (docs/decisions/033), else "Note template.md" from `Templates/` for any folder. The folder is the first part
    of `note_name`; none for a note at the vault's root. A definition is read only from `allowed_dirs` when given.
    `None` when nothing applies."""
    if not mv:
        return None
    name = note_name.replace("\\", "/")
    folder = name.split("/", 1)[0] if "/" in name else ""
    if matched := dedicated_template_file(mv, folder):
        return read_text_file(matched)
    if from_definition := folder_definitions.template_for_folder(mv, folder, allowed_dirs):
        return from_definition
    general = os.path.join(mv, "Templates", "Note template.md")
    return read_text_file(general) if os.path.exists(general) else None


def _render_template(raw_tmpl: str, title_heading: str, now: datetime.datetime) -> str:
    """Substitutes the core-Obsidian-Templates placeholders this vault's
    templates use: `{{date}}`, `{{time}}`, `{{title}}`, `{{date:YYYY}}`. A quoted `"{{title}}"` is filled with the
    title encoded as JSON, so a colon or a quote in it cannot break the frontmatter (docs/decisions/038)."""
    return (
        raw_tmpl.replace('"{{title}}"', json.dumps(title_heading, ensure_ascii=False))
        .replace("{{date}}", now.strftime("%Y-%m-%d"))
        .replace("{{time}}", now.strftime("%H:%M"))
        .replace("{{title}}", title_heading)
        .replace("{{date:YYYY}}", now.strftime("%Y"))
    ).strip()


def _resolve_create_target(
    mv: str, allowed_dirs: list[str], primary_dir: str | None, clean_name: str
) -> str | None:
    """Absolute target path for a new note/folder named `clean_name` — under
    the master vault when it contains a path separator, otherwise the
    persona's primary folder. `None` if the resolved path falls outside
    every allowed directory."""
    base = mv if ("/" in clean_name or "\\" in clean_name) else (primary_dir or mv)
    target = os.path.normpath(os.path.join(base, clean_name))
    if not vault_paths.is_within_any(target, allowed_dirs):
        return None
    return target


def create_note(
    profile: dict[str, Any], note_name: str, content: str | None = None
) -> str:
    """Create a *new* vault note. `note_name` is a path relative to the
    vault — `Folder/Sub/Title` — and is placed under the master vault when
    it contains a separator, otherwise in the persona's primary folder.
    Refuses (`NOTE_EXISTS`) rather than overwriting an existing file —
    that's `overwrite_note`'s job. `NOTE_DENIED` for a path outside the
    sandbox. When `content` is omitted, the note starts from the template of
    its top-level folder, so the editor opens onto the same frontmatter a
    hand-created note there would get: the user's own `Templates/` file made
    for the folder, else the folder's definition note's `## Template` block
    (docs/decisions/033), else `Templates/Note template.md`, else the generic
    template's keys (docs/decisions/038)."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope
    primary_dir = vault_paths.get_primary_dir(profile)
    clean_name = note_name.strip().strip("\"'").lstrip("/\\")
    if not clean_name:
        return NOTE_DENIED
    if not clean_name.endswith(".md"):
        clean_name += ".md"

    target_file = _resolve_create_target(mv, allowed_dirs, primary_dir, clean_name)
    if target_file is None:
        return NOTE_DENIED

    with get_file_lock(target_file):
        if os.path.exists(target_file):
            return NOTE_EXISTS

        if content is None:
            title = os.path.splitext(os.path.basename(clean_name))[0].strip()  # the file name as given (#102)
            now = datetime.datetime.now().astimezone()
            raw_tmpl = get_template_for_path(mv, clean_name, allowed_dirs)
            if not (raw_tmpl and raw_tmpl.strip().startswith("---")):
                raw_tmpl = generic_template.text()  # the setting's keys: title, created, tags unless the user changed them
            content = f"{_render_template(raw_tmpl, title, now)}\n\n# {title}\n\n"

        rel_display = os.path.relpath(target_file, mv)
        try:
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            write_atomic_text(
                target_file, content if content.endswith("\n") else content + "\n"
            )
            return f"Created note: `{rel_display}`"
        except OSError as e:
            return f"Error: Failed to create note: {e}"


def create_folder(profile: dict[str, Any], folder_name: str) -> str:
    """Create a new *empty* folder under the vault, alongside `create_note`'s
    path resolution and sandbox rules: `folder_name` is relative to the
    vault and lands under the master vault when it contains a separator,
    otherwise in the persona's primary folder. `NOTE_EXISTS` when the path
    is already a file or directory, `NOTE_DENIED` outside the sandbox."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return NOTE_DENIED
    mv, allowed_dirs = scope
    primary_dir = vault_paths.get_primary_dir(profile)
    clean_name = folder_name.strip().strip("\"'").strip("/\\")
    if not clean_name:
        return NOTE_DENIED

    target_dir = _resolve_create_target(mv, allowed_dirs, primary_dir, clean_name)
    if target_dir is None:
        return NOTE_DENIED

    rel_display = os.path.relpath(target_dir, mv)
    with get_file_lock(target_dir):
        if os.path.exists(target_dir):
            return NOTE_EXISTS
        try:
            os.makedirs(target_dir)
            return f"Created folder: `{rel_display}`"
        except FileExistsError:
            return NOTE_EXISTS
        except OSError as e:
            return f"Error: Failed to create folder: {e}"
