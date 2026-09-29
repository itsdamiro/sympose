"""Persona memory (docs/decisions/041): three plain markdown files beside a persona's
soul and config, `profiles/<handle>/{profile,context,decisions}.md`.

    profile.md    stable facts about the user (working style, defaults, dislikes)
    context.md    what's active right now (current projects, blockers)
    decisions.md  a dated, append-only log of past decisions and their reasoning

`profile.md` and `context.md` are read whole, unmodified, the same posture as
`persona_files.load_soul`: they are meant to stay small by design, so they are treated
as fixed prompt content, never sacrificed to fit the context window (`prompt`,
docs/decisions/015), the same as the vault map. `decisions.md` is read as a list of
entries, oldest first as the file has them, since it grows over time and is trimmed
from its oldest end under budget pressure — the newest decisions are the ones most
likely to matter, and least likely to be safely forgotten.

Nothing here writes to any of the three files: that is docs/decisions/041's write
side (`memory_rewrite`), not built yet. A persona cannot describe itself as having
written to its own memory."""

import os
from dataclasses import dataclass, field

from sympose.persona_files import persona_dir, profiles_dir
from sympose.security import is_safe_path

PROFILE_FILENAME = "profile.md"
CONTEXT_FILENAME = "context.md"
DECISIONS_FILENAME = "decisions.md"


@dataclass(frozen=True)
class ForTurn:
    profile: str | None = None
    context: str | None = None
    decisions: list[str] = field(default_factory=list)
    # Something existed but the model may not receive it (docs/decisions/031's own
    # reporting rule: withheld only means there was something to withhold).
    withheld: bool = False


def _read(handle: str, filename: str) -> str | None:
    """A persona memory file's whole text, stripped, or `None` when it has none --
    missing, empty, an unsafe path, or unreadable (the same posture as `load_soul`)."""
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
    except OSError:
        return None


def profile(handle: str) -> str | None:
    return _read(handle, PROFILE_FILENAME)


def context(handle: str) -> str | None:
    return _read(handle, CONTEXT_FILENAME)


def decisions(handle: str) -> list[str]:
    """`decisions.md`'s entries, oldest first, exactly as the file has them (one per
    line; a line that is not a dated bullet is still kept, whole, as its own entry,
    so a user's own freeform note in the file is never silently dropped). `[]` when
    there is no file or it is empty."""
    text = _read(handle, DECISIONS_FILENAME)
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def for_turn(handle: str, allowed: bool) -> ForTurn:
    """What of a persona's memory a turn may use: everything read from disk, when
    `allowed` (the model may receive the `memory` cloud-share category, docs/decisions/031
    -- true for every local model); otherwise nothing, with `withheld` true only when
    there was something to withhold in the first place."""
    prof, ctx, dec = profile(handle), context(handle), decisions(handle)
    if allowed:
        return ForTurn(prof, ctx, dec, False)
    return ForTurn(None, None, [], bool(prof or ctx or dec))


def sent_names(profile_text: str | None, context_text: str | None, decisions_sent: list[str]) -> list[str]:
    """Which of the three files actually reached a turn, for the session record
    (docs/decisions/025 and 041) -- never their text. `decisions_sent` is what
    `budget.fit` actually kept, which can be fewer than a `ForTurn`'s own `decisions`."""
    return [
        name for name, present in
        (("profile", bool(profile_text)), ("context", bool(context_text)), ("decisions", bool(decisions_sent)))
        if present
    ]
