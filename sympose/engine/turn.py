"""One turn, end to end (docs/decisions/006). `run_turn` stays a single
atomic unit (ground -> build -> call -> persist) — message queueing
(docs/decisions/008) is implemented at the CLI call site, sequencing and
attributing `run_turn` calls per persona, not inside this function.
`call_model` is a single blocking, non-cancelable call (ADR 007); there is
no in-progress generation to check for new input against, so the seam this
docstring used to point at (between the model call returning and the turn
persisting) was never exercised — see ADR 008."""

import contextlib
from dataclasses import replace
from typing import Any

from sympose import note_changes
from sympose import profile as profile_mod
from sympose.engine import (
    budget, compaction, confirmations, edit_tools, edit_turn, history_cap, lookup, memory, memory_tools, past_chats, persona_tools, reference, session, session_compaction, sharing, tool_support, turn_cancel, turn_evidence, turn_status,
)
from sympose.engine import model as model_mod
from sympose.engine.model import EngineModelError
from sympose.engine.turn_cancel import TurnCancelled
from sympose.engine.turn_record import sent_record
from sympose.engine.turn_result import TurnResult

__all__ = ["TurnResult", "run_turn", "EngineModelError", "PersonaNotFoundError", "TurnCancelled"]


class PersonaNotFoundError(Exception):
    """`resolve_profile(handle)` returned `None` — defensive-only today
    (the CLI's persona picker only ever offers real roster handles), but
    must degrade to a legible error instead of crashing a few lines
    further into `run_turn` on a bare `None`."""


def _reply_tokens(text: str, model: str) -> int:
    return budget.count_tokens([{"role": "assistant", "content": text}], model)


def run_turn(
    handle: str,
    user_message: str,
    session_id: str | None = None,
    model: str | None = None,
    open_note: edit_turn.OpenNote | None = None,
    edits: bool = False,
    attached: list[edit_turn.Attached] | None = None,
) -> TurnResult:
    """`open_note` is the note open in the editor, and `edits` says the caller can show a proposal at all (the web
    app); the terminal passes neither, so a persona there is never given the edit tool (docs/decisions/072).
    `attached` are the passages of the open note the user pointed at (docs/decisions/076)."""
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        raise PersonaNotFoundError(f"No persona named '{handle}' was found.")
    handle = persona["handle"]  # the canonical, lower-cased key `lookup.converse` and the CLI also use
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
    history, capped = history_cap.apply(history, target_model)  # the user's own limit on earlier turns (docs/decisions/055)
    # `ask` (docs/decisions/040) and `remember` (docs/decisions/041) are independent settings, each
    # checked against what this model can actually do and, for `ask`, whether the persona has a
    # vault to look up at all -- see `persona_tools.resolve`.
    since = existing["turns"][-1].get("timestamp") if existing and existing.get("turns") else None  # when the previous turn was recorded
    modes = persona_tools.resolve(persona, target_model, open_note, edits, since, attached)
    # Cleared in `finally`, not just on the normal path: an exception from `_run` (a raised
    # `EngineModelError`, or anything else) must not leave the busy indicator (docs/decisions/043)
    # showing a phase forever for a turn that's already over. `_run` narrows this further (searching,
    # reading) around its own steps; this is just the default for everything else in between.
    turn_status.bind(handle, sid)  # this turn's phase and stop are its conversation's own (docs/decisions/057)
    turn_status.set_phase(handle, turn_status.ASKING)
    turn_cancel.begin(handle, sid, named=session_id is not None)  # from here a stop request is heard (docs/decisions/054); cleared in `finally`
    try:
        try:
            result = _run(persona, handle, user_message, sid, existing, history, target_model, modes, capped)
        except lookup.ToolsRefused:
            # The model failed with the tools: the turn is run with none, and a model that does that twice in a
            # row while working without them is not given tools again (docs/decisions/040). `remember` falls
            # back to its marker mechanism for this same retry, since that needs no tool-calling at all -- the
            # user's "remember this" is not lost just because the tool attempt was.
            retry_remember = memory.MARKER if memory.remember_enabled() else None
            result = _run(
                persona, handle, user_message, sid, existing, history, target_model,
                persona_tools.Modes(
                    False, modes.chose_ask, retry_remember, False, modes.chose_chats,
                    replace(modes.edit, tool=False) if modes.edit else None,
                ),
                capped,
            )
            tool_support.note_refusal(target_model)
            return result
        if modes.ask or modes.chats or modes.remember == memory.TOOL or (modes.edit and modes.edit.tool):
            tool_support.note_success(target_model)
        return result
    finally:
        turn_status.set_phase(handle, None)
        turn_status.unbind()
        turn_cancel.finish(handle, sid)


