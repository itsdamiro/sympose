"""Where a persona's files live and how its soul is read (docs/decisions/011, 012):
`<profiles_dir>/<handle>/` holds `persona.yaml`, `soul.md`, and later memory,
expertise and sessions. Split out of `profile.py`, which keeps the roster,
the default persona and the fail-closed lookup (docs/decisions/009)."""

import logging
import os

from sympose.security import is_safe_path

log = logging.getLogger(__name__)

PERSONA_FILENAME = "persona.yaml"
# The user's own choices over the shipped file (docs/decisions/046): untracked, written by the app.
PERSONA_LOCAL_FILENAME = "persona.local.yaml"
SOUL_FILENAME = "soul.md"
# The user's own soul, saved from the web editor: untracked, read first, so the shipped file is never written
# (docs/decisions/061, 046).
SOUL_LOCAL_FILENAME = "soul.local.md"


def profiles_dir() -> str:
    return os.getenv("SYMPOSE_PROFILES_DIR") or os.path.join(os.getcwd(), "profiles")


def persona_dir(handle: str) -> str:
    """`<profiles_dir>/<handle>/` — everything belonging to one persona
    (config, and later soul/memory/expertise/sessions) lives here
    (docs/decisions/011). Raises `ValueError` unless `handle` is a single
    plain path component: `is_safe_path` alone only proves a path stays
    inside `profiles/`, which `.` (the directory itself) and `a/b` (a
    nested path) both do without naming one persona's own directory."""
    handle = handle.lower()
    if handle in ("", ".", "..") or os.path.basename(handle) != handle:
        raise ValueError(f"Not a valid persona handle: {handle!r}")
    return os.path.join(profiles_dir(), handle)


def _read_soul(handle: str, filename: str) -> str | None:
    try:
        path = os.path.join(persona_dir(handle), filename)
    except ValueError:
        return None
    if not is_safe_path(path, profiles_dir()):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as e:
        log.warning("Couldn't read %s, using the default soul: %s", path, e)
        return None


def load_soul(handle: str) -> str | None:
    """The persona's soul text (docs/decisions/012): the user's own `soul.local.md` when it has text, else the
    shipped `soul.md` (docs/decisions/061), or `None` when it has neither — missing, empty, unsafe path, or
    unreadable — so the caller can fall back to a generic soul. Read on demand rather than inside `get_profile`,
    which runs on every vault route that has no use for it; an edit to either file takes effect on the next call."""
    return _read_soul(handle, SOUL_LOCAL_FILENAME) or _read_soul(handle, SOUL_FILENAME)


def _found_as_lower(base: str, name: str) -> bool:
    """Whether the roster finds `name`'s persona under its lower-case name: always on a file system that
    ignores case, only when a folder of that name exists on one that keeps case."""
    return os.path.isfile(os.path.join(base, name.lower(), PERSONA_FILENAME))


def missed_folders() -> list[str]:
    """Persona folders (holding a `persona.yaml`) whose name is not lower case and which the roster cannot
    find, so the persona is missing (docs/decisions/029, issue #72). Empty on a file system that ignores case."""
    base = profiles_dir()
    if not os.path.isdir(base):
        return []
    return sorted(
        name
        for name in os.listdir(base)
        if name != name.lower() and os.path.isfile(os.path.join(base, name, PERSONA_FILENAME)) and not _found_as_lower(base, name)
    )


def missed_notice() -> str | None:
    """The start-up line for `missed_folders`, or `None` when nothing is missed."""
    missed = missed_folders()
    if not missed:
        return None
    names = ", ".join(repr(name) for name in missed)
    plural = len(missed) > 1
    return (
        f"Persona folder{'s' if plural else ''} {names} {'are' if plural else 'is'} not listed: "
        f"{'their names' if plural else 'its name'} must be lower case; run `sympose doctor --fix` to rename "
        f"{'them' if plural else 'it'}."
    )
