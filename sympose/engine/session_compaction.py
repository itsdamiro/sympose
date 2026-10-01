"""The compaction record of a session file (docs/decisions/055): one extra line saying that the first
`through` turns are, from now on, stood for by short notes when the history is sent. The turns stay in
the file word for word; only what is sent changes. A later record covers everything an earlier one did,
so the last one in the file is the one in force."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from sympose.engine.session_paths import session_path
from sympose.engine.session_records import append_text

TYPE = "compaction"
log = logging.getLogger(__name__)


def parse(record: dict[str, Any]) -> dict[str, Any] | None:
    """The record as the session carries it, or `None` for one that cannot be used (a hand-edited or
    damaged line is skipped, like a damaged turn)."""
    through, text = record.get("through"), record.get("text")
    if isinstance(through, bool) or not isinstance(through, int) or through < 1:
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    return {"through": through, "text": text.strip(), "timestamp": record.get("timestamp"), "model": record.get("model")}


def covered(session: dict[str, Any] | None) -> int:
    """How many of the session's first turns the notes stand for (never more than there are)."""
    found = (session or {}).get("compaction")
    return min(found["through"], len(session["turns"])) if found else 0


def notes(session: dict[str, Any] | None) -> str | None:
    """The notes in force, or `None` when there are none (or no turn is left for them to stand for)."""
    return session["compaction"]["text"] if covered(session) else None


def append(handle: str, session_id: str, through: int, text: str, model: str) -> bool:
    """Add a record to an existing session's file; `False` (and a warning) when it could not be written.
    Nothing already in the file is touched."""
    record = {
        "type": TYPE, "timestamp": datetime.now(timezone.utc).isoformat(), "through": through, "text": text, "model": model,
    }
    path = session_path(handle, session_id)
    try:
        if not os.path.exists(path):  # a session that was never used has no file, and this must not make one
            return False
        append_text(path, json.dumps(record) + "\n")
    except OSError as e:
        log.warning("Failed to write a compaction to session %s: %s", path, e)
        return False
    return True
