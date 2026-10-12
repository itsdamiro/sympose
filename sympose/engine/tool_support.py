"""Which models can call tools (docs/decisions/040). For a local model the question is put to the running
Ollama, which lists a model's capabilities (`/api/show`): that is current for the user's own pulls and for
models litellm's table does not know yet. For any other model, or when Ollama cannot say, it is litellm's
table (`litellm.supports_function_calling`), which can lag: so a model that fails when it is given tools
is remembered, after two turns in a row where it failed with tools and worked without, as unable until the
process restarts (one failure can be the network, a rate limit or a busy server, and must not take the
option away).

A timeout from a running Ollama is not "cannot say": a busy one (a model loading, another run in flight) answers
late, and litellm's table, which does not know a newly pulled model, would then run a tool model as a
marker-writing one for the turn without a word (ADR 083). So a timeout is asked once more with a longer limit,
and when that is also late the model is given tools: a wrong yes is corrected by the refusal path below, a wrong
no is silent."""

import json
import logging
import os
import threading
import time
from urllib.request import Request, urlopen

import litellm

from sympose.engine import budget

log = logging.getLogger(__name__)

STRIKES_TO_MARK = 2
_UNABLE: set[str] = set()
_STRIKES: dict[str, int] = {}
# Two personas can fail on the same model in the same instant; without this, one persona's
# `_STRIKES[model] = _STRIKES.get(model, 0) + 1` (read-modify-write, not one atomic step) can be
# overwritten by the other's, losing a strike (delays, never skips, when a model is marked unable).
_STRIKES_LOCK = threading.Lock()
# What the running Ollama said, per model: an answer is kept for the process, and a failure to get one for
# a minute, so a remote or slow Ollama is not put a two-second question on every turn.
_OLLAMA_TOOLS: dict[str, bool] = {}
_OLLAMA_SILENT_UNTIL: dict[str, float] = {}
_OLLAMA_DEFAULT_BASE = "http://localhost:11434"
_OLLAMA_TIMEOUT_SECONDS = 2
_OLLAMA_SLOW_TIMEOUT_SECONDS = 10
_OLLAMA_RETRY_SECONDS = 60
# Models whose last question timed out twice: while the minute of silence lasts they are taken to have tools.
_OLLAMA_SLOW: set[str] = set()


def _timed_out(error: Exception) -> bool:
    return isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError)


def _ask_ollama(model: str, timeout: float) -> list | None:
    """The capability list Ollama gives for `model`; `None` when it gave none. Raises on a failure to ask."""
    base = (os.environ.get("OLLAMA_API_BASE") or _OLLAMA_DEFAULT_BASE).rstrip("/")
    request = Request(
        f"{base}/api/show",
        data=json.dumps({"model": model.split("/", 1)[1]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 (the user's own Ollama)
        capabilities = json.load(response).get("capabilities")
    return capabilities if isinstance(capabilities, list) else None


def _ollama_says_tools(model: str) -> bool | None:
    """Whether the running Ollama lists `tools` among `model`'s capabilities; `None` when it cannot say
    (not running, an older Ollama with no capability list, an unexpected answer). An Ollama that is running
    but too slow to answer, twice, is taken to say yes (see the module's note)."""
    if model in _OLLAMA_TOOLS:
        return _OLLAMA_TOOLS[model]
    if _OLLAMA_SILENT_UNTIL.get(model, 0.0) > time.monotonic():
        return True if model in _OLLAMA_SLOW else None
    capabilities = None
    slow = False
    for timeout in (_OLLAMA_TIMEOUT_SECONDS, _OLLAMA_SLOW_TIMEOUT_SECONDS):
        try:
            capabilities = _ask_ollama(model, timeout)
            slow = False
            break
        except Exception as e:  # not running, refused, not JSON: the caller falls back to litellm's table
            slow = _timed_out(e)
            log.debug("Ollama could not say whether %s takes tools: %s", model, e)
            if not slow:
                break
    if capabilities is None:
        _OLLAMA_SILENT_UNTIL[model] = time.monotonic() + _OLLAMA_RETRY_SECONDS
        _OLLAMA_SLOW.discard(model)
        if slow:
            _OLLAMA_SLOW.add(model)
            return True
        return None
    _OLLAMA_TOOLS[model] = "tools" in capabilities
    return _OLLAMA_TOOLS[model]


def can_call_tools(model: str) -> bool:
    if model in _UNABLE:
        return False
    if budget.is_ollama(model) and (says := _ollama_says_tools(model)) is not None:
        return says
    try:
        return bool(litellm.supports_function_calling(model=model))
    except Exception as e:
        log.debug("Tool support of %s is unknown (%s); treating it as none", model, e)
        return False


def note_refusal(model: str) -> None:
    """`model` failed with tools and the same turn worked without them: a strike, and at
    `STRIKES_TO_MARK` in a row it is not given tools again until the process restarts."""
    with _STRIKES_LOCK:
        _STRIKES[model] = _STRIKES.get(model, 0) + 1
        unable = _STRIKES[model] >= STRIKES_TO_MARK
    if unable:
        mark_unable(model)


def note_success(model: str) -> None:
    """A turn with tools worked: the strikes against `model` are gone."""
    with _STRIKES_LOCK:
        _STRIKES.pop(model, None)


def mark_unable(model: str) -> None:
    with _STRIKES_LOCK:
        _UNABLE.add(model)
