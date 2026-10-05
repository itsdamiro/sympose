"""The two halves of merging a folder into one of the same name (docs/decisions/074, slice 3): giving what is in both
a new name so nothing is overwritten, and moving the folder's files across one at a time."""

import os
import posixpath
from typing import Any

from sympose.vault_write import get_file_locks
from sympose.vault_write_rename import rename_note_to_path


def free_name(name: str, is_dir: bool, *folders: str) -> str:
    """`Anna.md` -> `Anna (2).md`, the first number nothing in any of `folders` has."""
    stem, ext = (name, "") if is_dir else os.path.splitext(name)
    n = 2
    while any(os.path.lexists(os.path.join(f, f"{stem} ({n}){ext}")) for f in folders):
        n += 1
    return f"{stem} ({n}){ext}"


def rename_clashes(
    profile: dict[str, Any], mv: str, src: str, target: str, clashing: tuple[str, ...]
) -> tuple[list[tuple[str, str]], str | None]:
    """Rename what the incoming folder holds that is also at `target` (paths relative to the folder) to the first free
    numbered name, a note through the note rename so the links that named it follow. Returns the notes' `(old, new)`
    vault-relative paths and an error message when one could not be renamed (what was renamed stays renamed)."""
    notes: list[tuple[str, str]] = []
    for rel in clashing:
        folder, name = posixpath.split(rel)
        here = os.path.join(src, *folder.split("/")) if folder else src
        there = os.path.join(target, *folder.split("/")) if folder else target
        is_dir = os.path.isdir(os.path.join(here, name))
        new = free_name(name, is_dir, here, there)
        old_rel = os.path.relpath(os.path.join(here, name), mv).replace(os.sep, "/")
        new_rel = posixpath.join(posixpath.dirname(old_rel), new)
        if name.endswith(".md") and not is_dir:
            result, _ = rename_note_to_path(profile, old_rel, new)
            if not result.startswith("Renamed"):
                return notes, f"Error: could not rename `{old_rel}` before merging: {result}"
            notes.append((old_rel, new_rel))
            continue
        old_abs, new_abs = os.path.join(mv, old_rel), os.path.join(mv, new_rel)
        with get_file_locks(old_abs, new_abs):
            try:
                os.rename(old_abs, new_abs)
            except OSError as error:
                return notes, f"Error: could not rename `{old_rel}` before merging: {error}"
    return notes, None


def merge_files(src: str, target: str) -> int:
    """Move every file under `src` to the same place under `target`, making folders as needed, then remove the folders
    that are empty. Hidden names stay behind (nothing hidden is moved or overwritten), and so does anything that
    appeared at its place meanwhile. Returns how many files were left behind, which keep `src` in place."""
    left = 0
    for folder, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        rel = os.path.relpath(folder, src)
        there = target if rel == "." else os.path.join(target, rel)
        os.makedirs(there, exist_ok=True)
        for name in sorted(files):
            old, new = os.path.join(folder, name), os.path.join(there, name)
            if name.startswith(".") or os.path.lexists(new):
                left += 1
                continue
            with get_file_locks(old, new):
                try:
                    os.rename(old, new)
                except OSError:
                    left += 1
    for folder, _dirs, _files in os.walk(src, topdown=False):
        try:
            os.rmdir(folder)  # only when empty
        except OSError:
            pass
    return left
