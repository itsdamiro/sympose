"""Saving a persona's own model into its `persona.yaml` (docs/decisions/044), from the terminal's `/model`
and the web app's picker alike. The file is hand-written and carries comments, so it is never re-dumped:
only the top-level `model:` line is replaced, appended or removed, line endings and a byte-order mark are
kept, and nothing is written unless the edited text parses to exactly the old data with only `model`
changed (a `model:` written as a block, or a file that is not valid YAML, is left alone)."""

import logging
import os
import re
import threading

import yaml

from sympose.atomic_write import write_atomic_text
from sympose.persona_files import PERSONA_FILENAME, persona_dir, profiles_dir
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

_LOCK = threading.Lock()  # one read-modify-write of a persona file at a time
_MODEL_LINE = re.compile(r"^model[ \t]*:.*(?:\r?\n|$)", re.MULTILINE)


def _edited(text: str, model: str | None) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    found = _MODEL_LINE.search(text)
    line = "" if model is None else f"model: '{model.replace(chr(39), chr(39) * 2)}'"
    if found:
        return text[: found.start()] + (line + newline if line and found.group().endswith(("\n", "\r")) else line) + text[found.end() :]
    if not line:
        return text
    return text + ("" if not text or text.endswith("\n") else newline) + line + newline


def set_model(handle: str, model: str | None) -> bool:
    """Save `model` as the persona's own (`None` removes it, so the setting or the default applies).
    `False`, with the file untouched, when it could not be done safely."""
    try:
        path = os.path.join(persona_dir(handle), PERSONA_FILENAME)
    except ValueError:
        return False
    if not is_safe_path(path, profiles_dir()):
        return False
    with _LOCK:
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                old = f.read()
            before = yaml.safe_load(old)
            if not isinstance(before, dict):
                return False
            new = _edited(old, model)
            after = yaml.safe_load(new)
            expected = {k: v for k, v in before.items() if k != "model"} | ({} if model is None else {"model": model})
            if after != expected:
                log.warning("Not saving the model into %s: the edit could not be verified.", path)
                return False
            if new != old:
                write_atomic_text(path, new, newline="")
            return True
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            log.warning("Couldn't save the model into %s: %s", path, e)
            return False
