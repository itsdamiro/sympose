"""The Settings footer's two checks over HTTP (docs/decisions/063): the doctor reads on GET and fixes only on POST,
and the vault health reads as the default persona. Everything runs against temporary folders."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import doctor_models
from sympose.server import create_app


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setattr(doctor_models, "embedding_finding", lambda: None)
    return tmp_path


@pytest.fixture
def client():
    return TestClient(create_app())


def test_the_doctor_reports_the_models_and_no_findings_on_a_healthy_install(client):
    body = client.get("/api/doctor").json()

    assert body["findings"] == []
    assert any("chat model" in line for line in body["models"])


def test_a_get_never_fixes_and_a_post_does(client, scratch):
    (scratch / "settings.json").write_text('{"chat_model": 5, "default_persona": "samantha"}')

    first = client.get("/api/doctor").json()["findings"]
    assert [f["state"] for f in first] == ["fixable"]
    assert first[0]["fix"] and "chat_model" in first[0]["problem"]
    assert "chat_model" in (scratch / "settings.json").read_text()

    fixed = client.post("/api/doctor/fix").json()["findings"]
    assert [f["state"] for f in fixed] == ["fixed"]
    assert "chat_model" not in (scratch / "settings.json").read_text()
    assert client.get("/api/doctor").json()["findings"] == []


def test_a_problem_nothing_can_fix_is_marked_as_needing_the_person(client, scratch):
    (scratch / "settings.json").write_text("[1, 2]")

    findings = client.post("/api/doctor/fix").json()["findings"]

    assert [f["state"] for f in findings] == ["needs_you"]
    assert (scratch / "settings.json").read_text() == "[1, 2]"


def test_the_vault_health_lists_problems_first_with_the_notes_read(client, scratch):
    (scratch / "vault" / "Empty.md").write_text("")
    (scratch / "vault" / "Alien.md").write_text("See [[Missing]].")

    body = client.get("/api/vault/health").json()

    assert body["persona"] == "samantha" and body["notes"] == 2 and body["problems"] == 2
    headings = [c["heading"] for c in body["checks"]]
    assert "Empty notes" in headings and "Links to no note" in headings
    assert all(c["problem"] for c in body["checks"][:2])
    assert body["limits"]
    notes = [f["note"] for c in body["checks"] for f in c["findings"]]
    assert sorted(notes) == ["Alien.md", "Empty.md"]


def test_a_healthy_vault_has_no_checks_listed(client, scratch):
    (scratch / "vault" / "Fine.md").write_text("Some words.")

    body = client.get("/api/vault/health").json()

    assert body["problems"] == 0 and body["checks"] == []


def test_the_vault_health_says_so_when_there_is_no_vault(client, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", "")

    response = client.get("/api/vault/health")

    assert response.status_code == 409
    assert "vault" in response.json()["detail"].lower()
