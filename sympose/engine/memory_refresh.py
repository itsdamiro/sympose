"""Proposing an update to `context.md`/`profile.md` (docs/decisions/041's `memory_rewrite`) --
the one persona-memory write a weak model can lose or garble existing content on, not just add
to. Mirrors `recap_refresh`'s shape: run lazily on a background thread at the start of the next
session, fed the handle's recent recaps (already-compressed, not raw session transcripts -- the
same layering `recap_refresh.refresh` itself already uses over its own `_transcript`).

`profile.md` is meant to change rarely and deliberately, so a proposed change to it is always
staged for `/memory review`, regardless of the setting below. `context.md` is meant to change
more freely, so it follows `memory_rewrite`: `ask` (the default) stages it the same way, `auto`
writes it directly. Neither ever writes without `memory_write`'s own rolling `.bak`."""

import logging
import threading

from sympose import profile as profile_mod, settings_store
from sympose.engine import budget, helper_limit, memory, memory_write, prompt, recap, sharing
from sympose.engine import model as model_mod

log = logging.getLogger(__name__)

SETTING = "memory_rewrite"
AUTO, ASK = "auto", "ask"

# More of the arc than a turn's own prompt reads (`recap.READ_COUNT`, 2): a rewrite is meant to
# notice a pattern across sessions, not just carry the last one forward.
_READ_RECAPS = 6
_MAX_REPLY_TOKENS = 500
_NO_FILE = "NONE"  # what a missing profile.md/context.md reads as in the request -- distinct from
# `prompt.MEMORY_NO_CHANGE`, which is the model's own answer that nothing needs to change.

# A model that spent its whole small reply limit thinking cannot propose a rewrite (as with the
# recap and follow-up rewrite calls): not asked again until the process restarts.
_CANNOT_REWRITE: set[str] = set()


def mode() -> str:
    """The setting as the user chose it: only an explicit `auto` skips confirmation; anything
    else, malformed values included, is `ask` -- the safe, model-agnostic default this record
    treats as first-class, not a fallback for a weak model (docs/decisions/041)."""
    return AUTO if settings_store.get(SETTING) == AUTO else ASK


def _request(profile_text: str | None, context_text: str | None, recaps: list) -> list[dict[str, str]]:
    recap_lines = "\n".join(f"- {r['date']}: {r['text']}" for r in recaps)
    body = (
        f"profile.md:\n{profile_text or _NO_FILE}\n\n"
        f"context.md:\n{context_text or _NO_FILE}\n\n"
        f"Recent conversation recaps, oldest first:\n{recap_lines}"
    )
    return [{"role": "system", "content": prompt.MEMORY_REFRESH_INSTRUCTIONS}, {"role": "user", "content": body}]


