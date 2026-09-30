"""One background job per persona at a time: what `recap_refresh`, `memory_refresh` and
`status_phrases` each do at launch or on a persona switch. `start` runs a function on a daemon
thread and returns at once, so the user can type meanwhile and quitting never waits on a model
call; `wait` lets a caller (a turn, `/memory`'s "Refresh now") join a run already in flight
instead of racing a second one; `is_running` is a point-in-time read for `cli/background_status`."""

import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)


class Runner:
    def __init__(self, thread_name: str, failure_label: str):
        self._thread_name = thread_name
        self._failure_label = failure_label
        self._running: dict[str, threading.Event] = {}  # the event is set when the run finishes
        self._lock = threading.Lock()

    def start(self, handle: str, work: Callable[[], object]) -> bool:
        """Run `work` for `handle` on a daemon thread. `False` when one is already running for it."""
        with self._lock:
            if handle in self._running:
                return False
            done = self._running[handle] = threading.Event()

        def run() -> None:
            try:
                work()
            except Exception as e:  # a background thread must not print a traceback into the terminal
                log.warning("%s for %s failed: %s", self._failure_label, handle, e)
            finally:
                with self._lock:
                    del self._running[handle]
                done.set()

        threading.Thread(target=run, name=f"{self._thread_name}-{handle}", daemon=True).start()
        return True

    def wait(self, handle: str, timeout: float) -> bool:
        """Give a run in flight for `handle` up to `timeout` seconds. `True` when none is running or it
        finished, `False` when it is still going."""
        with self._lock:
            done = self._running.get(handle)
        return True if done is None else done.wait(timeout)

    def is_running(self, handle: str) -> bool:
        with self._lock:
            return handle in self._running
