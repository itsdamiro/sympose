"""What's happening in the background, shown as an animated line above the composer: a recap
refresh, a memory rewrite, the search index build, or -- the wait most turns actually spend most
of their time in -- the reply itself being generated, down to whether it's searching, reading a
note, or asking the model right now (`turn_status.py`). A real phase that runs long enough starts
alternating with the persona's own witty lines, so a slow moment reads as a lot going on rather
than the line looking frozen. Replaces the old `indexing NN%` notice that used to sit at the
meter's far right (docs/decisions/027) -- one place for all of it, so a quiet wait during any of
these reads as the persona being busy, not the app being broken."""

import math
import random
from time import monotonic as _monotonic

from rich.text import Text
from textual.widgets import Static

from sympose import settings_store
from sympose.engine import memory_refresh, recap_refresh, semantic_refresh, status_phrases, turn_status

SETTING = "show_background_status"
# How fast a phrase is typed out, in characters per second; `0` shows it whole at once
# (docs/decisions/043, amendment of 2026-09-30).
TYPING_SETTING = "status_typing"
DEFAULT_CHARS_PER_SECOND = 40

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
# The line is redrawn this often, so typed letters look smooth; the spinner advances every third
# redraw (about 0.12 s), the pace it always had.
_FRAMES_PER_SECOND = 25
_FRAMES_PER_SPINNER_STEP = 3
# A real phase (docs/decisions/043's second follow-up) that runs long enough starts alternating
# with the persona's own witty lines every this many seconds, the literal phrase reasserting itself
# every other slot -- a single frozen sentence for many seconds reads as stuck, not busy, but the
# line must still say what is actually happening at least as often as it says something merely lively.
_REAL_ROTATE_AFTER = 3.0
_REAL_ROTATE_INTERVAL = 3.0

# The turn's own real phases (docs/decisions/043's follow-up) show this literal text, not a
# persona-flavored phrase -- these say what is actually happening for *this* reply, not a vibe.
REAL_STATUS_TEXT = {
    turn_status.SEARCHING: "Searching your notes…",
    turn_status.READING: "Reading a note…",
    turn_status.ASKING: "Thinking about your message…",
}


def enabled() -> bool:
    """On unless explicitly turned off, like the other display knobs."""
    return settings_store.flag(SETTING)


def chars_per_second() -> float:
    """The user's `status_typing`, else the default. Only a finite number that is not a bool and not
    negative counts (`0` shows the phrase at once); anything else leaves the default."""
    value = settings_store.get(TYPING_SETTING)
    usable = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
    return value if usable else DEFAULT_CHARS_PER_SECOND


def activity(handle: str) -> tuple[str | None, str]:
    """`(kind, detail)` -- which one thing to show, when more than one is running at once. The
    turn's own real phase (searching/reading/asking) comes first when it is set: it explains what
    is happening for the reply the user is actually waiting on, which matters more than a
    background job's own phrase -- except right when the turn is itself blocked waiting on one
    (`turn.py` clears its own phase for exactly that window), so the block below can fall through
    to that job's own, more specific reason. After that: recap, then memory, then the persona's
    own phrases generating, then indexing -- the order a new session's own background work
    naturally finishes in. `kind` is `None` when nothing is running. `detail` is text appended
    after the phrase -- only indexing has one, its percent, since that is genuinely useful (almost
    done vs. just started) in a way the others' own progress is not. `status_phrases.is_running`
    is checked here too: it is itself a background model call (the first time a persona is ever
    used), and without it the busy indicator could not show the one background call it was built
    to cover."""
    turn_phase = turn_status.phase(handle)
    if turn_phase is not None:
        return turn_phase, ""
    if recap_refresh.is_running(handle):
        return "recap", ""
    if memory_refresh.is_running(handle):
        return "memory", ""
    if status_phrases.is_running(handle):
        return "phrases", ""
    percent = semantic_refresh.progress()
    if percent is not None:
        return "index", f" {percent}%"
    return None, ""


class BackgroundStatus(Static):
    """Empty when nothing is running, or the knob is off."""

    DEFAULT_CSS = """
    BackgroundStatus {
        height: 1;
        margin: 0 2 0 2;
        color: $text-muted;
    }
    """

    _ticks = 0
    # Keyed by (handle, kind), not kind alone: a persona switch that lands on the same kind of
    # activity (e.g. both persona's launches start a recap refresh) must still re-pick a phrase
    # from the *new* persona's own set, not keep showing the previous persona's under its name.
    _key: tuple[str | None, str | None] = (None, None)
    _phrase = ""
    _phrase_at = 0.0  # when the phrase now showing was chosen: typing counts from here
    _last_witty = ""  # the last witty phrase shown, so the next pick is a different one
    _phase_started = 0.0
    _rotation_slot = 0
    _shown = ""

    def on_mount(self) -> None:
        self.set_interval(1 / _FRAMES_PER_SECOND, self._tick)

    def _witty(self, handle: str) -> str:
        """A random one of the persona's own phrases, not the one shown just before when it has others."""
        phrases = status_phrases.phrases(handle)
        choice = random.choice([p for p in phrases if p != self._last_witty] or phrases)
        self._last_witty = choice
        return choice

    def _set_phrase(self, phrase: str, now: float) -> None:
        self._phrase, self._phrase_at = phrase, now

    def _line(self, handle: str | None, kind: str | None, detail: str, now: float) -> str:
        """The whole line for this moment (spinner, the typed part of the phrase, detail), `""` when
        nothing is running. Every kind rotates: a real phase shows its literal text, then from
        `_REAL_ROTATE_AFTER` a witty line, the literal one again every other slot; anything else
        shows a new witty phrase every `_REAL_ROTATE_INTERVAL`."""
        key = (handle, kind)
        if key != self._key:
            self._key, self._phase_started, self._rotation_slot = key, now, 0
            if kind in REAL_STATUS_TEXT:
                self._set_phrase(REAL_STATUS_TEXT[kind], now)
            elif kind and handle:
                self._set_phrase(self._witty(handle), now)
            else:
                self._set_phrase("", now)
        elif kind and handle:
            elapsed = now - self._phase_started
            real = kind in REAL_STATUS_TEXT
            if real:
                slot = int((elapsed - _REAL_ROTATE_AFTER) // _REAL_ROTATE_INTERVAL) + 1  # 0 until the threshold
            else:
                slot = int(elapsed // _REAL_ROTATE_INTERVAL)
            if slot != self._rotation_slot:
                self._rotation_slot = slot
                self._set_phrase(REAL_STATUS_TEXT[kind] if real and slot % 2 == 0 else self._witty(handle), now)
        if kind is None:
            return ""
        speed = chars_per_second()
        shown = self._phrase if speed <= 0 else self._phrase[: int((now - self._phrase_at) * speed) + 1]
        frame = _SPINNER_FRAMES[(self._ticks // _FRAMES_PER_SPINNER_STEP) % len(_SPINNER_FRAMES)]
        self._ticks += 1
        return f"{frame} {shown}{detail}"

    def _tick(self) -> None:
        persona = getattr(self.app, "persona", None)
        handle = persona.handle if persona else None
        kind, detail = activity(handle) if handle and enabled() else (None, "")
        line = self._line(handle, kind, detail, _monotonic())
        if line != self._shown:  # only redraw when something changed
            self._shown = line
            self.update(Text(line))
