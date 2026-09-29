"""What's happening in the background, shown as an animated line above the composer: a recap
refresh, a memory rewrite, or the search index build. Replaces the old `indexing NN%` notice that
used to sit at the meter's far right (docs/decisions/027) -- one place for all of it, so a quiet
wait during any of the three reads as the persona being busy, not the app being broken."""

import random

from rich.text import Text
from textual.widgets import Static

from sympose import settings_store
from sympose.engine import memory_refresh, recap_refresh, semantic_refresh, status_phrases

SETTING = "show_background_status"

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_FRAME_SECONDS = 0.12


def enabled() -> bool:
    """On unless explicitly turned off, like the other display knobs."""
    return settings_store.flag(SETTING)


def activity(handle: str) -> tuple[str | None, str]:
    """`(kind, detail)` -- which one thing to show, when more than one is running at once: recap,
    then memory, then the persona's own phrases generating, then indexing -- the order a new
    session's own background work naturally finishes in. `kind` is `None` when nothing is
    running. `detail` is text appended after the phrase -- only indexing has one, its percent,
    since that is genuinely useful (almost done vs. just started) in a way the others' own
    progress is not. `status_phrases.is_running` is checked here too: it is itself a background
    model call (the first time a persona is ever used), and without it the busy indicator could
    not show the one background call it was built to cover."""
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

    def on_mount(self) -> None:
        self.set_interval(_FRAME_SECONDS, self._tick)

    def _tick(self) -> None:
        persona = getattr(self.app, "persona", None)
        handle = persona.handle if persona else None
        kind, detail = activity(handle) if handle and enabled() else (None, "")
        key = (handle, kind)
        if key != self._key:
            self._key = key
            self._phrase = random.choice(status_phrases.phrases(handle)) if kind and handle else ""
        if kind is None:
            self.update(Text(""))
            return
        self._frame = (self._frame + 1) % len(_SPINNER_FRAMES)
        self.update(Text(f"{_SPINNER_FRAMES[self._frame]} {self._phrase}{detail}"))
