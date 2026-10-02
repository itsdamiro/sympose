"""`/grounded`: the full list of notes and passages that grounded the last reply, and what else
`sent` (docs/decisions/025) says reached the model — read back exactly as recorded, never
recomputed. Split out of `runtime.py` to hold the 200-LOC-per-file cap."""

from typing import Any

_VIA_LABELS = {
    "embedding": "by meaning", "name": "named in full", "value": "by a property value",
    "search": "found by the persona's search", "opened": "opened by the persona",
}
_TOOL_LABELS = {"search_notes": "searched", "open_note": "opened", "search_chats": "searched earlier conversations for", "open_chat": "opened earlier conversation"}
_SOURCE_LABELS = {"sympose": "the Sympose reference library"}


def _note_line(n: int, note: dict[str, Any]) -> str:
    where = note["path"] + (f" — {note['heading']}" if note.get("heading") else "")
    bits = [b for b in (_VIA_LABELS.get(note.get("via")), _SOURCE_LABELS.get(note["source"])) if b]
    if "similarity" in note:
        bits.append(f"similarity {note['similarity']:.2f}")
    return f"  {n}. {where}" + (f" ({', '.join(bits)})" if bits else "")


_MEMORY_FILES = {"profile": "profile.md", "context": "context.md", "decisions": "decisions.md"}


def _search_text(call: dict[str, Any]) -> str:
    label = _TOOL_LABELS.get(call.get("tool"), call.get("tool"))
    return f'{label} "{call.get("query") or call.get("path") or call.get("id")}" ({call.get("found", 0)} found)'


def _lookups(sent: dict[str, Any], name: str) -> list[str]:
    """What the persona looked up or remembered itself (docs/decisions/040, 041): each lookup as it was made, each
    `remember`, or, when the user chose `ask`, that the model could not take tools and Sympose searched instead."""
    fallback = []
    if sent.get("mode") == "auto":
        fallback = ["You chose ask, but this model can't call tools, so Sympose searched for the message."]
    if sent.get("chats_mode") == "auto":
        fallback += ["You chose ask for earlier conversations, but this model can't call tools, so Sympose searched for the message."]
    if fallback:
        return fallback
    calls = sent.get("lookups") or []
    searches = [_search_text(c) for c in calls if c.get("tool") != "remember"]
    lines = [f"{name} looked up: " + "; ".join(searches) + "."] if searches else []
    if not searches and "ask" in (sent.get("mode"), sent.get("chats_mode")):
        lines = [f"{name} looked nothing up for this message."]
    for call in calls:
        if call.get("tool") == "remember":
            lines.append(f"{name} remembered something." if call.get("saved") else f"{name} tried to remember something and could not save it.")
    return lines


def _memory(sent: dict[str, Any]) -> list[str]:
    files = [_MEMORY_FILES[m] for m in sent.get("memory") or [] if m in _MEMORY_FILES]
    return [f"Also sent: the persona's memory ({', '.join(files)})."] if files else []


def render(sent: dict[str, Any] | None, name: str = "The persona") -> list[str]:
    """One line per note or passage the last reply grounded on, then a line for whatever else
    `sent` says reached the model (recaps, an older-turns drop, a rewritten query, a cloud model's
    categories) — each only when it happened. `[]` before any reply this session."""
    if sent is None:
        return ["No reply yet this session to show what grounded it."]
    chats = sent.get("chats") or []
    if not sent["notes"] and not sent["recaps"] and not chats:
        return ["Nothing from the vault grounded the last reply.", *_memory(sent), *_lookups(sent, name)]
    lines = ["Grounded the last reply:"] if sent["notes"] else []
    lines += [_note_line(n, note) for n, note in enumerate(sent["notes"], start=1)]
    if sent["recaps"]:
        count = len(sent["recaps"])
        lines.append(f"Also sent: {count} earlier-conversation {'recap' if count == 1 else 'recaps'}.")
    if chats:
        lines.append(f"Also sent: {len(chats)} {'exchange' if len(chats) == 1 else 'exchanges'} from earlier conversations, word for word.")
    lines += _memory(sent)
    if sent["searched"]:
        lines.append(f'A follow-up rewrite searched: "{sent["searched"]}".')
    if sent["history_dropped"]:
        n = sent["history_dropped"]
        lines.append(f"{n} older {'turn' if n == 1 else 'turns'} left out of context.")
    lines += _lookups(sent, name)
    if sent.get("cloud"):
        lines.append(f"Sent to the cloud model: {', '.join(sent['cloud'])}.")
    if sent.get("withheld"):
        lines.append(f"Held back from it: {', '.join(sent['withheld'])}.")
    return lines
