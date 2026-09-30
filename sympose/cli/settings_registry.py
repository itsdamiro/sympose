"""The settings `/settings` lists (docs/decisions/036): the terminal's display knobs, then the engine
settings every channel shares. Each row names the module's own key and accessor, so the screen never
holds a second copy of a rule."""

from sympose.cli.display_settings import SETTINGS as DISPLAY_SETTINGS
from sympose.engine.settings_registry import CHOICE, NUMBER, SETTINGS as ENGINE_SETTINGS, TOGGLE, Setting

__all__ = ["CHOICE", "NUMBER", "TOGGLE", "SETTINGS", "Setting", "find"]

SETTINGS: list[Setting] = [*DISPLAY_SETTINGS, *ENGINE_SETTINGS]


def find(key: str | None) -> Setting | None:
    return next((s for s in SETTINGS if s.key == key), None)