def _section(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    if text.rstrip(".! ").upper() == prompt.MEMORY_NO_CHANGE:
        return None
    return text


def _parse(text: str) -> tuple[str | None, str | None]:
    """`(profile, context)`, each `None` when absent or the model judged no change needed.
    `(None, None)` also when the model did not use the two-section shape at all -- a malformed
    reply is treated the same as "nothing to propose", never guessed at. Finds each marker by
    position rather than assuming the instructed profile-then-context order, so a model that
    writes them the other way around still has both sections read, not one silently dropped."""
    profile_at = text.find(prompt.MEMORY_PROFILE_MARK)
    context_at = text.find(prompt.MEMORY_CONTEXT_MARK)
    if profile_at == -1 or context_at == -1:
        return None, None
    profile_start = profile_at + len(prompt.MEMORY_PROFILE_MARK)
    context_start = context_at + len(prompt.MEMORY_CONTEXT_MARK)
    if profile_at < context_at:
        profile_part, context_part = text[profile_start:context_at], text[context_start:]
    else:
        context_part, profile_part = text[context_start:profile_at], text[profile_start:]
    return _section(profile_part), _section(context_part)


def propose(handle: str, model: str | None = None) -> tuple[str | None, str | None]:
    """Ask `model` (else the persona's own) to propose an update to `context.md`/`profile.md`
    from their current content and `handle`'s recent recaps. `(profile_text, context_text)`,
    each `None` when the model judged no change needed; `(None, None)` also when nothing could
    be asked at all -- no persona, no recaps yet, cloud sharing not allowed for `memory` or (the
    recaps sent as input have their own category) `recaps`, or a model already known to fail this
    request -- the same "nothing happens, quietly" posture `recap_refresh.refresh` already has
    for its own missing/unusable cases."""
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        return None, None
    model = model or model_mod.resolve_model(persona.get("model"))
    if model in _CANNOT_REWRITE:
        return None, None
    if sharing.MEMORY not in sharing.allowed(model):
        return None, None  # the current files would go to a cloud model not approved for memory (ADR 031)
    if sharing.RECAPS not in sharing.allowed(model):
        return None, None  # the recaps that would be sent as input need their own approval too, same as a turn's own gate
    recaps = recap.latest(handle, count=_READ_RECAPS)
    if not recaps:
        return None, None  # nothing yet to synthesize a rewrite from
    limits = budget.budget_for(model)
    profile_now, context_now = memory.profile(handle), memory.context(handle)
    request = _request(profile_now, context_now, recaps)
    try:
        reply = model_mod.call_model(
            request, model=model, num_ctx=limits.num_ctx if limits else None,
            max_tokens=helper_limit.for_model(model, _MAX_REPLY_TOKENS),
        )
    except model_mod.ReplyLimitError as e:
        log.warning("'%s' cannot propose a memory rewrite in its reply limit; not asking again: %s", model, e)
        _CANNOT_REWRITE.add(model)
        return None, None
    except model_mod.EngineModelError as e:
        log.warning("Memory rewrite for %s failed: %s", handle, e)
        return None, None
    profile_text, context_text = _parse(reply.text)
    # A model observed (live, against gemma2:9b) to echo a file's content back verbatim instead
    # of using the NO_CHANGE sentinel, even when nothing about it actually changed: caught here,
    # structurally, rather than by asking the model to say NO_CHANGE more reliably, which would
    # be trying to perfect a fuzzy instruction instead of just checking the one thing that matters.
    if profile_text is not None and profile_text.strip() == (profile_now or "").strip():
        profile_text = None
    if context_text is not None and context_text.strip() == (context_now or "").strip():
        context_text = None
    return profile_text, context_text


def refresh(handle: str, model: str | None = None) -> bool:
    """Propose an update and, for whichever file it touched, either stage it for `/memory
    review` or (`context.md`, `memory_rewrite` `auto` only) write it directly. `False` when
    nothing was proposed, or a stage/write failed; never raises."""
    profile_text, context_text = propose(handle, model)
    if profile_text is None and context_text is None:
        return False
    ok = True
    if profile_text is not None:
        ok = memory_write.stage_profile(handle, profile_text) and ok
    if context_text is not None:
        writer = memory_write.apply_context if mode() == AUTO else memory_write.stage_context
        ok = writer(handle, context_text) and ok
    return ok


# One run per persona at a time; the event is set when it finishes -- the same shape
# `recap_refresh`'s own `_RUNNING` uses, so `/memory`'s manual "Refresh now" (`wait_for_refresh`
# below) joins an already-running background refresh instead of racing a second one against it.
_RUNNING: dict[str, threading.Event] = {}
_RUNNING_LOCK = threading.Lock()


def refresh_in_background(handle: str, model: str | None = None) -> bool:
    """Start `refresh` on a daemon thread and return at once, the same shape
    `recap_refresh.refresh_in_background` already uses. `False` when one is already running
    for `handle`."""
    with _RUNNING_LOCK:
        if handle in _RUNNING:
            return False
        done = _RUNNING[handle] = threading.Event()

    def work() -> None:
        try:
            refresh(handle, model)
        except Exception as e:  # a background thread must not print a traceback into the terminal
            log.warning("Memory rewrite for %s failed: %s", handle, e)
        finally:
            with _RUNNING_LOCK:
                del _RUNNING[handle]
            done.set()

    threading.Thread(target=work, name=f"memory-{handle}", daemon=True).start()
    return True


def wait_for_refresh(handle: str, timeout: float = 60.0) -> bool:
    """Give a refresh running for `handle` up to `timeout` seconds to finish. `True` when none is
    running or it finished, `False` when it is still going -- the same shape
    `recap_refresh.wait_for_refresh` already uses."""
    with _RUNNING_LOCK:
        done = _RUNNING.get(handle)
    return True if done is None else done.wait(timeout)
