"""The shape of a look value (docs/decisions/062, 064): the name of an icon and a colour, as a persona's
`persona.yaml` and a folder's definition note both write them. The value ends up in the web app (an icon's name, a
colour in a style attribute), so one of any other shape is ignored rather than passed on."""

import re
from typing import Any

ICON_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
COLOR = re.compile(r"[#a-zA-Z0-9(),.%/ -]{1,64}")


def clean(value: Any, pattern: re.Pattern[str]) -> str | None:
    """`value` as a short string of the safe shape `pattern`, else `None`: a bad look value never costs its owner
    its place."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if pattern.fullmatch(value) else None

# The names of the icons the web app draws (`ui/src/lib/persona-icons.ts`, the one set it ships). The engine needs them to
# offer a persona a choice and to refuse a name the app could not draw (docs/decisions/078); a test pins that the two lists
# are the same.
ICON_NAMES = (
    "anchor", "atom", "bird", "book", "book-open", "brain", "camera", "chart", "chef", "code", "coins", "compass", "crown",
    "dna", "fire", "flash", "ghost", "globe", "graduation", "home", "idea", "key", "lamp", "leaf", "mic", "moon", "music",
    "paintbrush", "pen", "plant", "rocket", "shield", "star", "stethoscope", "sun", "telescope", "user", "wrench", "calendar",
    "chef-hat", "copy", "film-roll", "folder", "folder-library", "hourglass", "paintbrush-2", "pencil-edit", "quote",
    "source-code", "users",
)
