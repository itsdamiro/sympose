"""Whether a persona is connected to Slack right now (docs/decisions/093): `sympose slack` touches one small file in the
persona's own folder, out of the vault, while the persona's connection is up. The web app and `sympose doctor` read it: a
file that was touched lately means connected; an old or missing one means not. A stopped or crashed command stops touching it,
so a stale file cannot say "connected" for long. Nothing is written to it that anyone reads: only its time matters."""

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event, Thread
from typing import Any

from sympose import persona_files

log = logging.getLogger(__name__)

FILE = "heartbeat"
EVERY_SECONDS = 20
FRESH_SECONDS = 3 * EVERY_SECONDS  # two missed beats are forgiven


def _path(handle: str) -> str:
    return os.path.join(persona_files.persona_dir(handle), persona_files.SLACK_FOLDER, FILE)


def beat(handle: str) -> None:
    """Say that `handle` is connected now. A failure is logged and not raised: a heartbeat must not take a connection down."""
    path = _path(handle)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Path(path).touch()  # makes it, or moves its time to now
    except OSError as e:
        log.warning("Couldn't write the Slack heartbeat of %s: %s", handle, e)


def stop(handle: str) -> None:
    """Say that `handle` is no longer connected (a clean stop does not leave the dot lit for a minute)."""
    try:
        os.remove(_path(handle))
    except FileNotFoundError:
        pass
    except OSError as e:
        log.warning("Couldn't remove the Slack heartbeat of %s: %s", handle, e)


def connected(handle: str, now: float | None = None) -> bool:
    """Whether `handle`'s file was touched within the last `FRESH_SECONDS`."""
    try:
        age = (time.time() if now is None else now) - os.path.getmtime(_path(handle))
    except (OSError, ValueError):
        return False
    return age <= FRESH_SECONDS


def keep(live: dict[str, Any]) -> Callable[[], None]:
    """Beat for each persona in `live` (handle to its Socket Mode handler) every `EVERY_SECONDS` while its connection is up, on
    a thread of its own. Returns the function that stops the thread and clears every file."""
    done = Event()

    def tick() -> None:
        for handle, handler in live.items():
            try:
                up = bool(handler.client.is_connected())  # a connection can drop and come back on its own
            except Exception:  # a handler that cannot say is not shown as connected
                log.exception("Couldn't tell whether the Slack connection of %s is up", handle)
                up = False
            if up:
                beat(handle)
            else:
                stop(handle)

    def loop() -> None:
        while not done.wait(EVERY_SECONDS):
            tick()

    tick()  # the dot is lit as soon as the connection is up, not a beat later
    thread = Thread(target=loop, name="slack-heartbeat", daemon=True)
    thread.start()

    def finish() -> None:
        done.set()
        thread.join(timeout=5)
        for handle in live:
            stop(handle)

    return finish
