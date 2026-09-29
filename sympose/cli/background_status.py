"""What's happening in the background, shown as an animated line above the composer: a recap
refresh, a memory rewrite, the search index build, or -- the wait most turns actually spend most
of their time in -- the reply itself being generated, down to whether it's searching, reading a
note, or asking the model right now (`turn_status.py`). A real phase that runs long enough starts
alternating with the persona's own witty lines, so a slow moment reads as a lot going on rather
than the line looking frozen. Replaces the old `indexing NN%` notice that used to sit at the
meter's far right (docs/decisions/027) -- one place for all of it, so a quiet wait during any of
these reads as the persona being busy, not the app being broken."""

import random
from time import monotonic as _monotonic

from rich.text import Text
from textual.widgets import Static

from sympose import settings_store
from sympose.engine import memory_refresh, recap_refresh, semantic_refresh, status_phrases, turn_status

SETTING = "show_background_status"

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_FRAME_SECONDS = 0.12
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

    _frame = 0
    # Keyed by (handle, kind), not kind alone: a persona switch that lands on the same kind of
    # activity (e.g. both persona's launches start a recap refresh) must still re-pick a phrase
    # from the *new* persona's own set, not keep showing the previous persona's under its name.
    _key: tuple[str | None, str | None] = (None, None)
    _phrase = ""
    _phase_started = 0.0
    _rotation_slot = 0

    def on_mount(self) -> None:
        self.set_interval(_FRAME_SECONDS, self._tick)

    def _tick(self) -> None:
        persona = getattr(self.app, "persona", None)
        handle = persona.handle if persona else None
        kind, detail = activity(handle) if handle and enabled() else (None, "")
        key = (handle, kind)
        now = _monotonic()
        if key != self._key:
            self._key = key
            self._phase_started = now
            self._rotation_slot = 0
            if kind in REAL_STATUS_TEXT:
                self._phrase = REAL_STATUS_TEXT[kind]
            elif kind and handle:
                self._phrase = random.choice(status_phrases.phrases(handle))
            else:
                self._phrase = ""
        elif kind in REAL_STATUS_TEXT and handle:
            elapsed = now - self._phase_started
            if elapsed >= _REAL_ROTATE_AFTER:
                slot = int((elapsed - _REAL_ROTATE_AFTER) // _REAL_ROTATE_INTERVAL) + 1
                if slot != self._rotation_slot:
                    self._rotation_slot = slot
                    self._phrase = (
                        random.choice(status_phrases.phrases(handle)) if slot % 2 else REAL_STATUS_TEXT[kind]
                    )
        if kind is None:
            self.update(Text(""))
            return
        self._frame = (self._frame + 1) % len(_SPINNER_FRAMES)
        self.update(Text(f"{_SPINNER_FRAMES[self._frame]} {self._phrase}{detail}"))
