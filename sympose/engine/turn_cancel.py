"""Stopping a persona's reply in flight (docs/decisions/054). A per-persona registry behind a lock, shaped
like `turn_status`: the turn runs on one thread and the stop comes from another (a web request, the
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


_ACTIVE: set[str] = set()
_REQUESTED: set[str] = set()
_COMMITTED: set[str] = set()
_LOCK = threading.Lock()
_HERE = threading.local()


def begin(handle: str) -> None:
    with _LOCK:
        _ACTIVE.add(handle)
    _HERE.handle = handle


def finish(handle: str) -> None:
    with _LOCK:
        _ACTIVE.discard(handle)
        _REQUESTED.discard(handle)
        _COMMITTED.discard(handle)
    _HERE.handle = None


def request(handle: str) -> bool:
    """Ask the persona's running turn to stop. `False` when none is running or it is already past `commit`:
    its reply will be saved and shown."""
    with _LOCK:
        if handle not in _ACTIVE or handle in _COMMITTED:
            return False
        _REQUESTED.add(handle)
        return True


def check() -> None:
    """Raise `TurnCancelled` if the turn this thread is running was asked to stop; a no-op on any thread
    that is not running one."""
    handle = getattr(_HERE, "handle", None)
    with _LOCK:
        stopped = handle in _REQUESTED
    if stopped:
        raise TurnCancelled(handle)


def commit() -> None:
    """The last check of a turn, right before its reply is applied and saved: raises `TurnCancelled` if a
    stop was requested, otherwise marks the turn as past the point where one can still be accepted. Atomic
    with `request`, so no stop is both accepted and ignored."""
    handle = getattr(_HERE, "handle", None)
    with _LOCK:
        if handle in _REQUESTED:
            raise TurnCancelled(handle)
        if handle in _ACTIVE:
            _COMMITTED.add(handle)
