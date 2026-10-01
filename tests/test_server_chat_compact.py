"""The web chat's side of compaction (docs/decisions/055): `POST /api/chat/compact`, the notes on a
conversation's page, and the count on a turn's answer."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import server_chat_handlers as ch
from sympose.engine import compaction, grounding, session, session_compaction, turn
from sympose.engine.model import EngineModelError, ModelReply
from sympose.server import create_app


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


@pytest.fixture(autouse=True)
def no_recaps(monkeypatch):
    """Opening a chat asks for recaps (ADR 023); a test here must not start a model call for them."""
    monkeypatch.setattr(ch.recap_refresh, "refresh_in_background", lambda handle, model=None: True)


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def notes_model(monkeypatch):
    calls = []

    class Fake(list):
        reply: object = ModelReply("The user is building Pantry.", 5)

    fake = Fake(calls)

    def call(messages, model=None, **limits):
        fake.append(model)
        if isinstance(fake.reply, Exception):
            raise fake.reply
        return fake.reply

    monkeypatch.setattr(compaction.model_mod, "call_model", call)
    return fake


def _chat(handle="samantha", sid="s1", turns=8):
    for i in range(turns):
        session.append_turn(handle, sid, f"question {i}", f"answer {i}")
    return sid


def _compact(client, persona="samantha", session_id="s1"):
    return client.post("/api/chat/compact", json={"persona": persona, "session_id": session_id})


def test_compact_writes_the_notes_and_answers_with_them(client, notes_model):
    _chat()
    body = _compact(client).json()
    assert body["status"] == "done" and body["covered"] == 5 and body["text"] == "The user is building Pantry."
    assert body["after"] < body["before"]
    assert session_compaction.notes(session.load_session("samantha", "s1")) == "The user is building Pantry."


def test_compact_uses_the_model_the_persona_runs_on(client, notes_model):
    _chat("cloudy")
    _compact(client, "cloudy")
    assert notes_model == ["gemini/gemini-flash-latest"]


@pytest.mark.parametrize(
    "setup,status",
    [("short", "nothing"), ("down", "failed")],
)
def test_compact_says_when_nothing_was_written(client, notes_model, setup, status):
    _chat(turns=2 if setup == "short" else 8)
    if setup == "down":
        notes_model.reply = EngineModelError("down")
    body = _compact(client).json()
    assert body["status"] == status and body["text"] == ""
    assert session.load_session("samantha", "s1")["compaction"] is None


def test_compact_with_nothing_more_to_fold_still_returns_the_notes_in_force(client, notes_model):
    _chat(turns=2)
    session_compaction.append("samantha", "s1", 1, "The user likes SQLite.", "m")
    body = _compact(client).json()
    assert body["status"] == "nothing" and body["text"] == "The user likes SQLite." and body["covered"] == 1


def test_compact_for_an_unknown_persona_or_session_is_404(client, notes_model):
    _chat()
    assert _compact(client, "nobody").status_code == 404
    assert _compact(client, session_id="no-such").status_code == 404
    assert _compact(client, session_id="../etc").status_code == 404
    assert notes_model == []


def test_compact_needs_a_session(client):
    assert client.post("/api/chat/compact", json={"persona": "samantha"}).status_code == 422


def test_a_conversation_page_carries_the_notes_and_what_they_stand_for(client):
    _chat()
    assert client.get("/api/chat/session", params={"persona": "samantha", "session_id": "s1"}).json()["compaction"] is None
    session_compaction.append("samantha", "s1", 5, "The user is building Pantry.", "m")
    page = client.get("/api/chat/session", params={"persona": "samantha", "session_id": "s1", "limit": 3}).json()
    assert page["compaction"] == {"through": 5, "text": "The user is building Pantry."}
    assert page["total"] == 8 and len(page["turns"]) == 3  # every turn is still there to be read


def test_a_turn_says_how_many_earlier_turns_the_notes_stood_for(client, monkeypatch):
    _chat()
    session_compaction.append("samantha", "s1", 5, "The user is building Pantry.", "m")
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("ok", 1))
    body = client.post("/api/chat/turn", json={"message": "next?", "persona": "samantha", "session_id": "s1"}).json()
    assert body["condensed"] == 5
