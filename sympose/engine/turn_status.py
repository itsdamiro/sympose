"""The real, mechanical phase of a persona's in-flight turn -- searching the vault, reading a
note, or asking the model -- not a witty phrase (that's `status_phrases.py`) but literally what
`turn.py`/`lookup.py` are doing right now for *this* reply. `cli/background_status.py` reads it
so a wait for the actual reply shows what is actually happening instead of nothing (docs/decisions/043
covered the four other background jobs; the wait on the reply itself, the one thing most turns
actually spend their time on, was the gap this closes). A plain dict behind a lock, like
`recap_refresh._RUNNING` and its siblings: set from whichever thread is running the turn
(`turns.py` hands `run_turn` to its own executor), read from the CLI's polling tick on a
different thread. Cleared in a `finally` in `turn.run_turn` so a turn that raises never leaves a
stale phase showing forever."""

import threading

SEARCHING = "searching"
READING = "reading"
ASKING = "asking"

_PHASE: dict[str, str] = {}
_LOCK = threading.Lock()


def set_phase(handle: str | None, value: str | None) -> None:
    """`None` handle is a no-op: some callers (`lookup.converse`'s own unit tests) pass a persona
    dict with no `handle` at all, and tracking nothing is the right behavior there, not an error."""
    if not handle:
        return
    with _LOCK:
        if value is None:
            _PHASE.pop(handle, None)
        else:
            _PHASE[handle] = value


def phase(handle: str) -> str | None:
    with _LOCK:
        return _PHASE.get(handle)
