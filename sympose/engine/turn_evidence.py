"""What one turn knows before its prompt is sized (docs/decisions/006): the vault and reference passages found for
the message, the recaps and earlier conversations, the vault map, the persona's memory and the condensed start of a
long conversation, each already limited to what the model may receive (docs/decisions/031). `gather` finds it all;
`prompt_builder` closes over it so the fitting loop (docs/decisions/015) can build the prompt again with less."""

from dataclasses import dataclass
from typing import Any, Callable

from sympose import profile as profile_mod, vault_map as vault_map_mod
from sympose.engine import (
    budget, connections, followup, grounding, grounding_properties, memory, past_chats, persona_tools, prompt, recap,
    recap_refresh, reference, related, session_compaction, sharing, skills, turn_status,
)


@dataclass
class Evidence:
    grounding: list[dict[str, Any]]
    searched: str | None  # the query the vault was searched with when it was a rewrite, else None
    rewrite: bool  # whether the follow-up rewrite step was asked (an extra model call, docs/decisions/025)
    recaps: list[dict[str, Any]]
    chats: list[dict[str, Any]]
    withheld: dict[str, int]  # what the model may not receive, by category, with how many items
    map_text: str
    map_allowed: bool
    mem: Any  # `memory.for_turn`'s answer
    notes: Any  # `session_compaction.notes`'s answer
    point_to: list[str]
    reference_found: int
    vault_found: int
    skill: str | None = None  # the skill chosen for this message (docs/decisions/077), as the prompt carries it


