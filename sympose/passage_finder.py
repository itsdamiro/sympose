"""Find a quoted passage in a note again (docs/decisions/070).

A proposal or a comment remembers the passage it was about and a little text on each side, not a position: a
position moves with the first edit above it, and a stored time says the note changed, not whether it changed
where the passage is. `locate` answers one of three things: the passage is there exactly once, it is not there
(someone rewrote those words), or it is there more than once and the surrounding text cannot tell which. It never
guesses between candidates and never matches a passage that is not there word for word."""

from typing import NamedTuple

ONE, NONE, MANY = "one", "none", "many"
# How much of the text on each side is kept with a passage. Only used to tell apart passages that occur more than
# once, so it need not be long.
CONTEXT_CHARS = 40


class Match(NamedTuple):
    status: str
    start: int = -1
    end: int = -1


def capture_context(text: str, start: int, end: int, size: int = CONTEXT_CHARS) -> tuple[str, str]:
    """The text just before `start` and just after `end`, each at most `size` characters."""
    return text[max(0, start - size):start], text[end:end + size]


def _starts(text: str, quote: str):
    at = text.find(quote)
    while at != -1:
        yield at
        at = text.find(quote, at + 1)  # one further, so overlapping occurrences count as separate


def _agreeing_before(text: str, at: int, before: str) -> int:
    """How many characters, counting back from `at`, `text` and `before` agree on."""
    n = 0
    while n < len(before) and n < at and text[at - 1 - n] == before[-1 - n]:
        n += 1
    return n


def _agreeing_after(text: str, at: int, after: str) -> int:
    n = 0
    while n < len(after) and at + n < len(text) and text[at + n] == after[n]:
        n += 1
    return n


def locate(text: str, quote: str, before: str = "", after: str = "") -> Match:
    """Where `quote` is in `text`, using `before` and `after` only when it occurs more than once."""
    if not quote:
        return Match(NONE)
    starts = list(_starts(text, quote))
    if not starts:
        return Match(NONE)
    if len(starts) == 1:
        return Match(ONE, starts[0], starts[0] + len(quote))
    fit = {at: _agreeing_before(text, at, before) + _agreeing_after(text, at + len(quote), after) for at in starts}
    best = max(fit.values())
    winners = [at for at, score in fit.items() if score == best]
    if len(winners) == 1 and best > 0:
        return Match(ONE, winners[0], winners[0] + len(quote))
    return Match(MANY)
