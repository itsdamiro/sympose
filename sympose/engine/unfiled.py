"""A reply that says a note or a change was made when nothing was filed (docs/decisions/082). A small model that can call
tools sometimes writes "I've drafted it for you" without calling `propose_note` or `propose_edit` (3 of 12 on
`gemma4:e4b`, ADR 077): the user is told about a draft that does not exist. The claim is read from the reply and
compared with what the turn did, the tool calls and the marked blocks alike (`lookups`, one entry per call).

Two things follow. A turn that gave the model tools asks it once more, privately, to file the note or to say it did
not (`recheck`); the first reply is dropped and never saved. And a reply that still says it after that, or one from a
model without tools, gets one plain line saying nothing was filed with this message (`correct`), which is true
whatever the earlier turns did. Reading English is a heuristic: it is tuned to leave a reply that says nothing of
the kind alone, and it does not read a promise ("I can draft one")."""

import re
from typing import Any, Callable

from sympose.engine import edit_tools, edit_turn, persona_proposal, setting_proposal

NOTHING_FILED = "(Nothing was filed with this message.)"
_NOUN = r"(?:note|draft|recipe|entry|page|proposal|change|edit|section|file|folder)"
# "I've drafted", "I went ahead and put together": verbs that mean a proposal on their own.
_SAYS_DRAFTED = re.compile(
    r"\bI(?:'ve|\s+have)?\s+(?:just\s+|already\s+|gone\s+ahead\s+and\s+|went\s+ahead\s+and\s+)?"
    r"(?:drafted|proposed|put\s+together|written\s+up|wrote\s+up|drawn\s+up)\b", re.I)
# "I've added a note to", "I updated the draft": verbs that need the thing named in the same sentence.
_SAYS_MADE = re.compile(
    r"\bI(?:'ve|\s+have)?\s+(?:just\s+|already\s+|gone\s+ahead\s+and\s+|went\s+ahead\s+and\s+)?"
    r"(?:added|created|made|saved|filed|updated|changed|edited|rewrote|rewritten|fixed|put|placed)\b[^.!?\n]*\b" + _NOUN + r"\b", re.I)
# "is now added to", "has been created": a new thing, not the vault's own ("your note is saved in Recipes").
_SAYS_NOW = re.compile(r"\b(?:is\s+now|are\s+now|has\s+been|have\s+been|was\s+just)\s+(?:added|created|saved|drafted|proposed|filed)\b", re.I)
_FILING = (edit_tools.EDIT, edit_tools.NOTE, persona_proposal.PROPOSE, setting_proposal.PROPOSE)  # any proposal the user will see: "I have proposed Ada" is true after `propose_persona`


def claims(reply: str) -> bool:
    return any(p.search(reply) for p in (_SAYS_DRAFTED, _SAYS_MADE, _SAYS_NOW))


def filed(lookups: list[dict[str, Any]]) -> bool:
    return any(entry.get("tool") in _FILING and entry.get("saved") for entry in lookups)


def said_but_not_filed(reply: str, lookups: list[dict[str, Any]]) -> bool:
    return claims(reply) and not filed(lookups)


def correct(reply: str) -> str:
    return f"{reply}\n\n{NOTHING_FILED}"


def recheck(edit: edit_turn.Edit) -> Callable[[str, list[dict[str, Any]]], str | None]:
    """For `lookup.converse`: given the reply a turn is about to end with and its tool calls so far, the line to ask the
    model once more with, or `None` when the reply is fine."""
    tools = f"{edit_tools.NOTE} or {edit_tools.EDIT}" if edit.note is not None else edit_tools.NOTE
    line = (
        f"[Sympose: you said a note or a change was made, but {tools} was not called, so nothing was filed and the user "
        "has nothing to review. If you meant to, call it now with the whole text. If not, tell the user plainly what you did not do.]"
    )
    return lambda reply, lookups: line if said_but_not_filed(reply, lookups) else None
