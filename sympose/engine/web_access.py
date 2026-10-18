"""Outside content comes in through the provider (docs/decisions/089). A link to a video in the user's message is
opened by the cloud model's maker, not by Sympose: it has no crawler and no page parser. This module decides, for one
turn, whether that happens: the knob `web_access`, the model, the link, and the user's approval of the `web` category.

`off` attaches nothing and `asked`, the default, attaches a video only when a link is in the message (or, for a
follow-up, in the conversation's latest message that had one, so the model can read the video again). `auto`, which
also lets the model search the web itself, comes with the search tools and is not offered yet.

A model in `WATCHERS` watches the video (`WATCH`); every other model, a local one included, is given its captions
(`CAPTIONS`, `engine/captions.py`), which also stand in when the watch is refused (`watch_call`)."""

import re
from dataclasses import dataclass
from typing import Any

from sympose import settings_store
from sympose.engine import sharing

SETTING = "web_access"
OFF, ASKED = "off", "asked"
MODES = (ASKED, OFF)
WATCH, CAPTIONS = "watch", "captions"
# The models that can watch a video through the provider's own agentic mode (ADR 089, Spike results); a model joins by
# measurement, like `lookup.MEASURED`.
WATCHERS = ("gemini/gemini-flash-latest",)
MAX_LINKS = 3  # videos watched for one message
# watch, youtu.be, shorts, live and embed addresses; the video's id is always 11 characters.
_LINK = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?(?:[^\s#]*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])"
)
_WATCH_ADDRESS = "https://www.youtube.com/watch?v={id}"


@dataclass(frozen=True)
class Watch:
    """What this turn does with the links in it: `links` are the addresses the model is to watch, and `withheld`
    says there was a link in the message and the user has not allowed it (the persona is told, to tell them)."""

    links: tuple[str, ...] = ()
    withheld: bool = False
    route: str = WATCH  # `WATCH`: the maker's model looks at the video; `CAPTIONS`: it is given the words


def mode() -> str:
    """`off` when the user chose it; anything else, unset or malformed, is the default, `asked`."""
    return OFF if settings_store.get(SETTING) == OFF else ASKED


def links_in(text: str) -> tuple[str, ...]:
    """The videos `text` links to, as one watch address each, in the order written and without repeats."""
    found = dict.fromkeys(_WATCH_ADDRESS.format(id=video) for video in _LINK.findall(text or ""))
    return tuple(found)[:MAX_LINKS]


def resolve(model: str, user_message: str, history: list[dict[str, Any]]) -> Watch:
    """The turn's `Watch`. The message's own links win; with none, the latest earlier message of the user's that had
    some is kept in front of the model (a question about the video after the first). That carried link is only
    ever watched when allowed, and never reported as withheld, so a conversation that began before the user
    allowed it does not nag on every later turn."""
    if mode() == OFF:
        return Watch()
    route = WATCH if model in WATCHERS else CAPTIONS
    allowed = sharing.WEB in sharing.allowed(model)
    own = links_in(user_message)
    if own:
        return Watch(own, route=route) if allowed else Watch(withheld=True)
    if not allowed:
        return Watch()
    for earlier in reversed(history):
        if earlier.get("role") == "user" and isinstance(earlier.get("content"), str) and (found := links_in(earlier["content"])):
            return Watch(found, route=route)
    return Watch()
