"""Archiving a conversation to a note (docs/decisions/086): `POST /api/chat/session/<id>/archive` through the real app on a
scratch vault and profiles folder. The model is a stub; what the real one writes is not checked here."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import note_changes
from sympose.engine import budget, session, turn_cancel
from sympose.engine import model as model_mod
from sympose.engine import session_archive as archive
from sympose.server import create_app

SID = "20261001T100000-aaaaaaaa"


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Projects").mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: ['Projects']\nsympose_reference: false\n")
    write_persona(profiles, "nowhere", "name: Nowhere\nvault_folders: []\nsympose_reference: false\n")
    write_persona(profiles, "everywhere", "name: Everywhere\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(budget, "_native_max", lambda model: 8192)
    return TestClient(create_app()), vault


class Asked(list):
    """The calls made to the model, and the replies it gives in turn (the last repeats)."""

    def __init__(self):
        super().__init__()
        self.replies: list = [model_mod.ModelReply("Atlas database choice\n\nThey planned the Atlas database.\n\n## Decided\n- SQLite first", 5)]


@pytest.fixture
def asked(monkeypatch):
    calls = Asked()

    def call_model(messages, model=None, **limits):
        calls.append({"messages": messages, "model": model, **limits})
        reply = calls.replies[min(len(calls), len(calls.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(archive.model_mod, "call_model", call_model)
    return calls


def talk(handle="samantha", sid=SID, turns=2):
    for n in range(turns):
        session.append_turn(handle, sid, f"user message {n}", f"secret reply {n}")


def post(client, handle="samantha", sid=SID, **body):
    return client.post(f"/api/chat/session/{sid}/archive", json={"persona": handle, **body})


def test_an_archive_is_a_new_note_draft_in_sessions_under_her_folder(env, asked):
    client, vault = env
    talk()

    response = post(client)

    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["folder"] == "Projects/Sessions"
    assert draft["name"] == "2026-10-01 Atlas database choice"
    waiting = note_changes.drafts("samantha")
    assert [(d["is_new"], d["folder"]) for d in waiting] == [(True, "Projects/Sessions")]
    proposal = note_changes.store.read("samantha", draft["path"])["proposals"][0]
    assert "type: session" in proposal["text"] and "SQLite first" in proposal["text"] and "persona: Samantha" in proposal["text"]
    assert os.listdir(vault) == ["Projects"] and os.listdir(vault / "Projects") == []  # nothing written to the vault


def test_a_whole_vault_persona_files_it_in_sessions_at_the_root(env, asked):
    client, _ = env
    talk("everywhere")

    assert post(client, "everywhere").json()["draft"]["folder"] == "Sessions"


def test_the_model_sees_only_the_users_messages(env, asked):
    client, _ = env
    talk()

    post(client)

    sent = asked[0]["messages"][1]["content"]
    assert "user message 0" in sent and "user message 1" in sent and "secret reply" not in sent


def test_a_reply_with_no_title_line_is_named_by_the_conversations_own_title(env, asked):
    client, _ = env
    talk()
    asked.replies[:] = [model_mod.ModelReply("The user planned the Atlas database choice and left backups open for later.\n- SQLite first", 5)]

    draft = post(client).json()["draft"]

    assert draft["name"] == "2026-10-01 user message 0"
    text = note_changes.store.read("samantha", draft["path"])["proposals"][0]["text"]
    assert "The user planned the Atlas database choice" in text  # the first line stays in the note


def test_a_title_is_made_safe_for_a_file_name(env):
    assert archive._name("2026-10-01", 'Plan: A/B "test" [x] #1.') == "2026-10-01 Plan A B test x 1"
    assert archive._name("2026-10-01", "") == "2026-10-01"


@pytest.mark.parametrize("reply", ["NONE", "none."])
def test_nothing_worth_keeping_makes_no_draft(env, asked, reply):
    client, _ = env
    talk()
    asked.replies[:] = [model_mod.ModelReply(reply, 5)]

    assert post(client).status_code == 422
    assert note_changes.drafts("samantha") == []


def test_a_model_that_fails_or_writes_nothing_is_a_502(env, asked):
    client, _ = env
    talk()
    asked.replies[:] = [model_mod.EngineModelError("down")]
    assert post(client).status_code == 502
    asked.replies[:] = [model_mod.ModelReply("   ", 5)]
    assert post(client).status_code == 502
    assert note_changes.drafts("samantha") == []


def test_a_reply_cut_by_the_limit_loses_its_unfinished_line(env, asked):
    client, _ = env
    talk()
    asked.replies[:] = [model_mod.ModelReply("Title\n\nA whole line.\n- half a li", 5, truncated=True)]

    draft = post(client).json()["draft"]

    text = note_changes.store.read("samantha", draft["path"])["proposals"][0]["text"]
    assert text.endswith("A whole line.\n") and "half a li" not in text


def test_the_same_conversation_twice_waits_for_the_first_to_be_decided(env, asked):
    client, _ = env
    talk()
    assert post(client).status_code == 200

    again = post(client)

    assert again.status_code == 409 and "already waiting" in again.json()["detail"]
    assert len(note_changes.drafts("samantha")) == 1


def test_a_short_unknown_busy_or_vaultless_conversation_is_refused(env, asked):
    client, _ = env
    talk(turns=1)
    assert post(client).status_code == 422
    assert post(client, sid="20261001T110000-bbbbbbbb").status_code == 404
    talk("nowhere")
    assert post(client, "nowhere").status_code == 422
    talk(sid="20261001T120000-cccccccc")
    turn_cancel.begin("samantha", "20261001T120000-cccccccc")
    try:
        assert post(client, sid="20261001T120000-cccccccc").status_code == 409
    finally:
        turn_cancel.finish("samantha", "20261001T120000-cccccccc")
    assert asked == []  # none of these reached the model


def test_a_cloud_model_the_user_has_not_allowed_is_not_sent_the_messages(env, asked):
    client, _ = env
    talk()

    refused = post(client, model="openai/gpt-4o")

    assert refused.status_code == 422 and asked == []
