"""The context meter's figure for a conversation before the next message is sent (docs/decisions/018,
"Update"): right after a model switch the meter shows this instead of going blank. The persona's
system prompt plus the conversation's kept history, counted with the given model's tokenizer against
that model's prompt budget, with the oldest turns left out when they do not fit, as a real turn would
(`budget.fit`), so it never reads above the budget. It leaves out the next message's grounding and any
recaps, which a real turn includes, so it leans low where the real figure leans high. Nothing here calls
a model."""

from sympose import profile as profile_mod, vault_map as vault_map_mod
from sympose.engine import budget, prompt, session, sharing


def estimate(handle: str, session_id: str | None, model: str) -> tuple[int, int] | None:
    """`(tokens in use, prompt budget)`, or `None` when there is nothing to count: no session yet or
    no reply in it, an unknown persona, or a model whose window is unknown."""
    if session_id is None:
        return None
    persona = profile_mod.resolve_profile(handle)
    limits = budget.budget_for(model)
    if persona is None or limits is None:
        return None
    history = session.history_as_messages(session.load_session(handle, session_id))
    if not history:
        return None
    map_text = vault_map_mod.build(persona)
    map_allowed = sharing.VAULT_MAP in sharing.allowed(model)
    system = prompt.build_system_prompt(
        persona, vault_map=map_text if map_allowed else None, vault_map_withheld=bool(map_text) and not map_allowed
    )
    try:
        fitted = budget.fit(
            lambda kept, _notes, _recaps: [{"role": "system", "content": system}, *kept],
            history, [], model, limits.prompt_tokens,
        )
    except budget.ContextTooSmallError:  # the instructions alone do not fit: the next turn says so
        return None
    return fitted.tokens, limits.prompt_tokens
