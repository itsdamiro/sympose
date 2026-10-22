"""One line in the terminal for each thing that happens to a Slack message (docs/decisions/093), so a message with no
reply can be told apart: never arrived (no line), dropped on purpose, or failed. A line carries the time, the persona and
what happened, never the message or the reply."""

import time


def note(handle: str, what: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {handle}: {what}", flush=True)
