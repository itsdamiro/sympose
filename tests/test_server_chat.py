"""The web chat's routes (docs/decisions/044): a thin door to `run_turn`, local models only for now,
one turn at a time per persona, and the live phase of the reply in flight."""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import server_chat_handlers as ch
from sympose.engine import grounding, session, turn, turn_status
from sympose.engine.model import EngineModelError, ModelReply
from sympose.server import create_app
from sympose.server_models import ChatTurn


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    write_persona(
        base, "cloudy", "name: Cloudy\nvault_folders: '*'\nsympose_reference: false\nmodel: gemini/gemini-flash-latest\n"
    )
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(ch, "_LOCKS", {})


@pytest.fixture
def client():
    return TestClient(create_app())


def model_says(monkeypatch, text="Hello from her."):
    calls = []

    def call_model(messages, model=None, **_):
        calls.append(model)
        return ModelReply(text, 12)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return calls


def test_a_message_gets_the_persona_reply_and_a_session(client, monkeypatch):
    model_says(monkeypatch)
    body = client.post("/api/chat/turn", json={"message": "hi", "persona": "samantha"}).json()
    assert body["reply"] == "Hello from her."
    assert body["session_id"] and body["saved"] is True and body["cloud"] == []


def test_the_session_id_continues_the_same_conversation(client, monkeypatch):
    model_says(monkeypatch)
    first = client.post("/api/chat/turn", json={"message": "hi", "persona": "samantha"}).json()
    second = client.post(
        "/api/chat/turn", json={"message": "and again", "persona": "samantha", "session_id": first["session_id"]}
    ).json()
    assert second["session_id"] == first["session_id"]
    assert len(session.load_session("samantha", first["session_id"])["turns"]) == 2


def test_an_unknown_persona_is_404(client):
    assert client.post("/api/chat/turn", json={"message": "hi", "persona": "nobody"}).status_code == 404


def test_an_empty_message_is_refused(client):
    assert client.post("/api/chat/turn", json={"message": "", "persona": "samantha"}).status_code == 422


def test_a_cloud_model_is_chatted_with_and_the_turn_says_what_was_held_back(client, monkeypatch):
    """The notice and switches are on screen before a message is written (docs/decisions/044), so the guard
    is gone; nothing of the vault is sent that the user has not approved, and the reply says so."""
    calls = model_says(monkeypatch)
    note = {"rel_path": "Atlas.md", "title": "Atlas", "heading": "Atlas", "text": "We use SQLite.", "kind": "text"}
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [note])
    response = client.post("/api/chat/turn", json={"message": "hi", "persona": "cloudy"})
    body = response.json()
    assert response.status_code == 200 and calls == ["gemini/gemini-flash-latest"]
    assert body["cloud"] == [] and body["withheld"] == ["notes"]
    assert body["sent"]["withheld"] == ["notes"]


def test_a_model_failure_is_a_502_with_its_message(client, monkeypatch):
    def failing(messages, model=None, **_):
        raise EngineModelError("the model is not running")

    monkeypatch.setattr(turn.model_mod, "call_model", failing)
    response = client.post("/api/chat/turn", json={"message": "hi", "persona": "samantha"})
    assert response.status_code == 502 and "not running" in response.json()["detail"]


def test_status_reports_the_phase_of_the_reply_in_flight(client):
    assert client.get("/api/chat/status", params={"persona": "samantha"}).json() == {"phase": None, "indexing": None}
    turn_status.set_phase("samantha", turn_status.SEARCHING)
    try:
        assert client.get("/api/chat/status", params={"persona": "samantha"}).json() == {"phase": "searching", "indexing": None}
    finally:
        turn_status.set_phase("samantha", None)


def test_status_reports_the_index_build_percent_while_one_runs(client, monkeypatch):
    from sympose.engine import semantic_refresh

    monkeypatch.setattr(semantic_refresh, "progress", lambda: 40)
    assert client.get("/api/chat/status", params={"persona": "samantha"}).json()["indexing"] == 40


