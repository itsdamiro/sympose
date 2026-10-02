"""What tools a turn gives the persona to call, and which of its two independent settings
apply this turn. `vault_lookup`'s `ask` mode (ADR 040) and `memory`'s `remember` (ADR 041)
can each be on or off regardless of the other -- `resolve` reads both against what the target
model can actually do, and `for_turn` composes whichever apply into one tool list and one
dispatcher, so `lookup.converse`'s loop does not need to know which capability a given tool
call belongs to."""

from dataclasses import dataclass
from typing import Any, Callable

from sympose import vault_paths
from sympose.engine import chat_tools, lookup, lookup_tools, memory, memory_tools, past_chats, tool_support


@dataclass(frozen=True)
class Modes:
    ask: bool
    chose_ask: bool  # `vault_lookup=ask` was chosen, even if this model can't act on it (ADR 040)
    remember: str | None  # `memory.TOOL`, `memory.MARKER`, or `None` (ADR 041)
    chats: bool = False  # `past_chats=ask` and the model can call tools: she searches earlier conversations (ADR 056)
    chose_chats: bool = False  # `past_chats=ask` was chosen, even if this model can't act on it


def resolve(persona: dict[str, Any], target_model: str) -> Modes:
    """What this turn's `ask`/`remember` actually are, given `target_model`'s own tool-calling
    capability and a persona with or without a vault -- the one place `run_turn` needs to check
    both settings against the model before deciding whether to run the tool-calling loop at all."""
    has_vault = vault_paths.resolve_sandbox(persona) is not None
    chose_ask = lookup.chooses_ask(target_model) and has_vault
    # Asking whether the model can call tools may cost a network probe, so only when a tool could be used.
    chose_chats = past_chats.chooses_ask()
    can_call_tools = (chose_ask or chose_chats or memory.remember_enabled()) and tool_support.can_call_tools(target_model)
    return Modes(
        ask=chose_ask and can_call_tools,
        chose_ask=chose_ask,
        remember=memory.remember_mode(can_call_tools),
        chats=chose_chats and can_call_tools,
        chose_chats=chose_chats,
    )


_UNKNOWN_TOOL = "There is no tool called {name}."


def for_turn(
    ask: bool, remember: bool, chats: bool = False, session_id: str | None = None,
) -> tuple[list[dict[str, Any]], Callable[..., Any]] | None:
    """`(tools, run)` for a turn that gets `ask`'s vault tools, `remember`'s memory tool, `chats`' tools for
    earlier conversations (`session_id` is the one in progress, never searched), or any mix; `None` when none applies, so the caller knows the tool-calling loop does not need
    to run at all this turn. `run` only ever reaches `lookup_tools` when `ask` is true: a vault
    tool must never run just because a model calls it by name -- a persona given only `remember`
    (`ask` off) must not be able to search or open notes by guessing `search_notes`/`open_note`."""
    if not ask and not remember and not chats:
        return None
    tools = [
        *(lookup_tools.TOOLS if ask else []), *(memory_tools.TOOLS if remember else []),
        *(chat_tools.TOOLS if chats else []),
    ]

    def run(persona: dict[str, Any], model: str, name: str, raw_arguments: Any) -> Any:
        if remember:
            result = memory_tools.run(persona["handle"], name, raw_arguments)
            if result is not None:
                return result
        if chats and name in (chat_tools.SEARCH, chat_tools.OPEN):
            return chat_tools.run(persona["handle"], session_id, model, name, raw_arguments)
        if ask:
            return lookup_tools.run(persona, model, name, raw_arguments)
        return lookup_tools.Result(_UNKNOWN_TOOL.format(name=name), lookup={"tool": name, "found": 0})

    return tools, run
