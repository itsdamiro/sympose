"""The direct Gemini request (docs/decisions/089): what it sends for a turn with a video in it, and how it reads the
answer. The server is a fake (`httpx.MockTransport`); nothing here reaches Google."""

import json

import httpx
import pytest

from sympose.engine import gemini_direct, network, turn_cancel
from sympose.engine.model import EmptyReplyError, EngineModelError, ReplyLimitError

LINK = "https://www.youtube.com/watch?v=8jPQjjsBbIc"
SEARCH = {"type": "function", "function": {"name": "search_notes", "description": "Search.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}}}


def sse(*chunks: dict) -> bytes:
    return b"".join(b"data: " + json.dumps(c).encode() + b"\r\n\r\n" for c in chunks)


def parts(*items: dict, finish: str | None = None) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": list(items)}, **({"finishReason": finish} if finish else {})}]}


@pytest.fixture
def server(monkeypatch):
    """A fake Google: `server.answer` is the response body to give; `server.requests` what it was sent."""
    class Server:
        answer: httpx.Response = httpx.Response(200, content=sse(parts({"text": "hi"}, finish="STOP")))
        requests: list[httpx.Request] = []

    Server.requests = []

    def handler(request):
        Server.requests.append(request)
        return Server.answer

    monkeypatch.setattr(network, "ipv4_transport", lambda: httpx.MockTransport(handler))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return Server


def body_of(request: httpx.Request) -> dict:
    return json.loads(request.content)


def test_the_key_travels_in_a_header_and_never_in_the_address(server):
    gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    (request,) = server.requests
    assert request.headers["x-goog-api-key"] == "test-key" and "key=" not in str(request.url)
    assert request.url.path.endswith("/models/gemini-flash-latest:streamGenerateContent") and request.url.params["alt"] == "sse"


def test_the_video_is_attached_to_the_message_of_the_turn_in_the_agentic_mode(server):
    messages = [
        {"role": "system", "content": "You are Samantha."},
        {"role": "user", "content": "earlier"}, {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "watch this"},
    ]

    gemini_direct.call(messages, model="gemini/gemini-flash-latest", links=(LINK,))

    body = body_of(server.requests[0])
    assert body["systemInstruction"] == {"parts": [{"text": "You are Samantha."}]}
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["contents"][0]["parts"] == [{"text": "earlier"}]
    assert body["contents"][2]["parts"] == [
        {"fileData": {"fileUri": LINK, "mimeType": "video/mp4"}, "mediaProcessing": "AGENTIC"}, {"text": "watch this"},
    ]
    assert "tools" not in body and "toolConfig" not in body


def test_a_tool_round_goes_back_as_a_function_call_and_one_turn_of_answers_and_the_video_stays_on_the_first_message(server):
    messages = [
        {"role": "user", "content": "make a note"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_0", "type": "function", "function": {"name": "search_notes", "arguments": '{"query": "x"}'}},
            {"id": "call_1", "type": "function", "function": {"name": "search_notes", "arguments": "not json"}},
        ]},
        {"role": "tool", "tool_call_id": "call_0", "name": "search_notes", "content": "found a"},
        {"role": "tool", "tool_call_id": "call_1", "name": "search_notes", "content": "found b"},
        {"role": "user", "content": "[Sympose: answer now.]"},
    ]

    gemini_direct.call(messages, model="gemini/gemini-flash-latest", tools=[SEARCH], tool_choice="none", links=(LINK,))

    body = body_of(server.requests[0])
    first, called, answered = body["contents"]
    assert "fileData" in first["parts"][0] and first["role"] == "user"
    assert [p["functionCall"] for p in called["parts"]] == [{"name": "search_notes", "args": {"query": "x"}}, {"name": "search_notes", "args": {}}]
    assert all(p["thoughtSignature"] for p in called["parts"])
    assert answered["role"] == "user" and [p.get("functionResponse", {}).get("response") for p in answered["parts"][:2]] == [{"result": "found a"}, {"result": "found b"}]
    assert answered["parts"][2] == {"text": "[Sympose: answer now.]"} and "fileData" not in json.dumps(answered)


def test_the_tools_are_declared_beside_the_video_and_the_provider_is_told_to_allow_it(server):
    gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", tools=[SEARCH], max_tokens=900, links=(LINK,))

    body = body_of(server.requests[0])
    (declaration,) = body["tools"][0]["functionDeclarations"]
    assert declaration["name"] == "search_notes" and declaration["parametersJsonSchema"]["required"] == ["query"]
    assert body["toolConfig"] == {"includeServerSideToolInvocations": True}
    assert body["generationConfig"] == {"maxOutputTokens": 900}


def test_asking_for_no_more_tools_says_so_to_the_provider(server):
    gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", tools=[SEARCH], tool_choice="none", links=(LINK,))

    assert body_of(server.requests[0])["toolConfig"]["functionCallingConfig"] == {"mode": "NONE"}


def test_a_reply_is_the_text_with_the_thoughts_and_what_the_provider_looked_at_left_out(server):
    server.answer = httpx.Response(200, content=sse(
        parts({"toolCall": {"toolType": "VIDEO"}, "thoughtSignature": "s"}),
        parts({"toolResponse": {"toolType": "VIDEO"}}),
        parts({"text": "pondering", "thought": True}),
        parts({"text": "In the video, "}),
        parts({"text": "he talks about stress."}, finish="STOP"),
    ))

    reply = gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    assert reply.text == "In the video, he talks about stress." and reply.tool_calls == () and not reply.truncated
    assert reply.ttft_ms is not None


def test_a_function_call_becomes_a_tool_call_with_its_arguments_as_text(server):
    server.answer = httpx.Response(200, content=sse(parts(
        {"functionCall": {"name": "search_notes", "args": {"query": "stress"}}}, {"functionCall": {"name": "open_note", "args": {}}}, finish="STOP",
    )))

    reply = gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", tools=[SEARCH], links=(LINK,))

    assert [(c.id, c.name, json.loads(c.arguments)) for c in reply.tool_calls] == [("call_0", "search_notes", {"query": "stress"}), ("call_1", "open_note", {})]


def test_a_refusal_says_what_google_said_and_nothing_leaks_the_key(server):
    server.answer = httpx.Response(400, json={"error": {"code": 400, "message": "Function call is missing a thought_signature"}})

    with pytest.raises(EngineModelError, match="400: Function call is missing") as caught:
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    assert "test-key" not in str(caught.value)


def test_a_missing_key_is_said_in_plain_words(server, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(EngineModelError, match="GEMINI_API_KEY"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))


def test_a_reply_that_hit_its_limit_is_truncated_and_one_with_no_words_is_a_limit_error(server):
    server.answer = httpx.Response(200, content=sse(parts({"text": "Half a"}, finish="MAX_TOKENS")))
    assert gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,)).truncated

    server.answer = httpx.Response(200, content=sse(parts({"text": "thinking", "thought": True}, finish="MAX_TOKENS")))
    with pytest.raises(ReplyLimitError):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))


