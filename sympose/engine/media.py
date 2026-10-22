"""Files the user attaches to a message (docs/decisions/089, `media`): a PDF, an image, a sound or a video, read by the
cloud model's maker, not by Sympose. The bytes go inside the one request to Google and are kept nowhere else: not in
the vault, not in the persona's data, not in the conversation's record (which keeps only the message's words). They are
held in this process's memory for `CARRY_TURNS` later messages, so a question about the file can be answered from it,
and are gone when Sympose stops.

Only a model in `READERS` can be given one, and only when the user has approved the `media` category (docs/decisions/031);
a local model, or a cloud model that cannot read files, is told so and the file is not sent."""

import re
import threading
from dataclasses import dataclass, field
from pathlib import PurePath

from sympose.engine import sharing
from sympose.engine.prompt_text import ATTACHED_FILES, GONE_FILES, UNSUPPORTED_FILES, WITHHELD_FILES

READERS = ("gemini/gemini-flash-latest",)  # a model joins by measurement, like `web_access.WATCHERS`
MAX_FILES = 3  # for one message
MAX_BYTES = 50 * 1024 * 1024  # all of one message's files together; measured: a 46 MB file (a 61 MB request) was taken, Google's own limit is a request of 100 MB
CARRY_TURNS = 5  # the later messages of a conversation the files are carried into, as a link is (`web_access.CARRY_TURNS`)
HELD_CONVERSATIONS = 4  # conversations whose files are held at once; the oldest is let go first
HELD_BYTES = 100 * 1024 * 1024  # and all the held files together, so big videos cannot fill the machine's memory
PDF, IMAGE, AUDIO, VIDEO = "pdf", "image", "audio", "video"

# By the file name's ending, which is what the user chose; the type a browser or a file manager reports is not trusted.
_TYPES = {
    ".pdf": ("application/pdf", PDF),
    ".png": ("image/png", IMAGE), ".jpg": ("image/jpeg", IMAGE), ".jpeg": ("image/jpeg", IMAGE), ".webp": ("image/webp", IMAGE),
    ".heic": ("image/heic", IMAGE), ".heif": ("image/heif", IMAGE),
    ".mp3": ("audio/mp3", AUDIO), ".wav": ("audio/wav", AUDIO), ".aac": ("audio/aac", AUDIO), ".ogg": ("audio/ogg", AUDIO),
    ".flac": ("audio/flac", AUDIO), ".aiff": ("audio/aiff", AUDIO), ".m4a": ("audio/aac", AUDIO),
    ".mp4": ("video/mp4", VIDEO), ".mov": ("video/mov", VIDEO), ".webm": ("video/webm", VIDEO), ".mpeg": ("video/mpeg", VIDEO),
    ".mpg": ("video/mpg", VIDEO), ".avi": ("video/avi", VIDEO), ".wmv": ("video/wmv", VIDEO), ".3gp": ("video/3gpp", VIDEO),
}
EXTENSIONS = tuple(_TYPES)


class MediaRefused(ValueError):
    """The attached files cannot be sent, said in words the user can act on."""


@dataclass(frozen=True)
class File:
    name: str
    mime: str
    kind: str
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class Plan:
    """What this turn does with the files: `files` are sent, `fresh` says the message itself brought them (as against
    ones carried from an earlier message), `withheld` and `unsupported` name the files that were attached and not sent."""

    files: tuple[File, ...] = ()
    fresh: bool = False
    withheld: tuple[str, ...] = ()  # the user has not approved `media` for this cloud model
    unsupported: tuple[str, ...] = ()  # this model cannot read files at all
    reserved: int = 0  # what these files counted as when they were first sent (the provider's own figure), 0 until known

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.files)


def file_name(raw: str) -> str:
    """A name safe to show and to put in a message: the last part of any path, no control characters, bounded."""
    name = "".join(c for c in PurePath(str(raw).replace("\\", "/")).name if c.isprintable()).strip()
    return name[:120]


def readable_name(name: str) -> tuple[str, tuple[str, str]]:
    """The clean name and its (mime, kind), or `MediaRefused` for an ending Google cannot read: asked before a file is fetched."""
    clean = file_name(name)
    kind = _TYPES.get(PurePath(clean).suffix.lower())
    if not clean or kind is None:
        raise MediaRefused(f"Sympose cannot attach {clean or 'that'}: it reads PDFs, images, sounds and videos ({', '.join(EXTENSIONS)}).")
    return clean, kind


def make(name: str, data: bytes) -> File:
    """A `File` from its name and bytes; `MediaRefused` for an ending Google cannot read or for nothing at all."""
    clean, kind = readable_name(name)
    if not data:
        raise MediaRefused(f"{clean} is empty.")
    return File(clean, kind[0], kind[1], data)