def test_status_for_an_unknown_persona_is_404(client):
    assert client.get("/api/chat/status", params={"persona": "nobody"}).status_code == 404


def test_two_messages_for_one_persona_run_one_at_a_time(monkeypatch):
    running, most = 0, 0
    guard = threading.Lock()

    def call_model(messages, model=None, **_):
        nonlocal running, most
        with guard:
            running += 1
            most = max(most, running)
        time.sleep(0.05)
        with guard:
            running -= 1
        return ModelReply("ok", 1)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    threads = [threading.Thread(target=ch.send_turn, args=(ChatTurn(message="hi", persona="samantha"),)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert most == 1


# -- resuming a conversation, a section at a time ----------------------------------------------------


def seed(sid, count, handle="samantha"):
    for n in range(count):
        session.append_turn(handle, sid, f"question {n}", f"answer {n}")


def page(client, **params):
    return client.get("/api/chat/session", params={"persona": "samantha", **params}).json()


def test_no_conversation_yet_is_an_empty_page(client):
    assert page(client) == {"session_id": None, "turns": [], "start": 0, "total": 0, "has_more": False}


def test_the_latest_conversation_comes_back_as_its_last_turns(client):
    seed("20260930T090000-aaaaaaaa", 2)
    seed("20260930T100000-bbbbbbbb", 5)
    body = page(client, limit=3)
    assert body["session_id"] == "20260930T100000-bbbbbbbb"
    assert [t["index"] for t in body["turns"]] == [2, 3, 4]
    assert body["turns"][-1]["user"] == "question 4" and body["turns"][-1]["assistant"] == "answer 4"
    assert (body["start"], body["total"], body["has_more"]) == (2, 5, True)


def test_older_turns_come_from_the_turn_before_the_one_given(client):
    seed("20260930T100000-bbbbbbbb", 5)
    first = page(client, limit=3)
    older = page(client, limit=3, before=first["start"], session_id=first["session_id"])
    assert [t["index"] for t in older["turns"]] == [0, 1]
    assert older["has_more"] is False


def test_a_whole_short_conversation_has_nothing_older(client):
    seed("20260930T100000-bbbbbbbb", 2)
    body = page(client, limit=20)
    assert [t["index"] for t in body["turns"]] == [0, 1] and body["has_more"] is False


def test_older_pages_stay_in_the_conversation_they_started_in(client):
    seed("20260930T100000-bbbbbbbb", 4)
    first = page(client, limit=2)
    seed("20260930T110000-cccccccc", 3)  # another conversation starts meanwhile
    older = page(client, limit=2, before=first["start"], session_id=first["session_id"])
    assert older["session_id"] == "20260930T100000-bbbbbbbb"
    assert [t["user"] for t in older["turns"]] == ["question 0", "question 1"]


def test_a_conversation_begun_on_purpose_and_left_blank_is_the_latest(client):
    seed("20260930T090000-aaaaaaaa", 2)
    session.start_session("samantha", "20260930T100000-bbbbbbbb")
    body = page(client)
    assert (body["session_id"], body["turns"], body["total"], body["has_more"]) == (
        "20260930T100000-bbbbbbbb", [], 0, False,
    )


def test_the_turns_carry_what_the_grounded_view_needs(client):
    session.append_turn("samantha", "20260930T100000-bbbbbbbb", "hi", "hello", ttft_ms=610, model="m", sent={"notes": []})
    turn_ = page(client)["turns"][0]
    assert (turn_["ttft_ms"], turn_["model"], turn_["sent"], turn_["truncated"]) == (610, "m", {"notes": []}, False)


def test_an_unknown_or_unsafe_session_id_is_404(client):
    for sid in ("20260930T100000-nothere", "../../etc/passwd"):
        response = client.get("/api/chat/session", params={"persona": "samantha", "session_id": sid})
        assert response.status_code == 404


def test_a_page_size_outside_its_bounds_is_refused(client):
    for limit in (0, 101):
        assert client.get("/api/chat/session", params={"persona": "samantha", "limit": limit}).status_code == 422


def test_resume_for_an_unknown_persona_is_404(client):
    assert client.get("/api/chat/session", params={"persona": "nobody"}).status_code == 404


# -- starting a fresh conversation ---------------------------------------------------------------------


def test_a_new_conversation_is_what_a_refresh_then_shows(client):
    seed("20260101T090000-aaaaaaaa", 3)
    started = client.post("/api/chat/session", json={"persona": "samantha"}).json()
    assert started["session_id"] != "20260101T090000-aaaaaaaa"
    assert page(client)["session_id"] == started["session_id"] and page(client)["turns"] == []


def test_pressing_new_conversation_twice_reuses_the_blank_one(client):
    seed("20260101T090000-aaaaaaaa", 1)
    first = client.post("/api/chat/session", json={"persona": "samantha"}).json()["session_id"]
    second = client.post("/api/chat/session", json={"persona": "samantha"}).json()["session_id"]
    assert first == second and len(session.session_ids("samantha")) == 2


def test_the_first_message_continues_the_blank_conversation_and_names_it(client, monkeypatch):
    model_says(monkeypatch)
    sid = client.post("/api/chat/session", json={"persona": "samantha"}).json()["session_id"]
    reply = client.post("/api/chat/turn", json={"message": "hello there friend", "persona": "samantha", "session_id": sid}).json()
    saved = session.load_session("samantha", sid)
    assert reply["session_id"] == sid and len(saved["turns"]) == 1
    assert saved["meta"]["title"] == "hello there friend"


def test_a_new_conversation_for_an_unknown_persona_is_404(client):
    assert client.post("/api/chat/session", json={"persona": "nobody"}).status_code == 404


# -- the busy line's phrases (docs/decisions/044, 043) -------------------------


class RunnerSpy:
    """Stands in for the one-generation-per-persona runner: records what is started, runs nothing."""

    def __init__(self):
        self.started = []

    def start(self, handle, job):
        self.started.append(handle)
        return True

    def is_running(self, handle):
        return False


@pytest.fixture
def runner(monkeypatch):
    spy = RunnerSpy()
    monkeypatch.setattr(ch.status_phrases, "_RUNNER", spy)
    return spy


def test_status_phrases_are_the_personas_own_when_it_has_them_and_nothing_is_generated(client, tmp_path, runner):
    (tmp_path / "profiles" / "samantha" / "status_phrases.md").write_text("Humming along…\nChasing a thread…\n", encoding="utf-8")
    body = client.get("/api/chat/status-phrases", params={"persona": "samantha"}).json()
    assert body == {"phrases": ["Humming along…", "Chasing a thread…"], "own": True}
    assert runner.started == []


def test_a_persona_with_none_of_its_own_gets_the_generic_ones_and_generation_starts(client, runner):
    body = client.get("/api/chat/status-phrases", params={"persona": "samantha"}).json()
    assert body == {"phrases": ch.status_phrases.FALLBACK, "own": False}
    assert runner.started == ["samantha"]


def test_reading_the_phrases_again_asks_the_runner_again_and_the_runner_deduplicates(client, runner):
    client.get("/api/chat/status-phrases", params={"persona": "samantha"})
    client.get("/api/chat/status-phrases", params={"persona": "samantha"})
    assert runner.started == ["samantha", "samantha"]  # `Runner.start` itself declines a second run in flight


def test_status_phrases_for_an_unknown_persona_is_404_and_starts_nothing(client, runner):
    assert client.get("/api/chat/status-phrases", params={"persona": "nobody"}).status_code == 404
    assert runner.started == []


# -- the context meter's estimate (docs/decisions/044, 018) --------------------


def test_the_estimate_is_the_engines_for_the_personas_current_model(client, monkeypatch):
    seen = []
    monkeypatch.setattr(ch.context_estimate, "estimate", lambda handle, session_id, model: seen.append((handle, session_id, model)) or (3812, 6144))
    body = client.get("/api/chat/context", params={"persona": "samantha", "session_id": "s1"}).json()
    assert body == {"used": 3812, "limit": 6144}
    assert seen == [("samantha", "s1", "ollama_chat/gemma2:9b")]


def test_the_estimate_uses_the_model_the_persona_runs_on(client, monkeypatch):
    seen = []
    monkeypatch.setattr(ch.context_estimate, "estimate", lambda handle, session_id, model: seen.append((handle, model)) or (10, 100))
    client.get("/api/chat/context", params={"persona": "cloudy", "session_id": "s1"})
    assert seen == [("cloudy", "gemini/gemini-flash-latest")]  # that persona, and the model it runs on


def test_no_estimate_when_there_is_nothing_to_count(client, monkeypatch):
    monkeypatch.setattr(ch.context_estimate, "estimate", lambda handle, session_id, model: None)
    assert client.get("/api/chat/context", params={"persona": "samantha", "session_id": "s1"}).json() == {"used": None, "limit": None}


def test_no_estimate_without_a_session_and_an_unknown_persona_or_session_is_handled(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ch.context_estimate, "estimate", lambda handle, session_id, model: calls.append(session_id) or None)
    assert client.get("/api/chat/context", params={"persona": "samantha"}).json() == {"used": None, "limit": None}
    assert client.get("/api/chat/context", params={"persona": "nobody", "session_id": "s1"}).status_code == 404
    assert calls == [None]  # the engine is asked with no session (it answers None); never for an unknown persona


def test_a_real_estimate_from_a_saved_conversation(client, monkeypatch):
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: 8192)  # the module the estimate counts against too
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("A reply.", 5))
    first = client.post("/api/chat/turn", json={"message": "hello there", "persona": "samantha"}).json()
    body = client.get("/api/chat/context", params={"persona": "samantha", "session_id": first["session_id"]}).json()
    assert body["used"] and body["limit"] and 0 < body["used"] < body["limit"]


