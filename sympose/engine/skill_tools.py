"""The persona's tool for taking up a skill (docs/decisions/077, `skill_lookup` `ask`): `use_skill(name)` gives back the steps
of one of the skills the turn offered, bounded by `skill_cap`. Nothing is run and nothing is written; the steps are text the
persona follows with the tools she has. Called again, it gives another skill, so a message that needs two gets both."""

import json
from typing import Any

from sympose.engine import skills
from sympose.engine.lookup_result import Result

USE = "use_skill"
_BAD = "The arguments of use_skill could not be read: give name as text."


def tool(offered: list[skills.Skill]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": USE,
        "description": (
            "Take up one of the listed skills: you get its steps. Use it when the user's message asks for what a skill is for, then do "
            "the work by those steps; do not use it for anything else."
        ),
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "enum": [s.name for s in offered], "description": "The skill's name, exactly as listed."},
        }, "required": ["name"]},
    }}


def _name(raw: str | dict[str, Any] | None) -> str | None:
    try:
        data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return None
    return data["name"].strip() if isinstance(data, dict) and isinstance(data.get("name"), str) else None


def run(offered: list[skills.Skill], name: str, raw: str | dict[str, Any] | None) -> Result | None:
    """The tool's result, or `None` for a name that is not ours so it composes in `persona_tools`."""
    if name != USE:
        return None
    asked = _name(raw)
    if asked is None:
        return Result(_BAD, lookup={"tool": USE, "found": 0})
    skill = next((s for s in offered if s.name == asked), None)
    if skill is None:
        names = ", ".join(s.name for s in offered)
        return Result(f"There is no skill called {asked!r}. The skills are: {names}.", lookup={"tool": USE, "query": asked, "found": 0})
    return Result(skills.text_for(skill), lookup={"tool": USE, "query": skill.name, "found": 1})