def check(files: list[File]) -> tuple[File, ...]:
    """`files` if they may travel with one message, else `MediaRefused`. A name used twice would make the model's
    reading of 'the first file' ambiguous, so a repeat is numbered."""
    if len(files) > MAX_FILES:
        raise MediaRefused(f"At most {MAX_FILES} files can go with one message.")
    if sum(len(f.data) for f in files) > MAX_BYTES:
        raise MediaRefused(f"Those files are too large to send together (the limit is {MAX_BYTES // (1024 * 1024)} MB for one message).")
    seen: dict[str, int] = {}
    named = []
    for f in files:
        seen[f.name] = seen.get(f.name, 0) + 1
        if seen[f.name] > 1:
            path = PurePath(f.name)
            f = File(f"{path.stem} ({seen[f.name]}){path.suffix}", f.mime, f.kind, f.data)
        named.append(f)
    return tuple(named)


# What is held for later messages: per (persona, conversation), the files and how many more messages they are carried into.
_held: dict[tuple[str, str], tuple[tuple[File, ...], int, int]] = {}
_lock = threading.Lock()


def plan(model: str, handle: str, session_id: str, files: tuple[File, ...]) -> Plan:
    """The turn's `Plan`. The message's own files win; with none, the files held for this conversation are used while
    any message of their `CARRY_TURNS` is left. A carried file is only ever sent when allowed and never reported as
    withheld or unsupported, so a conversation does not nag on every later turn."""
    with _lock:
        carried, _, counted = _held.get((handle, session_id), ((), 0, 0))
    chosen = files or carried
    if not chosen:
        return Plan()
    if model not in READERS:
        return Plan(unsupported=tuple(f.name for f in files))
    if sharing.MEDIA not in sharing.allowed(model):
        return Plan(withheld=tuple(f.name for f in files))
    return Plan(chosen, fresh=bool(files), reserved=0 if files else counted)


def settle(handle: str, session_id: str, found: Plan, counted: int = 0) -> None:
    """After a turn that was kept: hold a message's own files for the next `CARRY_TURNS` messages, or use up one of the
    carried ones. Files the message brought and the turn did not send (withheld, unsupported) let go of what was held, so
    the next message does not bring back an older file the user has since moved on from. `counted` is what the provider
    said the files came to, kept with them so a later message can leave room for them before it is sent."""
    key = (handle, session_id)
    with _lock:
        if found.withheld or found.unsupported:
            _held.pop(key, None)
        elif found.fresh:
            _held.pop(key, None)
            _held[key] = (found.files, CARRY_TURNS, counted)
            while len(_held) > HELD_CONVERSATIONS or (len(_held) > 1 and sum(len(f.data) for kept, _, _ in _held.values() for f in kept) > HELD_BYTES):
                _held.pop(next(iter(_held)))
        elif found.files and key in _held:
            kept, left, seen = _held[key]
            if left <= 1:
                del _held[key]
            else:
                _held[key] = (kept, left - 1, seen)


def forget(handle: str, session_id: str) -> None:
    """Let go of the files held for a conversation (it was deleted)."""
    with _lock:
        _held.pop((handle, session_id), None)


def _listed(names: tuple[str, ...]) -> str:
    return ", ".join(names)


_MARKER = re.compile(r"\[attached: (.+?)\]")


def named_in(message: dict) -> list[str]:
    """The files a message names with its `[attached: name]` markers, in the order it names them."""
    return _MARKER.findall(str(message.get("content") or ""))


def gone(history: list[dict], found: Plan) -> tuple[str, ...]:
    """The files the user's earlier messages name that are not attached to this one: they ran out of their five messages,
    Sympose was restarted, or the conversation moved to a model that cannot read them. The history still says they were
    attached, so without this the persona could answer as if she were reading them."""
    named = (n for m in history if m.get("role") == "user" for n in named_in(m))
    return tuple(n for n in dict.fromkeys(named) if n not in found.names)


def note(found: Plan, history: list[dict] | None = None) -> str | None:
    """The lines the prompt carries beside the message about the files, or `None` when there is nothing to say: that
    they are attached, or that they were not sent and why (the persona tells the user, who cannot see this prompt), and
    that files named earlier in the conversation are no longer there."""
    lines = []
    if found.files:
        lines.append(ATTACHED_FILES.format(names=_listed(found.names)))
    elif found.unsupported:
        lines.append(UNSUPPORTED_FILES.format(names=_listed(found.unsupported)))
    elif found.withheld:
        lines.append(WITHHELD_FILES.format(names=_listed(found.withheld)))
    if missing := gone(history or [], found):
        many = len(missing) > 1
        lines.append(GONE_FILES.format(names=_listed(missing), that="They are" if many else "It is", them="them" if many else "it"))
    return "\n\n".join(lines) or None


def note_kinds(found: Plan) -> str:
    """What the file capture skill is told the files are: each name with the `type:` its note carries."""
    return ", ".join(f"{f.name} (type: {f.kind} note)" for f in found.files)
