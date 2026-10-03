"""Tests for sympose.server_search_handlers — fail-closed persona resolution
via require_profile (docs/decisions/009)."""

from helpers import write_persona
import pytest
from fastapi import HTTPException

from sympose import server_search_handlers as sh


def test_search_vault_404s_an_unknown_persona_with_a_profiles_dir_configured(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    with pytest.raises(HTTPException) as exc_info:
        sh.search_vault("anything", "some-typo-handle")
    assert exc_info.value.status_code == 404


# -- notes close in meaning to the open note (docs/decisions/066) --


@pytest.fixture
def scratch(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "Anna.md").write_text("Anna", encoding="utf-8")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return root


def test_related_404s_an_unknown_persona(scratch):
    with pytest.raises(HTTPException) as exc_info:
        sh.related_notes("Anna.md", "some-typo-handle")
    assert exc_info.value.status_code == 404


def test_related_lists_the_neighbours_with_their_meter(scratch, monkeypatch):
    from sympose.engine import related

    seen = {}

    def fake(profile, path, limit, skip=()):
        seen["args"] = (path, limit)
        return [{"path": "Bo.md", "title": "Bo", "score": 0.55, "percent": 50}]

    monkeypatch.setattr(related, "neighbours", fake)

    out = sh.related_notes("Anna.md", "samantha")

    assert seen["args"] == ("Anna.md", related.FOR_PANEL)
    assert out == {"path": "Anna.md", "enabled": True, "indexing": False, "related": [{"rel_path": "Bo.md", "title": "Bo", "percent": 50}]}


def test_related_says_it_is_off_so_the_panel_can_hide_the_section(scratch, monkeypatch):
    from sympose import settings_store

    settings_store.set("connections_by_meaning", "off")

    assert sh.related_notes("Anna.md", "samantha") == {"path": "Anna.md", "enabled": False, "indexing": False, "related": []}


def test_related_marks_a_neighbour_the_user_hid(scratch, monkeypatch):
    from sympose import vault_hidden
    from sympose.engine import related

    monkeypatch.setattr(related, "neighbours", lambda *a, **k: [{"path": "Bo.md", "title": "Bo", "score": 0.6, "percent": 66}])
    monkeypatch.setattr(vault_hidden, "hidden_paths", lambda: ["Bo.md"])

    row = sh.related_notes("Anna.md", "samantha")["related"][0]

    assert row["hidden"] is True and row["hidden_by"] == ["Bo.md"]


def test_related_says_while_the_first_index_is_still_being_built(scratch, monkeypatch):
    from sympose.engine import related

    monkeypatch.setattr(related, "indexing", lambda profile: True)

    out = sh.related_notes("Anna.md", "samantha")

    assert out["enabled"] is True and out["indexing"] is True and out["related"] == []
