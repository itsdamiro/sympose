"""The `remember` tool (docs/decisions/041): appends one line to a persona's own
`decisions.md`, independent of `vault_lookup`'s `auto`/`ask` setting (ADR 040), since
remembering something said in conversation is not a vault lookup. `run` is dispatched
alongside `lookup_tools.run` by `persona_tools`, and returns `None` for a tool name it
does not own so the two compose without either knowing about the other.

A model that cannot call tools gets the same capability through `extract`: an inline
`<!-- remember: text -->` marker in its reply, the same convention `recap.py` already
uses for its own `<!-- turns: N -->` header, parsed out and stripped before the reply
is shown."""

import json
import re
from typing import Any

from sympose.engine import memory
from sympose.engine.lookup_tools import Result

REMEMBER = "remember"
# Shown when a marker was all the model wrote, so the saved reply is never blank.
MARKER_ONLY_REPLY = "Noted."

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": REMEMBER,
            "description": (
                "Save one thing worth remembering to your decisions.md: a decision that was made and why, "
                "or a preference the user stated. Use it when the user says something worth keeping, or "
                "asks you to remember, save, or write something down. It only adds a line; it can never "
                "change or remove what's already there, and it can't touch profile.md or context.md."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The one thing to remember, in a plain sentence."}
                },
                "required": ["text"],
            },
        },
    },
]

_BAD_ARGUMENTS = "The argument of remember could not be read: give text as text."
_SAVED = "Remembered."
_FAILED = "That could not be saved."

_MARKER = re.compile(r"<!--\s*remember:\s*(.+?)\s*-->", re.IGNORECASE | re.DOTALL)


def _text_argument(raw: str | dict[str, Any] | None) -> str | None:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        parsed = None
    value = parsed.get("text") if isinstance(parsed, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def run(handle: str, name: str, raw_arguments: str | dict[str, Any] | None) -> Result | None:
    """The `remember` tool's result, or `None` for any other tool name -- so this composes with
    `lookup_tools.run` in one dispatcher (`persona_tools.for_turn`) without either module
    knowing the other's tools."""
    if name != REMEMBER:
        return None
    text = _text_argument(raw_arguments)
    if text is None:
        return Result(_BAD_ARGUMENTS, lookup={"tool": REMEMBER, "saved": False})
    ok = memory.append_decision(handle, text)
    return Result(_SAVED if ok else _FAILED, lookup={"tool": REMEMBER, "saved": ok})


def extract(text: str) -> tuple[str, list[str]]:
    """`text` with every `<!-- remember: ... -->` marker removed, and the list of what each one
    asked to remember (blank ones dropped). For a model that cannot call tools (docs/decisions/041).
    A reply with no marker at all is returned exactly as given -- the cleanup below (collapsing the
    blank line a removed marker leaves behind) must not also reformat an ordinary reply that never
    had one, or `memory_remember` would visibly change replies it has nothing to do with."""
    matches = list(_MARKER.finditer(text))
    if not matches:
        return text, []
    remembered = [m.group(1).strip() for m in matches if m.group(1).strip()]
    cleaned = _MARKER.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, remembered


def apply_marker(handle: str, text: str) -> tuple[str, list[dict[str, Any]]]:
    """`extract`, applied: each marker found is appended to `handle`'s decisions.md and recorded
    the same way a `remember` tool call is, so a turn's record does not care which mechanism ran."""
    cleaned, remembered = extract(text)
    cleaned = cleaned or (MARKER_ONLY_REPLY if remembered else cleaned)
    return cleaned, [{"tool": REMEMBER, "saved": memory.append_decision(handle, item)} for item in remembered]
