"""Saving a persona's own model (docs/decisions/044, 046), from the terminal's `/model` and the web app's
picker alike. The pick goes into `persona.local.yaml` beside the persona, an untracked file the app owns,
never into the shipped `persona.yaml`: what is committed stays exactly the defaults. The local file holds
only `model:` and is written whole and atomically; clearing the pick deletes it."""

import logging
import os
import threading

import yaml

from sympose.atomic_write import write_atomic_text
from sympose.persona_files import PERSONA_FILENAME, PERSONA_LOCAL_FILENAME, persona_dir, profiles_dir
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

_LOCK = threading.Lock()  # one write of a persona's override at a time


def set_model(handle: str, model: str | None) -> bool:
    """Save `model` as the persona's own (`None` removes it, so the shipped file's model, the setting or
    the default applies). `False` when it could not be done: no such persona, or a failed write."""
    try:
        folder = persona_dir(handle)
    except ValueError:
        return False
    local = os.path.join(folder, PERSONA_LOCAL_FILENAME)
    if not is_safe_path(local, profiles_dir()) or not os.path.isfile(os.path.join(folder, PERSONA_FILENAME)):
        return False
    with _LOCK:
        try:
            if model is None:
                if os.path.isfile(local):
                    os.unlink(local)
            else:
                write_atomic_text(local, yaml.safe_dump({"model": model}, default_flow_style=False))
            return True
        except OSError as e:
            log.warning("Couldn't save the model into %s: %s", local, e)
            return False
