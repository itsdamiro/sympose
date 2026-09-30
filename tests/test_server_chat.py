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


def test_a_cloud_model_is_refused_before_anything_is_sent(client, monkeypatch):
    calls = model_says(monkeypatch)
    response = client.post("/api/chat/turn", json={"message": "hi", "persona": "cloudy"})
    assert response.status_code == 409 and response.json()["detail"] == ch.CLOUD_NOT_AVAILABLE
    assert calls == []


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
