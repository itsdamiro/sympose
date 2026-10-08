"""How the model's prompt is laid out (docs/decisions/020); the text itself, all of
it, is `prompt_text`, re-exported here so `prompt` is the one place to look. A small
model follows what sits last and nearest the question over what came first, so the
layout is:

    system:  the persona's soul, its name, how Sympose works, the rules, the recaps
    history: the conversation so far
    user:    the shape of the vault, the notes found for this message, then the message

The notes travel with the question, not in the system prompt, where the soul's
own instructions ("ask a real question", "have a point of view") outweighed
them and the model chatted instead of answering from the notes (docs/decisions/019
and 020). The shape of the vault travels with them for the same reason: in the system
prompt she denied knowing the vault's size with the answer in front of her
(docs/decisions/039). The engine's rules stay after the soul, so no soul can weaken them
(docs/decisions/012)."""

from typing import Any

from sympose.engine import reference as reference_mod
from sympose.engine.prompt_blocks import (
    chats_block, compaction_block, memory_block, notes_block, recaps_block, reference_block, vault_map_block,
)
from sympose.engine.prompt_text import (
    ANSWER_FROM_CHATS, CHAT_TOOLS_TEXT, ANSWER_FROM_NOTES, ANSWER_FROM_RECAPS, ANSWER_FROM_REFERENCE, CHATS_LABEL, SKILL_LABEL, WITHHELD_CHATS, CONNECTED_TO, RELATED_TO, DEFAULT_SOUL, GROUNDING_RULE,
    HOW_YOU_WORK, HOW_YOU_WORK_ASK, GROUNDING_RULE_ASK, MEMORY_CONTEXT_LABEL, MEMORY_CONTEXT_MARK,
    MEMORY_DECISIONS_LABEL, MEMORY_NO_CHANGE, MEMORY_PROFILE_LABEL, MEMORY_PROFILE_MARK, MEMORY_REFRESH_INSTRUCTIONS,
    NO_NOTES, NO_RECAP, NO_REFERENCE, NO_TOPIC, POINT_TO_REFERENCE, RECAPS_LABEL,
    RECAP_INSTRUCTIONS, REFERENCE_LABEL, REWRITE_INSTRUCTIONS, STATUS_PHRASES_INSTRUCTIONS, SYMPOSE_RULE,
    VAULT_MAP_LABEL, WITHHELD_CONNECTIONS, WITHHELD_MEMORY, WITHHELD_NOTES, WITHHELD_PROPERTIES, WITHHELD_RECAPS,
    WITHHELD_VAULT_MAP, how_you_work,
)
from sympose.engine.sharing import CHATS, MEMORY, RECAPS
from sympose.persona_files import load_soul
from sympose.profile import reference_persona_names

__all__ = [
    "ANSWER_FROM_CHATS", "CHAT_TOOLS_TEXT", "CHATS_LABEL", "WITHHELD_CHATS", "ANSWER_FROM_NOTES", "ANSWER_FROM_RECAPS", "ANSWER_FROM_REFERENCE", "CONNECTED_TO", "RELATED_TO", "DEFAULT_SOUL",
    "GROUNDING_RULE", "GROUNDING_RULE_ASK", "HOW_YOU_WORK", "HOW_YOU_WORK_ASK", "MEMORY_CONTEXT_LABEL",
    "MEMORY_CONTEXT_MARK", "MEMORY_DECISIONS_LABEL", "MEMORY_NO_CHANGE", "MEMORY_PROFILE_LABEL",
    "MEMORY_PROFILE_MARK", "MEMORY_REFRESH_INSTRUCTIONS", "NO_NOTES", "NO_RECAP", "NO_REFERENCE", "NO_TOPIC",
    "POINT_TO_REFERENCE", "RECAPS_LABEL", "RECAP_INSTRUCTIONS", "REFERENCE_LABEL", "STATUS_PHRASES_INSTRUCTIONS",
    "REWRITE_INSTRUCTIONS", "SYMPOSE_RULE", "VAULT_MAP_LABEL", "WITHHELD_CONNECTIONS", "WITHHELD_MEMORY",
    "WITHHELD_NOTES", "WITHHELD_PROPERTIES", "WITHHELD_RECAPS", "WITHHELD_VAULT_MAP",
    "build_messages", "build_system_prompt", "build_user_turn",
]

