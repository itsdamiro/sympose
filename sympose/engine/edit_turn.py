"""What one turn gives a persona to act on a note (docs/decisions/072): the mode that counts for her, whether she
makes a change with a tool call or a marked block in her reply, and the open note and the rules that travel with the
user's message. The note and the rules sit last in the user's turn, after the request's neighbours, where a small
model weighs them most (ADR 020, measured in ADR 072); what is stored in the conversation is the user's own words, not
this. Nothing here writes: a proposal waits for the user's Accept."""

import re
from dataclasses import dataclass

from sympose import settings_store
from sympose.engine import edit_mode

CAP_SETTING = "open_note_cap"
DEFAULT_CAP, MIN_CAP = 12000, 20  # characters of the open note she is shown


@dataclass(frozen=True)
class OpenNote:
    """The note open in the editor: its path, and the editor's text, which can be ahead of the file."""

    path: str
    text: str


@dataclass(frozen=True)
class Edit:
    mode: str
    tool: bool  # a tool call (a model that can call tools) rather than a marker in the reply
    note: OpenNote | None = None  # what she is shown, within the cap
    cut: bool = False  # the note was longer than the cap
    withheld: bool = False  # a note is open but the model may not have its text (a cloud model, ADR 031)
    source: OpenNote | None = None  # the whole open note, which a change is placed in (she is shown `note`, within the cap)

    @property
    def active(self) -> bool:
        return self.mode != edit_mode.PLAN


def cap() -> int:
    value = settings_store.get(CAP_SETTING)
    ok = isinstance(value, int) and not isinstance(value, bool) and value >= MIN_CAP
    return value if ok else DEFAULT_CAP


def _within(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    head = text[:limit]
    newline = head.rfind("\n")
    return (head[:newline] if newline > limit // 2 else head), True


def resolve(persona: dict, can_call_tools: bool, open_note: OpenNote | None, may_see: bool = True) -> Edit:
    """What this turn gives her. In `plan` she is given no tool and no note; otherwise the tool or the marker, and
    the open note when there is one, cut to the cap."""
    mode = edit_mode.for_persona(persona)
    if mode == edit_mode.PLAN:
        return Edit(mode, False)
    if open_note is None:
        return Edit(mode, can_call_tools)
    if not may_see:
        return Edit(mode, can_call_tools, withheld=True)
    text, cut = _within(open_note.text, cap())
    return Edit(mode, can_call_tools, OpenNote(open_note.path, text), cut, source=open_note)


_EDIT_TOOL = (
    "To change the note, call propose_edit once for each change. Its find is copied from the note exactly, character "
    "for character, and appears in the note exactly once (include a neighbouring word if it does not on its own); "
    "its replace is what takes its place; its say is one sentence on what you changed."
)
_EDIT_MARKER = (
    "To change the note, say in a sentence what you will change, then add one line for each change, exactly in this form: "
    '<!-- propose_edit: {"find": "...", "replace": "...", "say": "..."} --> '
    '"find" is copied from the note exactly, character for character, and appears in the note exactly once '
    "(include a neighbouring word if it does not on its own); write line breaks in strings as \\n."
)
_NOTE_TOOL = "To suggest a new note, call propose_note with its whole text, a title of three to five words and one sentence in say."
_NOTE_MARKER = (
    "To suggest a new note, add one line in this form: "
    '<!-- propose_note: {"text": "...", "title": "three to five words", "say": "..."} --> write line breaks in strings as \\n.'
)
_REVIEW = "The user reviews each change before anything is saved. Do not rewrite the note."
_ASKED = (
    "If the request needs information that is neither in the note nor in the request, propose nothing and say what you "
    "need. If the user is only asking or talking, propose nothing."
)
_UNASKED = (
    "You may also propose a change you notice the note needs, even if the user did not ask, and a new note when it "
    "would help. If the request needs information that is neither in the note nor in the request, propose nothing and "
    "say what you need."
)
_PLAN = (
    "In this conversation you cannot change notes: talk about a change if it helps, and the user will make it "
    "themselves. Do not write any block that proposes one."
)
_WITHHELD = (
    "A note is open in the editor, but the user has not allowed its text to be sent to this model, so you cannot see it "
    "or change it; if asked to change it, say so."
)
_CUT = "The note is longer than what is shown: only the first {n} characters are, so propose changes only to those."


def message(edit: Edit, user_message: str) -> str:
    """The user's turn as the model is sent it: the note, the request, then the rules, last."""
    if not edit.active:
        return f"{user_message}\n\n{_PLAN}"
    new_note = _NOTE_TOOL if edit.tool else _NOTE_MARKER
    if edit.note is None:
        held = f"{_WITHHELD} " if edit.withheld else ""
        return f"{user_message}\n\n{held}{new_note} {_REVIEW}"
    rules = [_EDIT_TOOL if edit.tool else _EDIT_MARKER, new_note, _REVIEW]
    if edit.cut:
        rules.append(_CUT.format(n=len(edit.note.text)))
    rules.append(_UNASKED if edit.mode == edit_mode.AUTO else _ASKED)
    fence = "`" * max(4, 1 + max((len(run) for run in re.findall(r"`+", edit.note.text)), default=0))
    head = f"The open note, {edit.note.path}:\n\n{fence}\n{edit.note.text}\n{fence}\n\nThe user's request: {user_message}\n\n"
    return head + " ".join(rules)
