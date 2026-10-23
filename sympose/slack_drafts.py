"""What a persona proposed, shown under its Slack reply (docs/decisions/093). The web app that holds Drafts cannot be reached
away from the Mac, so the reply carries the proposed text. The block is built from the draft as it waits in the persona's own
folder, not from what the model said about it, so what the user reads is what Accept would write: its words, escaped for Slack, and
a code block in it marked so it cannot close ours (said under the block). A draft is shown whole or only named, never cut: each one
shown whole also gets a message of buttons, Accept and Decline (docs/decisions/093, "Accept and Decline in Slack"); one only named is
read, and accepted, in the web app. Nothing here writes: a press is handled by `slack_channel.decide`."""

import json
import re
from typing import Any

from sympose import note_changes
from sympose import slack_text
from sympose.slack_text import LIMIT

FOOTER = "_Waiting in Drafts: nothing is saved until you accept it, with the buttons below or in the web app._"
FOOTER_WEB = "_Waiting in Drafts: nothing is saved until you accept it in the web app._"  # when no draft is shown, so none has buttons
ACCEPT, DECLINE = "sympose_accept", "sympose_decline"  # the buttons' action ids, which the connection listens for
NOT_SHOWN = "_Too long to show here; read in Drafts in the web app: {names}._"
MARKED_FENCE = "_A code block in the note is marked with an invisible character so it shows here; the draft itself has none._"
_NAMED = 3
_NAME_LENGTH = 60
_GAP = "\n\n"
_FENCE = "```"
_BROKEN_FENCE = "`\u200b``"  # looks the same, and no longer closes a code block
_MARKS = re.compile(r"[*_~`]")  # what Slack reads as bold, italic, strike or code in a line of ours
# Room kept for the line that names the drafts left out: the longest it can be (three names of full length and a count)
# and the blank line before it. Worked out from the line itself, so a change to its words changes the room.
_RESERVED = len(NOT_SHOWN.format(names=", ".join(["x" * _NAME_LENGTH] * _NAMED) + " and 999 more")) + len(_GAP)


def waiting(handle: str, made: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """The new notes of `made` (a turn's `draft_limit.Filing.made`) as they wait now, each with the `path` it waits under; one that
    is gone is left out."""
    found = ((path, note_changes.pending_new_note(handle, path, proposal_id)) for path, proposal_id in made)
    return [{**proposal, "path": path} for path, proposal in found if proposal is not None]


def _escape(text: str) -> str:
    """Slack reads `&`, `<` and `>` as its own marks even inside code, and a fence inside the text would close ours."""
    return slack_text.escape(text).replace(_FENCE, _BROKEN_FENCE)


def _label(text: str) -> str:
    return " ".join(_MARKS.sub("", _escape(text)).split())


def name_of(draft: dict[str, Any]) -> str:
    name = _label(str(draft.get("name") or "Untitled"))
    return name if len(name) <= _NAME_LENGTH else name[: _NAME_LENGTH - 1].rstrip() + "…"


def _show(draft: dict[str, Any], room: int) -> str | None:
    """The draft as a block that takes at most `room` characters, with all its words; `None` when it does not fit."""
    folder = _label(str(draft.get("folder") or ""))
    head = f"*New note: {name_of(draft)}*" + (f" in {folder}" if folder else "")
    text = str(draft.get("text") or "").strip("\n")
    marked = f"\n{MARKED_FENCE}" if _FENCE in text else ""
    top, bottom = f"{head}\n{_FENCE}\n", f"\n{_FENCE}{marked}"
    whole = _escape(text)
    return top + whole + bottom if len(top) + len(whole) + len(bottom) <= room else None


def compose(reply: str, drafts: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """`reply` with what was proposed below it, the whole kept within what Slack takes in one message, and the drafts shown
    (the only ones offered buttons: one only named cannot be read here, so it is decided in the web app)."""
    if not drafts:
        return reply, []
    # The blank line before the first block and the one before the footer; each block then counts the one after it, and _RESERVED the line naming the drafts left out and the blank line before it
    room = LIMIT - len(reply) - len(FOOTER) - 2 * len(_GAP) - _RESERVED
    parts, left_out, shown = [], [], []
    for draft in drafts:
        block = _show(draft, room)
        if block is None:
            left_out.append(draft)
            continue
        parts.append(block)
        shown.append(draft)
        room -= len(block) + len(_GAP)
    if left_out:
        names = [name_of(draft) for draft in left_out]
        more = f" and {len(names) - _NAMED} more" if len(names) > _NAMED else ""
        parts.append(NOT_SHOWN.format(names=", ".join(names[:_NAMED]) + more))
    return reply + _GAP + _GAP.join([*parts, FOOTER if shown else FOOTER_WEB]), shown


def prompt(draft: dict[str, Any]) -> dict[str, Any]:
    """The message of buttons for a waiting draft (as `draft_accept` takes it): `text` is what a notification shows, `blocks`
    the question and the two buttons. The buttons carry the draft's working path and id, nothing of its text."""
    folder = _label(str(draft.get("folder") or ""))
    text = f"Save *{name_of(draft)}*" + (f" to {folder}" if folder else "") + "?"
    value = json.dumps([draft["path"], draft["id"]])

    def button(action: str, label: str, **more: str) -> dict[str, Any]:
        return {"type": "button", "action_id": action, "text": {"type": "plain_text", "text": label}, "value": value, **more}

    return {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "actions", "elements": [button(ACCEPT, "Accept", style="primary"), button(DECLINE, "Decline")]},
        ],
    }


def outcome(text: str) -> dict[str, Any]:
    """What replaces a message of buttons once it is decided: one line, no buttons."""
    return {"text": text, "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]}


def saved(name: str, path: str) -> str:
    return f"Saved *{name_of({'name': name})}* as `{_escape(path.replace(chr(96), chr(39)))}`."


def declined(name: str) -> str:
    return f"Declined *{name_of({'name': name})}*; nothing was saved."
