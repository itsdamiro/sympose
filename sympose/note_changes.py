"""A persona's proposals and annotations for notes (docs/decisions/070, 042 and 069).

A proposal is a change she suggests and the user has not yet accepted: an edit (the passage she quoted, what
replaces it) or a whole new note. An annotation is a comment on a passage, from the user or from her. Both are
attached to a note by the passage they are about and the text around it, found again by `passage_finder`; whether
a proposal is still pending, or outdated because its passage was rewritten, is worked out from the note's current
text each time and never stored. Nothing here writes the vault: accepting a proposal is a vault write done by the
caller, through the ordinary note functions."""

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sympose import note_changes_store as store
from sympose import passage_finder as finder
from sympose.persona_files import profiles_dir

PENDING, OUTDATED = "pending", "outdated"
ATTACHED, DETACHED = "attached", "detached"
OPEN, RESOLVED = "open", "resolved"
_NAME_WORDS = 5


class CannotAnchor(ValueError):
    """The passage cannot be tied to one place in the note, so nothing was saved."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _anchor(note_text: str, quote: str, start: int | None) -> tuple[str, str]:
    """The text before and after `quote`: at `start` when the caller knows where, else where it is found, which
    must be the only place."""
    if start is not None:
        if note_text[start:start + len(quote)] != quote or not quote:
            raise CannotAnchor("That passage is not in the note where it was said to be.")
        return finder.capture_context(note_text, start, start + len(quote))
    found = finder.locate(note_text, quote)
    if found.status == finder.NONE:
        raise CannotAnchor("That passage is not in the note.")
    if found.status == finder.MANY:
        raise CannotAnchor("That passage is in the note more than once; quote more of it.")
    return finder.capture_context(note_text, found.start, found.end)


def propose_edit(handle: str, note_path: str, note_text: str, *, find: str, replace: str, say: str) -> dict[str, Any]:
    before, after = _anchor(note_text, find, None)
    proposal = {"id": _id(), "time": _now(), "kind": "edit", "find": find, "replace": replace, "before": before, "after": after, "say": say}
    start = finder.locate(note_text, find, before, after).start

    def add(entry: dict[str, Any]) -> None:
        if any(_overlaps(waiting, note_text, start, start + len(find)) for waiting in entry["proposals"]):
            raise CannotAnchor("A change to that passage is already waiting; the user decides it first.")
        entry["proposals"].append(proposal)

    store.update(handle, note_path, add)
    return proposal


def _overlaps(waiting: dict[str, Any], note_text: str, start: int, end: int) -> bool:
    """Whether a proposal still pending covers any of `start:end` (one that went outdated covers nothing)."""
    if waiting.get("kind") != "edit":
        return False
    found = finder.locate(note_text, waiting["find"], waiting.get("before", ""), waiting.get("after", ""))
    return found.status == finder.ONE and found.start < end and start < found.end


def working_name(text: str, title: str | None = None) -> str:
    """What a new note is called until it has a file name: her own title if she gave one, else its first
    heading, else its first words (docs/decisions/042)."""
    if title and title.strip():
        return title.strip()
    heading = re.search(r"^#{1,6}[ \t]+(.+?)[ \t#]*$", text, re.M)
    words = (heading.group(1) if heading else text).split()
    return " ".join(words[:_NAME_WORDS]) or "Untitled"


def propose_create(handle: str, note_path: str, text: str, *, say: str, title: str | None = None) -> dict[str, Any]:
    proposal = {"id": _id(), "time": _now(), "kind": "create", "text": text, "name": working_name(text, title), "say": say}
    store.update(handle, note_path, lambda entry: entry["proposals"].append(proposal))
    return proposal


def edit_draft(handle: str, note_path: str, text: str) -> None:
    """The user saved the new-note draft in the editor: its proposal now holds their text (still in her folder, never the
    vault; the working name stays). `KeyError` when the note has no new-note draft."""
    def apply(entry: dict[str, Any]) -> None:
        creates = [p for p in entry["proposals"] if p.get("kind") == "create"]
        if not creates:
            raise KeyError(note_path)
        creates[0]["text"] = text

    store.update(handle, note_path, apply)


def status(proposal: dict[str, Any], note_text: str) -> str:
    """`pending` while the passage is in the note exactly once (it follows the text); `outdated` once it was
    rewritten or can no longer be told from another. A new note has nothing to go stale."""
    if proposal.get("kind") == "create":
        return PENDING
    found = finder.locate(note_text, proposal["find"], proposal.get("before", ""), proposal.get("after", ""))
    return PENDING if found.status == finder.ONE else OUTDATED


def annotate(handle: str, note_path: str, note_text: str, *, quote: str, text: str, author: str, reply_to: str | None = None, start: int | None = None, context: tuple[str, str] | None = None) -> dict[str, Any]:
    """A comment on `quote`. The text around it is `context` (before, after) when the caller has it, as an editor
    does from its own text, which can be ahead of the file; else it is taken from where the passage is in `note_text`."""
    if not quote:
        raise CannotAnchor("There is no passage to comment on.")
    before, after = context if context is not None else _anchor(note_text, quote, start)
    annotation = {"id": _id(), "time": _now(), "author": author, "quote": quote, "before": before, "after": after, "text": text, "state": OPEN, "reply_to": reply_to}
    store.update(handle, note_path, lambda entry: entry["annotations"].append(annotation))
    return annotation


def reply(handle: str, note_path: str, comment_id: str, *, text: str, author: str) -> dict[str, Any]:
    """An answer under a comment, about the same passage. A reply to a reply goes under the comment it is in."""
    def add(entry: dict[str, Any]) -> dict[str, Any]:
        asked = _pick(entry["annotations"], comment_id)
        root = _pick(entry["annotations"], asked["reply_to"]) if asked.get("reply_to") else asked
        answer = {"id": _id(), "time": _now(), "author": author, "quote": root["quote"], "before": root["before"], "after": root["after"], "text": text, "state": root["state"], "reply_to": root["id"]}
        entry["annotations"].append(answer)
        return answer

    return store.update(handle, note_path, add)


def annotation_status(annotation: dict[str, Any], note_text: str) -> str:
    found = finder.locate(note_text, annotation["quote"], annotation.get("before", ""), annotation.get("after", ""))
    return ATTACHED if found.status == finder.ONE else DETACHED


def _pick(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise KeyError(item_id)


def set_annotation_state(handle: str, note_path: str, annotation_id: str, state: str) -> None:
    change_annotation(handle, note_path, annotation_id, state=state)


def change_annotation(handle: str, note_path: str, annotation_id: str, *, text: str | None = None, state: str | None = None) -> None:
    """Changes a comment's text and/or state in one save: a state that is not allowed changes nothing, not even the
    text that came with it."""
    if state is not None and state not in (OPEN, RESOLVED):
        raise ValueError(f"An annotation is {OPEN} or {RESOLVED}, not {state!r}")

    def apply(entry: dict[str, Any]) -> None:
        annotation = _pick(entry["annotations"], annotation_id)
        if text is not None:
            annotation["text"] = text
        if state is not None:
            annotation["state"] = state
            if not annotation.get("reply_to"):  # a comment and the answers under it are open or resolved together
                for answer in entry["annotations"]:
                    if answer.get("reply_to") == annotation_id:
                        answer["state"] = state

    store.update(handle, note_path, apply)


def delete_annotation(handle: str, note_path: str, annotation_id: str) -> None:
    """Removes the comment and the replies to it."""
    def remove(entry: dict[str, Any]) -> None:
        _pick(entry["annotations"], annotation_id)
        entry["annotations"] = [a for a in entry["annotations"] if a.get("id") != annotation_id and a.get("reply_to") != annotation_id]

    store.update(handle, note_path, remove)


def discard_proposal(handle: str, note_path: str, proposal_id: str) -> None:
    def remove(entry: dict[str, Any]) -> None:
        _pick(entry["proposals"], proposal_id)
        entry["proposals"] = [p for p in entry["proposals"] if p.get("id") != proposal_id]

    store.update(handle, note_path, remove)


def drafts(handle: str) -> list[dict[str, Any]]:
    """The notes with a proposal waiting or an open comment, newest first: what the Drafts section lists (ADR 071, amended
    2026-10-05). `count` is the changes waiting, `comments` the open comments (the answers under one belong to it)."""
    found = []
    for entry in store.entries(handle):
        proposals = entry["proposals"]
        open_comments = [a for a in entry["annotations"] if a.get("state") == OPEN and not a.get("reply_to")]
        if not proposals and not open_comments:
            continue
        creates = [p for p in proposals if p.get("kind") == "create"]
        found.append({
            "path": entry["path"],
            "name": creates[0].get("name") if creates else None,
            "is_new": bool(creates),
            "count": len(proposals),
            "comments": len(open_comments),
            "time": max(str(x.get("time", "")) for x in [*proposals, *open_comments]),
        })
    return sorted(found, key=lambda d: d["time"], reverse=True)


def rename(handle: str, old: str, new: str) -> None:
    store.move(handle, old, new)


def forget(handle: str, note_path: str) -> None:
    store.drop(handle, note_path)


def _handles() -> list[str]:
    """Every persona that has a folder: a note belongs to the vault, so a change to it reaches each persona's entry."""
    base = profiles_dir()
    try:
        return sorted(name for name in os.listdir(base) if os.path.isdir(os.path.join(base, name)))
    except OSError:
        return []


def rename_everywhere(old: str, new: str) -> None:
    """A note was renamed or moved: every persona's entry for it follows."""
    for handle in _handles():
        rename(handle, old, new)


def forget_everywhere(note_path: str) -> None:
    """A note was deleted for good: no persona keeps an entry for it."""
    for handle in _handles():
        forget(handle, note_path)
