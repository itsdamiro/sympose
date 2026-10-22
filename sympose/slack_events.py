"""What a Slack event is to Sympose (docs/decisions/093): the one shape the rest of the channel works with, and the
events that are not a message to a persona at all. Pure: no Slack library, no engine."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SlackFile:
    name: str
    size: int  # bytes, as Slack reports them (0 when it does not)
    url: str  # where the bot may download it; empty for a file Slack gave no address for


@dataclass(frozen=True)
class Incoming:
    user: str
    channel: str
    text: str
    ts: str  # this message's own time stamp, Slack's id for it
    thread_ts: str | None  # the thread it is in, when it is a reply
    direct: bool  # a direct message to the persona's bot, not a mention in a channel
    event_id: str | None  # Slack's id for this delivery, to recognise a redelivery
    files: tuple[SlackFile, ...] = ()  # shared with the message (docs/decisions/093, "files attached in Slack")


FILE_SHARE = "file_share"


def _files(raw: Any) -> tuple[SlackFile, ...]:
    """The files of an event, each with the address the bot may download it from. A file Slack gave no address for (one
    shared from another workspace, `file_access: check_file_info`) is kept with an empty address, so the user is told it
    could not be read and not left with a reply that ignores it."""
    found = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        url = item.get("url_private_download") or item.get("url_private")
        size = item.get("size")
        found.append(SlackFile(
            str(item.get("name") or item.get("title") or "file"),
            size if isinstance(size, int) and size > 0 else 0,
            url if isinstance(url, str) and item.get("file_access") != "check_file_info" else "",
        ))
    return tuple(found)


def parse(body: dict[str, Any], bot_user_id: str) -> Incoming | None:
    """The message in a Socket Mode event payload, or `None` for one a persona does not answer: anything but a direct
    message to the bot or a mention of it, a message from a bot, an edit or a deletion (any message with a `subtype` but
    a file share), and one with neither words nor files left once the mention is taken out."""
    event = body.get("event")
    if not isinstance(event, dict) or event.get("subtype") not in (None, FILE_SHARE) or event.get("bot_id"):
        return None
    kind = event.get("type")
    direct = kind == "message" and event.get("channel_type") == "im"
    if not direct and kind != "app_mention":
        return None
    user, channel, ts, text = (event.get(key) for key in ("user", "channel", "ts", "text"))
    files = _files(event.get("files"))
    if text is None and files:
        text = ""  # a file shared with no words may arrive without a `text` at all
    if not all(isinstance(value, str) and value for value in (user, channel, ts)) or not isinstance(text, str):
        return None
    if bot_user_id:
        text = text.replace(f"<@{bot_user_id}>", "")
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    if not text and not files:
        return None
    thread = event.get("thread_ts")
    event_id = body.get("event_id")
    return Incoming(
        user, channel, text, ts, thread if isinstance(thread, str) and thread else None, direct,
        event_id if isinstance(event_id, str) else None, files,
    )


def conversation_key(message: Incoming) -> str:
    """A direct message is one conversation, so the key is the channel alone: nobody clicks "reply in thread" when
    messaging a bot, and keying on the thread made every plain follow-up start from nothing. In a channel a thread is
    a conversation; a message that starts one is the thread's first message."""
    if message.direct:
        return f"dm:{message.channel}"
    return f"thread:{message.channel}:{message.thread_ts or message.ts}"
