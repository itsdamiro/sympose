"""`/grounded`: the full list of notes and passages that grounded the last reply, and what else
`sent` (docs/decisions/025) says reached the model — read back exactly as recorded, never
recomputed. Split out of `runtime.py` to hold the 200-LOC-per-file cap."""

from typing import Any

_VIA_LABELS = {
    "embedding": "by meaning", "name": "named in full", "value": "by a property value",
    "search": "found by her search", "opened": "opened by her",
}
_TOOL_LABELS = {"search_notes": "searched", "open_note": "opened"}
_SOURCE_LABELS = {"sympose": "the Sympose reference library"}


def _note_line(n: int, note: dict[str, Any]) -> str:
    where = note["path"] + (f" — {note['heading']}" if note.get("heading") else "")
    bits = [b for b in (_VIA_LABELS.get(note.get("via")), _SOURCE_LABELS.get(note["source"])) if b]
    if "similarity" in note:
        bits.append(f"similarity {note['similarity']:.2f}")
    return f"  {n}. {where}" + (f" ({', '.join(bits)})" if bits else "")


def _lookups(sent: dict[str, Any]) -> list[str]:
    """What the persona looked up herself (docs/decisions/040), when the user chose `ask`: each call as
    it was made, or that the model could not take tools and Sympose searched instead."""
    if sent.get("mode") == "auto":
        return ["You chose ask, but this model can't call tools, so Sympose searched for the message."]
    if sent.get("mode") != "ask":
        return []
    calls = [
        f'{_TOOL_LABELS.get(call.get("tool"), call.get("tool"))} "{call.get("query") or call.get("path")}"'
        f" ({call.get('found', 0)} found)"
        for call in sent.get("lookups") or []
    ]
    return ["She looked up: " + "; ".join(calls) + "."] if calls else ["She looked nothing up for this message."]


def render(sent: dict[str, Any] | None) -> list[str]:
    """One line per note or passage the last reply grounded on, then a line for whatever else
    `sent` says reached the model (recaps, an older-turns drop, a rewritten query, a cloud model's
    categories) — each only when it happened. `[]` before any reply this session."""
    if sent is None:
        return ["No reply yet this session to show what grounded it."]
    if not sent["notes"] and not sent["recaps"]:
        return ["Nothing from the vault grounded the last reply.", *_lookups(sent)]
    lines = ["Grounded the last reply:"] if sent["notes"] else []
    lines += [_note_line(n, note) for n, note in enumerate(sent["notes"], start=1)]
    if sent["recaps"]:
        count = len(sent["recaps"])
        lines.append(f"Also sent: {count} earlier-conversation {'recap' if count == 1 else 'recaps'}.")
    if sent["searched"]:
        lines.append(f'A follow-up rewrite searched: "{sent["searched"]}".')
    if sent["history_dropped"]:
        n = sent["history_dropped"]
        lines.append(f"{n} older {'turn' if n == 1 else 'turns'} left out of context.")
    lines += _lookups(sent)
    if sent.get("cloud"):
        lines.append(f"Sent to the cloud model: {', '.join(sent['cloud'])}.")
    if sent.get("withheld"):
        lines.append(f"Held back from it: {', '.join(sent['withheld'])}.")
    return lines
