"""The engine settings' routes (docs/decisions/044): the terminal's list, described to the browser and
changed through the same rules, so a refusal by the owning module reaches the browser as a reason."""

import json

import pytest
from fastapi.testclient import TestClient

from sympose.engine import settings_registry
from sympose.server import create_app


@pytest.fixture
def path(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(p))
    return p


@pytest.fixture
def client(path):
    return TestClient(create_app())


def rows(client):
    return {s["key"]: s for g in client.get("/api/settings").json()["groups"] for s in g["settings"]}


def test_lists_every_engine_setting_in_its_groups_and_no_terminal_display_knob(client):
    groups = client.get("/api/settings").json()["groups"]
    assert [g["name"] for g in groups] == ["Context", "Search", "Note lookup", "Memory", "Conversations"]
    assert sum(len(g["settings"]) for g in groups) == len(settings_registry.SETTINGS)
    assert "show_grounding" not in rows(client) and "reply_reveal" not in rows(client)


def test_a_row_describes_the_value_in_force_and_the_default(client, path):
    row = rows(client)["memory_remember"]
    assert (row["kind"], row["value"], row["default"], row["is_default"], row["text"]) == ("toggle", False, False, True, "off")
    path.write_text(json.dumps({"memory_remember": True}))
    row = rows(client)["memory_remember"]
    assert (row["value"], row["is_default"], row["text"]) == (True, False, "on")


def test_a_toggle_is_set_and_null_restores_the_default(client, path):
    r = client.put("/api/settings/memory_remember", json={"value": True})
    assert r.status_code == 200 and r.json()["setting"]["value"] is True
    assert json.loads(path.read_text())["memory_remember"] is True
    r = client.put("/api/settings/memory_remember", json={"value": None})
    assert r.json()["setting"]["is_default"] is True and "memory_remember" not in json.loads(path.read_text())


def test_a_choice_takes_only_one_of_its_values(client):
    assert client.put("/api/settings/vault_lookup", json={"value": "ask"}).json()["setting"]["value"] == "ask"
    r = client.put("/api/settings/vault_lookup", json={"value": "sideways"})
    assert r.status_code == 422 and "sideways" in r.json()["detail"]
    assert rows(client)["vault_lookup"]["value"] == "ask"


def test_a_toggle_refuses_a_non_boolean(client):
    assert client.put("/api/settings/memory_remember", json={"value": "yes"}).status_code == 422


def test_a_number_is_saved_and_a_value_the_module_refuses_is_left_as_it_was(client):
    assert client.put("/api/settings/reply_limit", json={"value": 300}).json()["setting"]["value"] == 300
    r = client.put("/api/settings/reply_limit", json={"value": 3})
    assert r.status_code == 422 and "left as it was" in r.json()["detail"]
    assert rows(client)["reply_limit"]["value"] == 300


def test_a_number_field_refuses_text_and_booleans_and_null_resets(client):
    assert client.put("/api/settings/reply_limit", json={"value": "lots"}).status_code == 422
    assert client.put("/api/settings/reply_limit", json={"value": True}).status_code == 422
    client.put("/api/settings/reply_limit", json={"value": 300})
    assert client.put("/api/settings/reply_limit", json={"value": None}).json()["setting"]["is_default"] is True


def test_an_unknown_key_is_404(client):
    assert client.put("/api/settings/show_grounding", json={"value": False}).status_code == 404
