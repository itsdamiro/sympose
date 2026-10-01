"""The persona looks up notes itself (docs/decisions/040). `vault_lookup` decides who searches the
user's vault for a message: `auto` (the default) is Sympose, before the reply is written, exactly as it has
always been; `ask` gives the persona three tools, `search_notes`, `open_note` and `list_notes` (`lookup_tools`, `lookup_list`), and it decides.

`converse` is the loop of a tool-calling turn: the model is called with the tools; when it asks for one, the
tool is run and the model is called again with its result, until it writes a reply or has used its
rounds. It defaults to `ask`'s own vault tools, but takes any `tools`/`run_tool` pair (`persona_tools`,
docs/decisions/041), since a turn can also give the persona `remember` independent of `ask`. Nothing here
changes what the persona may be sent: every vault result still passes `sharing.gate` inside `lookup_tools`,
before it is put in front of a model."""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from sympose import settings_store
from sympose.engine import budget, lookup_list, lookup_tools, model as model_mod, model_tools, turn_cancel, turn_status

log = logging.getLogger(__name__)

SETTING = "vault_lookup"
AUTO, ASK = "auto", "ask"
ROUNDS_SETTING = "vault_lookup_rounds"
DEFAULT_ROUNDS = 3
MAX_ROUNDS = 8
# What the busy indicator (docs/decisions/043) shows while a tool call the model asked for is
# actually running -- only the two vault ones get their own real phase; anything else this loop
# is ever handed (e.g. `remember`, docs/decisions/041) stays the generic "asking" default, which
# is accurate enough for a tool that's neither searching nor reading a note.
_TOOL_PHASE = {
    lookup_tools.SEARCH: turn_status.SEARCHING, lookup_tools.OPEN: turn_status.READING,
    lookup_list.LIST: turn_status.SEARCHING,
}
_NO_ROOM = "There was no room left in the context window for this result."
# Added, for the last call only and never saved, once the lookups are used up: a model was seen to answer
# with another tool call and no text even with `tool_choice: none`, which ended the turn in an error.
_ANSWER_NOW = (
    "[Sympose: your lookups for this message are used up. Answer the user now, from what you found. If it "
    "does not answer the question, say you couldn't find it in the vault. Do not ask for anything more.]"
)
_MIN_ROOM_TOKENS = 100
# A model whose window is not known is given no more than this of tool results in one turn, so the
# request cannot grow until the provider refuses it.
_UNKNOWN_WINDOW_TOKENS = 12000
_CUT = "\n[Cut: the rest did not fit the context window.]"


class ToolsRefused(model_mod.EngineModelError):
    """The very first call of an `ask` turn failed: most likely the model does not take tools although
    litellm's table says it does, and the turn is run again as `auto` (docs/decisions/040)."""


@dataclass(frozen=True)
class Conversed:
    """What an `ask` turn did: the final reply, the time to its first text from the start of the turn's
    first call (the user waited through every round), the passages the lookups sent and what was held
    back from a cloud model, and one entry per tool call for the turn record."""

    reply: model_mod.ModelReply
    ttft_ms: int | None
    hits: list[dict[str, Any]] = field(default_factory=list)
    withheld: dict[str, int] = field(default_factory=dict)
    lookups: list[dict[str, Any]] = field(default_factory=list)
    tokens_added: int = 0


def mode() -> str:
    """The setting as the user chose it: only an explicit `ask` asks; anything else, malformed values
    included, is `auto`."""
    return ASK if settings_store.get(SETTING) == ASK else AUTO


def rounds() -> int:
    value = settings_store.get(ROUNDS_SETTING)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return min(value, MAX_ROUNDS)
    return DEFAULT_ROUNDS


def _tokens(text: str, model: str) -> int:
    return budget.count_tokens([{"role": "user", "content": text}], model)


def _fit(text: str, model: str, room: int) -> str:
    """`text` cut at its end until it fits `room` tokens, counted with the model's own counter (so a note
    in a script that takes many tokens a character is cut shorter, not just by a fixed ratio)."""
    size = _tokens(text, model)
    if size <= room:
        return text
    if room < _MIN_ROOM_TOKENS:
        return _NO_ROOM
    for _ in range(8):
        text = text[: max(1, int(len(text) * room / size * 0.9))].rstrip()
        size = _tokens(text + _CUT, model)
        if size <= room:
            break
    return text + _CUT


