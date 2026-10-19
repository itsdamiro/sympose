"""A request made straight to Google's Gemini API (docs/decisions/089), for a turn that has a video link in it.
LiteLLM cannot send one: its Gemini route downloads every file address and sends the bytes, it has no field for the
agentic video mode (`mediaProcessing`), and it drops Google's own tools whenever a function is declared. So this
module is `model.call_model` for that turn, with the same arguments, the same `ModelReply` and the same errors:
`lookup.converse` takes it as its `call`, and the vault tools, `remember` and the edit tools work as they do on
any other model.

The video is attached to the user's message of the turn, in the agentic mode, where the model looks at the parts of
the video it needs (about 5,000 to 8,000 tokens for notes on a 20-minute video, against 68,000 for the whole of it).
What it looked at is not kept: the reply's `toolCall` and `toolResponse` parts are refused when sent back (400), so
the history carries text and function calls only."""

import base64
import json
import logging
import os
import re
import time
from typing import Any

import httpx

from sympose.engine import media, model_wait, network, reply_text, turn_cancel
from sympose.engine.model import EngineModelError, ModelReply, end_reply
from sympose.engine.model_tools import ToolCall

log = logging.getLogger(__name__)

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_CONNECT_TIMEOUT_SECONDS = 10
_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
# Google refuses a function call sent back without a thought signature, and Sympose does not keep the real one (the
# history is OpenAI-shaped); this is the value Google documents for a call the model did not make in this request.
_NO_SIGNATURE = "skip_thought_signature_validator"
# A reply that stopped for one of these did not end by itself, and says why in plain words.
_STOPPED = {
    "SAFETY": "Gemini would not answer this (its safety filter stopped the reply).",
    "RECITATION": "Gemini stopped the reply because it would repeat text too closely.",
    "PROHIBITED_CONTENT": "Gemini would not answer this.",
    "BLOCKLIST": "Gemini would not answer this.",
    "SPII": "Gemini would not answer this.",
    "IMAGE_SAFETY": "Gemini would not answer this.",
}


class WatchUnavailable(EngineModelError):
    """Google would not take the video itself: the preview changed, or this video cannot be read that way (a 400 or a
    404 answering a request that carried one). The turn falls back to the video's captions (`watch_call`)."""


# Statuses that mean the request, not the account or the load, was the trouble. A key, a quota or an overload is not
# helped by asking Google the same question another way.
_REQUEST_REFUSED = (400, 404)


# Where the model read a page or a search result it sometimes leaves the reader's own source marks in the text, `[1.1]` or
# `[1.1, 2.3]`; the user has no list they point into. Only a turn that carried Google's tools is cleaned.
_SOURCE_MARKS = re.compile(r"[ \t]*\[\d+\.\d+(?:,[ \t]*\d+\.\d+)*\]")


def _pages(candidate: dict[str, Any], opened: bool) -> list[str]:
    """The pages Google's reader was asked for, as the reply's metadata names them: those it opened, or those it could not."""
    found = (candidate.get("urlContextMetadata") or {}).get("urlMetadata") or []
    return [
        m.get("retrievedUrl") or "a page" for m in found
        if (m.get("urlRetrievalStatus") == "URL_RETRIEVAL_STATUS_SUCCESS") == opened and m.get("urlRetrievalStatus") is not None
    ]


def _key() -> str:
    for name in _KEY_NAMES:
        if value := os.environ.get(name):
            return value
    raise EngineModelError("No Gemini key was found. Set GEMINI_API_KEY in the .env file, then try again.")


def _declarations(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"name": t["function"]["name"], "description": t["function"].get("description", ""), "parametersJsonSchema": t["function"].get("parameters") or {"type": "object", "properties": {}}}
        for t in tools
    ]


def _arguments(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw) if isinstance(raw, str) and raw.strip() else raw
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _add(contents: list[dict[str, Any]], role: str, parts: list[dict[str, Any]]) -> None:
    """Consecutive turns of one role are one turn: the answers to several tool calls must arrive together."""
    if contents and contents[-1]["role"] == role:
        contents[-1]["parts"].extend(parts)
    else:
        contents.append({"role": role, "parts": parts})


