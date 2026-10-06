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
from collections.abc import Callable
from typing import Any

from sympose import note_changes_store as store
from sympose import passage_finder as finder
from sympose import table_spans
from sympose.persona_files import profiles_dir

PENDING, OUTDATED = "pending", "outdated"
ATTACHED, DETACHED = "attached", "detached"
OPEN, RESOLVED = "open", "resolved"
ACCEPTED, DECLINED = "accepted", "declined"  # the user's verdict on one of her comments (docs/decisions/069)
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
    if (refusal := table_spans.problem(note_text, start, start + len(find), replace)) is not None:
        raise CannotAnchor(refusal)

    def add(entry: dict[str, Any]) -> None:
        if any(_overlaps(waiting, note_text, start, start + len(find)) for waiting in entry["proposals"]):
            raise CannotAnchor("A change to that passage is already waiting; the user decides it first.")
        entry["proposals"].append(proposal)

    store.update(handle, note_path, add)
    if say:  # her answer goes where the user asked: under the comments on these words, so no comment is left unanswered
        for asked in comments_on(handle, note_path, note_text, start, start + len(find)):
            reply(handle, note_path, asked["id"], text=say, author="persona")
    return proposal


def comments_on(handle: str, note_path: str, note_text: str, start: int, end: int) -> list[dict[str, Any]]:
    """The user's open comments whose words overlap `start:end` of the note's text."""
    found = []
    for a in store.read(handle, note_path)["annotations"]:
        if a.get("reply_to") or a.get("state") != OPEN or a.get("author") != "user":
            continue
        there = finder.locate(note_text, a["quote"], a.get("before", ""), a.get("after", ""))
        if there.status == finder.ONE and there.start < end and start < there.end:
            found.append(a)
    return found


def settle_comments(handle: str, note_path: str, note_text: str, proposal_ids: list[str]) -> None:
    """The user accepted these changes: the comments on their words asked for them and are answered, so they go (with their
    answers). A declined change leaves them, for the persona to try again."""
    for proposal in store.read(handle, note_path)["proposals"]:
        if proposal.get("id") not in proposal_ids or proposal.get("kind") != "edit":
            continue
        here = finder.locate(note_text, proposal["find"], proposal.get("before", ""), proposal.get("after", ""))
        if here.status != finder.ONE:
            continue
        for asked in comments_on(handle, note_path, note_text, here.start, here.end):
            delete_annotation(handle, note_path, asked["id"])


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


def comment_on(handle: str, note_path: str, note_text: str, *, quote: str, text: str, author: str) -> dict[str, Any]:
    """A comment of the persona's on `quote`: an answer under the open comment already on exactly the same words, if there
    is one, so the two read as one thread; otherwise a comment of its own. (Two comments on one passage are drawn as one
    highlight, and a user who opens it should find the persona's words with their own.)"""
    before, after = _anchor(note_text, quote, None)
    here = finder.locate(note_text, quote, before, after)
    for existing in store.read(handle, note_path)["annotations"]:
        if existing.get("reply_to") or existing.get("state") != OPEN:
            continue
        there = finder.locate(note_text, existing["quote"], existing.get("before", ""), existing.get("after", ""))
        if there.status == finder.ONE and (there.start, there.end) == (here.start, here.end):
            return reply(handle, note_path, existing["id"], text=text, author=author)
    return annotate(handle, note_path, note_text, quote=quote, text=text, author=author)


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


def change_annotation(
    handle: str, note_path: str, annotation_id: str, *, text: str | None = None, state: str | None = None, verdict: str | None = None,
) -> None:
    """Changes a comment's text, state and/or verdict in one save: anything that is not allowed changes nothing, not even
    the text that came with it. A verdict (`accepted`, or `declined` after the user has replied) is the user's decision on
    one of her comments; it resolves the comment, and reopening it clears the verdict."""
    if state is not None and state not in (OPEN, RESOLVED):
        raise ValueError(f"An annotation is {OPEN} or {RESOLVED}, not {state!r}")
    if verdict is not None and verdict not in (ACCEPTED, DECLINED):
        raise ValueError(f"A verdict is {ACCEPTED} or {DECLINED}, not {verdict!r}")
    if verdict is not None and state not in (None, RESOLVED):
        raise ValueError("A verdict resolves the comment; it cannot come with a reopen.")

    def apply(entry: dict[str, Any]) -> None:
        annotation = _pick(entry["annotations"], annotation_id)
        if verdict is not None:
            if annotation.get("reply_to") or annotation.get("author") != "persona":
                raise ValueError("Only the persona's comments can be accepted or declined.")
            if verdict == DECLINED and not any(a.get("reply_to") == annotation_id and a.get("author") == "user" for a in entry["annotations"]):
                raise ValueError("Reply first, saying why you disagree.")
        if text is not None:
            annotation["text"] = text
        if verdict is not None:
            annotation["verdict"], annotation["decided"] = verdict, _now()
        if state is not None or verdict is not None:
            annotation["state"] = RESOLVED if verdict is not None else state
            if annotation["state"] == OPEN:
                annotation.pop("verdict", None)
                annotation.pop("decided", None)
            if not annotation.get("reply_to"):  # a comment and the answers under it are open or resolved together
                for answer in entry["annotations"]:
                    if answer.get("reply_to") == annotation_id:
                        answer["state"] = annotation["state"]

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


