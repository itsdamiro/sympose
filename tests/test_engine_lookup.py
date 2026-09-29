"""The persona looks up notes itself (docs/decisions/040): the `vault_lookup` setting and its fail-safe
reading, which mode a model really runs, and the loop of an `ask` turn (what each call is sent, when it
stops, what is recorded and how a big result is fitted). The model is a fake that replays a script."""

import json

import pytest

from sympose import settings_store
from sympose.engine import budget, lookup, lookup_tools, tool_support, turn_status
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
PERSONA = {"vault_folders": ["*"]}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Projects" / "Atlas.md").write_text("# Atlas\nWe chose SQLite for the Atlas prototype database.")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def script(*replies):
    """A model that answers with `replies` in turn and remembers what each call was sent."""
    sent: list[dict] = []
    queue = list(replies)

    def call(messages, **kwargs):
        sent.append({"messages": list(messages), **kwargs})
        return queue.pop(0)

    call.sent = sent
    return call


def asks(name, arguments, call_id="c1", text="", ttft=None):
    return ModelReply(text, ttft, tool_calls=(ToolCall(call_id, name, arguments),))


def says(text, ttft=100):
    return ModelReply(text, ttft)


BASE = [{"role": "system", "content": "soul"}, {"role": "user", "content": "what did we decide about Atlas?"}]


@pytest.mark.parametrize("value, expected", [("ask", "ask"), ("auto", "auto"), (None, "auto"), ("ASK", "auto"),
                                              ("", "auto"), (True, "auto"), (["ask"], "auto"), ("model-searches", "auto")])
def test_only_an_explicit_ask_asks(value, expected):
    if value is not None:
        settings_store.set("vault_lookup", value)

    assert lookup.mode() == expected


@pytest.mark.parametrize("value, expected", [(None, 3), (1, 1), (5, 5), (0, 3), (-2, 3), ("4", 3), (True, 3), (2.5, 3), (99, 8)])
def test_the_number_of_rounds_is_a_whole_number_from_one_and_bounded(value, expected):
    if value is not None:
        settings_store.set("vault_lookup_rounds", value)

    assert lookup.rounds() == expected


def test_ask_runs_only_on_a_model_that_can_call_tools(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)

    assert lookup.effective_mode(CLOUD) == "ask"
    assert lookup.effective_mode(LOCAL) == "auto"


def test_auto_stays_auto_on_a_model_that_can_call_tools(monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    assert lookup.effective_mode(CLOUD) == "auto"


def test_a_model_litellm_cannot_tell_about_is_treated_as_unable(monkeypatch):
    def unknown(model):
        raise ValueError("this model isn't mapped")

    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", unknown)

    assert tool_support.can_call_tools("some/new-model") is False


def test_a_model_marked_unable_is_not_asked_again(monkeypatch):
    settings_store.set("vault_lookup", "ask")
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    tool_support.mark_unable(CLOUD)

    assert lookup.effective_mode(CLOUD) == "auto"


def test_a_reply_with_no_tool_call_is_the_answer_and_nothing_was_looked_up():
    call = script(says("Hello!"))

    done = lookup.converse(PERSONA, BASE, CLOUD, None, call=call)

    assert done.reply.text == "Hello!" and done.lookups == [] and done.hits == []
    assert len(call.sent) == 1 and call.sent[0]["tools"] == lookup_tools.TOOLS and call.sent[0]["tool_choice"] is None


def test_converse_uses_the_tools_and_dispatcher_it_is_given_not_the_vault_ones(monkeypatch):
    # docs/decisions/041: `persona_tools` composes a `remember` tool into this same loop,
    # independent of the vault tools `converse` defaults to.
    custom_tools = [{"type": "function", "function": {"name": "remember"}}]
    seen_calls = []

    def run_tool(persona, model, name, raw_arguments):
        seen_calls.append((persona, model, name, raw_arguments))
        return lookup_tools.Result("Remembered.", lookup={"tool": name, "saved": True})

    call = script(asks("remember", '{"text": "x"}', "c1"), says("Done."))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call, tools=custom_tools, run_tool=run_tool)

    assert call.sent[0]["tools"] == custom_tools
    assert seen_calls == [(PERSONA, LOCAL, "remember", '{"text": "x"}')]
    assert done.lookups == [{"tool": "remember", "saved": True}]


