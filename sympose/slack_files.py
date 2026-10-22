"""Files shared with a Slack message, fetched for the turn (docs/decisions/093, "files attached in Slack"). Slack is only the
way the file arrives: what comes out is the `media.File` the web chat makes, and `media` decides the rest (the approval, the
models that can read it, how long it is held).

The bot token is sent to Slack's file host and nowhere else, and no redirect is followed: Slack answers a missing permission
with a login page or a redirect, which is read as "the App cannot read files". Every refusal is a `media.MediaRefused` in words
the user can act on, and none holds anything from the vault."""

from urllib.parse import urlsplit

import httpx

from sympose.engine import media
from sympose.slack_events import SlackFile

HOST = "files.slack.com"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)  # for each read, not for the whole file
NO_ACCESS = ("Sympose could not download {name} from Slack. The Slack App needs the files:read permission: add it under "
             "OAuth & Permissions, reinstall the App, and send the file again.")
FAILED = "Sympose could not download {name} from Slack. Send the file again in a moment."
NO_ADDRESS = "Slack gave Sympose no way to download {name} (a file shared from another workspace cannot be read). Send it from this workspace."


def _chunks(response: httpx.Response, name: str, room: int) -> bytes:
    """The body of `response`, refused as soon as it goes past `room` bytes (so a huge file is not read to the end)."""
    data = bytearray()
    for chunk in response.iter_bytes():
        data += chunk
        if len(data) > room:
            raise media.MediaRefused(f"{name} is too large to send (the limit is {media.MAX_BYTES // (1024 * 1024)} MB for one message).")
    return bytes(data)


def _on_slacks_file_host(url: str) -> bool:
    try:
        where = urlsplit(url)
    except ValueError:  # a malformed address, such as an unclosed bracket
        return False
    return where.scheme == "https" and where.hostname == HOST


def _get(client: httpx.Client, file: SlackFile, name: str, room: int) -> bytes:
    if not file.url:
        raise media.MediaRefused(NO_ADDRESS.format(name=name))
    if not _on_slacks_file_host(file.url):  # the token goes to Slack's file host only
        raise media.MediaRefused(NO_ACCESS.format(name=name))
    try:
        with client.stream("GET", file.url) as response:
            status, html = response.status_code, response.headers.get("content-type", "").startswith("text/html")
            if status == 200 and not html:
                return _chunks(response, name, room)
            denied = html or status in (301, 302, 303, 307, 308, 401, 403)  # a login page or a redirect: no permission
            raise media.MediaRefused((NO_ACCESS if denied else FAILED).format(name=name))
    except (httpx.HTTPError, httpx.InvalidURL) as e:  # InvalidURL is httpx's own, not an HTTPError: a port that is not a number
        raise media.MediaRefused(FAILED.format(name=name)) from e


def fetch(files: tuple[SlackFile, ...], bot_token: str, transport: httpx.BaseTransport | None = None) -> tuple[media.File, ...]:
    """The files of a message, downloaded and checked, or `media.MediaRefused` saying why they cannot be sent. What can be
    known without a download (how many, what type, the size Slack reports) is checked before any byte is fetched."""
    if len(files) > media.MAX_FILES:
        raise media.MediaRefused(f"At most {media.MAX_FILES} files can go with one message.")
    for file in files:
        media.readable_name(file.name)
    if sum(f.size for f in files) > media.MAX_BYTES:
        raise media.MediaRefused(f"Those files are too large to send together (the limit is {media.MAX_BYTES // (1024 * 1024)} MB for one message).")
    made: list[media.File] = []
    taken = 0
    headers = {"Authorization": f"Bearer {bot_token}"}
    with httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=False, transport=transport) as client:
        for file in files:
            name = media.file_name(file.name)
            data = _get(client, file, name, media.MAX_BYTES - taken)
            taken += len(data)
            made.append(media.make(name, data))
    return media.check(made)


def with_markers(text: str, files: tuple[media.File, ...]) -> str:
    """`text` followed by the `[attached: name]` marker the web chat's composer writes for each file (the names
    `media.check` settled on), so the history and the file capture skill work as they do there. With no words, only the markers."""
    return "\n".join(part for part in (text, " ".join(f"[attached: {f.name}]" for f in files)) if part)