# -- the layout --


def build_system_prompt(
    profile: dict[str, Any],
    recaps: list[dict[str, Any]] | None = None,
    recaps_omitted: int = 0,
    recaps_withheld: int = 0,
    lookup: bool = False,
    memory_profile: str | None = None,
    memory_context: str | None = None,
    memory_decisions: list[str] | None = None,
    memory_withheld: bool = False,
    remember: str | None = None,
    compaction: str | None = None,
    chats: list[dict[str, Any]] | None = None,
    chats_omitted: int = 0,
    chat_tools: bool = False,
) -> str:
    # `handle` is always lowercase (`profile.get_profile` lowercases it
    # before building a file path) -- title-cased here so a fallback
    # profile's identity line reads "Samantha", not "samantha". The
    # `or "Sam"` (not a `.get(..., "Sam")` default) matters: a profile
    # with an explicit `handle: null`/blank YAML value has the key
    # present but falsy, and `.get(key, default)`'s default only ever
    # applies when the key is *absent* -- a `.get("handle", "Sam")`
    # default here would silently return `None` and crash on `.title()`.
    name = profile.get("name") or (profile.get("handle") or "Sam").title()
    soul = load_soul(profile["handle"]) if profile.get("handle") else None
    aliases = [a for a in profile.get("aliases") or [] if isinstance(a, str) and a.strip()]
    identity = f"Your name is {name}." + (f" The user may also call you {' or '.join(aliases)}." if aliases else "")
    # `lookup`: the persona looks up notes itself, so it is told how (docs/decisions/040).
    # `remember`: whether, and how, it may write to decisions.md this turn (docs/decisions/041).
    parts = (
        [soul or DEFAULT_SOUL, identity, how_you_work(ask=lookup, remember=remember), GROUNDING_RULE_ASK]
        if lookup
        else [soul or DEFAULT_SOUL, identity, how_you_work(ask=lookup, remember=remember), GROUNDING_RULE]
    )
    if profile.get("sympose_reference"):
        parts.append(SYMPOSE_RULE)
    # A persona's own memory (docs/decisions/041): fixed, like the vault map, since `profile.md`
    # and `context.md` are meant to stay small by design; `decisions.md` arrives already trimmed
    # by `budget.fit` when it had to be. Placed near the soul and rules, ahead of recaps, since
    # it is foundational the way they are, not a recall of one earlier conversation.
    memory_text = memory_block(memory_profile, memory_context, memory_decisions or [], memory_withheld)
    if memory_text:
        parts.append(memory_text)
    # Recaps go here, not in the message: beside a request in the middle of a chat that is on the
    # same topic as a recap, they made her comment on the conversation instead of continuing it
    # (docs/decisions/026).
    recaps_text = recaps_block(recaps or [], recaps_omitted, recaps_withheld)
    if recaps_text:
        parts.append(recaps_text)
    # Earlier conversations word for word (docs/decisions/056), after the recaps they go deeper than.
    chats_text = chats_block(chats or [], chats_omitted)
    if chats_text:
        parts.append(chats_text)
    if chat_tools:  # she looks in earlier conversations herself (docs/decisions/056, `past_chats` `ask`)
        parts.append(CHAT_TOOLS_TEXT)
    # The notes of a compaction (docs/decisions/055) come last: they stand for the start of this very
    # conversation, so they sit closest to the history that follows. Fixed, like the memory above.
    notes_text = compaction_block(compaction)
    if notes_text:
        parts.append(notes_text)
    return "\n\n".join(parts)


