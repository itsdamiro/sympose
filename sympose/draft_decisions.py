"""What the server decided about a new-note draft, kept so the web app can follow (docs/decisions/093, "the web app follows a
draft decided in Slack").

A draft decided by `draft_accept` is gone from the persona's proposals; the editor that still has it open learns from this record
whether it became a note (and which) or was declined. It lives in the persona's `.slack` folder, out of the vault, as one small
JSON file of the latest decisions. Nothing here decides anything."""

import json
import os
import threading
from typing import Any

from sympose.atomic_write import write_atomic_text
from sympose.persona_files import slack_path

FILE = "decided.json"
KEPT = 50  # the latest decisions; an editor asks soon after, so older ones are no use
_lock = threading.Lock()


def _file(handle: str) -> str:
    return slack_path(handle, FILE)


def _load(handle: str) -> dict[str, dict[str, Any]]:
    try:
        with open(_file(handle), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def record(handle: str, draft_path: str, state: str, note_path: str | None) -> None:
    """Remember that the draft at `draft_path` was `accepted` (as the note at `note_path`) or `declined`."""
    with _lock:
        decided = _load(handle)
        decided.pop(draft_path, None)  # a repeat moves to the newest place
        decided[draft_path] = {"state": state, "path": note_path}
        file = _file(handle)
        os.makedirs(os.path.dirname(file), exist_ok=True)
        write_atomic_text(file, json.dumps(dict(list(decided.items())[-KEPT:]), ensure_ascii=False, indent=1) + "\n")


def read(handle: str, draft_path: str) -> dict[str, Any] | None:
    """`{state, path}` for a decided draft, `None` when nothing was recorded."""
    found = _load(handle).get(draft_path)
    return {"state": found.get("state"), "path": found.get("path")} if found else None
