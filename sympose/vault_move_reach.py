"""What a folder move does to what each persona may read (docs/decisions/074): a persona reads what is under the
folders her scope names, a move changes what is under them, and a scope that names the moved folder (or one inside
it) goes with it, so only the other personas' reach can change. Read only."""

import os
from dataclasses import dataclass

from sympose import profile as profiles
from sympose import vault_paths
from sympose.vault_defaults import NOTE_EXTENSIONS


@dataclass(frozen=True)
class Reach:
    handle: str
    name: str
    gains: int  # notes of the moved folder she could not read and now can
    loses: int  # notes of the moved folder she could read and now cannot


def notes_in(mv: str, src: str) -> list[str]:
    """The vault-relative paths of the notes under `src` at any depth, in no hidden folder."""
    found = []
    for folder, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        found += [os.path.relpath(os.path.join(folder, f), mv).replace(os.sep, "/") for f in files if f.endswith(NOTE_EXTENSIONS)]
    return found


def _follow(prefix: str, old: str, new: str) -> str:
    """A scope entry after the move: one that names the folder or one inside it goes with it."""
    return new + prefix[len(old):] if prefix == old or prefix.startswith(old + "/") else prefix


def _reads(path: str, prefixes: list[str]) -> bool:
    return "" in prefixes or any(path.startswith(p + "/") for p in prefixes)


def reach_changes(mv: str, old: str, new: str, notes: list[str]) -> tuple[Reach, ...]:
    """Every persona whose reach of `notes` (the notes under `old`, which becomes `new`) would change, by name."""
    changed = []
    for profile in profiles.list_profiles():
        before = vault_paths.scope_prefixes(mv, vault_paths.get_allowed_dirs(profile))
        after = [_follow(p, old, new) for p in before]
        gains = loses = 0
        for path in notes:
            was, now = _reads(path, before), _reads(new + path[len(old):], after)
            gains += now and not was
            loses += was and not now
        if gains or loses:
            changed.append(Reach(str(profile["handle"]), str(profile["name"]), gains, loses))
    return tuple(sorted(changed, key=lambda r: r.name.lower()))
