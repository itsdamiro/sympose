"""What a persona proposed, shown under its Slack reply (docs/decisions/093). The web app that holds Drafts cannot be reached
away from the Mac, so the reply carries the proposed text. The block is built from the draft as it waits in the persona's own
folder, not from what the model said about it, so what the user reads is what Accept would write. Nothing here writes."""

from typing import Any

from sympose import note_changes
from sympose.slack_text import LIMIT

FOOTER = "_Waiting in Drafts: nothing is saved until you accept it in the web app._"
NOT_SHOWN = "_Too long to show here; read in Drafts in the web app: {names}._"
LEFT_OUT = "_Cut here: {n} more characters. Read the whole note in Drafts in the web app._"
MIN_SHOWN = 200  # a draft is cut only when at least this much of it can be shown; below that it is named and left for Drafts
_RESERVED = 400  # room kept for the line that names the drafts left out (three names of at most 60 characters and a count fit well within it)
_NAMED = 3
_NAME_LENGTH = 60
_FENCE = "```"
_BROKEN_FENCE = "`\u200b``"  # looks the same, and no longer closes a code block


def waiting(handle: str, made: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """The new notes of `made` (from `note_changes.new_notes_made`) as they wait now; one that is gone is left out."""
    found = (note_changes.pending_new_note(handle, path, proposal_id) for path, proposal_id in made)
    return [proposal for proposal in found if proposal is not None]


def _escape(text: str) -> str:
    """Slack reads `&`, `<` and `>` as its own marks even inside code, and a fence inside the text would close ours."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(_FENCE, _BROKEN_FENCE)


def _label(text: str) -> str:
    return " ".join(_escape(text).replace("*", "").split())


def _name(draft: dict[str, Any]) -> str:
    name = _label(str(draft.get("name") or "Untitled"))
    return name if len(name) <= _NAME_LENGTH else name[: _NAME_LENGTH - 1].rstrip() + "…"


def _escaped_start(text: str, allowed: int) -> str:
    """The start of `text`, cut at the end of a line when one comes after its middle, whose escaped form is at most `allowed`."""
    cut = min(len(text), allowed)
    while (size := len(_escape(text[:cut]))) > allowed:
        cut = min(cut - 1, cut * allowed // size)
    newline = text.rfind("\n", 0, cut)
    return text[: newline if newline > cut // 2 else cut]


def _show(draft: dict[str, Any], room: int) -> str | None:
    """The draft as a block that takes at most `room` characters, cut to fit when at least `MIN_SHOWN` of it can be shown;
    `None` when it cannot."""
    folder = _label(str(draft.get("folder") or ""))
    head = f"*New note: {_name(draft)}*" + (f" in {folder}" if folder else "")
    text = str(draft.get("text") or "").strip("\n")
    top, bottom = f"{head}\n{_FENCE}\n", f"\n{_FENCE}"
    space = room - len(top) - len(bottom)
    whole = _escape(text)
    if len(whole) <= space:
        return top + whole + bottom
    allowed = space - len(LEFT_OUT) - 1
    if allowed < MIN_SHOWN:
        return None
    shown = _escaped_start(text, allowed)
    return top + _escape(shown) + bottom + "\n" + LEFT_OUT.format(n=len(text) - len(shown))


def under(reply: str, drafts: list[dict[str, Any]]) -> str:
    """`reply` with what was proposed below it, the whole kept within what Slack takes in one message."""
    if not drafts:
        return reply
    room = LIMIT - len(reply) - len(FOOTER) - 4 - _RESERVED  # the blank lines around the block
    parts, left_out = [], []
    for draft in drafts:
        shown = _show(draft, room)
        if shown is None:
            left_out.append(draft)
            continue
        parts.append(shown)
        room -= len(shown) + 2
    if left_out:
        names = [_name(draft) for draft in left_out]
        more = f" and {len(names) - _NAMED} more" if len(names) > _NAMED else ""
        parts.append(NOT_SHOWN.format(names=", ".join(names[:_NAMED]) + more))
    return reply + "\n\n" + "\n\n".join([*parts, FOOTER])