def test_a_search_is_run_and_its_result_goes_back_to_the_model_beside_the_call():
    call = script(asks("search_notes", '{"query": "Atlas database"}', "c9"), says("SQLite."))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    second = call.sent[1]["messages"]
    assert second[: len(BASE)] == BASE
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["id"] == "c9"
    assert second[-2]["tool_calls"][0]["function"] == {"name": "search_notes", "arguments": '{"query": "Atlas database"}'}
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c9" and "SQLite" in second[-1]["content"]
    assert done.reply.text == "SQLite."
    assert done.lookups == [{"tool": "search_notes", "query": "Atlas database", "found": 1}]
    assert [hit["rel_path"] for hit in done.hits] == ["Projects/Atlas.md"]
    assert BASE == BASE[:2] and len(BASE) == 2  # the prompt handed in is not changed


def test_two_calls_in_one_reply_are_both_run_and_both_answered_in_order():
    both = ModelReply("", None, tool_calls=(ToolCall("a", "search_notes", '{"query": "Atlas"}'), ToolCall("b", "open_note", '{"path": "Atlas"}')))
    call = script(both, says("done"))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    tail = call.sent[1]["messages"][-3:]
    assert [m["role"] for m in tail] == ["assistant", "tool", "tool"] and [m.get("tool_call_id") for m in tail[1:]] == ["a", "b"]
    assert [entry["tool"] for entry in done.lookups] == ["search_notes", "open_note"]


def test_a_search_tool_call_shows_searching_and_an_open_note_call_shows_reading():
    """The busy indicator's real per-turn phase (docs/decisions/043's follow-up): each tool round
    shows `asking` for the model call itself, then the specific phase for whichever tool it asked for."""
    both = ModelReply(
        "", None,
        tool_calls=(ToolCall("a", "search_notes", '{"query": "Atlas"}'), ToolCall("b", "open_note", '{"path": "Atlas"}')),
    )
    call = script(both, says("done"))
    persona = {**PERSONA, "handle": "samantha"}
    phases = []

    def spying_run_tool(persona, model, name, arguments):
        phases.append((name, turn_status.phase("samantha")))
        return lookup_tools.run(persona, model, name, arguments)

    lookup.converse(persona, BASE, LOCAL, None, call=call, run_tool=spying_run_tool)

    assert phases == [("search_notes", turn_status.SEARCHING), ("open_note", turn_status.READING)]


def test_the_same_passage_found_twice_is_recorded_once():
    call = script(asks("search_notes", '{"query": "Atlas"}'), asks("open_note", '{"path": "Atlas"}', "c2"), says("ok"))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    assert len(done.lookups) == 2
    keys = [(h["rel_path"], h["heading"], h["kind"]) for h in done.hits]
    assert len(keys) == len(set(keys))


def test_a_tool_that_finds_nothing_is_a_result_and_the_model_answers():
    call = script(asks("open_note", '{"path": "Nowhere"}'), says("I couldn't find it."))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    assert "No note called" in call.sent[1]["messages"][-1]["content"]
    assert done.lookups[0]["found"] == 0 and done.reply.text == "I couldn't find it."


def test_when_the_rounds_are_used_the_last_call_is_told_to_use_no_tool():
    settings_store.set("vault_lookup_rounds", 2)
    call = script(asks("search_notes", '{"query": "a"}', "1"), asks("search_notes", '{"query": "b"}', "2"), says("final"))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    assert [sent["tool_choice"] for sent in call.sent] == [None, None, "none"]
    assert done.reply.text == "final" and len(done.lookups) == 2
    assert call.sent[2]["messages"][-1] == {"role": "user", "content": lookup._ANSWER_NOW}
    assert all(lookup._ANSWER_NOW not in str(sent["messages"]) for sent in call.sent[:2])  # only the last call is told
    assert all(lookup._ANSWER_NOW not in str(sent["messages"][:-1]) for sent in call.sent)


