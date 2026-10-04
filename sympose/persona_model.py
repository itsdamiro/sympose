"""Saving what the user chose for a persona: her model (docs/decisions/044, 046), from the terminal's `/model` and the
web app's picker alike, and her edit mode (docs/decisions/072). A pick goes into `persona.local.yaml` beside the
persona, an untracked file the app owns, never into the shipped `persona.yaml`: what is committed stays exactly the
defaults. The local file holds only `model:` and `edit_mode:`, each pick keeps the other, and it is written whole and
atomically; clearing the last pick deletes the file."""

import logging
import os
import threading

import yaml

from sympose.atomic_write import write_atomic_text
from sympose.engine import edit_mode
from sympose.persona_files import PERSONA_FILENAME, PERSONA_LOCAL_FILENAME, persona_dir, profiles_dir
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

_LOCK = threading.Lock()  # one write of a persona's override at a time
_KEYS = ("model", "edit_mode")


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


def _read(local: str) -> dict[str, str]:
    """What the local file holds that is ours; a missing, broken or foreign file holds nothing."""
    try:
        with open(local, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return {k: v for k in _KEYS if isinstance(data, dict) and isinstance(v := data.get(k), str) and v.strip()}


def _set(handle: str, key: str, value: str | None) -> bool:
    try:
        folder = persona_dir(handle)
    except ValueError:
        return False
    local = os.path.join(folder, PERSONA_LOCAL_FILENAME)
    if not is_safe_path(local, profiles_dir()) or not os.path.isfile(os.path.join(folder, PERSONA_FILENAME)):
        return False
    with _LOCK:
        try:
            kept = _read(local)
            kept.pop(key, None)
            if value is not None:
                kept[key] = value
            if kept:
                write_atomic_text(local, yaml.safe_dump(kept, default_flow_style=False))
            elif os.path.isfile(local):
                os.unlink(local)
            return True
        except OSError as e:
            log.warning("Couldn't save %s into %s: %s", key, local, e)
            return False
