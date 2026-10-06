"""How long a model call may wait (docs/decisions/059): 120 s, and 1 s more for every 40 tokens of the prompt, so a
long cold prompt on a slow machine is slow and not a failure; or what the user chose with `model_timeout`."""

import httpx
import litellm

from sympose import settings_store

SETTING = "model_timeout"
MIN_SECONDS, MAX_SECONDS = 30, 3600
BASE_SECONDS = 120
TOKENS_PER_SECOND = 40
_CHARS_PER_TOKEN = 4


def chosen() -> int | None:
    """The wait the user set, or `None` (automatic) when it is missing or not a whole number of seconds in range."""
    value = settings_store.get(SETTING)
    ok = isinstance(value, int) and not isinstance(value, bool) and MIN_SECONDS <= value <= MAX_SECONDS
    return value if ok else None


def seconds(messages: list[dict]) -> int:
    """The wait for a call carrying `messages`."""
    picked = chosen()
    if picked is not None:
        return picked
    characters = sum(len(str(m.get("content") or "")) for m in messages)
    return BASE_SECONDS + characters // _CHARS_PER_TOKEN // TOKENS_PER_SECOND


def is_timeout(error: BaseException) -> bool:
    """Whether `error`, or what caused it, is a call that ran out of time."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, (httpx.TimeoutException, litellm.Timeout)):
            return True
        error = error.__cause__ or error.__context__
    return False


def message(model: str, waited: int) -> str:
    return (
        f"No answer from '{model}' in {waited} seconds. A long conversation on a slow computer can need longer. "
        f"Raise 'how long a model may take to answer' in Settings ({SETTING})."
    )
