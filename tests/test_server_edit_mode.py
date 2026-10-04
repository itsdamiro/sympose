"""The edit-mode routes (docs/decisions/072): the persona page reads which mode counts for a persona, where it comes from
and the note to show for the more autonomous modes (about the model she uses), and saves her own choice into her
untracked local file."""

import pytest
import yaml
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import settings_store
from sympose.engine import edit_mode
from sympose.server import create_app

FILE = "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "plain", FILE)
    write_persona(base, "shipped", FILE + "edit_mode: plan\n")
    write_persona(base, "cloudy", FILE + "model: gemini/gemini-flash-latest\n")
    write_persona(base, "small", FILE + "model: ollama_chat/gemma2:9b\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return base


@pytest.fixture
def client():
    return TestClient(create_app())


def test_a_persona_with_nothing_of_her_own_follows_the_global_mode_and_says_so(client):
    body = client.get("/api/personas/plain/edit-mode").json()
    assert (body["mode"], body["source"]) == ("manual", "global")
    settings_store.set(edit_mode.SETTING, "auto")
    body = client.get("/api/personas/plain/edit-mode").json()
    assert (body["mode"], body["source"]) == ("auto", "global")


def test_a_mode_in_her_shipped_file_is_hers_and_beats_the_global_one(client):
    settings_store.set(edit_mode.SETTING, "auto")
    body = client.get("/api/personas/shipped/edit-mode").json()
    assert (body["mode"], body["source"]) == ("plan", "persona")


def test_lists_the_four_modes_with_a_line_each(client):
    modes = client.get("/api/personas/plain/edit-mode").json()["modes"]
    assert [m["id"] for m in modes] == list(edit_mode.MODES)
    assert all(m["summary"] for m in modes)


def test_the_note_for_accept_and_auto_is_about_the_model_she_uses(client):
    small = client.get("/api/personas/small/edit-mode").json()["notes"]
    cloudy = client.get("/api/personas/cloudy/edit-mode").json()["notes"]
    assert set(small) == {"accept", "auto"}
    assert small["auto"] == edit_mode.note("auto", "ollama_chat/gemma2:9b") and "29" in small["auto"]
    assert cloudy["accept"] == edit_mode.note("accept", "gemini/gemini-flash-latest") and "36 of 36" in cloudy["accept"]


def test_saving_a_choice_goes_to_her_local_file_and_comes_back_as_hers(client, scratch):
    body = client.put("/api/personas/plain/edit-mode", json={"mode": "accept"}).json()
    assert (body["mode"], body["source"]) == ("accept", "persona")
    assert yaml.safe_load((scratch / "plain" / "persona.local.yaml").read_text(encoding="utf-8")) == {"edit_mode": "accept"}
    assert "edit_mode" not in (scratch / "plain" / "persona.yaml").read_text(encoding="utf-8")


def test_clearing_her_choice_puts_her_back_on_the_next_source(client, scratch):
    client.put("/api/personas/shipped/edit-mode", json={"mode": "auto"})
    body = client.put("/api/personas/shipped/edit-mode", json={"mode": None}).json()
    assert (body["mode"], body["source"]) == ("plan", "persona")  # her shipped file again
    assert not (scratch / "shipped" / "persona.local.yaml").exists()


def test_a_mode_that_is_not_one_of_the_four_is_refused_and_nothing_is_written(client, scratch):
    response = client.put("/api/personas/plain/edit-mode", json={"mode": "yolo"})
    assert response.status_code == 422
    assert not (scratch / "plain" / "persona.local.yaml").exists()


def test_a_persona_that_does_not_exist_is_a_404(client):
    assert client.get("/api/personas/nobody/edit-mode").status_code == 404
    assert client.put("/api/personas/nobody/edit-mode", json={"mode": "plan"}).status_code == 404


def test_picking_a_model_afterwards_keeps_her_mode(client, scratch):
    client.put("/api/personas/plain/edit-mode", json={"mode": "auto"})
    client.put("/api/personas/plain/model", json={"model": "gemini/gemini-flash-latest"})
    assert client.get("/api/personas/plain/edit-mode").json()["mode"] == "auto"