def _turn_start(messages: list[dict[str, Any]]) -> int:
    """Where this turn's own message is: the first user message after the last assistant reply that is text, not
    a tool call. The tool rounds of the turn come after it, and a line `converse` adds at the end is not it."""
    after = max((i for i, m in enumerate(messages) if m.get("role") == "assistant" and not m.get("tool_calls")), default=-1)
    return next((i for i in range(after + 1, len(messages)) if messages[i].get("role") == "user"), len(messages) - 1)


def _homes(messages: list[dict[str, Any]], start: int, files: tuple[media.File, ...]) -> dict[int, tuple[media.File, ...]]:
    """Which message carries each file: the latest user message, from the turn's own message back, that names it with
    its marker (`media.named_in`), else the turn's own. Kept where it was first attached, a carried file leaves the start
    of every later request as it was, which is what Google's automatic cache matches (docs/decisions/089)."""
    homes: dict[int, list[media.File]] = {}
    for f in files:
        at = next((i for i in range(start, -1, -1) if messages[i].get("role") == "user" and f.name in media.named_in(messages[i])), start)
        homes.setdefault(at, []).append(f)
    return {i: tuple(group) for i, group in homes.items()}


def _file_parts(files: tuple[media.File, ...]) -> list[dict[str, Any]]:
    """Each attached file as the bytes inside the request, with a line before it naming it (the message names it too). A
    video is read in the agentic mode, as a linked one is: measured on a 3-minute video, 8,500 tokens against 17,500 for
    the whole of it, and 1,800 against 3,000 on a 30-second one, for about three times the wait."""
    parts: list[dict[str, Any]] = []
    for f in files:
        parts.append({"text": f"File: {f.name}"})
        part: dict[str, Any] = {"inlineData": {"mimeType": f.mime, "data": base64.b64encode(f.data).decode("ascii")}}
        if f.kind == media.VIDEO:
            part["mediaProcessing"] = "AGENTIC"
        parts.append(part)
    return parts


def request_body(
    messages: list[dict[str, Any]], links: tuple[str, ...], tools: list[dict[str, Any]] | None, tool_choice: str | None,
    max_tokens: int | None, server_tools: tuple[str, ...] = (), files: tuple[media.File, ...] = (),
) -> dict[str, Any]:
    """The `generateContent` request for `messages` (OpenAI-shaped, as the engine builds them) with each of `links`
    attached to the turn's message as a video to watch, each of `files` attached as the bytes themselves to the message
    that named it (`_homes`), and
    `server_tools` (Google's search and page reading, named as its request names them) beside the vault's own functions."""
    system = "\n\n".join(str(m["content"]) for m in messages if m.get("role") == "system" and m.get("content"))
    start = _turn_start(messages)
    homes = _homes(messages, start, files)
    contents: list[dict[str, Any]] = []
    for index, m in enumerate(messages):
        role = m.get("role")
        if role == "user":
            watched = [
                {"fileData": {"fileUri": link, "mimeType": "video/mp4"}, "mediaProcessing": "AGENTIC"} for link in links
            ] if index == start else []
            given = _file_parts(homes.get(index, ()))
            _add(contents, "user", [*given, *watched, {"text": str(m.get("content") or "")}])
        elif role == "assistant":
            parts: list[dict[str, Any]] = [{"text": m["content"]}] if m.get("content") else []
            for call in m.get("tool_calls") or []:
                function = call["function"]
                parts.append({"functionCall": {"name": function["name"], "args": _arguments(function.get("arguments"))}, "thoughtSignature": _NO_SIGNATURE})
            if parts:
                _add(contents, "model", parts)
        elif role == "tool":
            _add(contents, "user", [{"functionResponse": {"name": m.get("name") or "tool", "response": {"result": str(m.get("content") or "")}}}])
    body: dict[str, Any] = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if max_tokens:
        body["generationConfig"] = {"maxOutputTokens": max_tokens}
    if tools:
        body["tools"] = [{"functionDeclarations": _declarations(tools)}]
        # Needed for a function beside a tool the provider runs (the video, search, page reading); without it Google refuses the request.
        body["toolConfig"] = {"includeServerSideToolInvocations": True}
        if tool_choice == "none":
            body["toolConfig"]["functionCallingConfig"] = {"mode": "NONE"}
    if server_tools:
        body["tools"] = [*body.get("tools", []), *({name: {}} for name in server_tools)]
    return body


def _explain(status: int, text: str) -> str:
    try:
        detail = json.loads(text).get("error", {}).get("message") or text
    except ValueError:
        detail = text
    return f"{status}: {detail}"[:400]


