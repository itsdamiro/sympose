"""Which models can call tools (docs/decisions/040). For a local model the question is put to the running
Ollama, which lists a model's capabilities (`/api/show`): that is current for the user's own pulls and for
models litellm's table does not know yet. For any other model, or when Ollama cannot say, it is litellm's
table (`litellm.supports_function_calling`), which can lag: so a model that fails when it is given tools
is remembered, after two turns in a row where it failed with tools and worked without, as unable until the
process restarts (one failure can be the network, a rate limit or a busy server, and must not take the
option away)."""

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
_OLLAMA_RETRY_SECONDS = 60


def _ollama_says_tools(model: str) -> bool | None:
    """Whether the running Ollama lists `tools` among `model`'s capabilities; `None` when it cannot say
    (not running, an older Ollama with no capability list, an unexpected answer)."""
    if model in _OLLAMA_TOOLS:
        return _OLLAMA_TOOLS[model]
    if _OLLAMA_SILENT_UNTIL.get(model, 0.0) > time.monotonic():
        return None
    base = (os.environ.get("OLLAMA_API_BASE") or _OLLAMA_DEFAULT_BASE).rstrip("/")
    request = Request(
        f"{base}/api/show",
        data=json.dumps({"model": model.split("/", 1)[1]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=_OLLAMA_TIMEOUT_SECONDS) as response:  # noqa: S310 (the user's own Ollama)
            capabilities = json.load(response).get("capabilities")
    except Exception as e:  # not running, refused, not JSON: the caller falls back to litellm's table
        log.debug("Ollama could not say whether %s takes tools: %s", model, e)
        capabilities = None
    if not isinstance(capabilities, list):
        _OLLAMA_SILENT_UNTIL[model] = time.monotonic() + _OLLAMA_RETRY_SECONDS
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
