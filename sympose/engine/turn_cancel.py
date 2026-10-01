"""Stopping a persona's reply in flight (docs/decisions/054). A registry behind a lock, keyed by persona and
conversation (docs/decisions/057) and shaped like `turn_status`: the turn runs on one thread and the stop comes from another (a web request, the
terminal's UI thread). `begin`/`finish` bracket a turn in `turn.run_turn` and name, in a thread-local, the
persona whose turn the current thread is running, so `check` -- called between the chunks of a model's
stream and between a turn's steps -- needs no parameter and a background job that also calls the model
(recaps, memory, phrases) never sees a stop meant for a reply. `request` is a no-op while no turn is
running, so a late click cannot cancel the next turn, and it is a promise: when it returns `True` nothing of
the turn is saved. A turn past `commit` (the last check, right before it is applied and saved) refuses it
instead, so the caller knows the reply is coming."""

import threading


class TurnCancelled(Exception):
    """The reply in flight was stopped. Deliberately not an `EngineModelError`: it is not a failure to show."""


_Key = tuple[str, str | None]
_ACTIVE: set[_Key] = set()
_REQUESTED: set[_Key] = set()
_COMMITTED: set[_Key] = set()
_LOCK = threading.Lock()
_HERE = threading.local()


def begin(handle: str, session_id: str | None = None) -> None:
    key = (handle, session_id)
    with _LOCK:
        _ACTIVE.add(key)
    _HERE.key = key


def finish(handle: str, session_id: str | None = None) -> None:
    key = (handle, session_id)
    with _LOCK:
        _ACTIVE.discard(key)
        _REQUESTED.discard(key)
        _COMMITTED.discard(key)
    _HERE.key = None


def request(handle: str, session_id: str | None = None) -> bool:
    """Ask the persona's running turn to stop (with `session_id`, the one of that conversation; without,
    every turn the persona is running). `False` when none is running or all are already past `commit`: the
    reply will be saved and shown."""
    with _LOCK:
        keys = [
            key for key in _ACTIVE
            if key[0] == handle and (session_id is None or key[1] == session_id) and key not in _COMMITTED
        ]
        _REQUESTED.update(keys)
        return bool(keys)


def check() -> None:
    """Raise `TurnCancelled` if the turn this thread is running was asked to stop; a no-op on any thread
    that is not running one."""
    key = getattr(_HERE, "key", None)
    with _LOCK:
        stopped = key in _REQUESTED
    if stopped:
        raise TurnCancelled(key[0])


def commit() -> None:
    """The last check of a turn, right before its reply is applied and saved: raises `TurnCancelled` if a
    stop was requested, otherwise marks the turn as past the point where one can still be accepted. Atomic
    with `request`, so no stop is both accepted and ignored."""
    key = getattr(_HERE, "key", None)
    with _LOCK:
        if key in _REQUESTED:
            raise TurnCancelled(key[0])
        if key in _ACTIVE:
            _COMMITTED.add(key)