def call(
    messages: list[dict[str, Any]],
    model: str | None = None,
    num_ctx: int | None = None,
    max_tokens: int | None = None,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    links: tuple[str, ...] = (),
    server_tools: tuple[str, ...] = (),
    files: tuple[media.File, ...] = (),
    unopened: list[str] | None = None,
    opened: list[str] | None = None,
    searched: list[str] | None = None,
    grounding: list[dict[str, Any]] | None = None,
) -> ModelReply:
    """`model.call_model` for a turn that watches `links`, sends `files` or has Google's `server_tools`; `num_ctx` is only there so the two can be swapped (it is for
    a local model). Streamed, so a stop (docs/decisions/054) is heard while the video is being read, and the time to the
    first text is measured."""
    name = (model or "").split("/", 1)[-1]
    waited = model_wait.seconds(messages)
    body = request_body(messages, links, tools, tool_choice, max_tokens, server_tools, files)
    started = time.perf_counter()
    ttft_ms: int | None = None
    texts: list[str] = []
    calls: list[ToolCall] = []
    reason: str | None = None
    usage: dict[str, Any] = {}
    try:
        with httpx.Client(transport=network.ipv4_transport(), timeout=httpx.Timeout(waited, connect=_CONNECT_TIMEOUT_SECONDS)) as client:
            with client.stream(
                "POST", f"{_BASE}/{name}:streamGenerateContent", params={"alt": "sse"}, json=body,
                headers={"x-goog-api-key": _key()},
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    refused = WatchUnavailable if links and response.status_code in _REQUEST_REFUSED else EngineModelError
                    what = "the attached file" if files and response.status_code in _REQUEST_REFUSED and not links else "the request"
                    raise refused(f"Gemini refused {what} ({_explain(response.status_code, response.text)})")
                for line in response.iter_lines():
                    turn_cancel.check()  # a stop ends the loop and, leaving the block, the request
                    if not line.startswith("data:"):
                        continue
                    try:
                        chunk = json.loads(line[5:])
                    except ValueError as e:
                        raise EngineModelError("Gemini sent a reply Sympose could not read.") from e
                    if error := chunk.get("error"):  # an error can arrive after the reply has begun
                        raise EngineModelError(f"Gemini stopped the reply ({error.get('code')}: {error.get('message') or error})")
                    usage = chunk.get("usageMetadata") or usage
                    candidate = (chunk.get("candidates") or [{}])[0]
                    if unopened is not None:
                        unopened.extend(_pages(candidate, opened=False))
                    if opened is not None:
                        opened.extend(_pages(candidate, opened=True))
                    if searched is not None:
                        searched.extend((candidate.get("groundingMetadata") or {}).get("webSearchQueries") or [])
                    if grounding is not None and candidate.get("groundingMetadata"):
                        grounding.append(candidate["groundingMetadata"])
                    if block := (chunk.get("promptFeedback") or {}).get("blockReason"):
                        raise EngineModelError(f"Gemini would not read this message ({block}).")
                    for part in (candidate.get("content") or {}).get("parts") or []:
                        if part.get("thought"):
                            continue
                        if text := part.get("text"):
                            if ttft_ms is None:
                                ttft_ms = round((time.perf_counter() - started) * 1000)
                            texts.append(text)
                        if function := part.get("functionCall"):
                            calls.append(ToolCall(f"call_{len(calls)}", function["name"], json.dumps(function.get("args") or {})))
                    reason = candidate.get("finishReason") or reason
    except turn_cancel.TurnCancelled:
        raise
    except EngineModelError:
        raise
    except Exception as e:
        log.warning("Direct Gemini call to %s failed: %s", name, e)
        if model_wait.is_timeout(e):
            raise EngineModelError(model_wait.message(model or name, waited)) from e
        raise EngineModelError(f"Couldn't reach model '{model}': {e}") from e
    content = reply_text.tidy(_SOURCE_MARKS.sub("", "".join(texts)) if server_tools else "".join(texts))
    if reason in _STOPPED:
        raise EngineModelError(_STOPPED[reason])
    return end_reply(model or name, content, tuple(calls), reason is not None, reason == "MAX_TOKENS", ttft_ms,
                     usage.get("promptTokenCount"), usage.get("cachedContentTokenCount"))
