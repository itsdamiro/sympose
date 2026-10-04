"""The blocks of a turn's prompt that say what was found (docs/decisions/020): the notes, the Sympose
reference and the recaps of earlier conversations, and what to say when some of it could not be
included (it did not fit the window, or the user has not allowed a cloud model to receive it,
docs/decisions/031). How they are laid out is `prompt`."""

from typing import Any

from sympose.engine.prompt_text import (
    ANSWER_FROM_CHATS, ANSWER_FROM_RECAPS, CHATS_HER, CHATS_LABEL, CHATS_USER, CONNECTED_TO, EMPTY_NOTE, EMPTY_NOTE_ALIASES, EMPTY_NOTE_HEADINGS, LINKS, LINKS_COMPLETE, LINKS_NO_NOTE, LINKS_SEE_RELATED, MEMORY_CONTEXT_LABEL,
    MEMORY_DECISIONS_LABEL, MEMORY_PROFILE_LABEL, NO_NOTES, NO_REFERENCE, PROPERTIES_OF_NOTE, RECAPS_LABEL,
    REFERENCE_LABEL, RELATED_TO, VAULT_MAP_LABEL, WITHHELD_CONNECTIONS, WITHHELD_MEMORY, WITHHELD_NOTES, WITHHELD_PROPERTIES,
    WITHHELD_RECAPS, WITHHELD_VAULT_MAP,
)
from sympose.engine.compaction_text import NOTES_LABEL
from sympose.engine.sharing import CONNECTIONS, NOTES, PROPERTIES


def reference_block(hits: list[dict[str, Any]], omitted: int = 0) -> str:
    """`omitted`: matching passages left out to fit the window, which must not
    be reported as "nothing matched" (docs/decisions/015)."""
    if not hits:
        if omitted:
            return (
                "Sympose reference passages matched this message, but they could not be included "
                "because the conversation is too long for the context window. Don't say Sympose "
                "does not do it: say you couldn't include the reference this time."
            )
        return NO_REFERENCE
    lines = [REFERENCE_LABEL]
    for hit in hits:
        where = hit["title"] if hit.get("heading") in (None, "", hit["title"]) else f"{hit['title']} › {hit['heading']}"
        lines.append(f"- {where}: {passage_text(hit)}")
    if omitted:
        lines.append(f"({omitted} more reference passages were left out to fit the context window.)")
    return "\n".join(lines)


def passage_text(result: dict[str, Any]) -> str:
    """What a grounded note says; a note with no text of its own is shown as empty, with its other names; a
    note's properties are shown as what they are, so a value is never read as something the user wrote. A
    note's connections to others (docs/decisions/035), when it has any, ride along in the same text so
    they are dropped with the note, not as a line item of their own."""
    if result.get("kind") == "properties":
        text = PROPERTIES_OF_NOTE.format(text="; ".join(result["text"].splitlines()))
    elif result.get("kind") != "title":
        text = result["text"]
    else:
        headings = result.get("heading") and result["heading"] != result["title"]  # as `where` shows them
        text = (
            EMPTY_NOTE
            + (EMPTY_NOTE_HEADINGS if headings else "")
            + (EMPTY_NOTE_ALIASES.format(names=result["text"]) if result["text"] else "")
        )
    if links := result.get("links"):
        text += "\n" + links_line(result["title"], links, bool(result.get("related")))
    if connections := result.get("connections"):
        text += "\n" + CONNECTED_TO.format(names="; ".join(connections))
    if related := result.get("related"):
        text += "\n" + RELATED_TO.format(names="; ".join(related))
    return text


def links_line(title: str, links: dict[str, Any], has_related: bool = False) -> str:
    """A note's links (docs/decisions/067): the names shown for each direction with a count of the rest, "no note" for
    a direction with none, and the note named in each sentence (several notes' passages sit side by side in a prompt); the reminder that an unnamed note is not linked only when nothing was cut off."""

    def side(key: str) -> str:
        names = list(links[key]) + ([f"and {links[f'more_{key}']} more"] if links[f"more_{key}"] else [])
        return "; ".join(names) or LINKS_NO_NOTE

    complete = not (links["more_to"] or links["more_from"])
    line = LINKS.format(title=title, to=side("to"), from_=side("from")) + (LINKS_COMPLETE.format(title=title) if complete else "")
    return line + (LINKS_SEE_RELATED.format(title=title) if has_related else "")


def vault_map_block(text: str | None, withheld: bool = False) -> str | None:
    """The vault map (docs/decisions/035), fixed ahead of the sacrifice loop and never left out to fit the
    window; a line saying it was withheld from a cloud model the user has not allowed to receive it; or
    nothing at all with no vault."""
    if text:
        return f"{VAULT_MAP_LABEL}\n{text}"
    return WITHHELD_VAULT_MAP if withheld else None


