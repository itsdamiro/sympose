"""A persona's own short, witty status-line phrases, shown in the CLI (`background_status.py`)
while something runs in the background -- so a quiet wait reads as the persona being busy, not the
app being broken. Generated once, from the persona's own soul, the first time it is ever used
(there is no "persona creation" step in Sympose to hook this into), and cached to a plain file
forever after -- never regenerated automatically, and never gated by cloud sharing, since `soul.md`
is the persona itself, sent with every turn regardless, not the user's own data.

    profiles/<handle>/status_phrases.md
        Humming through your notes…
        One moment…
        ...
"""

import logging
import os
import time

from sympose import profile as profile_mod
from sympose.atomic_write import write_atomic_text
from sympose.engine import background_job, budget, helper_limit, prompt
from sympose.engine import model as model_mod
from sympose.persona_files import load_soul, persona_dir, profiles_dir
from sympose.security import is_safe_path

log = logging.getLogger(__name__)

FILENAME = "status_phrases.md"
_COUNT = 12
_MAX_REPLY_TOKENS = 250
# The web chat asks again after every reply while a persona has no phrases of its own, so a model that cannot make
# them (an error, or a reply with nothing usable) is left alone this long instead of being called once per reply.
RETRY_AFTER_SECONDS = 600
_FAILED_AT: dict[str, float] = {}

# Shown before a persona has its own set yet -- generating for the first time, or failed -- the
# same generic, no-persona-voice posture the rest of Sympose's own system lines already use.
FALLBACK = ["Thinking it over…", "Working on it…", "One moment…", "Getting things in order…"]


def _path(handle: str) -> str | None:
    try:
        path = os.path.join(persona_dir(handle), FILENAME)
    except ValueError:
        return None
    return path if is_safe_path(path, profiles_dir()) else None


def has_own(handle: str) -> bool:
    path = _path(handle)
    return path is not None and os.path.isfile(path)


def phrases(handle: str) -> list[str]:
    """The persona's own phrases, one per line as generated; `FALLBACK` when it has none yet."""
    path = _path(handle)
    if path is None:
        return FALLBACK
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = [line.strip() for line in f if line.strip()]
    except OSError:
        return FALLBACK
    return lines or FALLBACK


def _request(soul: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt.STATUS_PHRASES_INSTRUCTIONS},
        {"role": "user", "content": soul},
    ]


def generate(handle: str, model: str | None = None) -> bool:
    """Writes `handle`'s own `status_phrases.md` from its soul, unless it already has one. `False`
    when there was nothing to do, no persona, or the model call failed; never raises."""
    if has_own(handle):
        return False
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        return False
    path = _path(handle)
    if path is None:
        return False
    soul = load_soul(handle) or prompt.DEFAULT_SOUL
    model = model or model_mod.resolve_model(persona.get("model"))
    try:
        limits = budget.budget_for(model)  # the chat's own window, so a local model is not reloaded for this call
        reply = model_mod.call_model(
            _request(soul),
            model=model,
            num_ctx=limits.num_ctx if limits else None,
            max_tokens=helper_limit.for_model(model, _MAX_REPLY_TOKENS),
        )
    except model_mod.EngineModelError as e:
        log.warning("Status phrases for %s failed: %s", handle, e)
        _FAILED_AT[handle] = time.monotonic()
        return False
    lines = [line.strip(" -*\"") for line in reply.text.splitlines() if line.strip()][:_COUNT]
    if not lines:
        _FAILED_AT[handle] = time.monotonic()
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_atomic_text(path, "\n".join(lines) + "\n")
    except OSError:
        return False
    return True


# One generation per persona at a time -- there is only ever one to do, ever, per persona.
_RUNNER = background_job.Runner("phrases", "Status phrases")


def _failed_recently(handle: str) -> bool:
    failed = _FAILED_AT.get(handle)
    return failed is not None and time.monotonic() - failed < RETRY_AFTER_SECONDS


def generate_in_background(handle: str, model: str | None = None) -> bool:
    """Start `generate` in the background and return at once. `False` when `handle` already has
    its own phrases, a generation is already running for it, or one failed less than `RETRY_AFTER_SECONDS` ago."""
    if has_own(handle) or _failed_recently(handle):
        return False
    return _RUNNER.start(handle, lambda: generate(handle, model))


def is_running(handle: str) -> bool:
    """Whether a phrase generation is in flight for `handle` right now -- for
    `background_status.py`'s busy indicator, a point-in-time read, not a wait. Without this, the
    one background model call this module itself makes would be the one thing the busy indicator
    cannot show while it runs (docs/decisions/043)."""
    return _RUNNER.is_running(handle)
