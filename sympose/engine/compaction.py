"""Live compaction of a long conversation (docs/decisions/055): the oldest turns are stood for by short
notes, written by the model that runs the conversation from the user's own messages, so a long chat
keeps its gist in much less room. The session file keeps every turn (`session_compaction` holds the
record); only what is sent changes. Automatic (`auto_compact`, on unless an explicit `false`) after a
reply that left the prompt near the budget, in the background and in one larger step so the start of the
prompt stays the same for several turns; or on request (`compact_now`). A notes call that fails, or
that would not save room, writes nothing and the engine drops the oldest turns as it always did."""

import logging
from dataclasses import dataclass
from typing import Any

from sympose import settings_store
from sympose.engine import background_job, budget, helper_limit, session, session_compaction
from sympose.engine import model as model_mod
from sympose.engine.compaction_text import INSTRUCTIONS

log = logging.getLogger(__name__)

SETTING = "auto_compact"
DEFAULT_ON = True  # the shipped default; tests start with it off (`tests/conftest.py`) so no turn starts a background call
AT_SETTING, TO_SETTING = "compact_at", "compact_to"  # percent of the prompt budget: start at, land at
DEFAULT_AT, DEFAULT_TO = 80, 40
_MIN_PERCENT, _MAX_PERCENT = 10, 95
# The newest turns that always stay word for word, so what was said a moment ago is still in view.
KEEP_TURNS = 3
# What notes of up to 150 words count as when planning how much to fold, and the most they may write.
_NOTES_TOKENS = 250
_MAX_NOTES_TOKENS = 300
_MAX_USER_CHARS = 1000
# After an automatic attempt that wrote nothing, not again for this many more turns: a model that is down,
# or turns too short to be worth notes, must not cost a call (on a cloud model, a paid one) every turn.
_RETRY_AFTER_TURNS = 5

DONE, NOTHING, TOO_SMALL, FAILED, BUSY = "done", "nothing", "too_small", "failed", "busy"

_JOBS = background_job.Runner("sympose-compact", "Compaction")
_GAVE_UP: dict[str, int] = {}  # session key -> its turn count at the last automatic attempt that wrote nothing


@dataclass(frozen=True)
class Outcome:
    status: str
    covered: int = 0  # the turns the notes now stand for
    text: str = ""
    before: int = 0  # tokens the notes replaced (the old notes and the folded turns), as they were sent
    after: int = 0  # tokens of the new notes


def enabled() -> bool:
    """Only an explicit `false` turns the automatic kind off; `/compact` works either way."""
    return settings_store.flag(SETTING, DEFAULT_ON)


def _percent(key: str) -> int | None:
    value = settings_store.get(key)
    ok = isinstance(value, int) and not isinstance(value, bool) and _MIN_PERCENT <= value <= _MAX_PERCENT
    return value if ok else None


def at_percent() -> int:
    return _percent(AT_SETTING) or DEFAULT_AT


