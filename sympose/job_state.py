"""What a job has done so far, and the lock that keeps one job from running twice (docs/decisions/091).

One small JSON file per job in `<persona>/jobs/.state/`, untracked and out of the vault: when it last ran, how it ended,
how many runs today, how many failures in a row, and whether it paused itself. A run that failed still counts as a run, so
a job that fails is not tried again every five minutes. Times are the user's own clock (naive local), as in `job_schedule`."""

import contextlib
import json
import logging
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sympose import jobs
from sympose.atomic_write import write_atomic_text

log = logging.getLogger(__name__)

STATE_FOLDER = ".state"
OK, FAILED = "ok", "failed"
PAUSE_AFTER = 3  # failures in a row
_IN_THIS_PROCESS: set[str] = set()
_GUARD = threading.Lock()


@dataclass(frozen=True)
class State:
    last_run: datetime | None = None
    outcome: str | None = None
    detail: str = ""  # what went wrong, or what was held back from a cloud model
    session_id: str | None = None
    day: str | None = None  # the date `runs_today` counts
    runs_today: int = 0
    failures: int = 0  # in a row
    paused: bool = False
    held: list[str] = field(default_factory=list)

    def runs_on(self, now: datetime) -> int:
        return self.runs_today if self.day == now.date().isoformat() else 0


def _folder(handle: str) -> str | None:
    folder = jobs.jobs_dir(handle)
    return None if folder is None else os.path.join(folder, STATE_FOLDER)


def _file(handle: str, name: str, suffix: str = ".json") -> str | None:
    folder = _folder(handle)
    return folder and jobs.valid_name(name) and os.path.join(folder, name + suffix) or None


def read(handle: str, name: str) -> State:
    """A job's record; an empty one when there is none or it cannot be read (the job is then treated as new)."""
    path = _file(handle, name)
    try:
        with open(path or "", encoding="utf-8") as f:
            raw = json.load(f)
        last = raw.get("last_run")
        held = raw.get("held")
        return State(
            last_run=datetime.fromisoformat(last) if isinstance(last, str) else None,
            outcome=raw["outcome"] if raw.get("outcome") in (OK, FAILED) else None,
            detail=str(raw.get("detail") or ""),
            session_id=raw["session_id"] if isinstance(raw.get("session_id"), str) else None,
            day=raw["day"] if isinstance(raw.get("day"), str) else None,
            runs_today=raw["runs_today"] if isinstance(raw.get("runs_today"), int) else 0,
            failures=raw["failures"] if isinstance(raw.get("failures"), int) else 0,
            paused=raw.get("paused") is True,
            held=[x for x in held if isinstance(x, str)] if isinstance(held, list) else [],
        )
    except FileNotFoundError:
        return State()
    except (OSError, ValueError, AttributeError, TypeError) as e:
        log.warning("Couldn't read the record of job %s: %s", name, e)
        return State()


def _write(handle: str, name: str, values: dict[str, Any]) -> None:
    path = _file(handle, name)
    if path is None:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_atomic_text(path, json.dumps(values, indent=1) + "\n")
    except OSError as e:
        log.warning("Couldn't save the record of job %s: %s", name, e)


def record(handle: str, name: str, now: datetime, session_id: str | None, error: str | None = None, held: list[str] | None = None) -> State:
    """Note that the job ran at `now`. An error counts a failure and, at `PAUSE_AFTER` in a row, pauses the job; a run
    without one clears both. A pause is lifted by a run that works (a manual `sympose run`) or by `resume`."""
    before = read(handle, name)
    failures = before.failures + 1 if error else 0
    after = State(
        last_run=now, outcome=FAILED if error else OK, detail=error or ", ".join(held or []), session_id=session_id,
        day=now.date().isoformat(), runs_today=before.runs_on(now) + 1, failures=failures, paused=failures >= PAUSE_AFTER, held=held or [],
    )
    _write(handle, name, {**after.__dict__, "last_run": now.isoformat(timespec="seconds")})
    return after


def resume(handle: str, name: str) -> None:
    """Take the pause off a job; its failures start again from none."""
    before = read(handle, name)
    if before.paused or before.failures:
        _write(handle, name, {**before.__dict__, "last_run": before.last_run.isoformat(timespec="seconds") if before.last_run else None, "paused": False, "failures": 0})


@contextlib.contextmanager
def claim(handle: str, name: str) -> Iterator[bool]:
    """`True` while this caller alone is running the job; `False` when another process (the OS scheduler, the open app) or
    another thread has it. The file lock is the operating system's, so it is released if the holder dies."""
    key = f"{handle}/{name}"
    with _GUARD:
        taken = key in _IN_THIS_PROCESS
        if not taken:
            _IN_THIS_PROCESS.add(key)
    if taken:
        yield False
        return
    handle_fd = None
    try:
        handle_fd = _lock_file(handle, name)
        yield handle_fd is not False
    finally:
        if handle_fd not in (None, False):
            handle_fd.close()  # closing releases the lock
        with _GUARD:
            _IN_THIS_PROCESS.discard(key)


def _lock_file(handle: str, name: str):
    """The open, locked file; `False` when another process holds it; `None` where file locks are not available (the
    in-process guard alone then stands)."""
    try:
        import fcntl
    except ImportError:
        return None
    path = _file(handle, name, ".lock")
    if path is None:
        return None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        f = open(path, "a")
    except OSError as e:
        log.warning("Couldn't open the lock of job %s: %s", name, e)
        return None
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    return f
