"""`POST /api/vault/folder/move-plan` (docs/decisions/074, slice 1), through the real app on a scratch vault and scratch
personas: what a move would do and what it needs the user's word for. It never moves anything."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose.server import create_app

FILES = {
    "People/Anna.md": "Anna\n",
    "People/People.md": "# People\n",
    "Archive/People/Anna.md": "an older Anna\n",
    "Archive/Old.md": "old\n",
    "Other/Note.md": "Other\n",
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for rel, text in FILES.items():
        (vault / rel).parent.mkdir(parents=True, exist_ok=True)
        (vault / rel).write_text(text)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "grace", "name: Grace\nvault_folders: ['Other']\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return TestClient(create_app()), vault


def ask(client, path, destination, persona="samantha"):
    return client.post("/api/vault/folder/move-plan", json={"path": path, "destination": destination, "persona": persona})


def test_the_plan_says_where_the_folder_would_go_and_what_needs_asking(env):
    client, _ = env

    res = ask(client, "People", "Archive")

    assert res.status_code == 200
    assert res.json() == {
        "path": "People",
        "destination": "Archive",
        "new_path": "Archive/People",
        "clash": True,
        "note_clashes": ["Anna.md"],
        "reach": [],
        "definition": "stops",
    }


def test_the_plan_names_each_persona_whose_reach_would_change_and_by_how_many_notes(env):
    client, _ = env

    body = ask(client, "People", "Other").json()

    assert body["reach"] == [{"handle": "grace", "name": "Grace", "gains": 2, "loses": 0}]
    assert body["clash"] is False and body["note_clashes"] == []


def test_the_vault_root_is_a_destination(env):
    client, _ = env
    assert ask(client, "Archive/People", "").json()["new_path"] == "People"


@pytest.mark.parametrize(
    "path, destination, persona, status",
    [
        ("Nope", "Archive", "samantha", 404),
        ("People", "Nope", "samantha", 404),
        (".", "Archive", "samantha", 403),
        ("Archive", "Other", "grace", 403),
        ("People", "People", "samantha", 400),
        ("Archive/People", "Archive", "samantha", 400),
    ],
)
def test_a_move_that_cannot_happen_is_answered_with_its_reason(env, path, destination, persona, status):
    client, _ = env

    assert ask(client, path, destination, persona).status_code == status


def test_a_file_with_the_folders_name_there_is_a_conflict(env):
    client, vault = env
    (vault / "Other" / "Archive").write_text("not a folder")

    assert ask(client, "Archive", "Other").status_code == 409


def test_an_unknown_persona_is_404(env):
    client, _ = env

    assert ask(client, "People", "Archive", "nobody").status_code == 404


def test_asking_changes_nothing_in_the_vault(env):
    client, vault = env
    before = sorted(str(p.relative_to(vault)) for p in vault.rglob("*"))

    ask(client, "People", "Archive")

    assert sorted(str(p.relative_to(vault)) for p in vault.rglob("*")) == before
