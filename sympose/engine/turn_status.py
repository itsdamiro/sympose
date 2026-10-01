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

# Keyed by persona and conversation (docs/decisions/057), so two conversations of one persona replying at
# once each have their own phase. A turn names its conversation with `bind`; a caller that does not (or
# asks only about a persona) sees the persona's phase, as before.
_PHASE: dict[tuple[str, str | None], str] = {}
_LOCK = threading.Lock()
_HERE = threading.local()


def bind(handle: str, session_id: str | None) -> None:
    """The turn this thread is running, so `set_phase` called from deep inside it (the lookup tools) needs
    no conversation parameter. `unbind` ends it; a thread with none binds nothing."""
    _HERE.turn = (handle, session_id)


def unbind() -> None:
    _HERE.turn = None


def _key(handle: str) -> tuple[str, str | None]:
    bound = getattr(_HERE, "turn", None)
    return bound if bound and bound[0] == handle else (handle, None)


def set_phase(handle: str | None, value: str | None) -> None:
    """`None` handle is a no-op: some callers (`lookup.converse`'s own unit tests) pass a persona
    dict with no `handle` at all, and tracking nothing is the right behavior there, not an error."""
    if not handle:
        return
    key = _key(handle)
    with _LOCK:
        if value is None:
            _PHASE.pop(key, None)
        else:
            _PHASE[key] = value


def phase(handle: str, session_id: str | None = None) -> str | None:
    """The phase of `session_id`'s reply, or without it of the persona's: the oldest of its replies in flight."""
    with _LOCK:
        if session_id is not None:
            return _PHASE.get((handle, session_id))
        return next((value for (owner, _), value in _PHASE.items() if owner == handle), None)
