"""Stopping a reply in flight (docs/decisions/054): the registry, the model call, the tool loop and a whole
turn, which must leave nothing behind."""

import threading
from types import SimpleNamespace

import pytest
from helpers import write_persona

from sympose.engine import followup, lookup, lookup_tools, model, session, turn, turn_cancel, turn_status
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.model_tools import ToolCall


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    for handle in ("samantha", "aria"):
        turn_cancel.finish(handle)


class TestRegistry:
    def test_a_request_with_no_turn_running_is_refused_and_does_not_linger(self):
        assert turn_cancel.request("samantha") is False
        turn_cancel.begin("samantha")  # the next turn starts clean: the late request left nothing behind
        turn_cancel.check()

    def test_a_request_stops_the_running_turn_at_its_next_check(self):
        turn_cancel.begin("samantha")
        turn_cancel.check()  # nothing asked yet
        assert turn_cancel.request("samantha") is True
        with pytest.raises(turn_cancel.TurnCancelled):
            turn_cancel.check()

    def test_a_request_is_for_one_persona_only(self):
        turn_cancel.begin("samantha")
        turn_cancel.begin("aria")  # this thread now runs aria's turn
        turn_cancel.request("samantha")
        turn_cancel.check()  # aria's turn is unaffected

    def test_finishing_a_turn_clears_its_request(self):
        turn_cancel.begin("samantha")
        turn_cancel.request("samantha")
        turn_cancel.finish("samantha")
        turn_cancel.begin("samantha")
        turn_cancel.check()

    def test_a_thread_that_runs_no_turn_is_never_stopped(self):
        turn_cancel.begin("samantha")
        turn_cancel.request("samantha")
        errors: list[BaseException] = []

        def background_job():  # a recap or memory refresh calling the model on its own thread
            try:
                turn_cancel.check()
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        t = threading.Thread(target=background_job)
        t.start()
        t.join()
        assert errors == []

    def test_a_thread_whose_turn_is_over_is_not_stopped_by_a_later_turn_of_the_same_persona(self):
        turn_cancel.begin("samantha")  # a pool thread runs a turn, finishes it, and is reused for a background job
        turn_cancel.finish("samantha")

        def next_turn_somewhere_else():
            turn_cancel.begin("samantha")
            turn_cancel.request("samantha")

        t = threading.Thread(target=next_turn_somewhere_else)
        t.start()
        t.join()
        turn_cancel.check()  # this thread runs no turn now

    def test_a_stop_after_the_last_check_is_refused_because_the_reply_is_coming(self):
        turn_cancel.begin("samantha")
        turn_cancel.commit()
        assert turn_cancel.request("samantha") is False
        turn_cancel.check()  # and it does not stop what is left of the turn

    def test_a_stop_accepted_before_the_last_check_wins_it(self):
        turn_cancel.begin("samantha")
        assert turn_cancel.request("samantha") is True
        with pytest.raises(turn_cancel.TurnCancelled):
            turn_cancel.commit()
        assert turn_cancel.request("samantha") is True  # still a running turn that is being stopped

    def test_committing_does_not_carry_over_to_the_next_turn(self):
        turn_cancel.begin("samantha")
        turn_cancel.commit()
        turn_cancel.finish("samantha")
        turn_cancel.begin("samantha")
        assert turn_cancel.request("samantha") is True

    def test_cancelled_is_not_a_model_failure(self):
        assert not issubclass(turn_cancel.TurnCancelled, EngineModelError)


