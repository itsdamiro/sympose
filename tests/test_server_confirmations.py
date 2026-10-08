"""The confirmation routes (docs/decisions/078) through the real app on a scratch vault and profiles folder: list a
conversation's requests with the folders the pills offer, answer one, and the refusals."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import persona_create
from sympose.engine import confirmations, sharing
from sympose.server import create_app

SOUL = "You are Ada, a warm tutor.\n\nHow you talk:\n- Gently.\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for folder in ("Work", "Recipes", "Journal"):
        (vault / folder).mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    return TestClient(create_app()), profiles


def file_request(name="Ada", session="s1"):
    draft = persona_create.Draft(name, "A tutor", SOUL, "graduation", "#3366cc", "#99bbee", ("Recipes", "Work"), "manual")
    return confirmations.propose_persona("samantha", session, draft)


def test_the_list_gives_the_proposal_its_state_and_the_folders_the_pills_offer(env):
    client, _ = env
    request = file_request()

    body = client.get("/api/chat/confirmations", params={"persona": "samantha", "session": "s1"}).json()

    (item,) = body["requests"]
    assert item["id"] == request["id"] and item["state"] == "waiting" and item["handle"] == "ada"
    assert item["draft"]["folders"] == ["Recipes", "Work"] and item["draft"]["icon"] == "graduation"
    assert item["folder_choices"] == ["Journal", "Recipes", "Work"]
    assert [m["id"] for m in item["edit_modes"]] == ["plan", "manual", "accept", "auto"] and all(m["summary"] for m in item["edit_modes"])
    assert client.get("/api/chat/confirmations", params={"persona": "samantha", "session": "other"}).json() == {"requests": []}


def test_accepting_makes_the_persona_and_it_shows_in_the_roster(env):
    client, profiles = env
    request = file_request()

    done = client.post(f"/api/chat/confirmations/{request['id']}", json={"persona": "samantha", "accept": True, "folders": ["Journal"]})

    assert done.status_code == 200 and done.json()["state"] == "accepted" and done.json()["draft"]["folders"] == ["Journal"]
    assert (profiles / "ada" / "soul.md").exists()
    assert "ada" in [p["handle"] for p in client.get("/api/personas").json()["personas"]]


def test_the_edit_mode_chosen_on_the_card_is_the_one_the_persona_gets(env):
    client, profiles = env
    request = file_request()

    done = client.post(f"/api/chat/confirmations/{request['id']}", json={"persona": "samantha", "accept": True, "edit_mode": "plan"})

    assert done.json()["draft"]["edit_mode"] == "plan" and "edit_mode: plan" in (profiles / "ada" / "persona.yaml").read_text()


def test_a_wrong_edit_mode_is_unprocessable(env):
    client, _ = env
    request = file_request()

    refused = client.post(f"/api/chat/confirmations/{request['id']}", json={"persona": "samantha", "accept": True, "edit_mode": "wild"})

    assert refused.status_code == 422 and "edit_mode" in refused.json()["detail"]


def test_declining_makes_nothing(env):
    client, profiles = env
    request = file_request()

    done = client.post(f"/api/chat/confirmations/{request['id']}", json={"persona": "samantha", "accept": False})

    assert done.json()["state"] == "declined" and not (profiles / "ada").exists()


def test_a_second_answer_is_a_conflict(env):
    client, _ = env
    request = file_request()
    url = f"/api/chat/confirmations/{request['id']}"
    client.post(url, json={"persona": "samantha", "accept": False})

    again = client.post(url, json={"persona": "samantha", "accept": True})

    assert again.status_code == 409 and "already been answered" in again.json()["detail"]


def test_no_pill_on_is_unprocessable_and_the_card_can_be_answered_again(env):
    client, profiles = env
    request = file_request()
    url = f"/api/chat/confirmations/{request['id']}"

    refused = client.post(url, json={"persona": "samantha", "accept": True, "folders": []})

    assert refused.status_code == 422 and "at least one folder" in refused.json()["detail"] and not (profiles / "ada").exists()
    assert client.post(url, json={"persona": "samantha", "accept": True, "folders": ["Work"]}).json()["state"] == "accepted"


def test_an_unknown_request_is_not_found_and_an_unknown_persona_too(env):
    client, _ = env

    assert client.post("/api/chat/confirmations/nope", json={"persona": "samantha", "accept": True}).status_code == 404
    assert client.post("/api/chat/confirmations/nope", json={"persona": "ghost", "accept": True}).status_code == 404
    assert client.get("/api/chat/confirmations", params={"persona": "ghost", "session": "s1"}).status_code == 404


def test_a_setting_request_is_listed_with_what_it_is_from_and_to_and_declining_changes_nothing(env):
    client, _ = env
    request = confirmations.propose_setting("samantha", "s1", "cloud_share:notes", True)

    (item,) = client.get("/api/chat/confirmations", params={"persona": "samantha", "session": "s1"}).json()["requests"]

    assert item["kind"] == "setting" and item["state"] == "waiting" and "draft" not in item
    assert item["setting"]["name"] == "cloud_share:notes" and item["setting"]["from"] == "no" and item["setting"]["to"] == "yes"
    assert item["setting"]["summary"] and "may then receive" in item["setting"]["note"]
    assert client.post(f"/api/chat/confirmations/{request['id']}", json={"persona": "samantha", "accept": False}).json()["state"] == "declined"
    assert sharing.NOTES not in sharing.approved()


def test_accepting_a_setting_request_saves_it_and_a_refused_value_comes_back_as_the_reason(env):
    client, _ = env
    good = confirmations.propose_setting("samantha", "s1", "cloud_share:notes", True)
    bad = confirmations.propose_setting("samantha", "s1", "history_tokens", 10)

    saved = client.post(f"/api/chat/confirmations/{good['id']}", json={"persona": "samantha", "accept": True})
    refused = client.post(f"/api/chat/confirmations/{bad['id']}", json={"persona": "samantha", "accept": True})

    assert saved.status_code == 200 and saved.json()["state"] == "accepted" and saved.json()["setting"]["from"] == "no"
    assert sharing.NOTES in sharing.approved()
    assert refused.status_code == 422 and "not valid" in refused.json()["detail"]
