"""The slash-command registry. `/clear` and `/quit` are real, wired to
the actual engine's concurrency state (docs/decisions/008). `/history` was a mock command and was removed
until it is real (#111); `/compact` is real since docs/decisions/055, and `/sessions` (also `/history`) since docs/decisions/057."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str  # e.g. "/help", matched case-insensitively
    summary: str
    # Color-coded $error in listings — a destructive/reset action, not a
    # neutral one (mirrors `selection.SelectionOption.danger`).
    danger: bool = False
    # Whether the rest of the typed line, after the command name, is passed to
    # `runtime.run_command` as free text (docs/decisions/041's `/remember <text>`)
    # rather than discarded — every other command ignores anything typed after it.
    takes_args: bool = False


COMMANDS: list[SlashCommand] = [
    SlashCommand("/help", "List commands, and read the Sympose guide"),
    SlashCommand("/model", "Switch the active model"),
    SlashCommand("/persona", "Switch the active persona"),
    SlashCommand("/default", "Make the current persona the default"),
    SlashCommand("/grounding", "Show or hide which notes were used for a reply"),
    SlashCommand("/grounded", "List the notes used for the last reply"),
    SlashCommand("/context", "Explain the meter under the chat box"),
    SlashCommand("/compact", "Condense the earlier part of this conversation"),
    SlashCommand("/sessions", "List, open, rename, pin or delete past conversations", takes_args=True),
    SlashCommand("/history", "The same as /sessions", takes_args=True),
    SlashCommand("/remember", "Save something to decisions.md, in your own words", takes_args=True),
    SlashCommand("/memory", "Update or review what the persona remembers about you"),
    SlashCommand("/share", "Choose what cloud models may receive"),
    SlashCommand("/clear", "Clear the transcript", danger=True),
    SlashCommand("/settings", "Change the settings"),
    SlashCommand("/quit", "Exit the CLI"),
]


def matching_commands(prefix: str) -> list[SlashCommand]:
    """Commands whose name starts with `prefix` — feeds the live
    `/`-autocomplete overlay as more of the command is typed."""
    needle = prefix.lower()
    return [c for c in COMMANDS if c.name.startswith(needle)]


def find_command(name: str) -> SlashCommand | None:
    needle = name.lower()
    return next((c for c in COMMANDS if c.name == needle), None)
