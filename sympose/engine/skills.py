"""Skills (docs/decisions/077): folders of know-how, each a `SKILL.md` with a `name` and a `description` in its header
and the steps as its body. A skill is text only: it tells the persona what to do with the tools she already has, and
nothing in a skill is ever run.

Where they live: the bundled ones in `sympose/skills/` (a persona carries those her `persona.yaml` names under
`skills:`), and the user's own in `profiles/<handle>/skills/` (a persona carries all of its own). A skill needing a
tool the persona cannot use this turn (its `tools:` line) is not offered.

`auto` is the way a skill is chosen for a message: the strict retriever over each skill's name and description (the
reference library's way, docs/decisions/019), no extra model call, and no skill when nothing matches. `ask` (a model
that can call tools) lists the usable skills by name and description and lets the model call `use_skill(name)`, as many
times as the message needs; a model without tools gets `auto`."""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import yaml

from sympose import settings_store
from sympose.engine import edit_tools, lookup_find, lookup_list, lookup_tools
from sympose.engine.grounding import retrieve
from sympose.engine.grounding_index import build_index
from sympose.persona_files import persona_dir

log = logging.getLogger(__name__)

BUNDLED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
FILENAME = "SKILL.md"
LOOKUP_SETTING = "skill_lookup"
AUTO, ASK, OFF = "auto", "ask", "off"
MODES = (AUTO, ASK, OFF)
CAP_SETTING = "skill_cap"
DEFAULT_CAP = 3000  # characters of a skill's body that join the prompt
MIN_CAP = 500
MAX_FILE = 20_000  # bytes; a larger file is not read (a copied-in skill is untrusted text)
MAX_DESCRIPTION = 400
CUT_NOTE = "[The rest of this skill was left out to fit.]"
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")  # ASCII only: the name is also the folder's
_HEADER_END = re.compile(r"^---[ \t]*$", re.MULTILINE)  # a line of its own, not a longer run of dashes
_EDITING = (edit_tools.EDIT, edit_tools.NOTE, edit_tools.COMMENT, edit_tools.SHOW)
_LOOKUP = (lookup_tools.SEARCH, lookup_tools.OPEN, lookup_find.FIND, lookup_list.LIST)


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    tools: tuple[str, ...] = ()
    source: str = "bundled"  # or "persona"


def mode() -> str:
    value = settings_store.get(LOOKUP_SETTING)
    return value if value in MODES else AUTO


def cap() -> int:
    """The longest body that is sent: the user's whole number of at least `MIN_CAP`, else the default."""
    value = settings_store.get(CAP_SETTING)
    ok = isinstance(value, int) and value >= MIN_CAP  # `True` is 1, below the least
    return value if ok else DEFAULT_CAP


def parse(text: str, folder_name: str, source: str) -> Skill | None:
    """The skill a `SKILL.md` holds, or `None` when its header is missing, unreadable or names it other than its folder
    (a lowercase name of letters, digits and hyphens that is the folder's own), or has no description or no steps."""
    if not text.startswith("---"):
        return None
    end = _HEADER_END.search(text, 3)
    if end is None:
        return None
    head, body = text[3:end.start()], text[end.end():]
    try:
        meta = yaml.safe_load(head)
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    name, description = meta.get("name"), meta.get("description")
    if name != folder_name or not isinstance(name, str) or not _NAME.fullmatch(name):
        return None
    if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION:
        return None
    needs = meta.get("tools") or []
    if not isinstance(needs, list) or not all(isinstance(t, str) for t in needs):
        return None
    steps = body.lstrip("\n").strip()
    if not steps:
        return None
    return Skill(name, " ".join(description.split()), steps, tuple(needs), source)


def _read(folder: str, source: str, only: set[str] | None = None) -> list[Skill]:
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    found = []
    for name in names:
        if only is not None and name not in only:
            continue
        path = os.path.join(folder, name, FILENAME)
        try:
            if os.path.getsize(path) > MAX_FILE:
                log.warning("Skill %s is too large to read (over %d bytes); skipped.", name, MAX_FILE)
                continue
            with open(path, encoding="utf-8-sig") as f:
                skill = parse(f.read(), name, source)
        except (OSError, UnicodeDecodeError):
            continue
        if skill is None:
            log.warning("Skill %s has no valid header or steps; skipped.", name)
        else:
            found.append(skill)
    return found


def carried(persona: dict[str, Any]) -> list[Skill]:
    """The skills a persona carries: the bundled ones her `persona.yaml` names, then all of her own folder's
    (a skill of her own with a bundled one's name replaces it)."""
    wanted = {s for s in persona.get("skills") or [] if isinstance(s, str)}
    skills = {s.name: s for s in _read(BUNDLED_DIR, "bundled", wanted)}
    try:
        own = os.path.join(persona_dir(persona.get("handle") or ""), "skills")
    except ValueError:
        return list(skills.values())
    skills.update({s.name: s for s in _read(own, "persona")})
    return list(skills.values())


def tools_of(ask: bool, edit: bool) -> frozenset[str]:
    """The tools this turn gives the persona that a skill can name: the vault lookups when she looks notes up herself
    (`ask`), the editing ones when she may propose changes (`edit`, a call or a marker alike)."""
    return frozenset((*(_LOOKUP if ask else ()), *(_EDITING if edit else ())))


def can_carry_out(skill: Skill, tools: frozenset[str]) -> bool:
    """Whether every tool the skill's `tools:` line names is there this turn. A skill that cannot be carried out is not
    offered: a half-done draft is worse than the plain answer."""
    return set(skill.tools) <= tools


def usable(persona: dict[str, Any], tools: frozenset[str], local: bool) -> list[Skill]:
    """The skills this turn can offer: carried, carried out with the tools there are, and, for a model that is not local
    (`local` false), only the bundled ones: a skill of the persona's own is the user's private text, the bundled skills
    are public (docs/decisions/031)."""
    return [s for s in carried(persona) if can_carry_out(s, tools) and (local or s.source == "bundled")]


def select(persona: dict[str, Any], message: str, tools: frozenset[str], local: bool) -> Skill | None:
    """The skill that best matches `message`, or `None`: skills are not in `auto`, none can be offered, or none shares
    enough with the message."""
    if mode() not in (AUTO, ASK):  # `ask` reaches here for a model that cannot call tools
        return None
    offered = usable(persona, tools, local)
    if not offered:
        return None
    notes = [
        {"rel_path": s.name, "file_name": s.name, "meta": {}, "body": f"# {s.name.replace('-', ' ')}\n\n{s.description}"}
        for s in offered
    ]
    hits = retrieve(build_index(notes), message, 1, strict=True)
    return next((s for s in offered if hits and s.name == hits[0]["rel_path"]), None)


def text_for(skill: Skill) -> str:
    """The skill as the prompt carries it, its body bounded by `skill_cap`: cut after a whole line, and saying so, so a
    half-skill is never mistaken for the whole."""
    body, limit = skill.body, cap()
    if len(body) > limit:
        cut = body[:limit]
        if body[limit] != "\n":
            cut = cut.rsplit("\n", 1)[0]  # the cut fell inside a line: leave that line out
        body = f"{cut.rstrip()}\n{CUT_NOTE}"
    return f"Skill: {skill.name}\n{body}"


def menu(offered: list[Skill]) -> str:
    """The skills a model that chooses (`ask`) is told it can take up, one line each."""
    return "\n".join(f"- {s.name}: {s.description}" for s in offered)