def test_a_model_that_still_asks_on_the_last_call_writes_no_answer_and_that_is_an_error():
    settings_store.set("vault_lookup_rounds", 1)
    call = script(asks("search_notes", '{"query": "a"}', "1"), asks("search_notes", '{"query": "b"}', "2"))

    with pytest.raises(EngineModelError, match="1 lookups without writing an answer"):
        lookup.converse(PERSONA, BASE, LOCAL, None, call=call)


def test_a_failing_model_call_is_not_swallowed():
    def call(messages, **kwargs):
        raise EngineModelError("no route")

    with pytest.raises(EngineModelError, match="no route"):
        lookup.converse(PERSONA, BASE, LOCAL, None, call=call)


def test_time_to_first_token_counts_the_rounds_the_user_waited_through(monkeypatch):
    clock = iter([10.0, 10.0, 12.0, 12.0])  # started; before call 1; (call 1 ran 2 s); before call 2
    monkeypatch.setattr(lookup.time, "perf_counter", lambda: next(clock))
    call = script(asks("search_notes", '{"query": "Atlas"}'), says("SQLite.", ttft=300))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    assert done.ttft_ms == 2000 + 300


def test_no_first_token_time_is_none_when_the_model_gave_none():
    assert lookup.converse(PERSONA, BASE, LOCAL, None, call=script(says("x", ttft=None))).ttft_ms is None


def test_the_window_asked_of_a_local_model_and_its_reply_cap_go_with_every_call():
    limits = budget.Budget(prompt_tokens=5000, num_ctx=8192, reply_cap=1024)
    call = script(asks("search_notes", '{"query": "Atlas"}'), says("x"))

    lookup.converse(PERSONA, BASE, LOCAL, limits, call=call)

    assert all(sent["num_ctx"] == 8192 and sent["max_tokens"] == 1024 for sent in call.sent)


def test_a_result_that_does_not_fit_the_window_is_cut_and_says_so(tmp_path):
    (tmp_path / "vault" / "Long.md").write_text("word " * 900)
    limits = budget.Budget(prompt_tokens=400, num_ctx=None, reply_cap=None)
    call = script(asks("open_note", '{"path": "Long"}'), says("x"))

    lookup.converse(PERSONA, BASE, LOCAL, limits, used_tokens=150, call=call)

    result = call.sent[1]["messages"][-1]["content"]
    assert result.endswith("did not fit the context window.]") and 0 < len(result) < 4500 / 2


def test_a_result_with_room_is_sent_whole():
    limits = budget.Budget(prompt_tokens=50000, num_ctx=None, reply_cap=None)
    call = script(asks("search_notes", '{"query": "Atlas"}'), says("x"))

    lookup.converse(PERSONA, BASE, LOCAL, limits, used_tokens=100, call=call)

    assert "did not fit" not in call.sent[1]["messages"][-1]["content"]


def test_with_no_room_left_at_all_the_result_is_replaced_by_a_line_saying_so():
    limits = budget.Budget(prompt_tokens=1000, num_ctx=None, reply_cap=None)
    call = script(asks("search_notes", '{"query": "Atlas"}'), says("x"))

    lookup.converse(PERSONA, BASE, LOCAL, limits, used_tokens=990, call=call)

    assert call.sent[1]["messages"][-1]["content"] == lookup._NO_ROOM


def test_what_a_cloud_model_may_not_have_is_counted_not_dropped_silently():
    call = script(asks("search_notes", '{"query": "Atlas"}'), says("I can't use the notes."))

    done = lookup.converse(PERSONA, BASE, CLOUD, None, call=call)

    assert done.withheld.get("notes", 0) >= 1 and done.hits == []
    assert "/share" in call.sent[1]["messages"][-1]["content"]


