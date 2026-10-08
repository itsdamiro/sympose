"""Making a new persona (docs/decisions/078): the checks a proposal passes before the user is asked, and the one function
that creates the files, so a persona's proposal and a future "new persona" button end in the same place.

`problem` answers a proposal with the first thing wrong with it, in words the proposing persona can act on (the way
`table_spans.problem` does); `create` writes `profiles/<handle>/persona.yaml` and `soul.md` and nothing else, never over
a folder that exists. Nothing here reads or writes the vault."""

import os
import re
from dataclasses import dataclass
from typing import Any

import yaml

from sympose import folder_definitions, look, vault_paths
from sympose.atomic_write import write_atomic_text
from sympose.engine import edit_mode
from sympose.persona_files import PERSONA_FILENAME, SOUL_FILENAME, persona_dir, profiles_dir

MAX_NAME = 40
MAX_TITLE = 80
SOUL_LIMIT = 2500  # characters; ADR 012 asks for about 1,500, so a soul over this is not voice only
_HANDLE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class Draft:
    name: str
    title: str
    soul: str
    icon: str
    accent: str
    accent_dark: str
    folders: tuple[str, ...]
    edit_mode: str


def handle_for(name: str) -> str:
    """A handle from a name: lower case, letters and digits, a single hyphen between words (`Marie Curie` -> `marie-curie`)."""
    return "-".join(re.findall(r"[a-z0-9]+", name.lower()))


def readable_folders(profile: dict[str, Any]) -> list[str]:
    """The folders of the vault `profile` may read, as vault-relative paths: the top-level folders of the user's content
    when she reads the whole vault, else the folders her scope names. A new persona's folders are chosen among these."""
    sandbox = vault_paths.resolve_sandbox(profile)
    if sandbox is None:
        return []
    vault, allowed = sandbox
    prefixes = vault_paths.scope_prefixes(vault, allowed)
    if prefixes != [""]:
        return sorted(prefixes)
    return sorted(n for n in os.listdir(vault) if os.path.isdir(os.path.join(vault, n)) and folder_definitions.can_have_definition(n))


def problem(draft: Draft, proposer: dict[str, Any], tool_names: tuple[str, ...], reveal_folders: bool = True) -> str | None:
    """The first thing wrong with `draft` as a proposal from `proposer`, said so the model can fix it, or `None`.
    `tool_names` are the engine's real tool names and markers: a soul that names one is describing powers, not a voice.
    `reveal_folders` is whether the vault's folder names may be said to the model (a cloud model the user has not allowed
    them); a proposal may have no folders, since the user chooses them on the card, and accepting needs at least one."""
    if not draft.name.strip() or len(draft.name) > MAX_NAME:
        return f"Give a name of at most {MAX_NAME} characters."
    handle = handle_for(draft.name)
    if not _HANDLE.fullmatch(handle):
        return "The name needs at least one letter or digit."
    if os.path.exists(persona_dir(handle)):
        return f"A persona called {handle} already exists; propose another name."
    if len(draft.title) > MAX_TITLE:
        return f"The title is over {MAX_TITLE} characters; shorten it."
    if draft.icon not in look.ICON_NAMES:
        return "The icon must be one of: " + ", ".join(look.ICON_NAMES) + "."
    for label, colour in (("accent", draft.accent), ("accent_dark", draft.accent_dark)):
        if look.clean(colour, look.COLOR) is None:
            return f"{label} must be a colour such as #3366cc, rgb(51, 102, 204) or oklch(0.55 0.13 233)."
    soul = draft.soul.strip()
    if not soul:
        return "Give the soul: how this persona talks and what it is like to talk to."
    if len(soul) > SOUL_LIMIT:
        return f"The soul is {len(soul)} characters; keep it near 1,500 and under {SOUL_LIMIT}. A soul is voice and temperament only."
    named = next((t for t in tool_names if t in soul), None)
    if named is not None:
        return f"The soul mentions {named}. A soul is voice and temperament only: leave out what the persona can do and which tools it has."
    if draft.edit_mode not in edit_mode.MODES:
        return "edit_mode must be one of: " + ", ".join(edit_mode.MODES) + "."
    readable = readable_folders(proposer)
    stray = [f for f in draft.folders if f not in readable]
    if stray:
        if not reveal_folders:
            return "One of the folders is not one you can read. Leave the folders out: the user chooses them on the card."
        return f"These are not folders you can read: {', '.join(stray)}. The folders are: {', '.join(readable) or 'none'}."
    return None


def create(draft: Draft) -> str:
    """Create the persona and return its handle. Raises `FileExistsError` when the handle is taken, so a second Accept
    or a race can never overwrite a persona."""
    handle = handle_for(draft.name)
    folder = persona_dir(handle)
    os.makedirs(profiles_dir(), exist_ok=True)
    os.mkdir(folder)  # fails if it exists: the one check that cannot race
    data = {
        "name": draft.name.strip(), "handle": handle, **({"title": draft.title.strip()} if draft.title.strip() else {}),
        "icon": draft.icon, "accent": draft.accent.strip(), "accent_dark": draft.accent_dark.strip(),
        "edit_mode": draft.edit_mode, "vault_folders": list(draft.folders),
    }
    write_atomic_text(os.path.join(folder, PERSONA_FILENAME), yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    write_atomic_text(os.path.join(folder, SOUL_FILENAME), draft.soul.strip() + "\n")
    return handle
