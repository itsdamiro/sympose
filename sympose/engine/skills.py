"""Skills (docs/decisions/077): folders of know-how, each a `SKILL.md` with a `name` and a `description` in its header
and the steps as its body. A skill is text only: it tells the persona what to do with the tools she already has, and
nothing in a skill is ever run.

Where they live: the bundled ones in `sympose/skills/` and the user's own in `profiles/<handle>/skills/`. A persona
carries only the skills its `skills:` list names, bundled or its own: a folder put in is off until the user turns it on
(docs/decisions/077, the amendment of 2026-10-14; `persona_skills` adds and switches them). A skill needing a
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
CAPTURE = "capturing-from-a-link"  # the skill a turn that watches a video is given (docs/decisions/089)
CAPTURE_PAGE = "capturing-from-a-page"  # the same for a turn that reads a page
CAPTURE_FILE = "capturing-from-a-file"  # and for a turn that has a file attached
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


def check(text: str, folder_name: str, source: str = "persona") -> Skill | str:
    """The skill a `SKILL.md` holds, or, in the user's words, the rule it breaks: no header, an unreadable one, a name
    other than its folder's (lowercase letters, digits and hyphens), no description or one that is too long, a `tools`
    that is not a list, a `context` nobody provides, or no steps."""
    end = _HEADER_END.search(text, 3) if text.startswith("---") else None
    if end is None:
        return "SKILL.md must start with a header between two lines of ---."
    try:
        meta = yaml.safe_load(text[3:end.start()])
    except yaml.YAMLError:
        meta = None
    if not isinstance(meta, dict):
        return "The header of SKILL.md can't be read. It needs a name and a description."
    name, description = meta.get("name"), meta.get("description")
    if name != folder_name or not isinstance(name, str) or not _NAME.fullmatch(name):
        return f"The name in the header must be the folder's name, {folder_name}, in lowercase letters, digits and hyphens."
    if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION:
        return f"The header needs a description of at most {MAX_DESCRIPTION} characters."
    needs = meta.get("tools") or []
    if not isinstance(needs, list) or not all(isinstance(t, str) for t in needs):
        return "tools: in the header must be a list of names."
    context = meta.get("context") or ""
    if context not in ("", FOLDER):
        return f"context: in the header may only be {FOLDER}."
    steps = text[end.end():].lstrip("\n").strip()
    if not steps:
        return "SKILL.md has no steps after the header."
    return Skill(name, " ".join(description.split()), steps, tuple(needs), source, context)


def parse(text: str, folder_name: str, source: str) -> Skill | None:
    """The skill a `SKILL.md` holds, or `None` when `check` finds a rule broken."""
    skill = check(text, folder_name, source)
    return skill if isinstance(skill, Skill) else None


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


def _gather(persona: dict[str, Any], only: set[str] | None) -> list[Skill]:
    skills = {s.name: s for s in _read(BUNDLED_DIR, "bundled", only)}
    try:
        own = own_dir(persona.get("handle") or "")
    except ValueError:
        return list(skills.values())
    skills.update({s.name: s for s in _read(own, "persona", only)})
    return list(skills.values())


def own_dir(handle: str) -> str:
    """The folder of a persona's own skills; `ValueError` when `handle` is not a persona's."""
    return os.path.join(persona_dir(handle), "skills")


def carried(persona: dict[str, Any]) -> list[Skill]:
    """The skills a persona carries: those its `skills:` list names, from the bundled ones and from its own folder
    (its own replaces a bundled one of the same name)."""
    wanted = {s for s in persona.get("skills") or [] if isinstance(s, str)}
    return _gather(persona, wanted)


def available(persona: dict[str, Any]) -> list[Skill]:
    """Every skill the persona could carry, switched on or not: all the bundled ones and all of its own."""
    return _gather(persona, None)


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
    none shares enough with the message (the capture skills are never matched here: they are for a turn that watches a video, reads a page or has a file attached, `for_video`, `for_page` and `for_file`). A skill of the persona's own is the user's private text, so a model that is
    not local (`local` false) is never given one: the bundled skills are public (docs/decisions/031)."""
    if mode() != AUTO:
        return None
    usable = [s for s in carried(persona) if s.name not in (CAPTURE, CAPTURE_PAGE, CAPTURE_FILE) and can_carry_out(s, tools) and (local or s.source == "bundled")]
    if not usable:
        return None
    notes = [
        {"rel_path": s.name, "file_name": s.name, "meta": {}, "body": f"# {s.name.replace('-', ' ')}\n\n{s.description}"}
        for s in usable
    ]
    hits = retrieve(build_index(notes, paired=False), message, 1, strict=True)
    return next((s for s in usable if hits and s.name == hits[0]["rel_path"]), None)


def for_video(persona: dict[str, Any], tools: frozenset[str]) -> Skill | None:
    """The capture skill on a turn that watches a video, or `None` when the persona does not carry it or cannot carry it
    out (no way to show a proposal). A message that is only a link, or a later one that says "save that", shares almost
    no words with the skill's description, so retrieval would not find it; the watch is the signal, the same one that
    attaches the video. The skill's own first line leaves a message that does not ask for a note alone. It is bundled, so
    it may go to a cloud model."""
    if mode() != AUTO:
        return None
    return next((s for s in carried(persona) if s.name == CAPTURE and s.source == "bundled" and can_carry_out(s, tools)), None)


def for_page(persona: dict[str, Any], tools: frozenset[str]) -> Skill | None:
    """The page capture skill on a turn that reads a page, on the same terms as `for_video`."""
    if mode() != AUTO:
        return None
    return next((s for s in carried(persona) if s.name == CAPTURE_PAGE and s.source == "bundled" and can_carry_out(s, tools)), None)


def for_file(persona: dict[str, Any], tools: frozenset[str]) -> Skill | None:
    """The file capture skill on a turn that has a file attached, on the same terms as `for_video`."""
    if mode() != AUTO:
        return None
    return next((s for s in carried(persona) if s.name == CAPTURE_FILE and s.source == "bundled" and can_carry_out(s, tools)), None)


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
