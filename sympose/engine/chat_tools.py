"""The two tools a persona has when `past_chats` is `ask` (docs/decisions/056): `search_chats`, the reader's
matcher on a query she writes, and `open_chat`, the whole of one earlier conversation. Both are read-only and
inside the persona's own conversations: `open_chat` takes an id from the persona's own list of conversations,
never a path, and never the conversation in progress or one in the Bin; any other id is "not found" without
saying why. What they find passes `sharing.gate` under `chats` before it reaches a model."""

import json
from typing import Any

from sympose.engine import past_chats, sharing
from sympose.engine.lookup_result import Result
from sympose.engine.prompt_text import CHATS_HER, CHATS_USER, WITHHELD_CHATS_TOOL

SEARCH, OPEN = "search_chats", "open_chat"
MAX_CHARS = 12000  # one opened conversation, cut with a marker; the prompt budget then fits what is left
_CUT = "\n[The conversation continues; the rest was left out because it is long.]"

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": SEARCH,
            "description": (
                "Search your earlier conversations with the user (not this one) for a topic, a name or a question "
                "and get back the best matching exchanges word for word, each with the id of its conversation. "
                "Use it when the user asks what was said or decided before, or what you said or suggested."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look for, in a few words."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": OPEN,
            "description": (
                "Read one earlier conversation in full, by the id search_chats gave. Use it when the exchanges "
                "found are not enough and you need the rest of that conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string", "description": "The conversation's id, from a search."}},
                "required": ["id"],
            },
        },
    },
]

_UNKNOWN_TOOL = "There is no tool called {name}. The tools are {names}."
_BAD_ARGUMENTS = "The arguments of {name} could not be read: give {argument} as text."
_NOTHING = "The search for {query} found nothing in your earlier conversations."
_NOT_FOUND = "No earlier conversation with the id {id} was found."


def _argument(raw: str | dict[str, Any] | None, argument: str) -> str | None:
    try:
        parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except json.JSONDecodeError:
        return None
    value = parsed.get(argument) if isinstance(parsed, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _lines(exchange: dict[str, Any]) -> str:
    return f"{CHATS_USER}: {exchange['user']}\n{CHATS_HER}: {exchange['assistant']}"


def _gated(model: str, chats: list[dict[str, Any]], text: str, nothing: str, lookup: dict[str, Any]) -> Result:
    gated = sharing.gate(model, [], [], chats)
    if chats and not gated.chats:
        return Result(WITHHELD_CHATS_TOOL, [], gated.withheld, {**lookup, "found": 0}, [])
    if not chats:
        return Result(nothing, lookup={**lookup, "found": 0})
    return Result(text, [], {}, {**lookup, "found": len(chats)}, chats)


def search_chats(handle: str, model: str, query: str, exclude: str | None) -> Result:
    found = past_chats.search(handle, query, exclude, about_the_past=True)
    chats = [{**x, "how": "searched"} for x in found]
    lines = [f"Exchanges from earlier conversations for the search {query!r}:"]
    for x in chats:
        lines.append(f"[id: {x['session']}] ({x['date']}, message {x['turn']} of that conversation)\n{_lines(x)}")
    return _gated(model, chats, "\n\n".join(lines), _NOTHING.format(query=repr(query)), {"query": query})


def open_chat(handle: str, model: str, session_id: str, exclude: str | None) -> Result:
    exchanges = past_chats.conversation(handle, session_id, exclude)
    if exchanges is None:
        return Result(_NOT_FOUND.format(id=repr(session_id)), lookup={"id": session_id, "found": 0})
    shown, size = [], 0
    for x in exchanges:
        block = f"(message {x['turn']})\n{_lines(x)}"
        if shown and size + len(block) > MAX_CHARS:
            break
        shown.append(x)
        size += len(block)
    text = f"The earlier conversation {session_id} ({exchanges[0]['date']}), {len(exchanges)} messages:\n\n" + "\n\n".join(
        f"(message {x['turn']})\n{_lines(x)}" for x in shown
    )
    if len(shown) < len(exchanges):
        text += _CUT
    return _gated(model, [{**x, "how": "opened"} for x in shown], text, _NOT_FOUND.format(id=repr(session_id)), {"id": session_id})


def run(handle: str, exclude: str | None, model: str, name: str, raw_arguments: str | dict[str, Any] | None) -> Result:
    """Run the tool `name`: an unknown tool, or arguments that are not readable, is a result like any other (the
    model can try again), never an exception that ends the turn. `exclude`: the conversation in progress."""
    tool = {SEARCH: ("query", search_chats), OPEN: ("id", open_chat)}.get(name)
    if tool is None:
        return Result(_UNKNOWN_TOOL.format(name=name, names=f"{SEARCH}, {OPEN}"), lookup={"tool": name, "found": 0})
    value = _argument(raw_arguments, tool[0])
    if value is None:
        return Result(_BAD_ARGUMENTS.format(name=name, argument=tool[0]), lookup={"tool": name, "found": 0})
    result = tool[1](handle, model, value, exclude)
    return Result(result.text, result.hits, result.withheld, {"tool": name, **result.lookup}, result.chats)
