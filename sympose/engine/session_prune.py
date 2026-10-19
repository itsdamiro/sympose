"""Conversations opened and never used (docs/decisions/057, the amendment of 2026-10-20): the web chat's "New conversation"
writes a file with only its meta line so a refresh does not lose it (`session.start_session`), and a blank one left behind
is never listed (`session_manage.list_sessions`) but stays on disk. Each launch deletes those that are a day old. Silent on
purpose: there is nothing for the user to act on, and a file with no turn holds nothing they wrote, so it does not go to the
Bin (a Bin of blank rows would be noise). The newest session is always kept: it may be the one just opened."""

import json
import logging
import os
import time

from sympose.engine import session, turn_cancel, turn_status

log = logging.getLogger(__name__)

MIN_AGE_SECONDS = 24 * 3600  # a session touched more recently may still be open in another window


def _holds_only_its_meta(path: str) -> bool:
    """Every non-blank line is a meta record; anything else, or a line that cannot be read, means leave the file alone.
    Stops at the first line that is not a meta record, so a long conversation costs one line, not a read of the file."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not (isinstance(r := json.loads(line), dict) and r.get("type") == "meta"):
                    return False
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def prune_empty(handle: str, now: float | None = None) -> int:
    """Delete the persona's sessions with no turn that are at least a day old, except the newest session. Returns how many."""
    now = time.time() if now is None else now
    removed = 0
    for session_id in session.session_ids(handle)[1:]:  # newest first; the newest is kept
        try:
            path = session.session_path(handle, session_id)
            if now - os.path.getmtime(path) < MIN_AGE_SECONDS or not _holds_only_its_meta(path):
                continue
            if turn_cancel.running(handle, session_id) or turn_status.phase(handle, session_id) is not None:
                continue
            os.remove(path)
        except (OSError, ValueError) as e:
            log.warning("Could not delete the empty session %s: %s", session_id, e)
            continue
        removed += 1
    return removed
