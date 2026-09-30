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
    assert client.get("/api/chat/status", params={"persona": "samantha"}).json() == {"phase": None}
    turn_status.set_phase("samantha", turn_status.SEARCHING)
    try:
        assert client.get("/api/chat/status", params={"persona": "samantha"}).json() == {"phase": "searching"}
    finally:
        turn_status.set_phase("samantha", None)


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
