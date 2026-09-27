"""The purpose paragraph of a folder's definition (docs/decisions/033, stage 2): one model call, made from what
the folder's notes are called and never from what they say, and a proposal like the rest of the draft.

The caller shows the proposal and writes it only on the user's yes. When the model cannot say what the folder is
for, cannot be sent the titles, or cannot be reached, the draft has the counted template and no purpose: nothing
is made up to fill the place."""

import dataclasses
import logging
import re
from dataclasses import dataclass
from typing import Any

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import vault_paths
from sympose.engine import budget, helper_limit, sharing
from sympose.engine import model as model_mod
from sympose.engine.prompt_text import PURPOSE_INSTRUCTIONS, UNCLEAR_PURPOSE
from sympose.vault_manifest_build import _stem
from sympose.vault_snapshot import get_vault_snapshot

log = logging.getLogger(__name__)

WRITTEN, UNCLEAR, WITHHELD, FAILED = "written", "unclear", "withheld", "failed"
MAX_TITLES = 40
MAX_SUBFOLDERS = 10
_MAX_TOKENS = 120
_MAX_SENTENCES = 2
_LIST_OR_HEADING = re.compile(r"^\s*(?:[-*#>]|\d+[.)])\s", re.MULTILINE)
_LABEL = re.compile(r"^(?:description|purpose|folder)\s*:\s*", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Proposal:
    draft: write_defs.Draft
    state: str  # WRITTEN, UNCLEAR (ask the user), WITHHELD (a cloud model without `notes`) or FAILED
    reason: str = ""  # why, for FAILED


def _spread(items: list[str], limit: int) -> list[str]:
    """At most `limit` of `items`, evenly spread over the list (all of it when it is short), in order."""
    if len(items) <= limit:
        return items
    return [items[round(i * (len(items) - 1) / (limit - 1))] for i in range(limit)] if limit > 1 else items[:1]


def _title(note: dict[str, Any]) -> str:
    """A note's title as text: its `title` or `name` property when that is text, else its file name (a list or a
    mapping there would reach the model as a Python repr)."""
    meta = note.get("meta") or {}
    return next((v.strip() for v in (meta.get("title"), meta.get("name")) if isinstance(v, str) and v.strip()), _stem(note["file_name"]))


def titles_in(notes: list[dict[str, Any]], folder: str, limit: int = MAX_TITLES) -> list[str]:
    """The titles of `folder`'s notes (`title` or `name` in the properties, else the file name), sorted by path (whatever the case) and
    at most `limit` of them spread over the whole folder, so a big folder shows its range and gives the same list twice."""
    found = sorted(defs.notes_in(notes, folder), key=lambda n: n["rel_path"].lower())
    return _spread([_title(n) for n in found], limit)


def subfolders_of(notes: list[dict[str, Any]], folder: str, limit: int = MAX_SUBFOLDERS) -> list[str]:
    """The names of the folders directly under `folder` that hold notes, sorted, at most `limit`."""
    parts = (n["rel_path"].replace("\\", "/").split("/") for n in defs.notes_in(notes, folder))
    return sorted({p[1] for p in parts if len(p) > 2}, key=str.lower)[:limit]


def request(folder: str, titles: list[str], subfolders: list[str]) -> list[dict[str, str]]:
    """What the model is given: the folder's name, some of its notes' titles and the names of its sub-folders. Never
    a note's text and never a property, its name or its value: the template section of the definition shows those."""
    lines = [f"Folder: {folder}", "Titles of some of the notes in it:", *(f"- {t}" for t in titles)]
    if subfolders:
        lines.append("Names of its sub-folders: " + ", ".join(subfolders))
    return [{"role": "system", "content": PURPOSE_INSTRUCTIONS}, {"role": "user", "content": "\n".join(lines) + "\n\nDescription:"}]


def clean(text: str, truncated: bool = False) -> str | None:
    """The purpose as it is to be written: `""` when the model said the titles do not show it, `None` when the reply
    is not usable (nothing, or a list or headings). At most two sentences; a reply cut by the limit ends at its last
    whole one."""
    if _LIST_OR_HEADING.search(text):
        return None
    text = " ".join(text.split()).strip("\"'“”")
    text = _LABEL.sub("", text).strip()
    if not text:
        return None
    if re.sub(r"[\W_]+", "", text).upper() == UNCLEAR_PURPOSE:  # a small model sometimes splits it: "UN CLEAR"
        return ""
    sentences = _SENTENCE_END.split(text)
    if truncated and not text.endswith((".", "!", "?")):
        sentences = sentences[:-1]  # the last one was cut mid-sentence
    return " ".join(sentences[:_MAX_SENTENCES]) or None


def propose(profile: dict[str, Any], folder: str, model: str | None = None) -> Proposal | None:
    """The definition `folder` would get (`write_defs.draft`, or `None` when it cannot have one) with its purpose
    asked of `model` (the persona's own, else the `chat_model` setting), unless the model is a cloud one the user
    has not approved `notes` for. One call. Never raises for a model problem."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return None
    vault, allowed = scope
    notes = get_vault_snapshot(vault, allowed)  # one read: the template and the titles sent are of the same notes
    base = write_defs.draft_from(vault, notes, folder)
    if base is None:
        return None
    model = model or model_mod.resolve_model(profile.get("model"))
    if sharing.NOTES not in sharing.allowed(model):
        return Proposal(base, WITHHELD)  # the titles would go to a cloud model the user has not approved for notes (ADR 031)
    messages = request(folder, titles_in(notes, folder), subfolders_of(notes, folder))
    limits = budget.budget_for(model)
    try:
        reply = model_mod.call_model(
            messages, model=model, num_ctx=limits.num_ctx if limits else None, max_tokens=helper_limit.for_model(model, _MAX_TOKENS)
        )
    except model_mod.EngineModelError as e:
        log.warning("Purpose of folder %r not drafted: %s", folder, e)
        return Proposal(base, FAILED, str(e))
    purpose = clean(reply.text, reply.truncated)
    if purpose is None:
        return Proposal(base, FAILED, "the model wrote nothing usable")
    if not purpose:
        return Proposal(base, UNCLEAR)
    return Proposal(dataclasses.replace(base, text=defs.render(folder, base.template, purpose)), WRITTEN)
