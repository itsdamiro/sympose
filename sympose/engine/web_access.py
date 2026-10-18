"""Outside content comes in through the provider (docs/decisions/089). A link in the user's message, a video or a
page, is opened by the cloud model's maker, not by Sympose: it has no crawler and no page parser. This module decides,
for one turn, whether that happens: the knob `web_access`, the model, the links, and the user's approval of the `web`
category.

`off` attaches nothing and `asked`, the default, attaches a video or a page only when a link is in the message (or, for
a follow-up, in the conversation's latest message that had one, so the model can read it again). `auto` also lets the
model search the web itself, on every turn.

A model in `WATCHERS` watches the video (`WATCH`) and reads pages and searches through Google's own tools; every other
model, a local one included, is given a video's captions (`CAPTIONS`, `engine/captions.py`), which also stand in when
the watch is refused (`watch_call`), and has no way to read a page."""

import ipaddress
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sympose import settings_store
from sympose.engine import sharing

SETTING = "web_access"
OFF, ASKED, AUTO = "off", "asked", "auto"
MODES = (ASKED, AUTO, OFF)
WATCH, CAPTIONS = "watch", "captions"
# The models that can watch a video through the provider's own agentic mode (ADR 089, Spike results); a model joins by
# measurement, like `lookup.MEASURED`.
WATCHERS = ("gemini/gemini-flash-latest",)
MAX_LINKS = 3  # videos watched, and pages read, for one message
CARRY_TURNS = 5  # the later messages of a conversation a link is carried into, so a question about it can be read from it
SEARCH_TOOL, PAGE_TOOL = "googleSearch", "urlContext"  # Google's own tools, named as its request names them
# watch, youtu.be, shorts, live and embed addresses; the video's id is always 11 characters.
_LINK = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?(?:[^\s#]*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])"
)
_WATCH_ADDRESS = "https://www.youtube.com/watch?v={id}"
_ADDRESS = re.compile(r"https?://[^\s<>\"`]+")
_SENTENCE_END = ".,;:!?'\u2019\u201d"


@dataclass(frozen=True)
class Watch:
    """What this turn does with the links in it: `links` are the addresses the model is to watch, and `withheld`
    says there was a link in the message and the user has not allowed it (the persona is told, to tell them)."""

    links: tuple[str, ...] = ()
    withheld: bool = False
    route: str = WATCH  # `WATCH`: the maker's model looks at the video; `CAPTIONS`: it is given the words
    pages: tuple[str, ...] = ()  # the pages the maker's model may read
    search: bool = False  # the maker's model may search the web (`auto`)
    asked: tuple[str, ...] = ()  # the pages the message itself links to, not one carried from an earlier message

    @property
    def outside(self) -> bool:
        """Whether anything from outside comes in on this turn: a video, a page or a search."""
        return bool(self.links or self.pages or self.search)

    @property
    def attached(self) -> bool:
        """Whether the message brings outside content in with it, a video or a page, as against a search the model may or may not run."""
        return bool(self.links or self.pages)

    @property
    def server_tools(self) -> tuple[str, ...]:
        """Google's tools this turn's request carries: reading pages, and with `search` the search itself."""
        return (*((SEARCH_TOOL,) if self.search else ()), *((PAGE_TOOL,) if self.search or self.pages else ()))

    @property
    def direct(self) -> bool:
        """Whether the request goes straight to Google: a video it watches, or tools it runs."""
        return bool(self.server_tools) or (bool(self.links) and self.route == WATCH)


def mode() -> str:
    """What the user chose; unset or malformed is the default, `asked`."""
    chosen = settings_store.get(SETTING)
    return chosen if chosen in MODES else ASKED


def links_in(text: str) -> tuple[str, ...]:
    """The videos `text` links to, as one watch address each, in the order written and without repeats."""
    found = dict.fromkeys(_WATCH_ADDRESS.format(id=video) for video in _LINK.findall(text or ""))
    return tuple(found)[:MAX_LINKS]


def _readable(address: str) -> bool:
    """Whether Google could be asked to read `address`: a public web page. A YouTube address is a video's (or not
    readable), and a name that only this machine or this network knows is not sent anywhere."""
    host = (urlsplit(address).hostname or "").lower()
    if not host or host == "youtu.be" or host.endswith("youtube.com"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." in host and not host.endswith((".local", ".localhost", ".internal", ".lan", ".home", ".test", ".invalid", ".example"))
    return ip.is_global


def pages_in(text: str) -> tuple[str, ...]:
    """The web pages `text` links to, as written without the punctuation of the sentence they end, in order and
    without repeats; a video's address and a private one are left out."""
    found = []
    for raw in _ADDRESS.findall(text or ""):
        address = raw.rstrip(_SENTENCE_END)
        while address.endswith((")", "]")) and address.count(")") + address.count("]") > address.count("(") + address.count("["):
            address = address[:-1].rstrip(_SENTENCE_END)  # the bracket of the sentence or of a Markdown link, not the address's own
        if _readable(address):
            found.append(address)
    return tuple(dict.fromkeys(found))[:MAX_LINKS]


def resolve(model: str, user_message: str, history: list[dict[str, Any]]) -> Watch:
    """The turn's `Watch`. The message's own links win; with none, the latest earlier message of the user's that had
    some is kept in front of the model (a question about the video or the page after the first), for `CARRY_TURNS` messages and
    no further, so a conversation that has moved on does not keep sending a link to Google. Carried links are
    only ever opened when allowed, and never reported as withheld, so a conversation that began before the user
    allowed it does not nag on every later turn. Pages and search are Google's tools, so only a model in `WATCHERS`
    has them. `auto` without the user's approval searches nothing and says nothing: no link was withheld."""
    if mode() == OFF:
        return Watch()
    tooled = model in WATCHERS
    route = WATCH if tooled else CAPTIONS
    allowed = sharing.WEB in sharing.allowed(model)
    videos, pages = links_in(user_message), pages_in(user_message) if tooled else ()
    if not allowed:
        return Watch(withheld=True) if videos or pages else Watch()
    if not (videos or pages):
        quiet = 0
        for earlier in reversed(history):
            if earlier.get("role") == "user" and isinstance(earlier.get("content"), str):
                quiet += 1
                if quiet > CARRY_TURNS:
                    break
                videos, pages = links_in(earlier["content"]), pages_in(earlier["content"]) if tooled else ()
                if videos or pages:
                    break
    found = Watch(videos, route=route, pages=pages, search=tooled and mode() == AUTO, asked=pages_in(user_message) if tooled else ())
    return found if found.outside else Watch()
