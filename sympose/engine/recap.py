"""Recaps of earlier conversations (docs/decisions/023): a short note per finished
session, written by the persona's own model from the session log (`recap_refresh`)
and read back here at the start of the next conversation, so a persona can pick up
where the last one left off. The session log stays the record and is never rewritten;
a recap is derived from it, kept beside it as a plain markdown file the user can read
and correct.

    profiles/<handle>/recaps/<session id>.md
        <!-- turns: 3 -->
        Working on the Atlas database choice; leaning towards SQLite ...

The header says how many turns the recap covers, so a session that was resumed later
gets a fresh one. A file that has lost its header was edited by the user, is theirs,
and is left as it is; a header with no text means "looked at, nothing to carry over"."""

import os
import re
import tempfile
from datetime import datetime

from sympose import settings_store
from sympose.engine import session

SETTING = "session_recaps"
# How many recaps a turn reads and how much of each, however long the user made the file (docs/decisions/056);
# the user's own numbers when they are in range, else these.
COUNT_SETTING, CHARS_SETTING = "recap_count", "recap_chars"
DEFAULT_COUNT, DEFAULT_CHARS = 2, 800
COUNT_RANGE, CHARS_RANGE = (1, 10), (200, 2000)
_HEADER = re.compile(r"^<!--\s*turns:\s*(\d+)\s*-->\s*$")


def _whole(key: str, bounds: tuple[int, int], default: int) -> int:
    value = settings_store.get(key)
    ok = isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1]
    return value if ok else default


def read_count() -> int:
    """How many recaps a turn reads (`recap_count`, 1 to 10, default 2)."""
    return _whole(COUNT_SETTING, COUNT_RANGE, DEFAULT_COUNT)


def read_chars() -> int:
    """How much of each recap is read (`recap_chars`, 200 to 2000, default 800)."""
    return _whole(CHARS_SETTING, CHARS_RANGE, DEFAULT_CHARS)


def enabled() -> bool:
    """Only an explicit `false` turns recaps off: none are then written or read."""
    return settings_store.flag(SETTING, True)


def path(handle: str, session_id: str) -> str:
    return os.path.join(session.recaps_dir(handle), f"{session_id}.md")


def _parse(text: str) -> tuple[int | None, str]:
    """`(turns, recap text)`; `turns` is `None` when the header line is missing."""
    first, _, rest = text.partition("\n")
    match = _HEADER.match(first.strip())
    if match:
        return int(match.group(1)), rest.strip()
    return None, text.strip()


def load(handle: str, session_id: str) -> tuple[int | None, str] | None:
    """The recap file's `(turns, text)`, or `None` when there is none it can read
    (a file the user saved in some other encoding is skipped, not a failed turn)."""
    try:
        with open(path(handle, session_id), encoding="utf-8") as f:
            return _parse(f.read())
    except (OSError, ValueError):
        return None


def write(handle: str, session_id: str, turns: int, text: str) -> None:
    """Save a recap whole or not at all: an interrupted write must not leave an empty,
    headerless file, which would read as the user's own and never be rewritten. The
    temporary file has its own name, so two processes refreshing at once do not share it."""
    target = path(handle, session_id)
    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    header = f"<!-- turns: {turns} -->\n"
    fd, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{header}{text}\n" if text else header)
        os.replace(temporary, target)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _date(session_id: str) -> str:
    """The day the session began, as `YYYY-MM-DD`, from the start of its id."""
    try:
        return datetime.strptime(session_id[:8], "%Y%m%d").date().isoformat()
    except ValueError:
        return session_id


def _has_turns(handle: str, session_id: str) -> bool:
    loaded = session.load_session(handle, session_id)
    return bool(loaded and loaded["turns"])


def latest(handle: str, exclude: str | None = None, count: int | None = None) -> list[dict[str, str | bool]]:
    """The newest recaps with something in them, newest first, as `{"session", "date",
    "text", "last"}` (`session` is the id of the session it recaps); `last` is true for the recap of the most recent earlier session of all,
    and false when that session had nothing to carry over or no recap yet (so an older
    one is not presented as the last conversation). `exclude` is the session being
    run, whose own turns are already in the chat. `count` defaults to what a turn's own
    prompt reads (`READ_COUNT`); a caller synthesizing across more history than one
    turn needs -- `memory_refresh`'s context.md/profile.md rewrite, docs/decisions/041 --
    passes a larger one."""
    if not enabled():
        return []
    count = read_count() if count is None else count
    chars = read_chars()
    found: list[dict[str, str | bool]] = []
    try:
        names = sorted(os.listdir(session.recaps_dir(handle)), reverse=True)
    except OSError:
        return []
    # A session opened and left blank (`session.start_session`) is not a conversation: it must not stand in
    # for the last one.
    newest = next((sid for sid in session.session_ids(handle) if sid != exclude and _has_turns(handle, sid)), None)
    for name in names:
        session_id = name.removesuffix(".md")
        if session_id == exclude:
            continue
        loaded = load(handle, session_id)
        if loaded and loaded[1]:
            found.append(
                {
                    "session": session_id,
                    "date": _date(session_id),
                    "text": loaded[1][:chars],
                    "last": session_id == newest,
                }
            )
        if len(found) == count:
            break
    return found
