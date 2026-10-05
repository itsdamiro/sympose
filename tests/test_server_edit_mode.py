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
    assert small["auto"] == edit_mode.note("auto", "ollama_chat/gemma2:9b") and "18" in small["auto"]
    assert cloudy["accept"] == edit_mode.note("accept", "gemini/gemini-flash-latest") and "35 times out of 36" in cloudy["accept"]


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


def test_the_global_note_lists_each_persona_that_follows_the_setting_with_her_model(client):
    body = client.get("/api/edit-mode/global").json()

    assert body["mode"] == "manual"
    assert [(f["handle"], f["model"]) for f in body["following"]] == [
        ("cloudy", "gemini/gemini-flash-latest"),
        ("plain", body["following"][1]["model"]),
        ("small", "ollama_chat/gemma2:9b"),
    ]
    for mode in (edit_mode.ACCEPT, edit_mode.AUTO):
        text = body["notes"][mode]
        assert edit_mode.note(mode, "ollama_chat/gemma2:9b") in text
        assert edit_mode.note(mode, "gemini/gemini-flash-latest") in text
        assert "Samantha" in text


def test_a_persona_with_a_mode_of_her_own_is_not_listed_because_the_global_one_does_not_reach_her(client):
    handles = [f["handle"] for f in client.get("/api/edit-mode/global").json()["following"]]
    assert "shipped" not in handles


def test_a_mode_in_her_local_file_also_takes_her_off_the_list(client, scratch):
    client.put("/api/personas/small/edit-mode", json={"mode": "plan"})
    handles = [f["handle"] for f in client.get("/api/edit-mode/global").json()["following"]]
    assert "small" not in handles


def test_with_no_follower_the_note_says_so_instead_of_quoting_a_model(client, scratch):
    for handle in ("plain", "cloudy", "small"):
        client.put(f"/api/personas/{handle}/edit-mode", json={"mode": "manual"})

    body = client.get("/api/edit-mode/global").json()

    assert body["following"] == []
    assert "No persona follows" in body["notes"]["accept"]
    assert "gemma2" not in body["notes"]["accept"] and "Flash" not in body["notes"]["accept"]


def test_the_global_note_reports_the_global_mode_in_force(client):
    settings_store.set(edit_mode.SETTING, "auto")
    assert client.get("/api/edit-mode/global").json()["mode"] == "auto"
