"""The generic note template (docs/decisions/038): the frontmatter a note starts with when no template was made for its
folder. `Templates/Note template.md` when the vault has one (the user's own words win), otherwise a list of keys the user
can change, `note_template_keys`, default `title`, `created` and `tags`. Nothing here reads a note or calls a model."""

import os
import re

from sympose import settings_store

KEYS_SETTING = "note_template_keys"
DEFAULT_KEYS = ["title", "created", "tags"]
KEY = re.compile(r"\w[\w -]*")  # a plain property name: `role`, `date created`
_STARTS = {"title": '"{{title}}"', "created": "{{date}}", "tags": "[]"}  # any other key starts empty
VAULT_FILE = os.path.join("Templates", "Note template.md")
FROM_VAULT, FROM_SETTINGS = "vault", "settings"


def keys() -> list[str]:
    """The user's `note_template_keys`, else `title`, `created`, `tags`. Only a list of plain property names (no space at either end) that
    includes `title` counts (a note must have a title); anything else leaves the default."""
    value = settings_store.get(KEYS_SETTING)
    usable = isinstance(value, list) and all(isinstance(k, str) and KEY.fullmatch(k) and k == k.strip() for k in value) and "title" in value
    return list(dict.fromkeys(value)) if usable else list(DEFAULT_KEYS)


def frontmatter_lines(text: str) -> list[str]:
    """The property lines between the rules at the top of a template file; `[]` when it has none."""
    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    return [line.rstrip() for line in lines[1:end] if line.strip()]


def key_lines() -> list[str]:
    """The setting's keys as property lines, with the placeholders a template file uses."""
    return [f"{key}: {_STARTS.get(key, '')}".rstrip() for key in keys()]


def lines_for(vault: str) -> tuple[list[str], str]:
    """The generic template's property lines for the vault at `vault`, and where they came from: the frontmatter of
    its `Templates/Note template.md` when that has some, otherwise the setting's keys."""
    try:
        with open(os.path.join(vault, VAULT_FILE), encoding="utf-8") as f:
            own = frontmatter_lines(f.read())
    except (OSError, ValueError):  # ValueError: not valid UTF-8
        own = []
    return (own, FROM_VAULT) if own else (key_lines(), FROM_SETTINGS)


def text() -> str:
    """The setting's keys as the frontmatter a new note starts with, before its placeholders are filled."""
    return "---\n" + "\n".join(key_lines()) + "\n---"
