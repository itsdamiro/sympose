"""Tests for sympose.engine.model — model resolution and the litellm call
itself, fully mocked (no network calls) (docs/decisions/007)."""

from types import SimpleNamespace

import pytest

from sympose.engine import model


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def _chunk(content=None, reasoning=None, no_choices=False, finish=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    choice = SimpleNamespace(delta=delta, finish_reason=finish)
    return SimpleNamespace(choices=[] if no_choices else [choice])


def _stream(*contents):
    """A complete stream: the given text chunks, then a final chunk with a
    finish signal, as real providers send."""
    return iter([_chunk(c) for c in contents] + [_chunk(None, finish="stop")])


def test_resolve_model_defaults_to_local(settings_file):
    assert model.resolve_model() == model.DEFAULT_LOCAL_MODEL
    assert model.DEFAULT_LOCAL_MODEL.startswith("ollama_chat/")


def test_resolve_model_honors_settings_override(settings_file):
    from sympose import settings_store

    settings_store.set("chat_model", "anthropic/claude-sonnet")
    assert model.resolve_model() == "anthropic/claude-sonnet"


def test_call_model_streams_internally_and_returns_the_joined_reply(settings_file, monkeypatch):
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["model"] = model
        captured["messages"] = messages
        captured["stream"] = stream
        return _stream("hello ", "from ", "the model")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    reply = model.call_model([{"role": "user", "content": "hi"}])

    assert reply.text == "hello from the model"
    assert captured["stream"] is True
    assert captured["model"] == model.DEFAULT_LOCAL_MODEL


def test_call_model_passes_a_finite_timeout(settings_file, monkeypatch):
    """Regression test: `litellm.completion` was called with no timeout —
    combined with the CLI's single global `turn_lock` (docs/decisions/006),
    a genuinely hung request (stalled Ollama process, a network partition)
    would wedge every future message behind it forever, with no error and
    no way out short of killing the process."""
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["timeout"] = timeout
        return _stream("ok")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    model.call_model([{"role": "user", "content": "hi"}])

    assert isinstance(captured["timeout"], model.httpx.Timeout)
    assert captured["timeout"].read == model.model_wait.BASE_SECONDS


def test_call_model_uses_a_short_connect_timeout(settings_file, monkeypatch):
    """Regression test: a single overall `timeout=` number applies to connecting too, so a dead
    route (a dead IPv6 address Python tries before falling back to IPv4) can stall for most of the
    whole request budget before it gives up — measured at 75 s (docs/decisions/040 "Measured"). The
    connect timeout must be much shorter than the read timeout so a dead route fails fast."""
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["timeout"] = timeout
        return _stream("ok")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    model.call_model([{"role": "user", "content": "hi"}])

    assert captured["timeout"].connect == model._CONNECT_TIMEOUT_SECONDS
    assert captured["timeout"].connect < captured["timeout"].read


def test_call_model_uses_explicit_model_override(settings_file, monkeypatch):
    captured = {}

    def fake_completion(model, messages, stream, timeout):
        captured["model"] = model
        return _stream("ok")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    model.call_model([{"role": "user", "content": "hi"}], model="ollama_chat/other")

    assert captured["model"] == "ollama_chat/other"


def test_call_model_failure_raises_engine_model_error(settings_file, monkeypatch):
    def failing_completion(model, messages, stream, timeout):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(model.litellm, "completion", failing_completion)

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])


def test_call_model_timeout_raises_engine_model_error(settings_file, monkeypatch):
    def timing_out_completion(model, messages, stream, timeout):
        raise TimeoutError("request timed out")

    monkeypatch.setattr(model.litellm, "completion", timing_out_completion)

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])


def test_a_failure_mid_stream_raises_engine_model_error(settings_file, monkeypatch):
    def dying_stream():
        yield _chunk("partial ")
        raise ConnectionError("connection dropped")

    monkeypatch.setattr(
        model.litellm, "completion", lambda model, messages, stream, timeout: dying_stream()
    )

    with pytest.raises(model.EngineModelError):
        model.call_model([{"role": "user", "content": "hi"}])


