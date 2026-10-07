"""The open comments on the note open in the editor, which travel with the user's message (docs/decisions/069): the
ones still open and still on a passage of the text, each with the answers under it, the newest within a cap so a long
list does not inflate every turn. They are vault-derived (the passage and the user's own words about it), so a cloud
model gets them only when the `annotations` category is approved (ADR 031); `edit_turn` asks that."""

from dataclasses import dataclass
from datetime import datetime

from sympose import note_changes, settings_store
from sympose import note_changes_store as store

CAP_SETTING = "annotations_cap"
DEFAULT_CAP, MIN_CAP = 20, 1  # comments carried with one message
DECIDED_CAP = 10  # decisions on her comments told to her with one message


@dataclass(frozen=True)
class Comment:
    quote: str
    thread: tuple[tuple[str, str], ...]  # (who, text), `who` being "user" or "persona", oldest first
    new: bool | None = None  # said (or answered) since the previous turn; `None` when there is no earlier turn to compare with


@dataclass(frozen=True)
class Decision:
    """What the user decided on one of her comments since her last reply (ADR 069): `verdict` is `accepted` or `declined`,
    `reason` the user's latest reply under it (what they wrote before declining)."""

    quote: str
    verdict: str
    reason: str | None = None
    id: str = ""  # the comment's, so it can be removed once she has been told


@dataclass(frozen=True)
class Found:
    items: tuple[Comment, ...] = ()
    left_out: int = 0  # older ones the cap left behind
    decided: tuple[Decision, ...] = ()
    settle: tuple[str, ...] = ()  # decided comments to remove once this turn's reply is recorded: told to her now, or decided before her last reply and so never to be told


def cap() -> int:
    value = settings_store.get(CAP_SETTING)
    ok = isinstance(value, int) and not isinstance(value, bool) and value >= MIN_CAP
    return value if ok else DEFAULT_CAP


def _later(time: str, since: str) -> bool:
    """Whether `time` is after `since`, compared as times (a session's carry fractions of a second, a comment's do not)."""
    try:
        return datetime.fromisoformat(time) > datetime.fromisoformat(since)
    except ValueError:
        return False


def _decided(entry: dict, answers: dict[str, list[dict]], since: str | None) -> tuple[Decision, ...]:
    """The verdicts given on her comments after `since`, oldest first, the newest within a small cap. Nothing when there
    is no earlier turn (`since` is `None`): there is no reply of hers to have decided since."""
    if since is None:
        return ()
    made = [a for a in entry["annotations"] if not a.get("reply_to") and a.get("verdict") and _later(str(a.get("decided", "")), since)]
    made.sort(key=lambda a: str(a.get("decided", "")))
    def reason(a: dict) -> str | None:
        mine = sorted((x for x in answers.get(a["id"], []) if x.get("author") == "user"), key=lambda r: str(r.get("time", "")))
        return mine[-1]["text"] if mine else None
    return tuple(Decision(a["quote"], a["verdict"], reason(a), a["id"]) for a in made[-DECIDED_CAP:])


def _settled(entry: dict, told: tuple[Decision, ...], since: str | None) -> tuple[str, ...]:
    """The decided comments of her that have done their work: the ones told now, and the ones decided before her last reply
    (a decision is told once, in the next message after it, so those can never be told). Nothing before there is an earlier
    turn: a decision then is still waiting to be told."""
    if since is None:
        return ()
    old = {a["id"] for a in entry["annotations"] if not a.get("reply_to") and a.get("verdict") and not _later(str(a.get("decided", "")), since)}
    return tuple(sorted(old | {d.id for d in told}))


def gather(handle: str, note, since: str | None = None) -> Found:
    """The open comments of `handle` on `note` (an `OpenNote`, or `None`), attached to a passage of its current text.
    `since` is when the previous turn of this conversation was recorded, if there was one: it decides which are new."""
    if note is None:
        return Found()
    entry = store.read(handle, note.path)
    answers: dict[str, list[dict]] = {}
    for item in entry["annotations"]:
        if item.get("reply_to"):
            answers.setdefault(item["reply_to"], []).append(item)
    roots = [
        a for a in entry["annotations"]
        if not a.get("reply_to") and a.get("state") == note_changes.OPEN
        and note_changes.annotation_status(a, note.text) == note_changes.ATTACHED
    ]
    roots.sort(key=lambda a: str(a.get("time", "")))
    limit = cap()
    kept = roots[-limit:]
    def comment(a: dict) -> Comment:
        thread = [a, *sorted(answers.get(a["id"], []), key=lambda r: str(r.get("time", "")))]
        fresh = None if since is None else any(_later(str(x.get("time", "")), since) for x in thread)
        return Comment(a["quote"], tuple((x["author"], x["text"]) for x in thread), fresh)

    decided = _decided(entry, answers, since)
    return Found(tuple(comment(a) for a in kept), len(roots) - len(kept), decided, _settled(entry, decided, since))


def block(found: Found, persona_name: str) -> str:
    """The comments as the model reads them, with where each is and who said what, and what the user decided on hers."""
    parts = []
    if found.items:
        lines = ["The user's open comments on this note:"]
        for comment in found.items:
            label = "" if comment.new is None else " (new since your last reply)" if comment.new else " (from before your last reply)"
            lines.append(f"- On “{comment.quote}”{label}:")
            lines.extend(f"    {persona_name if who == 'persona' else 'the user'}: {text}" for who, text in comment.thread)
        if found.left_out:
            lines.append(f"({found.left_out} older comments are left out.)")
        parts.append("\n".join(lines))
    if found.decided:
        lines = ["Since your last reply the user decided on your comments:"]
        for d in found.decided:
            lines.append(f"- On “{d.quote}”: accepted." if d.verdict == "accepted" else f"- On “{d.quote}”: declined" + (f", the user wrote: {d.reason}" if d.reason else "") + ".")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