def drafts(handle: str, text_of: Callable[[str], str | None] | None = None) -> list[dict[str, Any]]:
    """The notes with something for the user to look at, newest first: what the Drafts section lists (ADR 071, amended
    2026-10-05 and 2026-10-06). `items` is how many different marks the note shows: a change waiting, a new note proposed, or
    an open comment on words still in the note; a comment on the words a change of hers covers is the same item as that change
    (her change answers it). `count` is the changes among them and `comments` the other comments. `text_of(path)` is the note's
    text on disk, `None` when it has no file yet; without it every open comment is taken as on its words."""
    found = []
    for entry in store.entries(handle):
        text = text_of(entry["path"]) if text_of else None
        creates = [p for p in entry["proposals"] if p.get("kind") == "create"]
        edits = [p for p in entry["proposals"] if p.get("kind") != "create" and (text is None or status(p, text) == PENDING)]
        spans = []
        if text is not None:
            for p in edits:
                here = finder.locate(text, p["find"], p.get("before", ""), p.get("after", ""))
                spans.append((here.start, here.end))
        comments = []
        for a in entry["annotations"]:
            if a.get("state") != OPEN or a.get("reply_to"):
                continue
            if text is not None:
                there = finder.locate(text, a["quote"], a.get("before", ""), a.get("after", ""))
                if there.status != finder.ONE or any(start < there.end and there.start < end for start, end in spans):
                    continue
            comments.append(a)
        count = len(creates) + len(edits)
        if count + len(comments) == 0:
            continue
        found.append({
            "path": entry["path"],
            "name": creates[0].get("name") if creates else None,
            "is_new": bool(creates),
            "count": count,
            "comments": len(comments),
            "items": count + len(comments),
            "time": max(str(x.get("time", "")) for x in [*creates, *edits, *comments]),
        })
    return sorted(found, key=lambda d: d["time"], reverse=True)


def _written_before(time: str, mtime: float) -> bool:
    """Whether a comment's `time` is before the note's last write (`mtime`, seconds since the epoch), with two seconds to
    spare: a comment's time is kept to the whole second, and one made just after a write must not look older than it."""
    try:
        return datetime.fromisoformat(time).timestamp() + 2 < mtime
    except ValueError:
        return False


def _cleared(entry: dict[str, Any], text: str, mtime: float) -> tuple[set[str], set[str]]:
    """What no longer belongs: the ids of the comments whose words are not in the note, though the note was written after
    the comment (a comment on words still only in the editor is newer than the file, so it is not judged), and of those the
    user resolved (a persona's comment the user decided on is kept until it has been told to her); and the ids of the
    proposals whose words are not in the note at all (one that is in it more than once is only unclear, and is left)."""
    comments, proposals = set(), set()
    for a in entry["annotations"]:
        if a.get("reply_to"):
            continue
        lost = _written_before(str(a.get("time", "")), mtime) and annotation_status(a, text) == DETACHED
        resolved = a.get("state") == RESOLVED and not a.get("verdict")
        if lost or resolved:
            comments.add(a["id"])
    for p in entry["proposals"]:
        if p.get("kind") != "create" and _written_before(str(p.get("time", "")), mtime):
            if finder.locate(text, p["find"], p.get("before", ""), p.get("after", "")).status == finder.NONE:
                proposals.add(p["id"])
    return comments, proposals


def prune(handle: str, note_path: str, text: str, mtime: float | None) -> None:
    """The note is the truth about its comments and changes (docs/decisions/069): a comment whose words are gone from it, or
    that the user resolved, and a change whose words are gone, are deleted (a comment with its answers), and a note left
    with nothing keeps no file. Nothing is judged without the note's last write time."""
    if mtime is None or not any(_cleared(store.read(handle, note_path), text, mtime)):
        return

    def drop(entry: dict[str, Any]) -> None:
        comments, proposals = _cleared(entry, text, mtime)
        entry["annotations"] = [a for a in entry["annotations"] if a.get("id") not in comments and a.get("reply_to") not in comments]
        entry["proposals"] = [p for p in entry["proposals"] if p.get("id") not in proposals]

    store.update(handle, note_path, drop)


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


def rename_folder_everywhere(old_folder: str, new_folder: str) -> None:
    """A folder was renamed (docs/decisions/073): every persona's entries for the notes under it follow."""
    for handle in _handles():
        store.move_prefix(handle, old_folder, new_folder)


def forget_everywhere(note_path: str) -> None:
    """A note was deleted for good: no persona keeps an entry for it."""
    for handle in _handles():
        forget(handle, note_path)
