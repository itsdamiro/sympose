"""How fast a reply is revealed in the terminal chat (docs/decisions/032). The setting is words per
second; the screen is redrawn at a fixed rate whatever the speed, and each redraw shows the words
the speed has reached by then, so a faster reveal costs no more redraws."""

import math

from sympose import settings_store

SETTING = "reply_reveal"
DEFAULT_WORDS_PER_SECOND = 50
FRAMES_PER_SECOND = 20


def words_per_second() -> float:
    """The user's `reply_reveal`, else the default. Only a finite number that is not a bool and not
    negative counts (`0` shows the whole reply at once); anything else leaves the default."""
    value = settings_store.get(SETTING)
    usable = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
    return value if usable else DEFAULT_WORDS_PER_SECOND


def words_shown(total: int, frame: int, speed: float) -> int:
    """How many of `total` words show on frame number `frame` (1 is the first) at `speed` words per second."""
    if speed <= 0:
        return total
    return min(total, math.ceil(speed * frame / FRAMES_PER_SECOND))
