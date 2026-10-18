"""The captions of a video, for a model that cannot watch it (docs/decisions/089, the transcript route). A local model
and any cloud model but the one that watches get the words of a public video as timed lines; the model that watches
gets them when its own request fails. They cost a small part of the watch route's tokens and show no slide or line of
code on screen.

The caption source is not an official interface: a burst of fetches got the spike's address blocked, and a cloud
address is blocked from the first. So a video's captions are fetched once and kept (a follow-up does not fetch them
again), fetches are spaced, a block pauses every fetch for a while, and a failure says in plain words why.

IPv4 first and a short wait, because IPv6 connects take 23 s to fail on some networks. But YouTube blocks addresses,
not people, and on the machine this was built on the IPv4 address was blocked while the IPv6 one was not: so a block
over IPv4 is tried once more the way the system would connect by itself, and the way that worked is kept."""

import re
import threading
import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter

from sympose.engine import network
from sympose.engine.prompt_text import CAPTIONS, CAPTIONS_CUT, CAPTIONS_MISSING

MAX_TOKENS = 30_000  # of one message's captions, whatever the window (about 3 hours of speech)
GAP_SECONDS = 3  # between two fetches from the machine
BLOCKED_PAUSE_SECONDS = 900  # no fetch at all after YouTube blocked this address
FAILED_KEPT_SECONDS = 300  # a video that failed is not asked about again for this long
LINE_SECONDS = 20  # captions are grouped into lines about this long, one time in front of each
TOKEN_CHARS = 3  # a token is counted as this many characters, so the room is never overfilled
_TIMEOUT = (10, 20)  # connect, read: seconds
_ID = re.compile(r"[?&]v=([A-Za-z0-9_-]{11})")
_LANGUAGE = "en"


@dataclass(frozen=True)
class Captions:
    """The captions of one video as they go in the prompt: `lines` are `[m:ss] words`, `reached` is the second the
    last line starts at and `length` the second the captions end at, so a cut-short transcript says where it stops."""

    address: str
    lines: tuple[str, ...]
    reached: int
    length: int
    language: str
    generated: bool

    @property
    def cut(self) -> bool:
        return self.reached < self.length - LINE_SECONDS


@dataclass(frozen=True)
class Missing:
    address: str
    reason: str  # plain words, for the user's sake and the model's


class _Blocked(Exception):
    """YouTube refuses this address."""


class _Absent(Exception):
    """There is nothing to fetch for this video; the message says why."""


