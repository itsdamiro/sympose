"""The web chat's locks (docs/decisions/044, 057): two messages in one conversation always run in order, and
two conversations of one persona wait for each other unless `parallel_replies` lets them run side by side. A
message that is waiting for its turn can be stopped, and is then not run."""

import threading

from sympose.engine import parallel

_LOCKS: dict[tuple[str, str | None], threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
# The messages waiting for a lock, by (persona, conversation): a stop sets their event, and they give up the wait.
_WAITING: dict[tuple[str, str | None], list[threading.Event]] = {}
_POLL_SECONDS = 0.2


def lock_for(handle: str, session_id: str | None, model: str) -> threading.Lock:
    """The conversation's own lock when replies may run side by side, else the persona's one lock."""
    key = (handle, session_id if session_id and parallel.side_by_side(model) else None)
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def acquire(lock: threading.Lock, handle: str, session_id: str | None) -> bool:
    """Wait for `lock`; `False` when a stop arrived while waiting (the message is then not run at all)."""
    stopped, key = threading.Event(), (handle, session_id)
    with _LOCKS_GUARD:
        _WAITING.setdefault(key, []).append(stopped)
    try:
        while not lock.acquire(timeout=_POLL_SECONDS):
            if stopped.is_set():
                return False
        if stopped.is_set():  # the stop came as the lock was freed: it was accepted, so the message is not run
            lock.release()
            return False
        return True
    finally:
        with _LOCKS_GUARD:
            _WAITING[key].remove(stopped)
            if not _WAITING[key]:
                del _WAITING[key]


def is_waiting(handle: str, session_id: str | None) -> bool:
    with _LOCKS_GUARD:
        return any(
            events for (h, s), events in _WAITING.items() if h == handle and (session_id is None or s == session_id)
        )


def stop_waiting(handle: str, session_id: str | None, unnamed: bool = False) -> bool:
    """Stop the persona's waiting messages (a conversation's, or with `unnamed` only those that named none)."""
    with _LOCKS_GUARD:
        events = [
            e for (h, s), found in _WAITING.items()
            if h == handle and (s is None if unnamed else session_id is None or s == session_id) for e in found
        ]
    for event in events:
        event.set()
    return bool(events)
