"""The settings `/settings` lists (docs/decisions/036). Each row names the module's own key and
accessor, so what is valid, and what the default is, stays where the setting is read: the screen
never holds a second copy of a rule."""

from dataclasses import dataclass
from typing import Any, Callable

from sympose import settings_store
from sympose.cli import grounding_line, meter, reveal, trim_notice
from sympose.engine import budget, embeddings, followup, lookup, recap

TOGGLE, CHOICE, NUMBER = "toggle", "choice", "number"
ON, OFF = "on", "off"


@dataclass(frozen=True)
class Setting:
    key: str
    kind: str
    summary: str
    current: Callable[[], Any]  # the value in force, read through the module that owns the setting
    default: Callable[[], Any] = lambda: None  # what `current` gives when the setting is missing or unusable (`True` for a toggle)
    choices: tuple[str, ...] = ()  # a choice: its values, in the order they step through
    hint: str = ""  # a number: what to type, said in the prompt and when a value is refused
    whole: bool = False  # a number: whole numbers only


def _toggle(key: str, summary: str, current: Callable[[], bool]) -> Setting:
    """A true or false setting. Every one ships on, so turning it back on removes the key."""
    return Setting(key, TOGGLE, summary, current, lambda: True)


SETTINGS: list[Setting] = [
    # Display
    _toggle(grounding_line.SETTING, "the notes that grounded a reply, in its header", grounding_line.enabled),
    _toggle(trim_notice.SETTING, "the notice that older turns were left out", trim_notice.enabled),
    _toggle(meter.SETTING, "the context meter under the chat box", meter.enabled),
    _toggle(meter.NOTICE_SETTING, "the indexing notice", lambda: settings_store.flag(meter.NOTICE_SETTING)),
    Setting(
        reveal.SETTING, NUMBER, "how fast a reply is written out", reveal.words_per_second,
        lambda: reveal.DEFAULT_WORDS_PER_SECOND, hint="words per second, 0 or more; 0 shows the whole reply at once",
    ),
    # Context
    Setting(
        budget.CONTEXT_SETTING, NUMBER, "the window a local model is given", budget.context_setting,
        hint="tokens, 2048 or more; empty for automatic", whole=True,
    ),
    Setting(
        budget.REPLY_SETTING, NUMBER, "the room kept for the reply", budget.reply_setting,
        hint="tokens, 64 or more; empty for automatic", whole=True,
    ),
    Setting(
        followup.SETTING, CHOICE, "the extra search for follow-ups",
        lambda: ON if followup.enabled() else OFF, lambda: ON, choices=(ON, OFF),
    ),
    _toggle(recap.SETTING, "recaps of your earlier conversations", recap.enabled),
    # Search
    Setting(
        embeddings.MODE_SETTING, CHOICE, "how notes are found", embeddings.mode,
        lambda: embeddings.DEFAULT_MODE,
        choices=(embeddings.AUTO, embeddings.KEYWORDS, embeddings.EMBEDDINGS, embeddings.HYBRID),
    ),
    Setting(
        embeddings.THRESHOLD_SETTING, NUMBER, "how close a note must be", embeddings.min_similarity,
        lambda: embeddings.DEFAULT_THRESHOLD, hint="a number between 0 and 1, not including them",
    ),
    Setting(
        embeddings.MARGIN_SETTING, NUMBER, "how near the best a note must be", embeddings.margin,
        lambda: embeddings.DEFAULT_MARGIN, hint="a number from 0 to 1",
    ),
    Setting(
        lookup.SETTING, CHOICE, "who looks in your notes: Sympose or the persona",
        lookup.mode, lambda: lookup.AUTO, choices=(lookup.AUTO, lookup.ASK),
    ),
    Setting(
        lookup.ROUNDS_SETTING, NUMBER, "lookups the persona may make (ask)",
        lookup.rounds, lambda: lookup.DEFAULT_ROUNDS,
        hint=f"a whole number, 1 to {lookup.MAX_ROUNDS}", whole=True,
    ),
]


def find(key: str | None) -> Setting | None:
    return next((s for s in SETTINGS if s.key == key), None)
