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

`decisions.md` is the one file written to in-turn, since appending a line is already safe
on any model (the worst a weak model can do is add one bad line, as recoverable as any
other line in a plain-text file the user already owns): `append_decision` adds a dated
line and rolls the previous content into `decisions.md.bak`. Whether a turn may do this at
all is `remember_enabled`, a plain user setting, not inferred from what a model happens to
be capable of -- trusting a model with even a safe, append-only write is the user's own
call, which depends on their machine or which cloud model they run, not something Sympose
decides for them. `remember_mode` then picks the mechanism: a `remember` tool
(`memory_tools`) on a model that can call tools, or an inline `<!-- remember: ... -->`
marker in its reply on one that can't, so a local-only user is not second-class here
either (docs/decisions/041). `context.md` and `profile.md` have no write path yet: that is
`memory_rewrite`, still unbuilt."""

import datetime
import os
import threading
from dataclasses import dataclass, field

from sympose import settings_store
from sympose.atomic_write import write_atomic_text
from sympose.persona_files import persona_dir, profiles_dir
from sympose.security import is_safe_path

PROFILE_FILENAME = "profile.md"
CONTEXT_FILENAME = "context.md"
DECISIONS_FILENAME = "decisions.md"

REMEMBER_SETTING = "memory_remember"
TOOL, MARKER = "tool", "marker"

# `append_decision` is read-modify-write on a plain file; one lock for every persona, not one per
# handle, since a `remember` write is rare (one model-flagged or user-typed line at a time) and the
# whole read-write-backup is quick -- the contention a per-handle lock would avoid never happens in
# practice, and one lock is what `tool_support.py`'s own strike tracker already uses for the same reason.
_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class ForTurn:
    profile: str | None = None
    context: str | None = None
    decisions: list[str] = field(default_factory=list)
    # Something existed but the model may not receive it (docs/decisions/031's own
    # reporting rule: withheld only means there was something to withhold).
    withheld: bool = False


def read_file(handle: str, filename: str) -> str | None:
    """A persona memory file's whole text, stripped, or `None` when it has none --
    missing, empty, an unsafe path, or unreadable (the same posture as `load_soul`).
    Public: `memory_write.py` reads the same three files' `.pending`/`.bak` siblings
    through it too, rather than duplicating this."""
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
    except (OSError, ValueError):  # ValueError: a file saved in some other encoding
        return None


def profile(handle: str) -> str | None:
    return read_file(handle, PROFILE_FILENAME)


def context(handle: str) -> str | None:
    return read_file(handle, CONTEXT_FILENAME)


def decisions(handle: str) -> list[str]:
    """`decisions.md`'s entries, oldest first, exactly as the file has them (one per
    line; a line that is not a dated bullet is still kept, whole, as its own entry,
    so a user's own freeform note in the file is never silently dropped). `[]` when
    there is no file or it is empty."""
    text = read_file(handle, DECISIONS_FILENAME)
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


def remember_enabled() -> bool:
    """Whether a persona may write anything to `decisions.md` at all this turn -- a user's own
    setting, off until turned on. It being safe on any model (append-only, recoverable) is not
    reason enough to default it on: trusting a model with it is the user's own call, which
    depends on their machine or which cloud model they run, not something Sympose decides for
    them by default. Never inferred from a model's measured tool-calling capability, which only
    ever decides *how* (`remember_mode`), not *if*."""
    return settings_store.flag(REMEMBER_SETTING, False)


def remember_mode(can_call_tools: bool) -> str | None:
    """`TOOL`, `MARKER`, or `None` when the setting is off -- the mechanism a turn uses to let
    the persona add to `decisions.md` (docs/decisions/041)."""
    if not remember_enabled():
        return None
    return TOOL if can_call_tools else MARKER


def append_decision(handle: str, text: str) -> bool:
    """Adds one dated line to `decisions.md`, after rolling its current content into
    `decisions.md.bak` (docs/decisions/041's rolling one-generation backup for every write to
    any of the three files). `text` is collapsed to one line -- a decision is one line, not a
    place for a model to paste a multi-paragraph reply. `False` on a blank `text`, an unsafe
    handle, or a write that fails; never raises, the same posture as the rest of this module."""
    text = " ".join(text.split())
    if not text:
        return False
    try:
        directory = persona_dir(handle)
    except ValueError:
        return False
    path = os.path.join(directory, DECISIONS_FILENAME)
    if not is_safe_path(path, profiles_dir()):
        return False
    line = f"- {datetime.date.today().isoformat()}: {text}"
    with _WRITE_LOCK:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                current = f.read()
        except FileNotFoundError:
            current = ""
        except (OSError, ValueError):
            return False
        updated = f"{current.rstrip()}\n{line}\n" if current.strip() else f"{line}\n"
        try:
            os.makedirs(directory, exist_ok=True)
            if current:
                write_atomic_text(f"{path}.bak", current)
            write_atomic_text(path, updated)
        except OSError:
            return False
    return True