def test_the_same_search_made_twice_is_recorded_once():
    call = script(
        asks("search_notes", '{"query": "Atlas"}', "1"), asks("search_notes", '{"query": "Atlas"}', "2"), says("ok")
    )

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    assert len(done.lookups) == 2 and len(done.hits) == len({(h["rel_path"], h["heading"], h["kind"]) for h in done.hits})
    assert len(done.hits) == len(lookup_tools.search_notes(PERSONA, LOCAL, "Atlas").hits)


def test_what_is_held_back_from_a_cloud_model_adds_up_over_the_lookups():
    one = lookup_tools.search_notes(PERSONA, CLOUD, "Atlas").withheld["notes"]
    call = script(
        asks("search_notes", '{"query": "Atlas"}', "1"), asks("search_notes", '{"query": "Atlas"}', "2"), says("ok")
    )

    done = lookup.converse(PERSONA, BASE, CLOUD, None, call=call)

    assert done.withheld["notes"] == 2 * one


def test_a_second_result_is_fitted_to_what_the_first_left_of_the_window(tmp_path):
    (tmp_path / "vault" / "Long.md").write_text("word " * 300)
    limits = budget.Budget(prompt_tokens=700, num_ctx=None, reply_cap=None)
    call = script(asks("open_note", '{"path": "Long"}', "1"), asks("open_note", '{"path": "Long"}', "2"), says("x"))

    done = lookup.converse(PERSONA, BASE, LOCAL, limits, used_tokens=100, call=call)

    first, second = (m["content"] for m in call.sent[2]["messages"] if m["role"] == "tool")
    assert "did not fit" not in first and "did not fit" in second
    assert done.tokens_added > 0


# -- what a running Ollama says about a local model --


class _Answer:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        return self.body


def ollama_answers(monkeypatch, capabilities, calls=None):
    """A running Ollama that lists `capabilities` (`None`: an older one that lists none) for any model."""

    def fake(request, timeout):
        if calls is not None:
            calls.append((request.full_url, request.data, timeout))
        return _Answer(json.dumps({} if capabilities is None else {"capabilities": capabilities}).encode())

    monkeypatch.setattr(tool_support, "urlopen", fake)


def test_a_local_model_takes_tools_when_the_running_ollama_lists_them(monkeypatch):
    ollama_answers(monkeypatch, ["completion", "tools"])
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: False)  # the table lags

    assert tool_support.can_call_tools("ollama_chat/some-new-model:9b") is True


def test_a_local_model_that_does_not_list_tools_cannot_call_them_whatever_the_table_says(monkeypatch):
    ollama_answers(monkeypatch, ["completion"])
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    assert tool_support.can_call_tools(LOCAL) is False


def test_ollama_is_asked_for_the_models_name_without_the_prefix_and_only_once(monkeypatch):
    calls: list = []
    ollama_answers(monkeypatch, ["tools"], calls)

    tool_support.can_call_tools("ollama_chat/qwen3:8b")
    tool_support.can_call_tools("ollama_chat/qwen3:8b")

    assert len(calls) == 1
    url, body, timeout = calls[0]
    assert url == "http://localhost:11434/api/show" and json.loads(body) == {"model": "qwen3:8b"} and 0 < timeout <= 5


def test_ollama_is_asked_where_the_user_says_it_runs(monkeypatch):
    calls: list = []
    ollama_answers(monkeypatch, ["tools"], calls)
    monkeypatch.setenv("OLLAMA_API_BASE", "http://box:9999/")

    tool_support.can_call_tools("ollama_chat/qwen3:8b")

    assert calls[0][0] == "http://box:9999/api/show"


@pytest.mark.parametrize("capabilities", [None, "tools", {"tools": True}])
def test_an_ollama_that_lists_no_capabilities_leaves_the_question_to_litellms_table(monkeypatch, capabilities):
    ollama_answers(monkeypatch, capabilities)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    assert tool_support.can_call_tools(LOCAL) is True


