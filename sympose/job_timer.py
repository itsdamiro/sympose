"""The open web app's half of scheduled runs (docs/decisions/091, slice 4): a thread that asks `job_run.run_due` what is due,
once when the app starts (a time missed while the Mac slept or the app was closed is caught up) and every few minutes
after. The operating system's entry (`job_launchd`) calls the same function, and `job_state.claim` keeps either from
running a job the other has."""

import logging
import threading

from sympose import job_run

log = logging.getLogger(__name__)

EVERY_SECONDS = 300


def _loop(stop: threading.Event, every: float) -> None:
    while not stop.is_set():
        try:
            for outcome in job_run.run_due():
                log.info("Job %s: %s %s", outcome.job, outcome.status, outcome.detail)
        except Exception:  # the timer must outlive whatever one pass hit
            log.exception("Looking for due jobs failed")
        stop.wait(every)


def start(every: float = EVERY_SECONDS) -> threading.Event:
    """Start the timer on a thread that ends with the process. Setting the returned event stops it."""
    stop = threading.Event()
    threading.Thread(target=_loop, args=(stop, every), name="sympose-jobs", daemon=True).start()
    return stop