def _chunk(content=None, finish=None):
    delta = SimpleNamespace(content=content, reasoning_content=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


class Stream:
    """A provider stream that can be closed, and that runs `on_chunk(n)` as each chunk is handed out."""

    def __init__(self, texts, on_chunk=None):
        self.texts, self.on_chunk, self.closed, self.handed = texts, on_chunk, False, 0

    def __iter__(self):
        for text in self.texts:
            self.handed += 1
            if self.on_chunk:
                self.on_chunk(self.handed)
            yield _chunk(text)
        yield _chunk(None, finish="stop")

    def close(self):
        self.closed = True


class TestCallModel:
    @pytest.fixture(autouse=True)
    def settings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))

    def test_a_stop_between_chunks_ends_the_call_and_closes_the_stream(self, monkeypatch):
        turn_cancel.begin("samantha")
        stream = Stream(["a ", "b ", "c "], on_chunk=lambda n: turn_cancel.request("samantha") if n == 2 else None)
        monkeypatch.setattr(model.litellm, "completion", lambda **_: stream)
        with pytest.raises(turn_cancel.TurnCancelled):
            model.call_model([{"role": "user", "content": "hi"}])
        assert stream.handed == 2  # never read on to the third chunk
        assert stream.closed

    def test_a_call_that_is_not_stopped_is_unchanged(self, monkeypatch):
        turn_cancel.begin("samantha")
        stream = Stream(["hello ", "there"])
        monkeypatch.setattr(model.litellm, "completion", lambda **_: stream)
        assert model.call_model([{"role": "user", "content": "hi"}]).text == "hello there"
        assert stream.closed  # a finished stream is closed too, harmlessly

    def test_a_real_failure_is_still_a_model_error(self, monkeypatch):
        def boom(**_):
            raise RuntimeError("down")

        monkeypatch.setattr(model.litellm, "completion", boom)
        with pytest.raises(EngineModelError):
            model.call_model([{"role": "user", "content": "hi"}])


class TestToolLoop:
    def test_a_stop_before_a_tool_runs_ends_the_turn_without_running_it(self):
        ran: list[str] = []
        turn_cancel.begin("samantha")

        def call(messages, **_):
            turn_cancel.request("samantha")  # stopped while the model was answering
            return ModelReply("", None, tool_calls=(ToolCall("c1", "remember", '{"text": "x"}'),))

        def run_tool(persona, mdl, name, raw):
            ran.append(name)
            return lookup_tools.Result("Remembered.", lookup={"tool": name})

        persona = {"handle": "samantha"}
        with pytest.raises(turn_cancel.TurnCancelled):
            lookup.converse(persona, [], "ollama_chat/x", None, call=call, tools=[], run_tool=run_tool)
        assert ran == []


class TestWholeTurn:
    @pytest.fixture(autouse=True)
    def profiles(self, tmp_path, monkeypatch):
        base = tmp_path / "profiles"
        write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
        monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
        monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
        monkeypatch.setattr(turn.budget, "_native_max", lambda m: None)
        monkeypatch.setattr(followup, "enabled", lambda: False)

    def test_a_stopped_turn_saves_nothing_and_leaves_no_state(self, monkeypatch):
        def call_model(messages, model=None, **_):
            turn_cancel.request("samantha")  # the stop arrives while the model is still answering
            return ModelReply("a reply nobody will read", 5)

        monkeypatch.setattr(turn.model_mod, "call_model", call_model)
        with pytest.raises(turn_cancel.TurnCancelled):
            turn.run_turn("samantha", "hello", "sid-1")
        assert session.load_session("samantha", "sid-1") is None  # the message is not in the conversation
        assert turn_status.phase("samantha") is None
        assert turn_cancel.request("samantha") is False  # the turn is over: a late click finds nothing

    def test_a_stop_that_comes_with_the_finished_reply_is_refused_and_the_turn_is_saved(self, monkeypatch):
        monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("reply", 5))
        real_append = turn.session.append_turn

        def append_turn(*args, **kwargs):
            assert turn_cancel.request("samantha") is False  # past the point where a stop can still be accepted
            return real_append(*args, **kwargs)

        monkeypatch.setattr(turn.session, "append_turn", append_turn)
        assert turn.run_turn("samantha", "hello", "sid-3").saved

    def test_the_next_turn_after_a_stopped_one_runs_and_saves(self, monkeypatch):
        calls = iter([True, False])

        def call_model(messages, model=None, **_):
            if next(calls):
                turn_cancel.request("samantha")
            return ModelReply("reply", 5)

        monkeypatch.setattr(turn.model_mod, "call_model", call_model)
        with pytest.raises(turn_cancel.TurnCancelled):
            turn.run_turn("samantha", "first", "sid-2")
        result = turn.run_turn("samantha", "second", "sid-2")
        assert result.reply == "reply"
        assert [t["user"] for t in session.load_session("samantha", "sid-2")["turns"]] == ["second"]

    def test_the_engine_exports_the_stop(self):
        from sympose import engine

        assert engine.cancel_turn is turn_cancel.request and engine.TurnCancelled is turn_cancel.TurnCancelled