def to_percent() -> int:
    """Where an automatic compaction lands: always below where it starts, so a bad pair is not accepted."""
    chosen, at = _percent(TO_SETTING), at_percent()
    return chosen if chosen is not None and chosen < at else min(DEFAULT_TO, at // 2)


def _key(handle: str, session_id: str) -> str:
    return f"{handle}/{session_id}"


def _tokens(messages: list[dict[str, str]], model: str) -> int:
    return budget.count_tokens(messages, model)


def _turn_tokens(turn: dict[str, Any], model: str) -> int:
    return _tokens(
        [{"role": "user", "content": turn["user"]}, {"role": "assistant", "content": turn["assistant"]}], model
    )


def _request(notes: str | None, turns: list[dict[str, Any]]) -> list[dict[str, str]]:
    said = "\n".join(f"User: {turn['user'][:_MAX_USER_CHARS]}" for turn in turns)
    body = f"Notes so far:\n{notes or 'NONE'}\n\nNew messages from the user:\n{said}\n\nUpdated notes:"
    return [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": body}]


def _fit(notes: str | None, turns: list[dict[str, Any]], model: str, limits: budget.Budget | None) -> int:
    """How many of the oldest `turns` the request can take within the model's window; the rest wait for the next one."""
    if limits is None:
        return len(turns)
    taken = 0
    for count in range(1, len(turns) + 1):
        if _tokens(_request(notes, turns[:count]), model) > limits.prompt_tokens:
            break
        taken = count
    return taken


def _fold_count(tail: list[dict[str, Any]], used: int, limit: int, model: str) -> int:
    """How many of the oldest turns to fold into the notes so the conversation lands at the low mark:
    the fewest that do it, and at least those beyond the history cap, never the newest `KEEP_TURNS`."""
    room = len(tail) - KEEP_TURNS
    over_cap = len(tail) - session.HISTORY_TURNS
    target = to_percent() / 100 * limit - _NOTES_TOKENS
    saved = 0
    for count in range(1, room + 1):
        saved += _turn_tokens(tail[count - 1], model)
        if used - saved <= target:
            return min(max(count, over_cap), room)
    return max(room, 0)


def _clean(reply: model_mod.ModelReply) -> str:
    text = " ".join(reply.text.split())
    if reply.truncated and text:  # cut mid-sentence: stop at the last whole one
        cut = max(text.rfind(mark) for mark in ".!?")
        text = text[: cut + 1] if cut > 0 else ""
    return text


def _compact(handle: str, session_id: str, model: str, used: int | None, limit: int | None) -> Outcome:
    """`used` and `limit` (the prompt in use, and its budget) plan an automatic compaction down to the low
    mark; without them everything but the newest `KEEP_TURNS` turns is folded, as `/compact` asks."""
    saved = session.load_session(handle, session_id)
    if saved is None:
        return Outcome(NOTHING)
    done = session_compaction.covered(saved)
    tail = saved["turns"][done:]
    fold = len(tail) - KEEP_TURNS if used is None or limit is None else _fold_count(tail, used, limit, model)
    notes = session_compaction.notes(saved)
    limits = budget.budget_for(model)
    taken = _fit(notes, tail[: max(fold, 0)], model, limits) if fold > 0 else 0
    if taken == 0:
        return Outcome(NOTHING, done)
    folded = tail[:taken]
    try:
        reply = model_mod.call_model(
            _request(notes, folded),
            model=model,
            num_ctx=limits.num_ctx if limits else None,
            max_tokens=helper_limit.for_model(model, _MAX_NOTES_TOKENS),
        )
    except model_mod.EngineModelError as e:  # the model could not be reached, or its reply limit was too small
        log.warning("Compaction of session %s failed: %s", session_id, e)
        return Outcome(FAILED, done)
    text = _clean(reply)
    if not text:
        return Outcome(FAILED, done)
    before = sum(_turn_tokens(turn, model) for turn in folded) + (
        _tokens([{"role": "user", "content": notes}], model) if notes else 0
    )
    after = _tokens([{"role": "user", "content": text}], model)
    if after >= before:  # notes that are no shorter than what they replace would only add a model's errors
        return Outcome(TOO_SMALL, done)
    if not session_compaction.append(handle, session_id, done + taken, text, model):
        return Outcome(FAILED, done)
    return Outcome(DONE, done + taken, text, before, after)


def wanted(saved: dict[str, Any] | None, used: int | None, limit: int | None) -> bool:
    """Whether a reply that left the conversation at `used` of `limit` tokens should be followed by a
    compaction: the high mark is reached, or more turns than the history cap sends are waiting."""
    if saved is None or used is None or not limit:
        return False
    tail = len(saved["turns"]) - session_compaction.covered(saved)
    if tail <= KEEP_TURNS:
        return False
    return tail > session.HISTORY_TURNS or used >= at_percent() / 100 * limit


def start_if_wanted(
    handle: str, session_id: str, model: str, saved: dict[str, Any] | None, used: int | None, limit: int | None
) -> bool:
    """After a reply: start an automatic compaction in the background when one is wanted, and say so.
    Never waits and never raises (a failure is logged, and the next turns are sent as they would have been)."""
    if not enabled() or not wanted(saved, used, limit):
        return False
    key = _key(handle, session_id)
    if len(saved["turns"]) - _GAVE_UP.get(key, -_RETRY_AFTER_TURNS) < _RETRY_AFTER_TURNS:
        return False

    def work() -> None:
        outcome = _compact(handle, session_id, model, used, limit)
        if outcome.status in (DONE, NOTHING):
            _GAVE_UP.pop(key, None)
        else:
            _GAVE_UP[key] = len(saved["turns"])
        log.info("Compaction of session %s: %s", session_id, outcome.status)

    return _JOBS.start(key, work)


def compact_now(handle: str, session_id: str, model: str, wait: float = 300.0) -> Outcome:
    """`/compact`: fold everything but the newest turns now, and wait for it. `BUSY` when one is already
    running for this conversation (it is not run twice at once) or does not finish within `wait` seconds."""
    key, box = _key(handle, session_id), []
    if not _JOBS.start(key, lambda: box.append(_compact(handle, session_id, model, None, None))):
        return Outcome(BUSY)
    if not _JOBS.wait(key, wait):
        return Outcome(BUSY)
    return box[0] if box else Outcome(FAILED)
