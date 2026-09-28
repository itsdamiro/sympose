"""Tool calls in a streamed model reply (docs/decisions/040). `model.call_model` streams, and a model
that wants a tool sends it in pieces: which tool, then its arguments a few characters at a time.
This assembles them, and writes the assistant message that goes back into the conversation
beside the tool's result."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """One tool the model asked for: `arguments` is the JSON text as the model wrote it, which the
    tool reads (and answers plainly when it cannot)."""

    id: str
    name: str
    arguments: str


def collect(chunk: Any, slots: dict[int, dict[str, str]]) -> None:
    """Add the tool-call pieces one streamed chunk carries to `slots`, by the call's index."""
    if not chunk.choices:
        return
    for piece in getattr(chunk.choices[0].delta, "tool_calls", None) or []:
        index, piece_id = getattr(piece, "index", None) or 0, getattr(piece, "id", None)
        if piece_id and slots.get(index, {}).get("id") not in ("", None, piece_id):
            index = max(slots) + 1  # a different call under an index already taken: a provider that gives every call index 0
        slot = slots.setdefault(index, {"id": "", "name": "", "arguments": ""})
        slot["id"] = piece_id or slot["id"]
        function = getattr(piece, "function", None)
        if function is not None:
            slot["name"] = slot["name"] or getattr(function, "name", None) or ""
            slot["arguments"] += getattr(function, "arguments", None) or ""


def finish(slots: dict[int, dict[str, str]]) -> tuple[ToolCall, ...]:
    """The calls `collect` gathered, in the order asked; a call with no name is left out, and one the model
    gave no id is given one, since the result must say which call it answers."""
    return tuple(
        ToolCall(slot["id"] or f"call_{n}", slot["name"], slot["arguments"])
        for n, (_, slot) in enumerate(sorted(slots.items()))
        if slot["name"]
    )


def assistant_message(text: str, calls: tuple[ToolCall, ...]) -> dict[str, Any]:
    """The assistant's turn as the next request must carry it: the calls it made, then the tool
    results follow as their own messages."""
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments or "{}"}}
            for call in calls
        ],
    }


def result_message(call: ToolCall, text: str) -> dict[str, str]:
    return {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": text}
