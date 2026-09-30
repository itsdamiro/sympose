"""Reading and changing an engine setting, the same way for every channel (docs/decisions/036, 044).
A value is saved through `settings_store` and read back through the module that owns the setting,
which decides whether it is valid; what it refuses is put back as it was."""

import math

from sympose import settings_store
from sympose.engine.settings_registry import CHOICE, TOGGLE, Setting

_MISSING = object()


def value_text(setting: Setting) -> str:
    """`on`, `keywords`, `50 (default)`, `8192`, or `automatic`: the value in force."""
    value = setting.current()
    if setting.kind == TOGGLE:
        return "on" if value else "off"
    if setting.kind == CHOICE:
        return str(value)
    if value is None:
        return "automatic"
    return str(value) + ("" if settings_store.get(setting.key) is not None else " (default)")


def set_value(setting: Setting, wanted: object) -> tuple[str, bool]:
    """Move a toggle or a choice to `wanted`, and say what happened (with whether it was saved). The default's value removes the
    key, so the default applies again (and follows a later change of it)."""
    if setting.kind == TOGGLE and not isinstance(wanted, bool) or setting.kind == CHOICE and wanted not in setting.choices:
        return f"{wanted} is not a value for {setting.key}.", False
    saved = settings_store.remove(setting.key) if wanted == setting.default() else settings_store.set(setting.key, wanted)
    if not saved or setting.current() != wanted:
        return f"Couldn't save {setting.key}.", False
    return f"{setting.key} is now {value_text(setting)}.", True


def flip(setting: Setting) -> str:
    """Move a toggle on or off, or a choice to the next value."""
    if setting.kind == TOGGLE:
        return set_value(setting, not setting.current())[0]
    values = setting.choices
    return set_value(setting, values[(values.index(setting.current()) + 1) % len(values)])[0]


def _parse(setting: Setting, text: str) -> int | float | None:
    try:
        value = int(text) if setting.whole else float(text)
    except ValueError:
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return int(value) if value.is_integer() else value
    return value


def set_number(setting: Setting, text: str) -> tuple[str, bool]:
    """Save what was typed and say what happened; `True` when that ends the prompt (saved, adjusted or
    reset), `False` when it stays open (not a number, not valid, or not saved)."""
    text = text.strip()
    key = setting.key
    if not text:
        if not settings_store.remove(key):
            return f"Couldn't save {key}.", False
        return f"{key} is back to {value_text(setting)}.", True
    value = _parse(setting, text)
    if value is None:
        return f"'{text}' is not {'a whole number' if setting.whole else 'a number'}: {setting.hint}.", False
    previous = settings_store.get(key, _MISSING)
    if not settings_store.set(key, value):
        return f"Couldn't save {key}.", False
    now = setting.current()
    if now == value:
        return f"{key} is now {value_text(setting)}.", True
    if now == setting.default():  # the module does not accept it: put it back as it was
        restored = settings_store.remove(key) if previous is _MISSING else settings_store.set(key, previous)
        if not restored:
            return f"{text} is not valid for {key}: {setting.hint}. Couldn't put it back: check settings.json.", False
        return f"{text} is not valid for {key}: {setting.hint}. It is left as it was.", False
    return f"{key} is now {value_text(setting)} ({text} was adjusted: {setting.hint}).", True