def test_call_model_no_choices_or_no_content_raises_engine_model_error(settings_file, monkeypatch):
    """Regression test: a response with no choices (or only null content)
    used to raise a raw IndexError/AttributeError instead of the friendly
    EngineModelError every other failure path produces."""
    for stream in (
        iter([_chunk(no_choices=True)]),
        iter([_chunk(None), _chunk("")]),
        iter([]),
    ):
        monkeypatch.setattr(
            model.litellm, "completion", lambda model, messages, stream, timeout, s=stream: s
        )
        with pytest.raises(model.EngineModelError):
            model.call_model([{"role": "user", "content": "hi"}])


# -- TTFT (docs/decisions/013) --


def _fake_clock(monkeypatch, ticks):
    """`time.perf_counter` returning `ticks` in order (seconds)."""
    it = iter(ticks)
    monkeypatch.setattr(model.time, "perf_counter", lambda: next(it))


def test_ttft_is_start_to_first_content_chunk_in_ms(settings_file, monkeypatch):
    _fake_clock(monkeypatch, [10.0, 10.25, 10.9])  # start, first chunk, second chunk
    monkeypatch.setattr(
        model.litellm, "completion", lambda model, messages, stream, timeout: _stream("a", "b")
    )

    reply = model.call_model([{"role": "user", "content": "hi"}])

    assert reply.ttft_ms == 250  # measured at the first chunk, not the last


def test_ttft_skips_leading_empty_and_choiceless_chunks(settings_file, monkeypatch):
    _fake_clock(monkeypatch, [0.0, 0.5])  # start, then only the real first token
    chunks = iter(
        [_chunk(no_choices=True), _chunk(None), _chunk(""), _chunk("hi"), _chunk(None, finish="stop")]
    )
    monkeypatch.setattr(
        model.litellm, "completion", lambda model, messages, stream, timeout: chunks
    )

    assert model.call_model([{"role": "user", "content": "hi"}]).ttft_ms == 500


def test_reasoning_text_is_not_the_first_token_and_not_the_reply(settings_file, monkeypatch):
    """A thinking model streams reasoning before its answer. The user waits
    for the answer, so TTFT is measured to the first *reply* text; counting
    the reasoning would make a slow-to-answer model look fast."""
    _fake_clock(monkeypatch, [0.0, 2.0])  # start, then only the first reply chunk
    chunks = iter(
        [
            _chunk(None, reasoning="thinking..."),
            _chunk(None, reasoning="still thinking"),
            _chunk("the answer"),
            _chunk(None, finish="stop"),
        ]
    )
    monkeypatch.setattr(
        model.litellm, "completion", lambda model, messages, stream, timeout: chunks
    )

    reply = model.call_model([{"role": "user", "content": "hi"}])

    assert reply.ttft_ms == 2000
    assert reply.text == "the answer"


def test_a_stream_cut_off_without_a_finish_signal_is_an_error_not_a_reply(settings_file, monkeypatch):
    """A connection that closes cleanly mid-generation ends the stream with
    no exception. That partial text must not be returned and saved as if it
    were a whole reply (the old non-streaming call would have raised)."""
    truncated = iter([_chunk("half a sen"), _chunk("tence")])  # no finish_reason
    monkeypatch.setattr(
        model.litellm, "completion", lambda model, messages, stream, timeout: truncated
    )

    with pytest.raises(model.EngineModelError, match="cut off"):
        model.call_model([{"role": "user", "content": "hi"}])


# -- precedence: persona model > chat_model setting > built-in default
# (docs/decisions/010; an explicit per-call model beats all of these, see
# test_engine_turn.py) --


def test_resolve_model_prefers_the_persona_model_over_the_setting(settings_file):
    from sympose import settings_store

    settings_store.set("chat_model", "anthropic/claude-sonnet")
    assert model.resolve_model("ollama_chat/persona-pick") == "ollama_chat/persona-pick"


def test_resolve_model_falls_through_when_the_persona_has_none(settings_file):
    from sympose import settings_store

    settings_store.set("chat_model", "anthropic/claude-sonnet")
    assert model.resolve_model(None) == "anthropic/claude-sonnet"


