"""The engine settings both channels list (docs/decisions/036, 044). Each row names the module's own
key and accessor, so what is valid, and what the default is, stays where the setting is read: a screen
never holds a second copy of a rule. Settings that only change how one channel draws things are that
channel's own (the terminal's are in `cli/display_settings.py`)."""

from dataclasses import dataclass
from typing import Any, Callable

from sympose.engine import budget, compaction, edit_mode, edit_turn, open_comments, embeddings, followup, history_cap, lookup, memory, memory_refresh, model_wait, parallel, past_chats, recap, related

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
    group: str = ""  # the section a screen lists it under


def toggle(key: str, summary: str, current: Callable[[], bool], default: bool = True, group: str = "") -> Setting:
    """A true or false setting. Ships on unless `default=False` is passed (memory_remember: the user's
    own call to trust a model with even a safe write, docs/decisions/041), so flipping back to the
    default removes the key rather than writing it explicitly."""
    return Setting(key, TOGGLE, summary, current, lambda: default, group=group)


CONTEXT, SEARCH, LOOKUP, MEMORY, CONVERSATIONS, EDITING = "Conversation memory", "Search", "Searching notes", "Memory", "Conversations", "Editing"
GROUPS = (CONTEXT, SEARCH, LOOKUP, MEMORY, CONVERSATIONS, EDITING)

