"""Skills (docs/decisions/077): folders of know-how, each a `SKILL.md` with a `name` and a `description` in its header
and the steps as its body. A skill is text only: it tells the persona what to do with the tools she already has, and
nothing in a skill is ever run.

Where they live: the bundled ones in `sympose/skills/` (a persona carries those her `persona.yaml` names under
`skills:`), and the user's own in `profiles/<handle>/skills/` (a persona carries all of its own). A skill needing a
tool the persona cannot use this turn (its `tools:` line) is not offered. `tool_calls` there is not a tool but a
demand on the model: it calls tools rather than writing markers in its reply, which a skill that must file a faithful
note needs (a model without tools did not, docs/decisions/077). `context: folder` asks for the shape of the folder the
message names to be sent with the steps (`skill_folder`).

`auto` is the way a skill is chosen for a message: the strict retriever over each skill's name and description (the
reference library's way, docs/decisions/019), no extra model call, and no skill when nothing matches."""

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
AUTO, OFF = "auto", "off"
MODES = (AUTO, OFF)
CAP_SETTING = "skill_cap"
DEFAULT_CAP = 3000  # characters of a skill's body that join the prompt
MIN_CAP = 500
MAX_FILE = 20_000  # bytes; a larger file is not read (a copied-in skill is untrusted text)
MAX_DESCRIPTION = 400
TOOL_CALLS = "tool_calls"
FOLDER = "folder"
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
    context: str = ""  # `FOLDER`, or nothing


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
    context = meta.get("context") or ""
    if context not in ("", FOLDER):
        return None
    steps = body.lstrip("\n").strip()
    if not steps:
        return None
    return Skill(name, " ".join(description.split()), steps, tuple(needs), source, context)


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


def tools_of(ask: bool, edit: bool, calls: bool = False) -> frozenset[str]:
    """The tools this turn gives the persona that a skill can name: the vault lookups when she looks notes up herself
    (`ask`), the editing ones when she may propose changes (`edit`, a call or a marker alike), and `TOOL_CALLS` when
    the model calls them (`calls`)."""
    return frozenset((*(_LOOKUP if ask else ()), *(_EDITING if edit else ()), *((TOOL_CALLS,) if calls else ())))


def can_carry_out(skill: Skill, tools: frozenset[str]) -> bool:
    """Whether every tool the skill's `tools:` line names is there this turn. A skill that cannot be carried out is not
    offered: a half-done draft is worse than the plain answer."""
    return set(skill.tools) <= tools


def select(persona: dict[str, Any], message: str, tools: frozenset[str], local: bool) -> Skill | None:
    """The skill that best matches `message`, or `None`: skills are off, none is carried, none can be carried out, or
    none shares enough with the message. A skill of the persona's own is the user's private text, so a model that is
    not local (`local` false) is never given one: the bundled skills are public (docs/decisions/031)."""
    if mode() != AUTO:
        return None
    usable = [s for s in carried(persona) if can_carry_out(s, tools) and (local or s.source == "bundled")]
    if not usable:
        return None
    notes = [
        {"rel_path": s.name, "file_name": s.name, "meta": {}, "body": f"# {s.name.replace('-', ' ')}\n\n{s.description}"}
        for s in usable
    ]
    hits = retrieve(build_index(notes), message, 1, strict=True)
    return next((s for s in usable if hits and s.name == hits[0]["rel_path"]), None)


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
