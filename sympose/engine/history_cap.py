"""An optional cap on the earlier turns a prompt carries (docs/decisions/055, update of 2026-10-02): `history_tokens`.
Unset, nothing changes; set, the oldest turns are dropped until the rest is within it."""

from sympose import settings_store
from sympose.engine import budget

SETTING = "history_tokens"
MIN_TOKENS = 500


def chosen() -> int | None:
    """The cap the user set, or `None` (no cap) when it is missing or not a whole number of at least `MIN_TOKENS`."""
    value = settings_store.get(SETTING)
    ok = isinstance(value, int) and not isinstance(value, bool) and value >= MIN_TOKENS
    return value if ok else None


def apply(history: list[dict[str, str]], model: str) -> tuple[list[dict[str, str]], int]:
    """`(history within the cap, how many turns were dropped from its old end)`. `history` is `user, assistant` pairs,
    oldest first; the newest pair always stays."""
    cap = chosen()
    if cap is None:
        return history, 0
    kept, dropped = list(history), 0
    while len(kept) > 2 and budget.count_tokens(kept, model) > cap:
        del kept[:2]
        dropped += 1
    return kept, dropped