SETTINGS: list[Setting] = [
    Setting(
        budget.CONTEXT_SETTING, NUMBER, "how much text a local model takes", budget.context_setting,
        hint="a number, 2048 or more (a token is roughly a word); leave empty for automatic", whole=True, group=CONTEXT,
    ),
    Setting(
        budget.REPLY_SETTING, NUMBER, "space kept for the reply", budget.reply_setting,
        hint="a number, 64 or more (a token is roughly a word); leave empty for automatic", whole=True, group=CONTEXT,
    ),
    Setting(
        history_cap.SETTING, NUMBER, "most earlier chat sent per message", history_cap.chosen,
        hint=f"a number, {history_cap.MIN_TOKENS} or more (a token is roughly a word); leave empty for no limit", whole=True, group=CONTEXT,
    ),
    Setting(
        model_wait.SETTING, NUMBER, "how long a model may take to answer", model_wait.chosen,
        hint=f"seconds, {model_wait.MIN_SECONDS} to {model_wait.MAX_SECONDS}; empty for automatic", whole=True, group=CONTEXT,
    ),
    Setting(
        followup.SETTING, CHOICE, "a second search for follow-up questions",
        lambda: ON if followup.enabled() else OFF, lambda: ON, choices=(ON, OFF), group=CONTEXT,
    ),
    toggle(recap.SETTING, "recaps of your earlier conversations", recap.enabled, group=CONTEXT),
    Setting(
        recap.COUNT_SETTING, NUMBER, "how many recaps are read", recap.read_count,
        lambda: recap.DEFAULT_COUNT, hint=f"a whole number, {recap.COUNT_RANGE[0]} to {recap.COUNT_RANGE[1]}", whole=True, group=CONTEXT,
    ),
    Setting(
        recap.CHARS_SETTING, NUMBER, "how much of each recap is read", recap.read_chars,
        lambda: recap.DEFAULT_CHARS, hint=f"characters, {recap.CHARS_RANGE[0]} to {recap.CHARS_RANGE[1]}", whole=True, group=CONTEXT,
    ),
    Setting(
        past_chats.SETTING, CHOICE, "past chats word for word (auto: local, ask: cloud)", past_chats.mode,
        lambda: past_chats.OFF, choices=past_chats.MODES, group=CONTEXT,
    ),
    Setting(
        related.SETTING, CHOICE, "suggest related notes", related.mode,
        lambda: related.AUTO, choices=related.MODES, group=CONTEXT,
    ),
    Setting(
        related.LEVEL_SETTING, CHOICE, "how similar they must be", related.level,
        lambda: related.BALANCED, choices=related.LEVELS, group=CONTEXT,
    ),
    toggle(compaction.SETTING, "condensing a long conversation on its own", compaction.enabled, group=CONTEXT),
    Setting(
        compaction.AT_SETTING, NUMBER, "percent full when it is condensed", compaction.at_percent,
        lambda: compaction.DEFAULT_AT, hint="percent of the space the model has for the conversation, 10 to 95", whole=True, group=CONTEXT,
    ),
    Setting(
        compaction.TO_SETTING, NUMBER, "percent full after it is condensed", compaction.to_percent,
        lambda: compaction.DEFAULT_TO, hint="percent, 10 to 95, below the one above", whole=True, group=CONTEXT,
    ),
    Setting(
        embeddings.MODE_SETTING, CHOICE, "how notes are searched", embeddings.mode,
        lambda: embeddings.DEFAULT_MODE, group=SEARCH,
        choices=(embeddings.AUTO, embeddings.KEYWORDS, embeddings.EMBEDDINGS, embeddings.HYBRID),
    ),
    Setting(
        embeddings.THRESHOLD_SETTING, NUMBER, "how alike a note must be", embeddings.min_similarity,
        lambda: embeddings.DEFAULT_THRESHOLD, hint="a number between 0 and 1, not including them", group=SEARCH,
    ),
    Setting(
        embeddings.MARGIN_SETTING, NUMBER, "how near the best a note must be", embeddings.margin,
        lambda: embeddings.DEFAULT_MARGIN, hint="a number from 0 to 1", group=SEARCH,
    ),
    Setting(
        lookup.SETTING, CHOICE, "who searches your notes (persona/auto/ask)",
        lookup.mode, lambda: lookup.BY_MODEL, choices=(lookup.BY_MODEL, lookup.AUTO, lookup.ASK), group=LOOKUP,
    ),
    Setting(
        lookup.ROUNDS_SETTING, NUMBER, "searches allowed per message",
        lookup.rounds, lambda: lookup.DEFAULT_ROUNDS, group=LOOKUP,
        hint=f"a whole number, 1 to {lookup.MAX_ROUNDS}", whole=True,
    ),
    toggle(
        memory.REMEMBER_SETTING, "adding to decisions.md when asked to remember",
        memory.remember_enabled, default=False, group=MEMORY,
    ),
    Setting(
        memory_refresh.SETTING, CHOICE, "memory updates: ask first, or apply directly",
        memory_refresh.mode, lambda: memory_refresh.ASK, group=MEMORY,
        choices=(memory_refresh.ASK, memory_refresh.AUTO),
    ),
    toggle(
        memory_refresh.AUTO_REFRESH_SETTING, "checking for a memory update on its own",
        memory_refresh.auto_refresh_enabled, default=False, group=MEMORY,
    ),
    Setting(
        parallel.SETTING, CHOICE, "replies in several conversations at once",
        parallel.mode, lambda: parallel.AUTO, choices=(parallel.AUTO, parallel.ON, parallel.OFF), group=CONVERSATIONS,
    ),
    Setting(
        edit_mode.SETTING, CHOICE, "what the persona does to notes before you accept",
        edit_mode.mode, lambda: edit_mode.DEFAULT, choices=edit_mode.MODES, group=EDITING,
    ),
    Setting(
        edit_turn.CAP_SETTING, NUMBER, "open note text the persona sees", edit_turn.cap,
        lambda: edit_turn.DEFAULT_CAP, hint=f"characters, {edit_turn.MIN_CAP} or more", whole=True, group=EDITING,
    ),
    Setting(
        open_comments.CAP_SETTING, NUMBER, "open comments the persona is shown", open_comments.cap,
        lambda: open_comments.DEFAULT_CAP, hint="a whole number, 1 or more", whole=True, group=EDITING,
    ),
]


def find(key: str | None) -> Setting | None:
    return next((s for s in SETTINGS if s.key == key), None)
