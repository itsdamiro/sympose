"""Which conversation a Slack thread or direct message is (docs/decisions/093), and the deliveries already seen.

The map is one small JSON file in the persona's own folder, `<persona>/.slack/sessions.json`: out of the vault, and not
listed among the persona's files. The conversation itself is an ordinary one in the persona's `sessions/`."""

import json
import logging
import os
import threading
from collections import OrderedDict

from sympose import persona_files
from sympose.atomic_write import write_atomic_text
from sympose.engine import session

log = logging.getLogger(__name__)

FILE = "sessions.json"
_GUARD = threading.Lock()


def _path(handle: str) -> str:
    return os.path.join(persona_files.persona_dir(handle), persona_files.SLACK_FOLDER, FILE)


def _read(handle: str) -> dict[str, str]:
    try:
        with open(_path(handle), encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning("Couldn't read the Slack conversations of %s: %s", handle, e)
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(raw, dict) else {}


def _write(handle: str, found: dict[str, str]) -> None:
    path = _path(handle)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_atomic_text(path, json.dumps(found, indent=1) + "\n")
    except OSError as e:
        log.warning("Couldn't save the Slack conversations of %s: %s", handle, e)


def session_for(handle: str, key: str) -> str:
    """The conversation `key` has, opened and remembered the first time it is asked for."""
    with _GUARD:
        found = _read(handle)
        if key not in found:
            found[key] = session.new_session_id()
            _write(handle, found)
        return found[key]


def start_over(handle: str, key: str) -> str:
    """Another conversation for `key`, from now on (`/new` in a direct message); the old one stays in the list."""
    with _GUARD:
        found = _read(handle)
        found[key] = session.new_session_id()
        _write(handle, found)
        return found[key]


class Seen:
    """The deliveries a connection has handled. Slack sends an event again when it was not acknowledged in time, and a
    second answer to one message is a second turn that costs and may file a second draft."""

    def __init__(self, limit: int = 500):
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._limit = limit
        self._guard = threading.Lock()

    def first_time(self, event_id: str | None) -> bool:
        """`True` once for each id; a delivery with no id is always taken as new."""
        if event_id is None:
            return True
        with self._guard:
            if event_id in self._ids:
                return False
            self._ids[event_id] = None
            while len(self._ids) > self._limit:
                self._ids.popitem(last=False)
            return True
