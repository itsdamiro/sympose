"""The terminal's own display knobs, listed first in `/settings` (docs/decisions/036, 044). They change
how this channel draws things, not what the engine does, so they live beside the display modules they
name; the web has its own."""

from sympose.cli import background_status, grounding_line, meter, reveal, trim_notice
from sympose.engine.settings_registry import NUMBER, Setting, toggle

DISPLAY = "Display"

SETTINGS: list[Setting] = [
    toggle(grounding_line.SETTING, "the notes that grounded a reply, in its header", grounding_line.enabled, group=DISPLAY),
    toggle(trim_notice.SETTING, "the notice that older turns were left out", trim_notice.enabled, group=DISPLAY),
    toggle(meter.SETTING, "the context meter under the chat box", meter.enabled, group=DISPLAY),
    toggle(background_status.SETTING, "the busy indicator above the box", background_status.enabled, group=DISPLAY),
    Setting(
        background_status.TYPING_SETTING, NUMBER, "how fast the busy line is typed out",
        background_status.chars_per_second, lambda: background_status.DEFAULT_CHARS_PER_SECOND, group=DISPLAY,
        hint="characters per second, 0 or more; 0 shows each phrase at once",
    ),
    Setting(
        reveal.SETTING, NUMBER, "how fast a reply is written out", reveal.words_per_second,
        lambda: reveal.DEFAULT_WORDS_PER_SECOND, group=DISPLAY,
        hint="words per second, 0 or more; 0 shows the whole reply at once",
    ),
]