def test_stopping_a_reply_in_flight_answers_cancelled_and_saves_nothing(client, monkeypatch):
    """The turn is running when the stop arrives (`/api/chat/cancel`); its own request then answers
    `{"cancelled": true}` instead of a reply, and the conversation file does not exist (docs/decisions/054)."""
    from sympose.engine import turn_cancel

    running = threading.Event()

    def call_model(messages, model=None, **_):
        running.set()
        for _ in range(200):  # the model's chunks, each a chance for the stop to be heard
            time.sleep(0.01)
            turn_cancel.check()
        return ModelReply("too late", 1)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    answers: list = []
    t = threading.Thread(
        target=lambda: answers.append(
            client.post("/api/chat/turn", json={"message": "hi", "persona": "samantha", "session_id": "stopme"})
        )
    )
    t.start()
    assert running.wait(5)
    assert client.post("/api/chat/cancel", json={"persona": "samantha"}).json() == {"stopping": True}
    t.join(5)
    assert not t.is_alive()
    assert answers[0].status_code == 200 and answers[0].json() == {"cancelled": True}
    assert session.load_session("samantha", "stopme") is None


def test_stopping_when_nothing_is_running_says_so_and_does_not_affect_the_next_reply(client, monkeypatch):
    assert client.post("/api/chat/cancel", json={"persona": "samantha"}).json() == {"stopping": False}
    model_says(monkeypatch)
    assert client.post("/api/chat/turn", json={"message": "hi", "persona": "samantha"}).json()["reply"] == "Hello from her."


def test_stopping_an_unknown_persona_is_404(client):
    assert client.post("/api/chat/cancel", json={"persona": "nobody"}).status_code == 404
