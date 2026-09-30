"""A state-changing request from a web page on another origin is refused (sympose/server_origin.py)."""

import pytest
from fastapi.testclient import TestClient

from sympose import settings_store
from sympose.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return TestClient(create_app())


def _add_vault(client, tmp_path, origin=None):
    headers = {"Origin": origin} if origin else {}
    return client.post("/api/vaults", json={"path": str(tmp_path)}, headers=headers)


def test_a_page_on_another_origin_cannot_add_a_vault(client, tmp_path):
    response = _add_vault(client, tmp_path, "https://evil.example")
    assert response.status_code == 403
    assert settings_store.get("added_vaults") is None


def test_a_request_with_no_origin_is_not_a_browser_page_and_goes_through(client, tmp_path):
    assert _add_vault(client, tmp_path).status_code == 201


def test_the_pages_own_origin_goes_through(client, tmp_path):
    assert _add_vault(client, tmp_path, "http://testserver").status_code == 201


def test_the_dev_server_origin_goes_through(client, tmp_path):
    assert _add_vault(client, tmp_path, "http://localhost:5173").status_code == 201


def test_reading_from_another_origin_is_not_refused_here(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200
