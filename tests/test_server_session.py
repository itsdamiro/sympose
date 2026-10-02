"""The web chat's list of past conversations (docs/decisions/057): `GET /api/chat/sessions`, and `PATCH` and
`DELETE` on one conversation."""

import json
import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import server_chat_handlers as ch
from sympose.engine import session, turn_cancel
from sympose.server import create_app

A, B = "20261001T100000-aaaaaaaa", "20261001T110000-bbbbbbbb"
T1, T2 = "2026-10-01T10:00:00+00:00", "2026-10-01T11:00:00+00:00"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(ch.recap_refresh, "refresh_in_background", lambda handle, model=None: True)
    yield
    for sid in (A, B):
        turn_cancel.finish("samantha", sid)


@pytest.fixture
def client():
    return TestClient(create_app())


def write(sid, stamp, title="hello there"):
    path = session.session_path("samantha", sid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    meta = {"type": "meta", "session_id": sid, "handle": "samantha", "title": title, "created_at": stamp, "updated_at": stamp}
    turn = {"type": "turn", "timestamp": stamp, "user": "hi", "assistant": "hello"}
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n" + json.dumps(turn) + "\n")


def test_the_list_gives_the_conversations_newest_first(client):
    write(A, T1, title="first")
    write(B, T2, title="second")

    body = client.get("/api/chat/sessions", params={"persona": "samantha"}).json()

    assert [row["id"] for row in body["sessions"]] == [B, A]
    assert body["sessions"][0] == {
        "id": B, "title": "second", "turns": 1, "created_at": T2, "updated_at": T2, "pinned_at": None, "replying": False,
    }


def test_the_list_of_a_persona_with_none_is_empty(client):
    assert client.get("/api/chat/sessions", params={"persona": "samantha"}).json() == {"sessions": []}


def test_an_unknown_persona_is_404_on_every_route(client):
    assert client.get("/api/chat/sessions", params={"persona": "nobody"}).status_code == 404
    assert client.patch(f"/api/chat/session/{A}", json={"persona": "nobody", "title": "x"}).status_code == 404
    assert client.delete(f"/api/chat/session/{A}", params={"persona": "nobody"}).status_code == 404


def test_a_rename_comes_back_as_the_row_and_shows_in_the_list(client):
    write(A, T1)

    row = client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "title": "Garden plans"}).json()

    assert row["title"] == "Garden plans" and row["id"] == A
    assert client.get("/api/chat/sessions", params={"persona": "samantha"}).json()["sessions"][0]["title"] == "Garden plans"


def test_a_pin_puts_the_conversation_first_and_an_unpin_puts_it_back(client):
    write(A, T1)
    write(B, T2)

    pinned = client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "pinned": True}).json()
    first = client.get("/api/chat/sessions", params={"persona": "samantha"}).json()["sessions"][0]
    client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "pinned": False})
    after = client.get("/api/chat/sessions", params={"persona": "samantha"}).json()["sessions"][0]

    assert pinned["pinned_at"] and first["id"] == A and after["id"] == B


def test_a_title_and_a_pin_can_come_in_one_request(client):
    write(A, T1)

    row = client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "title": "x", "pinned": True}).json()

    assert row["title"] == "x" and row["pinned_at"]


def test_a_bad_title_is_422_and_changes_nothing(client):
    write(A, T1, title="keep me")

    assert client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "title": "  "}).status_code == 422
    assert client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "title": "x" * 81}).status_code == 422
    assert client.get("/api/chat/sessions", params={"persona": "samantha"}).json()["sessions"][0]["title"] == "keep me"


def test_a_conversation_that_is_not_there_is_404(client):
    assert client.patch(f"/api/chat/session/{A}", json={"persona": "samantha", "title": "x"}).status_code == 404
    assert client.delete(f"/api/chat/session/{A}", params={"persona": "samantha"}).status_code == 404


def test_a_delete_takes_the_conversation_out_of_the_list_and_keeps_its_file(client, tmp_path):
    write(A, T1)

    response = client.delete(f"/api/chat/session/{A}", params={"persona": "samantha"})

    assert response.json() == {"deleted": A}
    assert client.get("/api/chat/sessions", params={"persona": "samantha"}).json() == {"sessions": []}
    assert (tmp_path / "profiles" / "samantha" / "sessions" / ".trash" / f"{A}.jsonl").exists()


def test_a_delete_is_409_while_a_reply_is_being_written_into_it(client):
    write(A, T1)
    turn_cancel.begin("samantha", A)

    assert client.delete(f"/api/chat/session/{A}", params={"persona": "samantha"}).status_code == 409
    assert client.get("/api/chat/sessions", params={"persona": "samantha"}).json()["sessions"][0]["replying"] is True