def build_user_turn(
    user_message: str,
    grounding_results: list[dict[str, Any]],
    omitted: int = 0,
    reference: bool = False,
    reference_omitted: int = 0,
    point_to: list[str] | None = None,
    withheld: dict[str, int] | None = None,
    vault_map: str | None = None,
    vault_map_withheld: bool = False,
    lookup: bool = False,
    chats_withheld: bool = False,
    skill: str | None = None,
) -> str:
    """`chats_withheld`: earlier conversations matched but a cloud model may not have them; the line saying so
    sits with the message, where a small model weighs it most (the notes' own withheld lines do too).
    `lookup`: no notes were searched for the message, the persona looks them up itself
    (docs/decisions/040), so there is no notes block to say "nothing matched" about. `vault_map`, or the line saying a cloud model may not have it (`vault_map_withheld`), comes first
    (docs/decisions/039): it is fixed and never left out to fit the window, unlike the notes below it.
    `reference`: the persona has the Sympose reference library, so the turn
    says what it found in it (or that nothing matched). Its passages are marked
    `source: reference.SOURCE` and kept apart from the user's own notes; `omitted` and
    `reference_omitted` count the passages of each left out for size. `point_to`:
    the personas that have the library, for one that does not to send the user to. `skill`: the steps of the skill
    chosen for the message (docs/decisions/077), set right before it where a small model weighs it most."""
    reference_hits = [h for h in grounding_results if h.get("source") == reference_mod.SOURCE]
    notes = [h for h in grounding_results if h.get("source") != reference_mod.SOURCE]
    map_text = vault_map_block(vault_map, vault_map_withheld)
    parts = [map_text] if map_text else []
    if not lookup:
        parts.append(notes_block(notes, omitted, withheld))
        if notes:
            parts.append(ANSWER_FROM_NOTES)
    if reference:
        parts.append(reference_block(reference_hits, reference_omitted))
        if reference_hits:
            parts.append(ANSWER_FROM_REFERENCE)
    if point_to and not reference:
        parts.append(POINT_TO_REFERENCE.format(names=" or ".join(point_to)))
    if chats_withheld:
        parts.append(WITHHELD_CHATS)
    if skill:
        parts.append(f"{SKILL_LABEL}\n{skill}")
    parts.append(f"User's message: {user_message}")
    return "\n\n".join(parts)


def build_messages(
    profile: dict[str, Any],
    history: list[dict[str, str]],
    grounding_results: list[dict[str, Any]],
    user_message: str,
    omitted: int = 0,
    reference_omitted: int = 0,
    point_to: list[str] | None = None,
    recaps: list[dict[str, Any]] | None = None,
    recaps_omitted: int = 0,
    withheld: dict[str, int] | None = None,
    vault_map: str | None = None,
    vault_map_withheld: bool = False,
    lookup: bool = False,
    memory_profile: str | None = None,
    memory_context: str | None = None,
    memory_decisions: list[str] | None = None,
    remember: str | None = None,
    compaction: str | None = None,
    chats: list[dict[str, Any]] | None = None,
    chats_omitted: int = 0,
    chat_tools: bool = False,
    skill: str | None = None,
) -> list[dict[str, str]]:
    """The system prompt (with the recaps of earlier conversations, docs/decisions/023 and 026, and the
    persona's own memory, docs/decisions/041), the history as it was said (the notes of earlier turns
    are not repeated), and this turn's vault map (docs/decisions/035 and 039) and notes with the
    message. `point_to`: the personas that have the reference library, read from the roster when not
    given (a turn gives it once, since fitting builds this many times). `withheld`: what a cloud model
    was not sent because the user has not allowed it, by category (docs/decisions/031). `vault_map`,
    `vault_map_withheld`, `memory_profile` and `memory_context` are constant across every attempt of
    the prompt-fitting loop (docs/decisions/015): unlike grounding, recaps, `memory_decisions` and
    history, none of the four is ever sacrificed to fit the window."""
    withheld = withheld or {}
    system = {
        "role": "system",
        "content": build_system_prompt(
            profile, recaps, recaps_omitted, withheld.get(RECAPS, 0), lookup,
            memory_profile, memory_context, memory_decisions, bool(withheld.get(MEMORY, 0)), remember, compaction,
            chats, chats_omitted, chat_tools,
        ),
    }
    has_library = bool(profile.get("sympose_reference"))
    if point_to is None:
        point_to = [] if has_library else reference_persona_names()
    user = {
        "role": "user",
        "content": build_user_turn(
            user_message, grounding_results, omitted, has_library, reference_omitted, point_to, withheld,
            vault_map, vault_map_withheld, lookup, bool(withheld.get(CHATS, 0)), skill,
        ),
    }
    return [system, *history, user]
