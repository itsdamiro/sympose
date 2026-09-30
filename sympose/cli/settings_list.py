"""`/settings` (docs/decisions/036): a numbered list of the settings a user would tune. A toggle flips
and a choice steps when its row is chosen; a number is typed into the chat box, which asks for it until
Enter or Esc. A value is saved and read back through the module that owns the setting, which decides
whether it is valid (`settings_registry`)."""

from sympose.cli import picker, transcript as transcript_mod
from sympose.cli.composer import DEFAULT_PLACEHOLDER
from sympose.cli.selection import SelectionOption
from sympose.cli.settings_registry import NUMBER, SETTINGS, find
from sympose.engine.settings_apply import flip, set_number, value_text

PICKER_KIND = "settings"


def options() -> list[SelectionOption]:
    return [SelectionOption(f"{s.key} — {value_text(s)}: {s.summary}", s.key) for s in SETTINGS]


async def open_picker(app, highlight: str | None = None) -> None:
    """The list, on the row just changed when there is one (so several can be changed in a row)."""
    row = next((i for i, s in enumerate(SETTINGS) if s.key == highlight), -1)
    await picker.open_picker(app, PICKER_KIND, "Settings (Esc when done)", options(), highlight=row)


def choose(app, key: str) -> bool:
    """A row was chosen. `True` when the list should open again at once (a toggle or a choice was
    changed); a number row starts the prompt instead."""
    setting = find(key)
    if setting is None:
        return False
    if setting.kind == NUMBER:
        app.pending_setting = key
        app.composer.placeholder = f"{key}: {setting.hint} · Esc cancels"
        return False
    transcript_mod.mount_line(app, flip(setting), "system")
    app.transcript.scroll_end(animate=False)
    return True


def _end_prompt(app) -> None:
    app.pending_setting = None
    app.composer.placeholder = DEFAULT_PLACEHOLDER


async def submit(app, text: str) -> None:
    """A line typed while a number is being asked for."""
    setting = find(app.pending_setting)
    if setting is None:
        _end_prompt(app)
        return
    message, done = set_number(setting, text)
    transcript_mod.mount_line(app, message, "system")
    app.transcript.scroll_end(animate=False)
    if done:
        _end_prompt(app)
        await open_picker(app, setting.key)


def cancel(app) -> None:
    app.composer.value = ""  # what was half typed is not a message to send
    _end_prompt(app)
    transcript_mod.mount_line(app, "Left as it was.", "system")
    app.transcript.scroll_end(animate=False)
