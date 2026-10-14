"""Adding, reading and switching a persona's skills from Settings (docs/decisions/077, the amendment of 2026-10-14).

A skill is text, never run. The user points at a skill's folder; the server (on the user's own computer) checks its
`SKILL.md` by the rules `skills.check` has, copies that one file into the persona's `skills/` folder and leaves it
**off**: nothing in a folder the user did not write reaches a prompt until it has been read and switched on. Switching
writes what differs from the persona's shipped `skills:` list into `persona.local.yaml` (`persona_model.set_skills`).
A refusal is a `SkillRefused` whose message is for the user."""

import os
import threading
from typing import Any

from sympose import persona_model
from sympose.atomic_write import write_atomic_text
from sympose.engine import skills
from sympose.persona_files import profiles_dir
from sympose.profile import get_profile
from sympose.security import is_safe_path


_LOCK = threading.Lock()  # a switch reads her list and writes it back: two at once must not lose one


class SkillRefused(ValueError):
    """A request the user's skill folder, name or persona cannot satisfy; the message says why, plainly."""


def _persona(handle: str) -> dict[str, Any]:
    persona = get_profile(handle)
    if persona is None:
        raise SkillRefused(f"There is no persona called {handle}.")
    return persona


def _names(persona: dict[str, Any]) -> list[str]:
    """The skills her list names; a value that is not a list of names (a hand-written mistake) names none, as the engine reads it."""
    names = persona["skills"]
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def _row(skill: skills.Skill, persona: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": skill.name,
        "description": skill.description,
        "own": skill.source == "persona",
        "enabled": skill.name in _names(persona),
        "length": len(skill.body),
        "cap": skills.cap(),
        "tools": list(skill.tools),
    }


def listing(handle: str) -> list[dict[str, Any]]:
    persona = _persona(handle)
    return sorted((_row(s, persona) for s in skills.available(persona)), key=lambda r: r["name"])


def read(handle: str, name: str) -> dict[str, Any]:
    """One skill's row and its `SKILL.md` exactly as stored, for the user to read before it is switched on."""
    persona = _persona(handle)
    skill = next((s for s in skills.available(persona) if s.name == name), None)
    if skill is None:
        raise SkillRefused(f"There is no skill called {name}.")
    folder = skills.own_dir(persona["handle"]) if skill.source == "persona" else skills.BUNDLED_DIR
    try:
        with open(os.path.join(folder, name, skills.FILENAME), encoding="utf-8-sig") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        raise SkillRefused(f"Couldn't read {name}.") from None
    return {**_row(skill, persona), "text": text}


def add(handle: str, folder: str) -> dict[str, Any]:
    """Copy the `SKILL.md` of the skill folder at `folder` into the persona's own skills, off. Answers with the new row
    and `left_out`, how many other things (hidden files aside) sat in that folder and were not copied: nothing else is ever read."""
    with _LOCK:
        return _add(handle, folder)


def _add(handle: str, folder: str) -> dict[str, Any]:
    persona = _persona(handle)
    source = os.path.normpath(os.path.expanduser(folder.strip()))
    if not folder.strip() or not os.path.isabs(source):
        raise SkillRefused("Give the folder's full path, for example /Users/you/skills/my-skill.")
    if not os.path.isdir(source):
        raise SkillRefused("There is no folder at that path.")
    path = os.path.join(source, skills.FILENAME)
    if not os.path.isfile(path):
        raise SkillRefused(f"That folder has no {skills.FILENAME}.")
    if os.path.getsize(path) > skills.MAX_FILE:
        raise SkillRefused(f"{skills.FILENAME} is over {skills.MAX_FILE:,} bytes, more than Sympose reads.")
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        raise SkillRefused(f"Couldn't read {skills.FILENAME} as text.") from None
    found = skills.check(text, os.path.basename(source))
    if not isinstance(found, skills.Skill):
        raise SkillRefused(found)
    if found.name in {s.name for s in skills.available(persona)}:
        raise SkillRefused(f"{persona['name']} already has a skill called {found.name}.")
    target = os.path.join(skills.own_dir(persona["handle"]), found.name)
    if not is_safe_path(target, profiles_dir()):
        raise SkillRefused("That skill can't be saved here.")
    if found.name in _names(persona):  # a name left in her list by a folder deleted by hand must not switch this one on
        if not persona_model.set_skills(persona["handle"], [n for n in _names(persona) if n != found.name]):
            raise SkillRefused(f"Couldn't save the change for {persona['name']}.")
        persona = _persona(handle)
    try:
        os.makedirs(target, exist_ok=True)
        write_atomic_text(os.path.join(target, skills.FILENAME), text)
    except OSError:
        raise SkillRefused(f"Couldn't save {found.name}. Check that the persona's folder can be written.") from None
    left_out = sum(1 for n in os.listdir(source) if n != skills.FILENAME and not n.startswith("."))
    return {"skill": _row(found, persona), "left_out": left_out}


def set_enabled(handle: str, name: str, enabled: bool) -> dict[str, Any]:
    """Switch a skill on or off for the persona: its name goes into, or out of, the list she carries."""
    with _LOCK:
        persona = _persona(handle)
        skill = next((s for s in skills.available(persona) if s.name == name), None)
        if skill is None:
            raise SkillRefused(f"There is no skill called {name}.")
        names = [n for n in _names(persona) if n != name]
        if enabled:
            names.append(name)
        if not persona_model.set_skills(persona["handle"], names):
            raise SkillRefused(f"Couldn't save the change for {persona['name']}.")
        return _row(skill, _persona(handle))