def _run(
    persona: dict[str, Any],
    handle: str,
    user_message: str,
    sid: str,
    existing: Any,
    history: list[dict[str, str]],
    target_model: str,
    modes: "persona_tools.Modes",
    capped: int = 0,
) -> TurnResult:
    ask, chose_ask, remember = modes.ask, modes.chose_ask, modes.remember
    # The prompt is sized to this model's window, not left to the runtime's
    # silent cut (docs/decisions/015); the follow-up rewrite shares that window.
    limits = budget.budget_for(target_model)
    found = turn_evidence.gather(persona, handle, sid, user_message, history, target_model, limits, modes, existing)
    grounding_results, recaps_found, chats_found, withheld = found.grounding, found.recaps, found.chats, found.withheld
    mem, notes = found.mem, found.notes
    # The note and the rules go with the message to the model; the conversation keeps only what the user said.
    asked = edit_turn.message(modes.edit, user_message) if modes.edit else user_message
    told = confirmations.outcomes(handle, sid) if modes.edit and modes.edit.proposes else []
    if told:
        asked = "\n".join(confirmations.lines(told)) + "\n\n" + asked
    build = turn_evidence.prompt_builder(persona, asked, found, modes)

    prompt_tokens = 0
    recaps_sent, chats_sent = recaps_found, chats_found
    decisions_sent = mem.decisions
    # The exchanges ride at the end of the recaps' list through the fitting, so they are the first of the
    # two to be left out when the prompt does not fit: they cost the most and answer the fewest questions.
    if limits is None:
        messages, dropped = build(history, grounding_results, recaps_found + chats_found, mem.decisions), 0
    else:
        fitted = budget.fit(
            build, history, grounding_results, target_model, limits.prompt_tokens,
            recaps_found + chats_found, mem.decisions,
        )
        messages, grounding_results, dropped = fitted.messages, fitted.grounding, fitted.history_dropped
        recaps_sent, chats_sent = turn_evidence.split_chats(fitted.recaps)
        prompt_tokens = fitted.tokens
        decisions_sent = fitted.decisions
    dropped += capped  # the turns `history_tokens` left out count with the ones the window's own fitting dropped
    lookups: list[dict[str, Any]] = []
    tools = persona_tools.for_turn(ask, remember == memory.TOOL, modes.chats, sid, modes.edit, persona, found.map_allowed)
    if tools:
        tool_list, run_tool = tools
        done = lookup.converse(
            persona, messages, target_model, limits, used_tokens=prompt_tokens, tools=tool_list, run_tool=run_tool,
        )
        reply, reply_ttft, lookups = done.reply, done.ttft_ms, done.lookups
        grounding_results = grounding_results + done.hits
        chats_sent = chats_sent + done.chats
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

    turn_cancel.commit()  # a stop after this is refused; before it, nothing below (marker, record, session) happens

    # What the user decided on her comments was told to her in this prompt, so those comments are not kept (docs/decisions/069).
    if modes.edit and modes.edit.settle and modes.edit.source:
        for annotation_id in modes.edit.settle:
            with contextlib.suppress(KeyError):
                note_changes.delete_annotation(handle, modes.edit.source.path, annotation_id)

    # A model that can't call tools gets `remember` through a marker instead (docs/decisions/041),
    # stripped before the reply is shown; each one found is recorded like a tool call above.
    reply_text = reply.text
    if remember == memory.MARKER:
        reply_text, marker_lookups = memory_tools.apply_marker(handle, reply_text)
        lookups += marker_lookups
    if modes.edit and modes.edit.active and not modes.edit.tool:  # the same for a proposal (docs/decisions/072)
        opened = modes.edit.source
        reply_text, edit_lookups = edit_tools.apply_marker(
            handle, opened.path if opened else None, opened.text if opened else None, reply_text, persona,
        )
        lookups += edit_lookups
    if told:
        confirmations.mark_told(handle, told)  # she has now been told what the user decided (docs/decisions/078)

    if modes.edit and modes.edit.withheld:
        withheld[sharing.OPEN_NOTE] = 1
    if modes.edit and modes.edit.comments_withheld:
        withheld[sharing.ANNOTATIONS] = modes.edit.comments_withheld
    searched_used = found.searched if any(h.get("source") != reference.SOURCE for h in grounding_results) else None
    memory_sent = memory.sent_names(mem.profile, mem.context, decisions_sent)
    cloud = None if sharing.is_local(target_model) else (
        sharing.categories_of(
            grounding_results, recaps_sent, vault_map=found.map_allowed and bool(found.map_text), memory=bool(memory_sent),
            chats=bool(chats_sent), open_note=bool(modes.edit and modes.edit.note), annotations=bool(modes.edit and modes.edit.comments),
        ),
        [name for name in sharing.CATEGORIES if name in withheld],
    )
    sent = sent_record(
        grounding_results, recaps_sent, searched_used, dropped, found.rewrite, cloud,
        (lookup.ASK if ask else lookup.AUTO) if chose_ask else None, lookups, memory_sent, chats_sent,
        (past_chats.ASK if modes.chats else past_chats.AUTO) if modes.chose_chats else None,
        modes.edit.attached if modes.edit else 0,
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
    context_used = prompt_tokens + _reply_tokens(reply_text, target_model) if limits else None
    if saved:  # a long conversation is condensed in the background, for the turns after this one (docs/decisions/055)
        compaction.start_if_wanted(handle, sid, target_model, existing, context_used, limits.prompt_tokens if limits else None)
    return TurnResult(
        reply=reply_text,
        session_id=sid,
        grounding=grounding_results,
        ttft_ms=reply_ttft,
        model=target_model,
        history_dropped=dropped,
        searched=searched_used,
        context_used=context_used,
        context_limit=limits.prompt_tokens if limits else None,
        truncated=reply.truncated,
        saved=saved,
        cloud=cloud[0] if cloud else [],
        withheld=cloud[1] if cloud else [],
        sent=sent,
        lookups=lookups,
        condensed=session_compaction.covered(existing) if notes else 0,
    )
