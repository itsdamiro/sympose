"""What a turn gives back (docs/decisions/006 and the ones each field cites), split out of `turn.py`
to hold the file-size cap."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TurnResult:
    reply: str
    session_id: str
    grounding: list[dict[str, Any]] = field(default_factory=list)
    # Time to first token in ms and the model that produced it
    # (docs/decisions/013); `None` when a caller builds a result by hand.
    ttft_ms: int | None = None
    model: str | None = None
    # Turns left out of what the model was sent because they did not fit its
    # window (docs/decisions/015); the session record keeps them all.
    history_dropped: int = 0
    # The search query a follow-up was rewritten into when that rewrite is what
    # grounded the reply (docs/decisions/017); `None` when the message itself was.
    searched: str | None = None
    # The conversation's size as the next turn starts from it, and the prompt
    # budget it is measured against (docs/decisions/018); `None` when the
    # model's window is unknown.
    context_used: int | None = None
    context_limit: int | None = None
    # The reply stopped at the reply limit, so it may end mid-sentence.
    truncated: bool = False
    # The session file was written; `False` when it could not be, so this reply is not part of the
    # record and later messages will not remember it (a warning is in the log as well).
    saved: bool = True
    # For a model that is not local (docs/decisions/031): the categories of the user's vault that were
    # sent to it this turn, and the ones held back because the user has not allowed them. Both are
    # empty for a local model, where nothing leaves the machine.
    cloud: list[str] = field(default_factory=list)
    withheld: list[str] = field(default_factory=list)
    # Exactly what was persisted alongside this turn (docs/decisions/025) — `None` only when a
    # caller builds a result by hand. A display command reads this back rather than rebuilding it
    # from `grounding`/`searched`/etc., so it can never drift from what the session record says (#26).
    sent: dict[str, Any] | None = None
    # The tools the persona used this turn when it looked up notes itself (docs/decisions/040): one
    # entry per call, a count and never text. Empty in `auto`, and in `ask` when nothing was looked up.
    lookups: list[dict[str, Any]] = field(default_factory=list)
