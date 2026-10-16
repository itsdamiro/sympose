"""
Finding one image file of the vault for the web app to show (docs/decisions/085). Read-only, and only for a
file the persona can read: a path from the vault's root, then from the open note's folder, then (for a name
with no folder in it) a file of that name anywhere in what the persona can read, the shortest path first.
An image is never listed anywhere: this is the one door to it.
"""

import os
from typing import Any

from sympose import vault_paths

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class ImageTooLarge(Exception):
    pass


def media_type(path: str) -> str | None:
    return IMAGE_TYPES.get(os.path.splitext(path)[1].lower())


def _served(mv: str, allowed_dirs: list[str], path: str) -> bool:
    """A file inside the persona's folders, with no part of its path from the vault's root that starts with a
    dot (`.obsidian`, `.trash`, `..`). A hidden or `Attachments` folder is not refused. The caller has checked
    that the name is an image type."""
    if not os.path.isfile(path):
        return False
    rel = os.path.relpath(path, mv)
    if rel.startswith("..") or any(part.startswith(".") for part in rel.split(os.sep)):
        return False
    return vault_paths.is_within_any(path, allowed_dirs)


def _by_name(mv: str, allowed_dirs: list[str], name: str) -> str | None:
    found: set[str] = set()
    wanted = name.lower()  # Obsidian finds a file by name whatever the case
    for base in allowed_dirs:
        for folder, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            found.update(os.path.join(folder, f) for f in files if f.lower() == wanted)
    ranked = sorted(((os.path.relpath(p, mv), p) for p in found), key=lambda item: (len(item[0]), item[0]))
    return next((p for _, p in ranked if _served(mv, allowed_dirs, p)), None)


def resolve_image(profile: dict[str, Any], ref: str, from_path: str = "") -> str | None:
    """The absolute path of the image `ref` names, or `None`. Raises `ImageTooLarge` for one over the limit."""
    scope = vault_paths.resolve_sandbox(profile)
    clean = ref.strip().strip("\"'").replace("\\", "/")
    if scope is None or media_type(clean) is None or os.path.isabs(clean):
        return None
    mv, allowed_dirs = scope
    note_folder = os.path.dirname(from_path.strip().replace("\\", "/"))
    found = next(
        (c for c in (os.path.join(mv, clean), os.path.join(mv, note_folder, clean)) if _served(mv, allowed_dirs, c)),
        None,
    )
    if found is None and "/" not in clean:
        found = _by_name(mv, allowed_dirs, clean)
    if found is None:
        return None
    try:
        too_large = os.path.getsize(found) > MAX_IMAGE_BYTES
    except OSError:  # moved or deleted since it was found
        return None
    if too_large:
        raise ImageTooLarge(clean)
    return found
