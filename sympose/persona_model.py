"""Saving what the user chose for a persona: her model (docs/decisions/044, 046), from the terminal's `/model` and the
web app's picker alike, her edit mode (docs/decisions/072) and the skills she carries (docs/decisions/077). A pick goes
into `persona.local.yaml` beside the persona, an untracked file the app owns, never into the shipped `persona.yaml`: what
is committed stays exactly the defaults. The local file holds only `model:`, `edit_mode:`, `skills_on:` and `skills_off:`,
each pick keeps the others, and it is written whole and atomically; clearing the last pick deletes the file."""

import logging
import os
import threading
from typing import Any

import yaml

from sympose.atomic_write import write_atomic_text
from sympose.engine import edit_mode
from sympose.persona_files import PERSONA_FILENAME, PERSONA_LOCAL_FILENAME, persona_dir, profiles_dir
from sympose.profile import local_overrides
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

_LOCK = threading.Lock()  # one write of a persona's override at a time


def set_model(handle: str, model: str | None) -> bool:
    """Save `model` as the persona's own (`None` removes it, so the shipped file's model, the setting or
    the default applies). `False` when it could not be done: no such persona, or a failed write."""
    return _set(handle, "model", model)


def set_edit_mode(handle: str, mode: str | None) -> bool:
    """Save `mode` as the persona's own edit mode (`None` removes it, so her shipped file's, the global setting's or
    `manual` applies). `False` when it could not be done: not one of the modes, no such persona, or a failed write."""
    if mode is not None and edit_mode.valid(mode) is None:
        return False
    return _set(handle, "edit_mode", mode)


def set_skills(handle: str, names: list[str] | None) -> bool:
    """Save `names` as the skills the persona carries now, as what differs from the shipped file's list: `skills_on` the
    ones it does not name, `skills_off` the ones it names that are left out, so a skill a later release adds to the shipped
    list is on unless it was switched off. `None` removes both, so the shipped list applies again. `False` when it could
    not be done: no such persona, or a failed write."""
    if names is None:
        return _set(handle, {"skills": None, "skills_on": None, "skills_off": None})
    try:
        with open(os.path.join(persona_dir(handle), PERSONA_FILENAME), encoding="utf-8") as f:
            shipped = (yaml.safe_load(f) or {}).get("skills")
    except (ValueError, OSError, UnicodeDecodeError, yaml.YAMLError, AttributeError):
        return False
    shipped = [n for n in shipped if isinstance(n, str)] if isinstance(shipped, list) else []
    return _set(
        handle,
        {
            "skills": None,  # an older full list, now said as the two below
            "skills_on": [n for n in dict.fromkeys(names) if n not in shipped] or None,
            "skills_off": [n for n in shipped if n not in names] or None,
        },
    )


def _set(handle: str, key: str | dict[str, Any], value: Any = None) -> bool:
    try:
        folder = persona_dir(handle)
    except ValueError:
        return False
    local = os.path.join(folder, PERSONA_LOCAL_FILENAME)
    if not is_safe_path(local, profiles_dir()) or not os.path.isfile(os.path.join(folder, PERSONA_FILENAME)):
        return False
    with _LOCK:
        try:
            kept = local_overrides(local)
            for k, v in (key if isinstance(key, dict) else {key: value}).items():
                kept.pop(k, None)
                if v is not None:
                    kept[k] = v
            if kept:
                write_atomic_text(local, yaml.safe_dump(kept, default_flow_style=False))
            elif os.path.isfile(local):
                os.unlink(local)
            return True
        except OSError as e:
            log.warning("Couldn't save %s into %s: %s", key, local, e)
            return False