class _Session(requests.Session):
    """A session that never waits forever and, unless `ipv6` is asked for, connects over IPv4 like the model calls
    (`network`)."""

    def __init__(self, ipv6: bool = False) -> None:
        super().__init__()
        adapter = _Adapter(ipv6)
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    def request(self, *args, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", _TIMEOUT)
        return super().request(*args, **kwargs)


class _Adapter(HTTPAdapter):
    def __init__(self, ipv6: bool) -> None:
        self._ipv6 = ipv6
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if network.ipv4_only() and not self._ipv6:
            kwargs["source_address"] = ("0.0.0.0", 0)  # noqa: S104 (a local source address, not a listener)
        super().init_poolmanager(*args, **kwargs)


_lock = threading.Lock()
_kept: dict[str, tuple[float, "_Raw | str"]] = {}  # video id -> (when, its captions or why it has none)
_last_fetch = 0.0
_blocked_until = 0.0
_ipv6_first = False  # IPv4 was blocked and the system's own way of connecting was not

_Raw = tuple[list[tuple[float, str]], str, bool]  # (start seconds, words) per snippet, language, generated


def video_id(address: str) -> str | None:
    found = _ID.search(address)
    return found.group(1) if found else None


def _download(video: str, ipv6: bool = False) -> _Raw:
    """The caption snippets of `video`: an English track if there is one, manual before generated, else the first the
    video has. Raises `_Absent` with the reason or `_Blocked`."""
    from youtube_transcript_api import (  # imported here: the library is only needed when a video is read this way
        AgeRestricted, IpBlocked, NoTranscriptFound, RequestBlocked, TranscriptsDisabled, VideoUnavailable,
        VideoUnplayable, YouTubeTranscriptApi, YouTubeTranscriptApiException,
    )

    try:
        listing = YouTubeTranscriptApi(http_client=_Session(ipv6)).list(video)
        try:
            track = listing.find_transcript([_LANGUAGE])
        except NoTranscriptFound:
            track = next(iter(listing))
        fetched = track.fetch()
    except (IpBlocked, RequestBlocked) as e:
        raise _Blocked from e
    except TranscriptsDisabled as e:
        raise _Absent("the video's owner has turned captions off") from e
    except (NoTranscriptFound, StopIteration) as e:
        raise _Absent("the video has no captions") from e
    except AgeRestricted as e:
        raise _Absent("the video is age-restricted") from e
    except (VideoUnavailable, VideoUnplayable) as e:
        raise _Absent("the video is private, removed or not available here") from e
    except YouTubeTranscriptApiException as e:
        raise _Absent("YouTube did not give its captions") from e
    except requests.RequestException as e:
        raise (_Blocked() if ipv6 else _Absent("YouTube could not be reached")) from e  # no IPv6 route at all is no way round a block
    return [(s.start, " ".join(s.text.split())) for s in fetched], fetched.language_code, fetched.is_generated


def _stamp(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


def _lines(snippets: list[tuple[float, str]]) -> list[tuple[int, str]]:
    """The snippets as `(start second, words)` lines of about `LINE_SECONDS`."""
    grouped: list[tuple[int, list[str]]] = []
    for start, words in snippets:
        if not words:
            continue
        if not grouped or start - grouped[-1][0] >= LINE_SECONDS:
            grouped.append((int(start), []))
        grouped[-1][1].append(words)
    return [(start, " ".join(parts)) for start, parts in grouped]


def _get(video: str) -> "_Raw | str":
    """The captions of `video`, from memory when they were fetched lately, else from YouTube; a string is the reason
    there are none. Spaced, and silent after a block."""
    global _last_fetch, _blocked_until, _ipv6_first
    now = time.monotonic()
    if (held := _kept.get(video)) and (not isinstance(held[1], str) or now - held[0] < FAILED_KEPT_SECONDS):
        return held[1]
    if now < _blocked_until:
        return "YouTube is not giving captions to this computer right now"
    if wait := _last_fetch + GAP_SECONDS - now:
        time.sleep(max(0.0, wait))
    try:
        try:
            result: "_Raw | str" = _download(video, _ipv6_first)
        except _Blocked:
            if _ipv6_first:
                raise
            result = _download(video, True)
            _ipv6_first = True  # the first way was blocked and this one was not: start with it from now on
    except _Blocked:
        _blocked_until = time.monotonic() + BLOCKED_PAUSE_SECONDS
        return "YouTube is not giving captions to this computer right now"
    except _Absent as e:
        result = str(e)
    finally:
        _last_fetch = time.monotonic()
    _kept[video] = (time.monotonic(), result)
    return result


def fetch(addresses: tuple[str, ...], token_room: int) -> tuple[list[Captions], list[Missing]]:
    """The captions of each of `addresses` (watch addresses), cut to fit `token_room` tokens between them: a long video
    keeps its start, and `Captions.cut` says so. Those that could not be fetched come back as `Missing`, with the reason."""
    got: list[Captions] = []
    missing: list[Missing] = []
    room = max(token_room, 0) * TOKEN_CHARS // max(len(addresses), 1)
    with _lock:
        for address in addresses:
            video = video_id(address)
            raw = _get(video) if video else "that is not a video address"
            if isinstance(raw, str):
                missing.append(Missing(address, raw))
                continue
            snippets, language, generated = raw
            every = _lines(snippets)
            kept: list[str] = []
            used = 0
            for start, words in every:
                line = f"[{_stamp(start)}] {words}"
                if used + len(line) + 1 > room:
                    break
                kept.append(line)
                used += len(line) + 1
            if not kept:
                missing.append(Missing(address, "there is no room for its captions in this model's window"))
                continue
            last = snippets[-1]
            got.append(Captions(
                address, tuple(kept), every[len(kept) - 1][0], int(last[0]), language, generated,
            ))
    return got, missing


def render(got: list[Captions], missing: list[Missing]) -> str | None:
    """What the prompt carries in place of a video: the framing, then each video's captions with where they come from
    (and where they stop, when they do), and a line for each video that could not be fetched. `None` when there is
    no video at all."""
    parts: list[str] = []
    if got:
        parts.append(CAPTIONS)
    for c in got:
        kind = "generated by YouTube" if c.generated else "written by the video's makers"
        head = f"Video: {c.address} (captions in {c.language}, {kind})"
        if c.cut:
            head += "\n" + CAPTIONS_CUT.format(reached=_stamp(c.reached), length=_stamp(c.length))
        parts.append(head + "\n" + "\n".join(c.lines))
    if missing:
        parts.append(CAPTIONS_MISSING.format(reasons="; ".join(f"{m.address}: {m.reason}" for m in missing)))
    return "\n\n".join(parts) or None


def forget() -> None:
    """Empty what was kept and lift a pause (for tests)."""
    global _last_fetch, _blocked_until, _ipv6_first
    with _lock:
        _kept.clear()
        _last_fetch = _blocked_until = 0.0
        _ipv6_first = False