def test_call_model_forwards_the_window_and_reply_cap_only_when_given(settings_file, monkeypatch):
    seen = []

    def fake_completion(model, messages, stream, timeout, **extra):
        seen.append(extra)
        return _stream("ok")

    monkeypatch.setattr(model.litellm, "completion", fake_completion)

    model.call_model([{"role": "user", "content": "hi"}])
    model.call_model([{"role": "user", "content": "hi"}], num_ctx=8192, max_tokens=1024)
    model.call_model([{"role": "user", "content": "hi"}], num_ctx=4096)

    assert seen == [{}, {"num_ctx": 8192, "max_tokens": 1024}, {"num_ctx": 4096}]


def _finished(*contents, finish):
    return iter([_chunk(c) for c in contents] + [_chunk(None, finish=finish)])


def test_a_reply_that_stopped_at_the_reply_limit_is_marked_truncated(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm, "completion",
        lambda model, messages, stream, timeout, **kw: _finished("half a sen", finish="length"),
    )
    reply = model.call_model([{"role": "user", "content": "hi"}], max_tokens=5)
    assert reply.truncated is True and reply.text == "half a sen"


def test_a_normal_reply_is_not_marked_truncated(settings_file, monkeypatch):
    monkeypatch.setattr(model.litellm, "completion", lambda model, messages, stream, timeout: _stream("done."))
    assert model.call_model([{"role": "user", "content": "hi"}]).truncated is False


def test_a_model_that_spends_its_whole_reply_limit_thinking_gets_a_clear_error(settings_file, monkeypatch):
    chunks = iter([_chunk(None, reasoning="thinking..."), _chunk(None, finish="length")])
    monkeypatch.setattr(
        model.litellm, "completion",
        lambda model, messages, stream, timeout, **kw: chunks,
    )
    with pytest.raises(model.ReplyLimitError, match="reply limit"):
        model.call_model([{"role": "user", "content": "hi"}], max_tokens=5)


def test_the_reply_is_tidied_before_it_is_returned(settings_file, monkeypatch):
    monkeypatch.setattr(model.litellm, "completion", lambda **kw: _stream("Hi there!", "  How are you?", " \n\n\n"))

    assert model.call_model([{"role": "user", "content": "hi"}]).text == "Hi there! How are you?"


def test_a_reply_of_only_whitespace_is_an_empty_reply(settings_file, monkeypatch):
    monkeypatch.setattr(model.litellm, "completion", lambda **kw: _stream(" \n", "\n\n"))

    with pytest.raises(model.EngineModelError, match="empty reply"):
        model.call_model([{"role": "user", "content": "hi"}])


@pytest.mark.parametrize("value", [None, "", "   ", 5, ["ollama_chat/x"]])
def test_a_chat_model_setting_that_is_not_a_model_name_is_the_default(settings_file, value):
    from sympose import settings_store

    settings_store.set("chat_model", value)

    assert model.resolve_model() == model.DEFAULT_LOCAL_MODEL


# -- tool calls in a streamed reply (docs/decisions/040) --


def _tool_chunk(index=0, id=None, name=None, arguments=None, finish=None):
    function = SimpleNamespace(name=name, arguments=arguments)
    piece = SimpleNamespace(index=index, id=id, function=function)
    delta = SimpleNamespace(content=None, reasoning_content=None, tool_calls=[piece])
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


def test_a_tool_call_sent_in_pieces_is_assembled_and_the_reply_has_no_text(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda **kwargs: iter(
            [
                _tool_chunk(0, "call_1", "search_notes", '{"que'),
                _tool_chunk(0, None, None, 'ry": "Atlas"}'),
                _chunk(None, finish="tool_calls"),
            ]
        ),
    )

    reply = model.call_model([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])

    assert reply.text == "" and reply.ttft_ms is None
    assert reply.tool_calls == (model.ToolCall("call_1", "search_notes", '{"query": "Atlas"}'),)


