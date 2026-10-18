"""Timestamps in a note made from a video (docs/decisions/089). The model writes a moment as `[3:10]` and the engine makes
it a link to that moment of the video, so the address and the seconds are never the model's to get wrong. Only when the
turn watched exactly one video: with several, a bare timestamp does not say which one it belongs to, so it is left as
written."""

import re

# `[3:10]` or `[1:02:15]`, not already a link (`[3:10](...)`, `[3:10][ref]`) and not part of a longer bracket.
_STAMP = re.compile(r"(?<![\w\[])\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\](?![(\[])")


def link(text: str, videos: tuple[str, ...]) -> str:
    """`text` with each bare `[m:ss]` or `[h:mm:ss]` turned into a link to that moment of the one video watched; `text`
    as it came when no video or several were watched, and for a time that is not one (`[1:75]`)."""
    if len(videos) != 1:
        return text

    def replace(found: re.Match[str]) -> str:
        hours, minutes, seconds = int(found.group(1) or 0), int(found.group(2)), int(found.group(3))
        if seconds > 59 or (found.group(1) is not None and minutes > 59):
            return found.group(0)
        shown = found.group(0)[1:-1]
        return f"[{shown}]({videos[0]}&t={hours * 3600 + minutes * 60 + seconds}s)"

    return _STAMP.sub(replace, text)