def _merge(into: list[dict[str, Any]], hits: list[dict[str, Any]]) -> None:
    seen = {(hit["rel_path"], hit.get("heading"), hit.get("kind")) for hit in into}
    for hit in hits:
        key = (hit["rel_path"], hit.get("heading"), hit.get("kind"))
        if key not in seen:
            seen.add(key)
            into.append(hit)


def converse(
    persona: dict[str, Any],
    messages: list[dict[str, Any]],
    model: str,
    limits: budget.Budget | None,
    used_tokens: int = 0,
    call: Callable[..., model_mod.ModelReply] | None = None,
    tools: list[dict[str, Any]] | None = None,
    run_tool: Callable[..., Any] | None = None,
) -> Conversed:
    """Run a tool-calling turn on `messages` (the fitted prompt, `used_tokens` of the window).
    `tools`/`run_tool` default to ADR 040's vault-only pair, but a caller composing more than one
    capability into one turn (`persona_tools.for_turn`, ADR 041) passes its own combined list and
    dispatcher -- this loop does not care which capability a tool call belongs to. Raises what
    `call_model` raises, except that a failure of the very first call is `ToolsRefused`. When the rounds are
    used up the model is called once more with `tool_choice: none` and a line telling it to answer now."""
    call = call or model_mod.call_model  # looked up now, so a test can stand in for the model
    tools = tools if tools is not None else lookup_tools.TOOLS
    run_tool = run_tool or lookup_tools.run
    handle = persona.get("handle")  # `None` in a unit test's bare persona dict -- `turn_status` no-ops on that
    started = time.perf_counter()
    work: list[dict[str, Any]] = list(messages)
    hits: list[dict[str, Any]] = []
    withheld: dict[str, int] = {}
    lookups: list[dict[str, Any]] = []
    added = 0
    limit = rounds()
    for round_number in range(limit + 1):
        last = round_number == limit
        turn_status.set_phase(handle, turn_status.ASKING)
        before = time.perf_counter()
        try:
            reply = call(
                [*work, {"role": "user", "content": _ANSWER_NOW}] if last else work,
                model=model,
                num_ctx=limits.num_ctx if limits else None,
                max_tokens=limits.reply_cap if limits else None,
                tools=tools,
                tool_choice="none" if last else None,
            )
        except model_mod.EngineModelError as e:
            if round_number == 0 and not isinstance(e, model_mod.ReplyLimitError):
                raise ToolsRefused(str(e)) from e
            raise
        if not reply.tool_calls or last:
            if not reply.text:
                raise model_mod.EngineModelError(
                    f"Model '{model}' used its {limit} lookups without writing an answer."
                )
            ttft = None if reply.ttft_ms is None else round((before - started) * 1000) + reply.ttft_ms
            return Conversed(reply, ttft, hits, withheld, lookups, added)
        asked = model_tools.assistant_message(reply.text, reply.tool_calls)
        work.append(asked)
        added += _tokens(json.dumps(asked["tool_calls"]) + (reply.text or ""), model)  # replayed with every later call
        for tool_call in reply.tool_calls:
            turn_cancel.check()  # a stop (docs/decisions/054) lands between tool calls too
            turn_status.set_phase(handle, _TOOL_PHASE.get(tool_call.name, turn_status.ASKING))
            result = run_tool(persona, model, tool_call.name, tool_call.arguments)
            room = (_UNKNOWN_WINDOW_TOKENS if limits is None else limits.prompt_tokens - used_tokens) - added
            text = _fit(result.text, model, room)
            work.append(model_tools.result_message(tool_call, text))
            added += _tokens(text, model)
            if text == _NO_ROOM:  # the model never saw these notes: they did not ground the reply and were not sent
                lookups.append({**result.lookup, "found": 0, "no_room": True})
                continue
            _merge(hits, result.hits)
            for category, count in result.withheld.items():
                withheld[category] = withheld.get(category, 0) + count
            lookups.append(result.lookup)
    raise AssertionError("unreachable: the last round returns")  # pragma: no cover