def test_two_tool_calls_keep_their_order_and_a_call_with_no_id_is_given_one(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda **kwargs: iter(
            [
                _tool_chunk(1, None, "open_note", '{"path": "B"}'),
                _tool_chunk(0, "keep", "search_notes", '{"query": "A"}'),
                _chunk(None, finish="stop"),
            ]
        ),
    )

    calls = model.call_model([{"role": "user", "content": "hi"}], tools=[{}]).tool_calls

    assert [(c.name, c.id) for c in calls] == [("search_notes", "keep"), ("open_note", "call_1")]


def test_tools_and_tool_choice_are_sent_only_when_given(settings_file, monkeypatch):
    seen = []

    def completion(**kwargs):
        seen.append(kwargs)
        return _stream("ok")

    monkeypatch.setattr(model.litellm, "completion", completion)

    model.call_model([{"role": "user", "content": "hi"}])
    model.call_model([{"role": "user", "content": "hi"}], tools=[{"type": "function"}], tool_choice="none")

    assert "tools" not in seen[0] and "tool_choice" not in seen[0]
    assert seen[1]["tools"] == [{"type": "function"}] and seen[1]["tool_choice"] == "none"


def test_text_before_a_tool_call_is_kept_with_it(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda **kwargs: iter([_chunk("Let me look."), _tool_chunk(0, "c", "search_notes", "{}"), _chunk(None, finish="stop")]),
    )

    reply = model.call_model([{"role": "user", "content": "hi"}], tools=[{}])

    assert reply.text == "Let me look." and len(reply.tool_calls) == 1


def test_a_tool_call_cut_off_before_the_stream_finished_is_an_error_not_a_call(settings_file, monkeypatch):
    monkeypatch.setattr(model.litellm, "completion", lambda **kwargs: iter([_tool_chunk(0, "c", "search_notes", '{"que')]))

    with pytest.raises(model.EngineModelError, match="empty reply"):
        model.call_model([{"role": "user", "content": "hi"}], tools=[{}])


def test_the_assistant_message_that_carries_the_calls_back_keeps_each_id_and_its_arguments():
    from sympose.engine import model_tools

    call = model.ToolCall("call_1__thought__abc", "open_note", "")

    message = model_tools.assistant_message("", (call,))

    assert message == {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "call_1__thought__abc", "type": "function", "function": {"name": "open_note", "arguments": "{}"}}],
    }
    assert model_tools.result_message(call, "found") == {
        "role": "tool", "tool_call_id": "call_1__thought__abc", "name": "open_note", "content": "found",
    }


def test_a_provider_that_repeats_the_tools_name_in_every_piece_does_not_double_it(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda **kwargs: iter(
            [
                _tool_chunk(0, "c", "search_notes", '{"query"'),
                _tool_chunk(0, None, "search_notes", ': "A"}'),
                _chunk(None, finish="stop"),
            ]
        ),
    )

    calls = model.call_model([{"role": "user", "content": "hi"}], tools=[{}]).tool_calls

    assert calls == (model.ToolCall("c", "search_notes", '{"query": "A"}'),)


def test_two_calls_that_both_arrive_under_index_zero_are_two_calls_not_one(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda **kwargs: iter(
            [
                _tool_chunk(0, "a", "search_notes", '{"query": "A"}'),
                _tool_chunk(0, "b", "open_note", '{"path": "B"}'),
                _chunk(None, finish="stop"),
            ]
        ),
    )

    calls = model.call_model([{"role": "user", "content": "hi"}], tools=[{}]).tool_calls

    assert calls == (
        model.ToolCall("a", "search_notes", '{"query": "A"}'),
        model.ToolCall("b", "open_note", '{"path": "B"}'),
    )


def test_a_call_whose_id_is_repeated_in_every_piece_is_still_one_call(settings_file, monkeypatch):
    monkeypatch.setattr(
        model.litellm,
        "completion",
        lambda **kwargs: iter(
            [_tool_chunk(0, "a", "open_note", '{"pa'), _tool_chunk(0, "a", None, 'th": "B"}'), _chunk(None, finish="stop")]
        ),
    )

    calls = model.call_model([{"role": "user", "content": "hi"}], tools=[{}]).tool_calls

    assert calls == (model.ToolCall("a", "open_note", '{"path": "B"}'),)
