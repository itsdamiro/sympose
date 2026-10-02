"""The persona's own earlier conversations, word for word (docs/decisions/056): what the user and the
persona said in them, cut into exchanges (one user message and the reply to it), and the few that match
the message being answered. The conversation in progress is never searched (it is already in the prompt)
and neither is anything in the Bin. A recap holds none of what the persona said; this is the only place
that answer lives, which is why what it says is shown as hers and possibly wrong."""

import math
import os
import re
from datetime import datetime
from typing import Any

from sympose import settings_store
from sympose.engine import reply_text, session
from sympose.engine.grounding_index import index_terms

SETTING = "past_chats"
OFF, AUTO, ASK = "off", "auto", "ask"
MODES = (OFF, AUTO, ASK)
EXCHANGES, SIDE_CHARS = 3, 600  # how many exchanges a turn attaches, and how much of each side of one
_MIN_SHARE = 0.5  # of the message's informative words that an exchange must contain
_SPECIFIC = 1  # a word found in no more conversations than this is evidence enough on its own
# The words that say a message is about an earlier conversation. They are no evidence of which exchange is
# meant, as "note" and "vault" are none of which note (`grounding_index.STOPWORDS`), so they are not searched;
# their presence is what lets one specific word of the message be enough (`find`).
_ASKING = frozenset(
    """last time times before earlier previous previously ago talk talked talking conversation conversations
    chat chats discuss discussed mention mentioned said told suggested suggest remember remind reminded session
    yesterday week""".split()
)
_WORD = re.compile(r"\w+")
# One parsed file kept until it changes: a turn would otherwise re-read every conversation there is.
_CACHE: dict[str, tuple[tuple[int, int], list[dict[str, Any]]]] = {}


def mode() -> str:
    """`off` (the default), `auto` or `ask`; anything else a hand-edited file holds is `off`."""
    value = settings_store.get(SETTING)
    return value if value in MODES else OFF


def _date(session_id: str) -> str:
    try:
        return datetime.strptime(session_id[:8], "%Y%m%d").date().isoformat()
    except ValueError:
        return session_id


def _exchanges(handle: str, session_id: str) -> list[dict[str, Any]]:
    try:
        path = session.session_path(handle, session_id)
        stat = os.stat(path)
    except (OSError, ValueError):
        return []
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(path)
    if cached and cached[0] == key:
        return cached[1]
    try:
        loaded = session.load_session(handle, session_id)
    except ValueError:  # a file that is not text (`session.load_session` only skips lines that are not JSON)
        loaded = None
    found = [
        {
            "session": session_id,
            "date": _date(session_id),
            "turn": number,
            "user": turn["user"],
            "assistant": reply_text.tidy(turn["assistant"]),
        }
        for number, turn in enumerate(loaded["turns"] if loaded else [], start=1)
    ]
    _CACHE[path] = (key, found)
    return found


def _terms(exchange: dict[str, Any]) -> set[str]:
    return set(index_terms(f"{exchange['user']} {exchange['assistant']}"))


def chooses_ask() -> bool:
    """Whether the user chose `ask`: the persona looks in earlier conversations with tools (`chat_tools`)."""
    return mode() == ASK


def find(handle: str, message: str, exclude: str | None = None, tools: bool = False) -> list[dict[str, Any]]:
    """What Sympose attaches for `message` before the reply: nothing when the setting is `off`, or `ask` with the
    tools in use this turn (`tools`: the persona looks for herself); otherwise the matching exchanges. `ask` on a
    model that cannot call tools runs as `auto`, so `tools` is false for it."""
    if mode() == OFF or (mode() == ASK and tools):
        return []
    return [{**x, "how": AUTO} for x in search(handle, message, exclude)]


def search(handle: str, message: str, exclude: str | None = None, about_the_past: bool | None = None) -> list[dict[str, Any]]:
    """The exchanges of the persona's other conversations that match `message`, in the order they were
    held, each cut to `SIDE_CHARS` a side; at most `EXCHANGES`, the best matches. Nothing when no exchange
    matches strongly enough: a wrong one derails a small model's reply, and none only costs a normal one
    (the rule the notes follow, docs/decisions/014). `about_the_past`: whether the message is known to be
    about an earlier conversation (a query the persona wrote for the search tool is); left out, the message's
    own words say."""
    wanted = [t for t in dict.fromkeys(index_terms(message)) if t not in _ASKING]
    if about_the_past is None:
        about_the_past = any(word in _ASKING for word in _WORD.findall(message.lower()))
    if not wanted:
        return []
    pool = [x for sid in session.session_ids(handle) if sid != exclude for x in _exchanges(handle, sid)]
    if not pool:
        return []
    terms = [_terms(x) for x in pool]
    spread = {w: sum(1 for t in terms if w in t) for w in wanted}  # exchanges holding each word, for the score
    # A conversation about a topic repeats its words in every exchange, so what marks a word as specific is
    # how few conversations it is in, not how few exchanges.
    in_conversations = {w: len({x["session"] for x, t in zip(pool, terms) if w in t}) for w in wanted}
    scored = []
    for exchange, own in zip(pool, terms):
        matched = [w for w in wanted if w in own]
        if not matched:
            continue
        enough = len(matched) >= max(2, math.ceil(_MIN_SHARE * len(wanted)))
        if not enough and not (about_the_past and any(in_conversations[w] <= _SPECIFIC for w in matched)):
            continue
        score = sum(math.log(1 + (len(pool) - spread[w] + 0.5) / (spread[w] + 0.5)) for w in matched)
        scored.append((score, exchange))
    best = sorted(scored, key=lambda pair: pair[0], reverse=True)[:EXCHANGES]
    chosen = sorted((x for _, x in best), key=lambda x: (x["session"], x["turn"]))
    return [{**x, "user": x["user"][:SIDE_CHARS], "assistant": x["assistant"][:SIDE_CHARS]} for x in chosen]


def conversation(handle: str, session_id: str, exclude: str | None = None) -> list[dict[str, Any]] | None:
    """Every exchange of one earlier conversation, or `None` when `session_id` is not one of the persona's own
    saved conversations (an id is never turned into a path: it must be in the list), is the conversation in
    progress, or is in the Bin (which the list never holds)."""
    if session_id == exclude or session_id not in session.session_ids(handle):
        return None
    return _exchanges(handle, session_id) or None
