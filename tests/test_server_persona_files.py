"""The routes that serve a persona's own files to the web editor (docs/decisions/061): the list, one file read and
saved, the soul's reset, and a rewrite waiting for review. Behaviour of the files themselves is
`test_persona_editable.py`; this is the door: names, statuses, and the shapes the editor reads."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose.server import create_app


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return directory


@pytest.fixture
def client(home):
    return TestClient(create_app())


def test_it_lists_the_four_files(client, home):
    (home / "soul.md").write_text("voice")
    body = client.get("/api/personas/samantha/files").json()
    assert [f["name"] for f in body["files"]] == ["soul.md", "profile.md", "context.md", "decisions.md"]
    assert body["files"][0]["exists"] is True


def test_an_unknown_persona_is_404_and_so_is_a_name_that_is_not_one_of_the_four(client, home):
    assert client.get("/api/personas/nobody/files").status_code == 404
    assert client.get("/api/personas/samantha/files/persona.yaml").status_code == 404
    assert client.put("/api/personas/samantha/files/persona.yaml", json={"content": "x"}).status_code == 404
    assert client.get("/api/personas/samantha/files/..%2Fpersona.yaml").status_code == 404
    assert (home / "persona.yaml").read_text().startswith("name: Samantha")


def test_a_file_is_read_whole_with_its_mtime(client, home):
    (home / "profile.md").write_text("likes small steps\n")
    body = client.get("/api/personas/samantha/files/profile.md").json()
    assert body["content"] == "likes small steps\n" and body["mtime"] == (home / "profile.md").stat().st_mtime
    assert client.get("/api/personas/samantha/files/context.md").json() == {
        "name": "context.md", "content": "", "mtime": None, "local": False,
    }


def test_saving_returns_the_mtime_the_next_save_presents(client, home):
    (home / "profile.md").write_text("old")
    opened = client.get("/api/personas/samantha/files/profile.md").json()["mtime"]
    saved = client.put("/api/personas/samantha/files/profile.md", json={"content": "new", "expected_mtime": opened})
    assert saved.status_code == 200
    assert saved.json()["mtime"] == (home / "profile.md").stat().st_mtime
    assert (home / "profile.md").read_text() == "new"


def test_saving_over_a_change_made_meanwhile_is_a_409_that_says_so(client, home):
    (home / "profile.md").write_text("old")
    opened = client.get("/api/personas/samantha/files/profile.md").json()["mtime"]
    os.utime(home / "profile.md", (opened + 50, opened + 50))
    refused = client.put("/api/personas/samantha/files/profile.md", json={"content": "mine", "expected_mtime": opened})
    assert refused.status_code == 409 and "changed on disk" in refused.json()["detail"]
    assert (home / "profile.md").read_text() == "old"


def test_saving_the_soul_makes_a_local_copy_and_a_reset_removes_it(client, home):
    (home / "soul.md").write_text("shipped")
    opened = client.get("/api/personas/samantha/files/soul.md").json()
    assert opened["local"] is False
    client.put("/api/personas/samantha/files/soul.md", json={"content": "mine", "expected_mtime": opened["mtime"]})
    assert (home / "soul.md").read_text() == "shipped" and (home / "soul.local.md").read_text() == "mine"
    assert client.get("/api/personas/samantha/files/soul.md").json()["local"] is True
    assert client.post("/api/personas/samantha/files/soul.md/reset").json() == {"removed": True}
    assert client.get("/api/personas/samantha/files/soul.md").json()["content"] == "shipped"
    assert (home / "soul.local.md.bak").read_text() == "mine"
    assert client.post("/api/personas/samantha/files/soul.md/reset").json() == {"removed": False}


def test_a_waiting_rewrite_can_be_read_accepted_and_discarded(client, home):
    (home / "profile.md").write_text("old profile")
    (home / "profile.md.pending").write_text("new profile")
    (home / "context.md").write_text("old context")
    (home / "context.md.pending").write_text("new context")
    waiting = client.get("/api/personas/samantha/files/profile.md/pending").json()
    assert waiting["text"] == "new profile" and "+new profile" in waiting["diff"]
    assert client.get("/api/personas/samantha/files/decisions.md/pending").status_code == 404
    assert client.post("/api/personas/samantha/files/profile.md/pending/accept").json() == {"ok": True}
    assert (home / "profile.md").read_text().strip() == "new profile" and (home / "profile.md.bak").read_text() == "old profile"
    assert client.post("/api/personas/samantha/files/context.md/pending/discard").json() == {"ok": True}
    assert (home / "context.md").read_text() == "old context" and not (home / "context.md.pending").exists()
    assert client.post("/api/personas/samantha/files/context.md/pending/accept").status_code == 404  # none waiting now
