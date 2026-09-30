"""The web chat's cloud-sharing routes (docs/decisions/044, 031): what the persona's model may receive,
read and changed through the same `cloud_share` list the terminal's `/share` uses."""

import json

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose.engine import sharing
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
    return tmp_path / "settings.json"


@pytest.fixture
def client():
    return TestClient(create_app())


def shared(body):
    return {c["name"] for c in body["categories"] if c["shared"]}


def test_a_local_persona_is_reported_local_with_the_categories_listed(client):
    body = client.get("/api/sharing", params={"persona": "samantha"}).json()
    assert body["cloud"] is False and body["model"].startswith("ollama")
    assert [c["name"] for c in body["categories"]] == list(sharing.CATEGORIES)
    assert all(c["description"] == sharing.DESCRIPTIONS[c["name"]] for c in body["categories"])


def test_a_cloud_persona_is_reported_cloud_and_nothing_is_shared_by_default(client):
    body = client.get("/api/sharing", params={"persona": "cloudy"}).json()
    assert body["cloud"] is True and body["model"] == "gemini/gemini-flash-latest"
    assert shared(body) == set()


def test_a_category_is_approved_and_stopped_through_the_one_shared_list(client, scratch):
    body = client.put("/api/sharing/notes", params={"persona": "cloudy"}, json={"shared": True}).json()
    assert shared(body) == {"notes"} and json.loads(scratch.read_text())["cloud_share"] == ["notes"]
    assert sharing.approved() == {"notes"}  # what the terminal's /share reads
    body = client.put("/api/sharing/notes", params={"persona": "cloudy"}, json={"shared": False}).json()
    assert shared(body) == set()


def test_an_unknown_category_is_404(client):
    assert client.put("/api/sharing/everything", json={"shared": True}).status_code == 404


def test_an_unknown_persona_is_404(client):
    assert client.get("/api/sharing", params={"persona": "nobody"}).status_code == 404


def test_a_failed_save_is_a_500_and_changes_nothing(client, monkeypatch):
    monkeypatch.setattr(sharing.settings_store, "set", lambda key, value: False)
    assert client.put("/api/sharing/notes", json={"shared": True}).status_code == 500
    assert sharing.approved() == frozenset()
