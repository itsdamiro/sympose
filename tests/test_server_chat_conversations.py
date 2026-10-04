"""Two conversations of one persona replying (docs/decisions/057): the locks, `parallel_replies`, a message that
waits for its turn and stopping it, and the status and Stop of one conversation."""

import threading

import pytest
from helpers import write_persona

from sympose import server_chat_handlers as ch
from sympose import server_chat_locks as chat_locks
from sympose import settings_store
from sympose.engine import parallel, turn
from sympose.engine.turn_cancel import finish
from sympose.server_models import ChatCancel, ChatTurn

A, B = "20261001T100000-aaaaaaaa", "20261001T110000-bbbbbbbb"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "local", "name: Local\nvault_folders: '*'\nsympose_reference: false\nmodel: ollama_chat/gemma2:9b\n")
    write_persona(base, "cloud", "name: Cloud\nvault_folders: '*'\nsympose_reference: false\nmodel: gemini/gemini-flash-latest\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(chat_locks, "_LOCKS", {})
    monkeypatch.setattr(chat_locks, "_POLL_SECONDS", 0.01)
    yield
    for persona in ("local", "cloud"):
        for sid in (A, B):
            finish(persona, sid)


class Replies:
    """A stand-in for `run_turn`: each call records that it started, then waits to be let go."""

    def __init__(self, monkeypatch):
        self.started: list[str] = []
        self.release = {A: threading.Event(), B: threading.Event()}
        self.began = {A: threading.Event(), B: threading.Event()}
        monkeypatch.setattr(turn, "run_turn", self.run)
        monkeypatch.setattr(ch.turn, "run_turn", self.run)

    def run(self, handle, message, session_id=None, model=None, **_):
        self.started.append(f"{session_id}:{message}")
        self.began[session_id].set()
        self.release[session_id].wait(5)
        return turn.TurnResult(reply=f"re: {message}", session_id=session_id, ttft_ms=1, model="m")


def send(persona, session_id, message="hi"):
    out = {}

    def go():
        out["body"] = ch.send_turn(ChatTurn(persona=persona, session_id=session_id, message=message))

    thread = threading.Thread(target=go)
    thread.start()
    return thread, out


def settle(thread):
    thread.join(5)
    assert not thread.is_alive()


@pytest.fixture
def replies(monkeypatch):
    return Replies(monkeypatch)


def test_a_local_model_runs_the_second_conversation_after_the_first(replies):
    first, _ = send("local", A)
    assert replies.began[A].wait(5)
    second, out = send("local", B)
    assert not replies.began[B].wait(0.3)  # waiting for the first
    replies.release[A].set()
    assert replies.began[B].wait(5)
    replies.release[B].set()
    settle(first)
    settle(second)
    assert out["body"]["reply"] == "re: hi"


def test_a_cloud_model_runs_both_side_by_side(replies):
    first, _ = send("cloud", A)
    assert replies.began[A].wait(5)
    second, _ = send("cloud", B)
    assert replies.began[B].wait(5)  # did not wait
    replies.release[A].set()
    replies.release[B].set()
    settle(first)
    settle(second)


def test_on_runs_a_local_model_side_by_side_and_off_holds_a_cloud_one_back(replies):
    settings_store.set(parallel.SETTING, "on")
    first, _ = send("local", A)
    assert replies.began[A].wait(5)
    second, _ = send("local", B)
    assert replies.began[B].wait(5)
    replies.release[A].set()
    replies.release[B].set()
    settle(first)
    settle(second)

    settings_store.set(parallel.SETTING, "off")
    replies.began[A].clear()
    replies.began[B].clear()
    replies.release[A].clear()
    replies.release[B].clear()
    third, _ = send("cloud", A)
    assert replies.began[A].wait(5)
    fourth, _ = send("cloud", B)
    assert not replies.began[B].wait(0.3)
    replies.release[A].set()
    assert replies.began[B].wait(5)
    replies.release[B].set()
    settle(third)
    settle(fourth)


def test_two_messages_in_one_conversation_always_run_in_order_even_side_by_side(replies):
    first, _ = send("cloud", A, "one")
    assert replies.began[A].wait(5)
    second, _ = send("cloud", A, "two")
    threading.Event().wait(0.3)
    assert replies.started == [f"{A}:one"]
    replies.release[A].set()
    settle(first)
    settle(second)
    assert replies.started == [f"{A}:one", f"{A}:two"]


def test_a_waiting_message_says_queued_and_the_one_running_does_not(replies):
    first, _ = send("local", A)
    assert replies.began[A].wait(5)
    second, _ = send("local", B)
    threading.Event().wait(0.2)
    assert ch.get_status("local", B)["phase"] == "queued"
    assert ch.get_status("local", A)["phase"] is None
    replies.release[A].set()
    replies.release[B].set()
    settle(first)
    settle(second)
    assert ch.get_status("local", B)["phase"] is None


def test_stopping_a_waiting_message_is_accepted_and_it_never_runs(replies):
    first, _ = send("local", A)
    assert replies.began[A].wait(5)
    second, out = send("local", B, "never")
    threading.Event().wait(0.2)
    assert ch.cancel_turn(ChatCancel(persona="local", session_id=B)) == {"stopping": True}
    settle(second)
    assert out["body"] == {"cancelled": True}
    replies.release[A].set()
    settle(first)
    assert replies.started == [f"{A}:hi"]


def test_a_stop_with_nothing_running_or_waiting_is_refused(replies):
    assert ch.cancel_turn(ChatCancel(persona="local", session_id=B)) == {"stopping": False}
    assert ch.cancel_turn(ChatCancel(persona="local")) == {"stopping": False}


def test_a_stop_for_one_conversation_leaves_the_message_waiting_in_another(replies):
    first, _ = send("local", A)
    assert replies.began[A].wait(5)
    second, out = send("local", B)
    threading.Event().wait(0.2)
    ch.cancel_turn(ChatCancel(persona="local", session_id="some-other-conversation"))
    replies.release[A].set()
    assert replies.began[B].wait(5)
    replies.release[B].set()
    settle(first)
    settle(second)
    assert out["body"]["reply"] == "re: hi"


def test_a_stop_without_a_conversation_stops_every_waiting_message(replies):
    first, _ = send("local", A)
    assert replies.began[A].wait(5)
    second, out = send("local", B)
    threading.Event().wait(0.2)
    assert ch.cancel_turn(ChatCancel(persona="local"))["stopping"] is True
    settle(second)
    assert out["body"] == {"cancelled": True}
    replies.release[A].set()
    settle(first)


def test_a_stop_that_arrives_as_the_lock_is_freed_still_wins():
    """The stop was accepted, so the message must not run: the browser has already put it back in the box."""

    class FreedByTheStop:
        def __init__(self):
            self.held = False

        def acquire(self, timeout=None):
            ch.locks.stop_waiting("local", "a")  # the stop is accepted just before the lock is handed over
            self.held = True
            return True

        def release(self):
            self.held = False

    lock = FreedByTheStop()
    assert chat_locks.acquire(lock, "local", "a") is False
    assert lock.held is False  # and the lock was given back


def test_a_stop_for_a_first_reply_with_no_conversation_id_leaves_the_other_conversations_alone():
    """The web chat names no conversation for a first message; its stop must not end the replies of its others."""
    from sympose.engine import turn_cancel

    turn_cancel.begin("local", A)  # a conversation the browser named
    turn_cancel.begin("local", B, named=False)  # a first message: the engine made up its id
    assert ch.cancel_turn(ChatCancel(persona="local", unnamed=True)) == {"stopping": True}
    with pytest.raises(turn_cancel.TurnCancelled):
        turn_cancel.check()  # this thread runs B
    turn_cancel.begin("local", A)
    turn_cancel.check()  # A went on


def test_stopping_the_unnamed_waiting_message_leaves_a_named_one_waiting(monkeypatch):
    unnamed, named = threading.Event(), threading.Event()
    monkeypatch.setattr(chat_locks, "_WAITING", {("local", None): [unnamed], ("local", A): [named]})
    assert chat_locks.stop_waiting("local", None, unnamed=True) is True
    assert unnamed.is_set() and not named.is_set()