def test_an_empty_reply_a_filtered_reply_and_a_cut_off_stream_are_errors(server):
    server.answer = httpx.Response(200, content=sse(parts(finish="STOP")))
    with pytest.raises(EmptyReplyError):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    server.answer = httpx.Response(200, content=sse(parts({"text": "x"}, finish="SAFETY")))
    with pytest.raises(EngineModelError, match="would not answer"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    server.answer = httpx.Response(200, content=sse(parts({"text": "x"})))
    with pytest.raises(EngineModelError, match="cut off"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    server.answer = httpx.Response(200, content=sse({"promptFeedback": {"blockReason": "OTHER"}}))
    with pytest.raises(EngineModelError, match="OTHER"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))


def test_an_error_that_arrives_after_the_reply_began_is_reported_with_googles_words_and_so_is_a_line_that_is_not_json(server):
    server.answer = httpx.Response(200, content=sse(parts({"text": "In the"}), {"error": {"code": 429, "message": "Quota exceeded for this model"}}))
    with pytest.raises(EngineModelError, match="429: Quota exceeded"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))

    server.answer = httpx.Response(200, content=b"data: not json\r\n\r\n")
    with pytest.raises(EngineModelError, match="could not read"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))


def test_a_stop_is_heard_while_the_reply_is_being_read(server, monkeypatch):
    def stopped():
        raise turn_cancel.TurnCancelled()

    monkeypatch.setattr(turn_cancel, "check", stopped)

    with pytest.raises(turn_cancel.TurnCancelled):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))


def test_a_connection_that_runs_out_of_time_says_how_to_wait_longer(monkeypatch):
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(network, "ipv4_transport", lambda: httpx.MockTransport(slow))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with pytest.raises(EngineModelError, match="model_timeout"):
        gemini_direct.call([{"role": "user", "content": "hi"}], model="gemini/gemini-flash-latest", links=(LINK,))