def interleave(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`first[0], second[0], first[1], second[1], ...`, then whichever list is longer."""
    merged: list[dict[str, Any]] = []
    for i in range(max(len(first), len(second))):
        merged.extend(part[i] for part in (first, second) if i < len(part))
    return merged


def split_chats(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The recaps and the earlier-conversation exchanges (which carry a `user` side) of a list that holds both."""
    return [i for i in items if "user" not in i], [i for i in items if "user" in i]


def gather(
    persona: dict[str, Any],
    handle: str,
    sid: str,
    user_message: str,
    history: list[dict[str, str]],
    target_model: str,
    limits: "budget.Budget | None",
    modes: "persona_tools.Modes",
    existing: Any,
) -> Evidence:
    # In `ask` Sympose does not search the vault for the message: the persona decides (docs/decisions/040).
    if modes.ask:
        vault_hits, searched, rewrite = [], None, False
    else:
        turn_status.set_phase(handle, turn_status.SEARCHING)
        vault_hits, searched, rewrite = followup.ground(persona, user_message, history, target_model, limits)
        turn_status.set_phase(handle, turn_status.ASKING)
    # The two sources take turns, the reference first: when the prompt does not fit, the
    # end of the list goes first, so the best passage of each source stays longest and
    # neither's evidence is dropped wholesale before the other's (docs/decisions/022).
    grounding_results = interleave(reference.ground(persona, user_message), vault_hits)
    # Each note's connections to others (docs/decisions/035) ride inside its own passage, before
    # properties are appended below, so both `gate` and the sacrifice loop see them as one item.
    grounding_results = connections.for_hits(persona, grounding_results)
    # Then the notes close in meaning (docs/decisions/066), a separate guess beside them, never merged into them.
    grounding_results = related.for_hits(persona, grounding_results)
    # The properties of the notes found come after all the text, so they are the first to go (docs/decisions/030).
    index = grounding.scope_index(persona) if vault_hits else None
    if index is not None:
        grounding_results += grounding_properties.for_hits(index.properties, vault_hits)
    point_to = [] if persona.get("sympose_reference") else profile_mod.reference_persona_names()

    # What earlier conversations were about (docs/decisions/023); the session being
    # run is excluded, its own turns are already the history. Cleared, not left as "asking",
    # for the wait itself: `recap_refresh.is_running` is true for exactly this window, so clearing
    # here lets `background_status.activity` fall through to its own, more specific "recap" phrase
    # instead of a misleading "asking" while the turn is actually blocked on it (docs/decisions/043).
    turn_status.set_phase(handle, None)
    recap_refresh.wait_for_refresh(handle)  # right after launch the recap may still be being written
    turn_status.set_phase(handle, turn_status.ASKING)
    # Only what this model may receive goes any further (docs/decisions/031): the prompt, its token
    # count and the record all see the same set.
    # Earlier conversations word for word (docs/decisions/056) are found locally and pass the same gate.
    gated = sharing.gate(
        target_model, grounding_results, recap.latest(handle, exclude=sid), past_chats.find(handle, user_message, sid, tools=modes.chats),
    )
    withheld = gated.withheld

    # The vault map (docs/decisions/035): computed locally either way (nothing leaves the machine by
    # computing it), sent only when the model may receive it; fixed for every attempt of the fitting
    # loop, unlike the notes, recaps and history it sizes around.
    map_text = vault_map_mod.build(persona)
    map_allowed = sharing.VAULT_MAP in sharing.allowed(target_model)
    if map_text and not map_allowed:
        withheld[sharing.VAULT_MAP] = 1

    # A persona's own memory (docs/decisions/041): read locally either way, sent only when the model
    # may receive it. `profile.md`/`context.md` are fixed like the vault map; `decisions.md`'s entries
    # go through the fitting loop and may come back trimmed from their oldest end.
    mem = memory.for_turn(handle, sharing.MEMORY in sharing.allowed(target_model))
    if mem.withheld:
        withheld[sharing.MEMORY] = 1

    chosen = skills.select(persona, user_message, skills.tools_of(modes.ask, modes.edit is not None and modes.edit.active), sharing.is_local(target_model))
    reference_found = sum(1 for h in gated.grounding if h.get("source") == reference.SOURCE)
    return Evidence(
        grounding=gated.grounding,
        searched=searched,
        rewrite=rewrite,
        recaps=gated.recaps,
        chats=gated.chats,
        withheld=withheld,
        map_text=map_text,
        map_allowed=map_allowed,
        mem=mem,
        # The notes that stand for the start of a long conversation (docs/decisions/055): fixed for every
        # attempt of the fitting loop, since they are all that is left of the turns they replace.
        notes=session_compaction.notes(existing),
        point_to=point_to,
        reference_found=reference_found,
        vault_found=len(gated.grounding) - reference_found,
        skill=skills.text_for(chosen) if chosen else None,
    )


def prompt_builder(
    persona: dict[str, Any], user_message: str, found: Evidence, modes: "persona_tools.Modes",
) -> Callable[[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], list[str]], list[dict[str, str]]]:
    """The function the fitting loop calls with the history, passages, recaps and decisions that still fit."""

    def build(
        hist: list[dict[str, str]],
        hits: list[dict[str, Any]],
        recap_chat_items: list[dict[str, Any]],
        decisions: list[str],
    ) -> list[dict[str, str]]:
        recaps, chats = split_chats(recap_chat_items)
        # Passages of each source that did not fit are left out: the prompt says
        # so, per source, instead of claiming nothing matched.
        kept_reference = sum(1 for h in hits if h.get("source") == reference.SOURCE)
        return prompt.build_messages(
            persona,
            hist,
            hits,
            user_message,
            omitted=found.vault_found - (len(hits) - kept_reference),
            reference_omitted=found.reference_found - kept_reference,
            point_to=found.point_to,
            recaps=recaps,
            recaps_omitted=len(found.recaps) - len(recaps),
            chats=chats,
            chats_omitted=len(found.chats) - len(chats),
            withheld=found.withheld,
            vault_map=found.map_text if found.map_allowed else None,
            vault_map_withheld=bool(found.map_text) and not found.map_allowed,
            lookup=modes.ask,
            memory_profile=found.mem.profile,
            memory_context=found.mem.context,
            memory_decisions=decisions,
            remember=modes.remember,
            compaction=found.notes,
            chat_tools=modes.chats,
            skill=found.skill,
            personas=bool(modes.edit and modes.edit.active and modes.edit.proposes_personas),
        )

    return build
