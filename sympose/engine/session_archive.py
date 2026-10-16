"""Archiving a conversation to a note (docs/decisions/086): one model call writes a short summary from the user's own
messages, and it is filed as a new-note draft in `<her first folder>/Sessions/` for the user to read, edit and Accept. The
vault is never written here (docs/decisions/042); the session log is only read."""

import logging
import re
from datetime import datetime
from typing import Any

from sympose import note_changes, vault_paths
from sympose.engine import budget, helper_limit, session, sharing, turn_cancel, turn_status
from sympose.engine import model as model_mod
from sympose.engine.prompt_text import ARCHIVE_INSTRUCTIONS, NO_RECAP
from sympose.profile import resolve_profile

log = logging.getLogger(__name__)

OK, NOT_FOUND, BUSY, TOO_SHORT, NO_VAULT = "ok", "not_found", "busy", "too_short", "no_vault"
NOT_ALLOWED, NOTHING_TO_KEEP, MODEL_FAILED, WAITING = "not_allowed", "nothing_to_keep", "model_failed", "waiting"

FOLDER = "Sessions"
_MIN_TURNS = 2
_MAX_TURNS = 60  # a very long conversation is written from its newest turns, as a recap is
_MAX_USER_CHARS = 1000
_MAX_TITLE_WORDS = 10  # asked for six; a few more is a title, a sentence is not
_MAX_TOKENS = 2500  # a model that thinks first (gemma4:e4b) used up 450 before writing a word; the user asked and is waiting
_UNFIT_FOR_A_NAME = re.compile(r"[\\/:*?\"<>|#\[\]^\x00-\x1f]")


def _request(turns: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages = "\n".join(f"User: {turn['user'][:_MAX_USER_CHARS]}" for turn in turns)
    return [{"role": "system", "content": ARCHIVE_INSTRUCTIONS}, {"role": "user", "content": f"Conversation:\n{messages}\n\nNote:"}]


def _fitting(turns: list[dict[str, Any]], model: str, limits: budget.Budget | None) -> list[dict[str, Any]]:
    """The newest turns whose request fits the model's window."""
    kept = list(turns)
    while kept and limits is not None and budget.count_tokens(_request(kept), model) > limits.prompt_tokens:
        del kept[0]
    return kept


def _whole(reply: model_mod.ModelReply) -> str:
    """The note as written; a reply cut by the limit loses its last, unfinished line."""
    text = reply.text.strip()
    if reply.truncated and "\n" in text:
        text = text[: text.rfind("\n")].rstrip()
    return text


def _title_and_body(text: str) -> tuple[str, str]:
    """The title line the model was asked to start with, and the note after it; no title (`""`) when the first line is not
    a short one-line title, with the whole text as the note."""
    first, _, rest = text.partition("\n")
    title = first.strip().lstrip("#").strip().strip("\"'*_ ")
    if rest.strip() and title and len(title.split()) <= _MAX_TITLE_WORDS and not title.startswith(("-", "*", "<")):
        return title, rest.strip()
    return "", text


def _day(session_id: str, meta: dict[str, Any]) -> str:
    try:
        return datetime.strptime(session_id[:8], "%Y%m%d").date().isoformat()
    except ValueError:
        return str(meta.get("created_at") or "")[:10]


def _name(day: str, title: str) -> str:
    """`YYYY-MM-DD title`, with what a file name or a link cannot hold taken out."""
    cleaned = " ".join(_UNFIT_FOR_A_NAME.sub(" ", title).split()).strip(".' ")
    return f"{day} {cleaned}".strip()


def _folder(profile: dict[str, Any]) -> str | None:
    """Where the note is made: `Sessions` in the first folder of her scope, or `None` when she has no vault."""
    sandbox = vault_paths.resolve_sandbox(profile)
    if sandbox is None:
        return None
    prefix = vault_paths.scope_prefixes(*sandbox)[0]
    return f"{prefix}/{FOLDER}" if prefix else FOLDER


def archive(handle: str, session_id: str, model: str | None = None) -> tuple[str, dict[str, str] | None]:
    """`(outcome, draft)`: `draft` is `{"path", "name", "folder"}` of the new-note draft when `outcome` is `OK`. Never raises for
    a model problem; the outcome says why nothing was made."""
    profile = resolve_profile(handle)
    loaded = session.load_session(handle, session_id)
    if profile is None or loaded is None:
        return NOT_FOUND, None
    if turn_status.phase(handle, session_id) is not None or turn_cancel.running(handle, session_id):
        return BUSY, None
    turns = loaded["turns"]
    if len(turns) < _MIN_TURNS:
        return TOO_SHORT, None
    folder = _folder(profile)
    if folder is None:
        return NO_VAULT, None
    model = model or model_mod.resolve_model(profile.get("model"))
    if sharing.RECAPS not in sharing.allowed(model):
        return NOT_ALLOWED, None  # the user's messages would go to a cloud model they have not approved for this (ADR 031)
    limits = budget.budget_for(model, profile)
    fitting = _fitting(turns[-_MAX_TURNS:], model, limits)
    if not fitting:
        return TOO_SHORT, None
    try:
        reply = model_mod.call_model(
            _request(fitting), model=model, num_ctx=limits.num_ctx if limits else None, max_tokens=helper_limit.for_model(model, _MAX_TOKENS),
        )
    except model_mod.EngineModelError as e:
        log.warning("Archive of session %s failed: %s", session_id, e)
        return MODEL_FAILED, None
    body = _whole(reply)
    if not body:
        return MODEL_FAILED, None
    if body.rstrip(".! ").upper() == NO_RECAP:
        return NOTHING_TO_KEEP, None
    title, body = _title_and_body(body)
    day = _day(session_id, loaded["meta"])
    name = _name(day, title or str(loaded["meta"].get("title") or ""))
    persona = str(profile.get("name") or handle)
    text = f"---\ntype: session\ndate: {day}\npersona: {persona}\n---\n\n# {name}\n\n{body}\n"
    path = f"new/{note_changes._id()}"
    try:
        note_changes.propose_create(handle, path, text, say=f"Archive of the conversation of {day}.", title=name, folder=folder)
    except note_changes.CannotAnchor:
        return WAITING, None
    return OK, {"path": path, "name": name, "folder": folder}
