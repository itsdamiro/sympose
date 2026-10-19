"""The skill routes (docs/decisions/077, the amendment of 2026-10-14): list, read, add a folder by its path, switch on
and off. A refusal is a 422 with the reason, an unknown persona or skill a 404."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose.engine import skills
from sympose.server import create_app

SKILL = "---\nname: {name}\ndescription: Plans a trip itinerary. Use when the user wants to plan a trip.\ntools: [propose_note]\n---\n1. Ask the dates.\n"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "ada", "name: Ada\nvault_folders: '*'\nsympose_reference: false\nskills: ['poem-writing']\n")
    bundled = tmp_path / "bundled" / "poem-writing"
    bundled.mkdir(parents=True)
    (bundled / "SKILL.md").write_text(SKILL.format(name="poem-writing"), encoding="utf-8")
    monkeypatch.setattr(skills, "BUNDLED_DIR", str(tmp_path / "bundled"))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    folder = tmp_path / "elsewhere" / "trip-planning"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(SKILL.format(name="trip-planning"), encoding="utf-8")
    return folder


@pytest.fixture
def client():
    return TestClient(create_app())


def test_the_list_names_each_skill_with_its_state(client):
    rows = client.get("/api/personas/ada/skills").json()["skills"]

    assert [(r["name"], r["enabled"], r["own"]) for r in rows] == [("poem-writing", True, False)]
    assert rows[0]["tools"] == ["propose_note"] and rows[0]["description"].startswith("Plans a trip")


def test_a_folder_is_added_off_then_read_then_switched_on(client, scratch):
    added = client.post("/api/personas/ada/skills", json={"folder": str(scratch)})
    assert added.status_code == 200
    assert added.json()["skill"]["enabled"] is False and added.json()["left_out"] == 0

    read = client.get("/api/personas/ada/skills/trip-planning").json()
    assert read["text"] == SKILL.format(name="trip-planning") and read["own"] is True

    on = client.put("/api/personas/ada/skills/trip-planning", json={"enabled": True})
    assert on.json()["skill"]["enabled"] is True
    rows = {r["name"]: r["enabled"] for r in client.get("/api/personas/ada/skills").json()["skills"]}
    assert rows == {"poem-writing": True, "trip-planning": True}


def test_a_folder_that_is_refused_is_a_422_with_the_reason(client, tmp_path):
    response = client.post("/api/personas/ada/skills", json={"folder": str(tmp_path / "nowhere")})

    assert response.status_code == 422 and response.json()["detail"] == "There is no folder at that path."


def test_an_unknown_persona_or_skill_is_a_404_on_a_read_and_a_422_on_a_change(client):
    assert client.get("/api/personas/nobody/skills").status_code == 404
    assert client.get("/api/personas/ada/skills/ghost").status_code == 404
    put = client.put("/api/personas/ada/skills/ghost", json={"enabled": True})
    assert put.status_code == 422 and "no skill called ghost" in put.json()["detail"]


def test_an_own_skill_is_removed_and_one_that_ships_with_sympose_is_a_422(client, scratch):
    client.post("/api/personas/ada/skills", json={"folder": str(scratch)})

    assert client.delete("/api/personas/ada/skills/trip-planning").json() == {"removed": "trip-planning"}
    assert [r["name"] for r in client.get("/api/personas/ada/skills").json()["skills"]] == ["poem-writing"]

    refused = client.delete("/api/personas/ada/skills/poem-writing")
    assert refused.status_code == 422 and "ships with Sympose" in refused.json()["detail"]
    assert client.delete("/api/personas/ada/skills/trip-planning").status_code == 422
