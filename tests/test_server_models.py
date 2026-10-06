"""The web chat's model routes (docs/decisions/044): the one list of models, and saving a persona's own
model into its persona.yaml, the same file the terminal's /model writes."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import profile
from sympose.engine.model_options import MODEL_OPTIONS
from sympose.server import create_app

FILE = "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n# kept\n"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", FILE)
    write_persona(base, "cloudy", FILE + "model: gemini/gemini-flash-latest\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return base


@pytest.fixture
def client():
    return TestClient(create_app())


def test_lists_the_shared_models_marked_cloud_or_local(client):
    body = client.get("/api/models", params={"persona": "samantha"}).json()
    assert [m["id"] for m in body["models"]] == [m.id for m in MODEL_OPTIONS]
    by_id = {m["id"]: m for m in body["models"]}
    assert by_id[MODEL_OPTIONS[0].id]["cloud"] is False
    assert by_id["gemini/gemini-flash-latest"]["cloud"] is True
    assert by_id["gemini/gemini-flash-latest"]["label"] == "Gemini Flash — cloud"


def test_says_the_model_in_use_and_the_one_that_applies_with_none_of_its_own(client):
    plain = client.get("/api/models", params={"persona": "samantha"}).json()
    assert plain["current"] == plain["fallback"] and plain["own"] is None
    cloudy = client.get("/api/models", params={"persona": "cloudy"}).json()
    assert cloudy["current"] == "gemini/gemini-flash-latest" == cloudy["own"]
    assert cloudy["fallback"] == plain["fallback"]


def test_says_whether_the_model_in_use_is_cloud_even_when_the_list_does_not_hold_it(client, scratch):
    assert client.get("/api/models", params={"persona": "samantha"}).json()["current_cloud"] is False
    assert client.get("/api/models", params={"persona": "cloudy"}).json()["current_cloud"] is True
    write_persona(scratch, "handmade", FILE + "model: openai/some-model-not-listed\n")
    assert client.get("/api/models", params={"persona": "handmade"}).json()["current_cloud"] is True


def test_says_whether_the_fallback_is_cloud_too_since_clearing_a_model_lands_on_it(client, monkeypatch):
    assert client.get("/api/models", params={"persona": "samantha"}).json()["fallback_cloud"] is False
    from sympose import settings_store

    settings_store.set("chat_model", "openai/gpt-4o-mini")
    body = client.get("/api/models", params={"persona": "samantha"}).json()
    assert body["fallback"] == "openai/gpt-4o-mini" and body["fallback_cloud"] is True


def test_a_listed_model_is_saved_into_the_local_override_and_read_back(client, scratch):
    r = client.put("/api/personas/samantha/model", json={"model": "openai/gpt-4o-mini"})
    assert r.status_code == 200 and r.json()["current"] == "openai/gpt-4o-mini" and r.json()["own"] == "openai/gpt-4o-mini"
    assert (scratch / "samantha" / "persona.yaml").read_text() == FILE  # the shipped file is never written
    assert (scratch / "samantha" / "persona.local.yaml").read_text() == "model: openai/gpt-4o-mini\n"
    assert profile.get_profile("samantha")["model"] == "openai/gpt-4o-mini"  # what the terminal reads


def test_the_answer_describes_the_persona_that_was_changed_not_the_default_one(client):
    r = client.put("/api/personas/cloudy/model", json={"model": "openai/gpt-4o-mini"})
    assert r.json()["own"] == "openai/gpt-4o-mini" == r.json()["current"]


def test_null_removes_the_pick_and_returns_to_the_shipped_model(client, scratch):
    client.put("/api/personas/cloudy/model", json={"model": "openai/gpt-4o-mini"})
    r = client.put("/api/personas/cloudy/model", json={"model": None})
    assert r.status_code == 200 and r.json()["own"] == "gemini/gemini-flash-latest"  # the persona file's own
    assert not (scratch / "cloudy" / "persona.local.yaml").exists()
    plain = client.put("/api/personas/samantha/model", json={"model": None})
    assert plain.json()["own"] is None and plain.json()["current"] == plain.json()["fallback"]


def test_a_model_the_list_does_not_offer_is_refused_and_nothing_is_written(client, scratch):
    before = (scratch / "samantha" / "persona.yaml").read_text()
    r = client.put("/api/personas/samantha/model", json={"model": "evil/anything"})
    assert r.status_code == 422 and r.json()["detail"] == "Pick a model from the list."
    assert (scratch / "samantha" / "persona.yaml").read_text() == before


def test_an_unknown_persona_is_404_for_both_routes(client):
    assert client.get("/api/models", params={"persona": "nobody"}).status_code == 404
    assert client.put("/api/personas/nobody/model", json={"model": None}).status_code == 404


def test_a_write_that_fails_is_a_500_and_leaves_the_shipped_file_alone(client, scratch, monkeypatch):
    from sympose import persona_model

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(persona_model, "write_atomic_text", boom)
    r = client.put("/api/personas/samantha/model", json={"model": "openai/gpt-4o-mini"})
    assert r.status_code == 500
    assert (scratch / "samantha" / "persona.yaml").read_text() == FILE


def test_a_model_named_by_hand_gets_its_own_row_and_keeps_its_cloud_flag(client, scratch):
    write_persona(scratch, "handmade2", FILE + "model: openrouter/mistralai/mistral-large\n")
    body = client.get("/api/models", params={"persona": "handmade2"}).json()
    row = next(m for m in body["models"] if m["id"] == "openrouter/mistralai/mistral-large")
    assert row["cloud"] is True and row["short"] == "mistral-large" and body["current_cloud"] is True
    assert [m["id"] for m in body["models"]].count("openrouter/mistralai/mistral-large") == 1
    assert len(body["models"]) == len(MODEL_OPTIONS) + 1
    # Choosing the row that is already in use is accepted, and an unrelated unlisted id is still refused.
    assert client.put("/api/personas/handmade2/model", json={"model": row["id"]}).status_code == 200
    assert client.put("/api/personas/handmade2/model", json={"model": "evil/anything"}).status_code == 422


def test_a_hand_named_default_model_is_accepted_so_the_default_can_be_picked(client):
    from sympose import settings_store

    settings_store.set("chat_model", "openrouter/mistralai/mistral-large")
    assert client.put("/api/personas/samantha/model", json={"model": "openrouter/mistralai/mistral-large"}).status_code == 200


def test_a_listed_model_gets_no_extra_row(client):
    assert len(client.get("/api/models", params={"persona": "samantha"}).json()["models"]) == len(MODEL_OPTIONS)
