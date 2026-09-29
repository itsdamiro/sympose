"""One turn, end to end (docs/decisions/006). `run_turn` stays a single
atomic unit (ground -> build -> call -> persist) — message queueing
(docs/decisions/008) is implemented at the CLI call site, sequencing and
attributing `run_turn` calls per persona, not inside this function.
`call_model` is a single blocking, non-cancelable call (ADR 007); there is
no in-progress generation to check for new input against, so the seam this
docstring used to point at (between the model call returning and the turn
persisting) was never exercised — see ADR 008."""

from typing import Any

from sympose import profile as profile_mod, vault_map as vault_map_mod
from sympose.engine import (
    budget, connections, followup, grounding, grounding_properties, lookup, memory, memory_tools, persona_tools,
    prompt, recap, recap_refresh, reference, session, sharing, tool_support,
)
from sympose.engine import model as model_mod
from sympose.engine.model import EngineModelError
from sympose.engine.turn_record import sent_record
from sympose.engine.turn_result import TurnResult

__all__ = ["TurnResult", "run_turn", "EngineModelError", "PersonaNotFoundError"]


class PersonaNotFoundError(Exception):
    """`resolve_profile(handle)` returned `None` — defensive-only today
    (the CLI's persona picker only ever offers real roster handles), but
    must degrade to a legible error instead of crashing a few lines
    further into `run_turn` on a bare `None`."""