def test_an_ollama_that_is_not_running_leaves_the_question_to_litellms_table(monkeypatch):
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == "ollama_chat/qwen3:8b")

    assert tool_support.can_call_tools("ollama_chat/qwen3:8b") is True and tool_support.can_call_tools(LOCAL) is False


def test_a_cloud_model_is_never_put_to_ollama(monkeypatch):
    calls: list = []
    ollama_answers(monkeypatch, [], calls)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: True)

    assert tool_support.can_call_tools(CLOUD) is True and calls == []


# -- sizing what the tools return (docs/decisions/040) --


def per_character(monkeypatch):
    """A counter for a script that takes a token a character (the fixed ratio a cut used to assume is wrong for it)."""
    monkeypatch.setattr(lookup, "_tokens", lambda text, model: len(text))


def test_a_result_is_cut_until_it_fits_by_the_models_own_count_not_by_a_fixed_ratio(monkeypatch):
    per_character(monkeypatch)

    cut = lookup._fit("x" * 5000, LOCAL, 500)

    assert len(cut) <= 500 and cut.endswith(lookup._CUT)


def test_a_result_with_less_room_than_a_useful_cut_is_replaced_by_a_line_saying_so():
    assert lookup._fit("x" * 5000, LOCAL, lookup._MIN_ROOM_TOKENS - 1) == lookup._NO_ROOM
    assert lookup._fit("x" * 5000, LOCAL, -50) == lookup._NO_ROOM


def test_notes_the_model_was_not_shown_for_want_of_room_are_not_recorded_as_having_grounded_the_reply():
    limits = budget.Budget(prompt_tokens=1000, num_ctx=None, reply_cap=None)
    call = script(asks("search_notes", '{"query": "Atlas"}'), says("x"))

    done = lookup.converse(PERSONA, BASE, LOCAL, limits, used_tokens=990, call=call)

    assert done.hits == [] and done.lookups == [{"tool": "search_notes", "query": "Atlas", "found": 0, "no_room": True}]
    assert call.sent[1]["messages"][-1]["content"] == lookup._NO_ROOM


def test_a_model_with_no_known_window_is_still_given_a_bounded_amount_of_results(tmp_path):
    (tmp_path / "vault" / "Long.md").write_text("word " * 2400)  # about 12000 characters: cut by the note's own limit
    both = ModelReply("", None, tool_calls=(
        ToolCall("a", "open_note", '{"path": "Long"}'), ToolCall("b", "open_note", '{"path": "Long"}'),
    ))
    call = script(both, both, both, says("x"))

    lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    results = [m["content"] for m in call.sent[-1]["messages"] if m["role"] == "tool"]
    assert lookup._NO_ROOM in results or any("did not fit" in r for r in results)
    assert sum(lookup._tokens(r, LOCAL) for r in results) <= lookup._UNKNOWN_WINDOW_TOKENS + 200


def test_the_tool_calls_the_model_made_count_against_the_window_as_well_as_their_results(monkeypatch):
    per_character(monkeypatch)
    call = script(asks("search_notes", '{"query": "Atlas"}', "c1", text="Let me look."), says("x"))

    done = lookup.converse(PERSONA, BASE, LOCAL, None, call=call)

    asked = call.sent[1]["messages"][-2]
    result = call.sent[1]["messages"][-1]["content"]
    assert done.tokens_added == len(json.dumps(asked["tool_calls"]) + "Let me look.") + len(result)


def test_a_cut_that_still_does_not_fit_is_cut_again(monkeypatch):
    monkeypatch.setattr(lookup, "_tokens", lambda text, model: len(text) + 100)  # every message carries a fixed overhead

    cut = lookup._fit("x" * 5000, LOCAL, 500)

    assert len(cut) + 100 <= 500 and cut.endswith(lookup._CUT)