def compaction_block(text: str | None) -> str | None:
    """The notes that stand for the first part of this conversation (docs/decisions/055), or nothing."""
    return f"{NOTES_LABEL}\n{text}" if text else None


def recaps_block(recaps: list[dict[str, Any]], omitted: int = 0, withheld: int = 0) -> str | None:
    """The recaps of earlier conversations (given newest first), or a line saying some were left out to
    fit the window or were not allowed to reach a cloud model (so she does not claim there were none),
    or nothing at all."""
    if not recaps:
        if withheld:
            return WITHHELD_RECAPS
        if omitted:
            return (
                "Recaps of earlier conversations exist but could not be included because the "
                "conversation is too long for the context window. Don't say there were none: "
                "say you couldn't include them this time."
            )
        return None
    # Named by whether it really is the last conversation, not left to the dates: a small
    # model has no idea what day it is, so "last time" would otherwise be any of them.
    # Oldest first, since it leans on what it read last, which must be the newest.
    lines = [RECAPS_LABEL] + [
        f"- {'Last conversation' if recap['last'] else 'An earlier conversation'} ({recap['date']}): {recap['text']}"
        for recap in reversed(recaps)
    ]
    if omitted:
        lines.append(f"({omitted} more recaps were left out to fit the context window.)")
    lines.append(ANSWER_FROM_RECAPS)
    return "\n".join(lines)


def chats_block(chats: list[dict[str, Any]], omitted: int = 0) -> str | None:
    """Exchanges from earlier conversations, word for word (docs/decisions/056), in the order they were
    held, or nothing at all. What a cloud model was not allowed is said with the message, not here."""
    if not chats:
        return None
    lines = [CHATS_LABEL]
    for chat in chats:
        lines.append(f"({chat['date']}, message {chat['turn']} of that conversation)\n{CHATS_USER}: {chat['user']}\n{CHATS_HER}: {chat['assistant']}")
    if omitted:
        lines.append(f"({omitted} more matching exchanges were left out to fit the context window.)")
    lines.append(ANSWER_FROM_CHATS)
    return "\n\n".join(lines)


def memory_block(
    profile: str | None, context: str | None, decisions: list[str], withheld: bool = False
) -> str | None:
    """A persona's own memory (docs/decisions/041): `profile.md` and `context.md` whole, and
    `decisions.md`'s surviving entries (already trimmed from their oldest end by `budget.fit`
    when it had to), or a line saying the user has not allowed a cloud model to receive any of
    it, or nothing at all when the persona has none yet."""
    if not (profile or context or decisions):
        return WITHHELD_MEMORY if withheld else None
    parts = []
    if profile:
        parts.append(f"{MEMORY_PROFILE_LABEL}\n{profile}")
    if context:
        parts.append(f"{MEMORY_CONTEXT_LABEL}\n{context}")
    if decisions:
        parts.append(f"{MEMORY_DECISIONS_LABEL}\n" + "\n".join(decisions))
    return "\n\n".join(parts)


def notes_block(
    grounding_results: list[dict[str, Any]], omitted: int = 0, withheld: dict[str, int] | None = None
) -> str:
    """`omitted` is how many matching passages were left out to fit the
    model's window (docs/decisions/015): the block must say so, since "no
    notes matched" would be false and the model would tell the user the vault
    has nothing on it. `withheld` is what the user has not allowed a cloud
    model to receive (docs/decisions/031), which must be said for the same reason."""
    withheld = withheld or {}
    reasons_by_category = ((NOTES, WITHHELD_NOTES), (PROPERTIES, WITHHELD_PROPERTIES), (CONNECTIONS, WITHHELD_CONNECTIONS))
    held = [text for category, text in reasons_by_category if withheld.get(category)]
    if not grounding_results:
        # Every reason there is, since "the vault has nothing" would be false for each of them.
        reasons = held + (
            [
                "Notes in the vault matched this message, but they could not be included because "
                "the conversation is too long for the context window. Don't say the vault "
                "has nothing on it: say you couldn't include the matching notes this time."
            ]
            if omitted
            else []
        )
        return "\n".join(reasons) or NO_NOTES
    lines = ["Notes found in the vault for this message:"]
    seen: set[tuple[str, str]] = set()
    for result in grounding_results:
        heading = result.get("heading")
        where = result["rel_path"]
        if heading and heading != result["title"]:
            where += f" › {heading}"
        if (result["title"], where) in seen:  # two passages under one label read as two notes (docs/decisions/067)
            where += ", another passage of the same note"
        seen.add((result["title"], where))
        lines.append(f"- {result['title']} ({where}): {passage_text(result)}")
    if omitted:
        lines.append(f"({omitted} more matching passages were left out to fit the context window.)")
    lines.extend(held)
    return "\n".join(lines)