def _interleave(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`first[0], second[0], first[1], second[1], ...`, then whichever list is longer."""
    merged: list[dict[str, Any]] = []
    for i in range(max(len(first), len(second))):
        merged.extend(part[i] for part in (first, second) if i < len(part))
    return merged


def _reply_tokens(text: str, model: str) -> int:
    return budget.count_tokens([{"role": "assistant", "content": text}], model)


def run_turn(
    handle: str,
    user_message: str,
    session_id: str | None = None,
    model: str | None = None,
) -> TurnResult:
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        raise PersonaNotFoundError(f"No profile found for persona '{handle}'.")
    sid = session_id or session.new_session_id()
    # A brand-new sid resolves to a file that doesn't exist yet, so this is
    # a cheap `os.path.exists` check in that case, not a real extra read —
    # loading unconditionally lets the already-loaded state be handed
    # straight to `append_turn` below instead of it re-reading the file.
    existing = session.load_session(handle, sid)
    history = session.history_as_messages(existing)

    # An explicit per-call model wins; otherwise `resolve_model` owns the
    # rest of the order (persona's model > setting > default), so this
    # and every display of "which model runs" share one definition.
    target_model = model or model_mod.resolve_model(persona.get("model"))
    # `ask` (docs/decisions/040) and `remember` (docs/decisions/041) are independent settings, each
    # checked against what this model can actually do and, for `ask`, whether the persona has a
    # vault to look up at all -- see `persona_tools.resolve`.
    modes = persona_tools.resolve(persona, target_model)
    try:
        result = _run(persona, handle, user_message, sid, existing, history, target_model, modes)
    except lookup.ToolsRefused:
        # The model failed with the tools: the turn is run with none, and a model that does that twice in a
        # row while working without them is not given tools again (docs/decisions/040). `remember` falls
        # back to its marker mechanism for this same retry, since that needs no tool-calling at all -- the
        # user's "remember this" is not lost just because the tool attempt was.
        retry_remember = memory.MARKER if memory.remember_enabled() else None
        result = _run(
            persona, handle, user_message, sid, existing, history, target_model,
            persona_tools.Modes(False, modes.chose_ask, retry_remember),
        )
        tool_support.note_refusal(target_model)
        return result
    if modes.ask or modes.remember == memory.TOOL:
        tool_support.note_success(target_model)
    return result


def _run(
    persona: dict[str, Any],
    handle: str,
    user_message: str,
    sid: str,
    existing: Any,
    history: list[dict[str, str]],
    target_model: str,
    modes: "persona_tools.Modes",
) -> TurnResult:
    ask, chose_ask, remember = modes.ask, modes.chose_ask, modes.remember
    # The prompt is sized to this model's window, not left to the runtime's
    # silent cut (docs/decisions/015); the follow-up rewrite shares that window.
    limits = budget.budget_for(target_model)
    # In `ask` Sympose does not search the vault for the message: the persona decides (docs/decisions/040).
    vault_hits, searched, rewrite = (
        ([], None, False) if ask else followup.ground(persona, user_message, history, target_model, limits)
    )
    # The two sources take turns, the reference first: when the prompt does not fit, the
    # end of the list goes first, so the best passage of each source stays longest and
    # neither's evidence is dropped wholesale before the other's (docs/decisions/022).
    grounding_results = _interleave(reference.ground(persona, user_message), vault_hits)
    # Each note's connections to others (docs/decisions/035) ride inside its own passage, before
    # properties are appended below, so both `gate` and the sacrifice loop see them as one item.
    grounding_results = connections.for_hits(persona, grounding_results)
    # The properties of the notes found come after all the text, so they are the first to go (docs/decisions/030).
    index = grounding.scope_index(persona) if vault_hits else None
    if index is not None:
        grounding_results += grounding_properties.for_hits(index.properties, vault_hits)
    point_to = [] if persona.get("sympose_reference") else profile_mod.reference_persona_names()

    # What earlier conversations were about (docs/decisions/023); the session being
    # run is excluded, its own turns are already the history.
    recap_refresh.wait_for_refresh(handle)  # right after launch the recap may still be being written
    # Only what this model may receive goes any further (docs/decisions/031): the prompt, its token
    # count and the record below all see the same set.
    gated = sharing.gate(target_model, grounding_results, recap.latest(handle, exclude=sid))
    grounding_results, recaps_found, withheld = gated.grounding, gated.recaps, gated.withheld

    # The vault map (docs/decisions/035): computed locally either way (nothing leaves the machine by
    # computing it), sent only when the model may receive it; fixed for every attempt of the fitting
    # loop below, unlike the notes, recaps and history it sizes around.
    map_text = vault_map_mod.build(persona)
    map_allowed = sharing.VAULT_MAP in sharing.allowed(target_model)
    if map_text and not map_allowed:
        withheld[sharing.VAULT_MAP] = 1

    # A persona's own memory (docs/decisions/041): read locally either way, sent only when the model
    # may receive it. `profile.md`/`context.md` are fixed like the vault map; `decisions.md`'s entries
    # go through the fitting loop below and may come back trimmed from their oldest end.
    mem = memory.for_turn(handle, sharing.MEMORY in sharing.allowed(target_model))
    if mem.withheld:
        withheld[sharing.MEMORY] = 1

    reference_found = sum(1 for h in grounding_results if h.get("source") == reference.SOURCE)
    vault_found = len(grounding_results) - reference_found

    def build(
        hist: list[dict[str, str]],
        hits: list[dict[str, Any]],
        recaps: list[dict[str, Any]],
        decisions: list[str],
    ) -> list[dict[str, str]]:
        # Passages of each source that did not fit are left out: the prompt says
        # so, per source, instead of claiming nothing matched.
        kept_reference = sum(1 for h in hits if h.get("source") == reference.SOURCE)
        return prompt.build_messages(
            persona,
            hist,
            hits,
            user_message,
            omitted=vault_found - (len(hits) - kept_reference),
            reference_omitted=reference_found - kept_reference,
            point_to=point_to,
            recaps=recaps,
            recaps_omitted=len(recaps_found) - len(recaps),
            withheld=withheld,
            vault_map=map_text if map_allowed else None,
            vault_map_withheld=bool(map_text) and not map_allowed,
            lookup=ask,
            memory_profile=mem.profile,
            memory_context=mem.context,
            memory_decisions=decisions,
            remember=remember,
        )

    prompt_tokens = 0
    recaps_sent = recaps_found
    decisions_sent = mem.decisions
    if limits is None:
        messages, dropped = build(history, grounding_results, recaps_found, mem.decisions), 0
    else:
        fitted = budget.fit(
            build, history, grounding_results, target_model, limits.prompt_tokens, recaps_found, mem.decisions,
        )
        messages, grounding_results, dropped = fitted.messages, fitted.grounding, fitted.history_dropped
        recaps_sent, prompt_tokens = fitted.recaps, fitted.tokens
        decisions_sent = fitted.decisions
    lookups: list[dict[str, Any]] = []
    tools = persona_tools.for_turn(ask, remember == memory.TOOL)
    if tools:
        tool_list, run_tool = tools
        done = lookup.converse(
            persona, messages, target_model, limits, used_tokens=prompt_tokens, tools=tool_list, run_tool=run_tool,
        )
        reply, reply_ttft, lookups = done.reply, done.ttft_ms, done.lookups
        grounding_results = grounding_results + done.hits
        for category, count in done.withheld.items():
            withheld[category] = withheld.get(category, 0) + count
        prompt_tokens += done.tokens_added
    else:
        reply = model_mod.call_model(
            messages,
            model=target_model,
            num_ctx=limits.num_ctx if limits else None,
            max_tokens=limits.reply_cap if limits else None,
        )
        reply_ttft = reply.ttft_ms

    # A model that can't call tools gets `remember` through a marker instead (docs/decisions/041),
    # stripped before the reply is shown; each one found is recorded like a tool call above.
    reply_text = reply.text
    if remember == memory.MARKER:
        reply_text, marker_lookups = memory_tools.apply_marker(handle, reply_text)
        lookups += marker_lookups

    searched_used = searched if any(h.get("source") != reference.SOURCE for h in grounding_results) else None
    memory_sent = memory.sent_names(mem.profile, mem.context, decisions_sent)
    cloud = None if sharing.is_local(target_model) else (
        sharing.categories_of(
            grounding_results, recaps_sent, vault_map=map_allowed and bool(map_text), memory=bool(memory_sent),
        ),
        [name for name in sharing.CATEGORIES if name in withheld],
    )
    sent = sent_record(
        grounding_results, recaps_sent, searched_used, dropped, rewrite, cloud,
        (lookup.ASK if ask else lookup.AUTO) if chose_ask else None, lookups, memory_sent,
    )
    saved = session.append_turn(
        handle,
        sid,
        user_message,
        reply_text,
        existing=existing,
        ttft_ms=reply_ttft,
        model=target_model,
        sent=sent,
        truncated=reply.truncated,
    )
    return TurnResult(
        reply=reply_text,
        session_id=sid,
        grounding=grounding_results,
        ttft_ms=reply_ttft,
        model=target_model,
        history_dropped=dropped,
        searched=searched_used,
        context_used=prompt_tokens + _reply_tokens(reply_text, target_model) if limits else None,
        context_limit=limits.prompt_tokens if limits else None,
        truncated=reply.truncated,
        saved=saved,
        cloud=cloud[0] if cloud else [],
        withheld=cloud[1] if cloud else [],
        sent=sent,
        lookups=lookups,
    )
