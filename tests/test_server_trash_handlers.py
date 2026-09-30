"""Tests for sympose.server_trash_handlers — fail-closed persona resolution
via require_profile (docs/decisions/009)."""

from helpers import write_persona
import pytest
from fastapi import HTTPException

from sympose import server_trash_handlers as th
from sympose.server_models import TrashEmpty, TrashRestore


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    return profiles


def test_list_trash_404s_an_unknown_persona_with_a_profiles_dir_configured(profiles_dir):
    with pytest.raises(HTTPException) as exc_info:
        th.list_trash("some-typo-handle")
    assert exc_info.value.status_code == 404


def test_every_mutating_trash_handler_404s_an_unknown_persona(profiles_dir):
    """`_require_trash_scope` (restore/purge/empty) now routes through
    `require_profile` the same way `_trash_scope` (list) does -- confirms
    all three, not just the read route already covered above."""
    calls = [
        lambda: th.restore_trash(TrashRestore(path="X.md", persona="bogus")),
        lambda: th.purge_trash("X.md", "bogus"),
        lambda: th.empty_trash(TrashEmpty(persona="bogus")),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404


def test_a_note_whose_name_starts_with_error_is_restored_not_reported_as_a_failure(profiles_dir, tmp_path):
    """`translate_vault_result` reads a result starting with `Error:` as a failure; the restored path is not a result."""
    (tmp_path / ".trash").mkdir()
    (tmp_path / ".trash" / "Error: timeout notes.md").write_text("kept", encoding="utf-8")

    result = th.restore_trash(TrashRestore(path="Error: timeout notes.md", persona="samantha"))

    assert result == {"path": "Error: timeout notes.md", "detail": "Restored to `Error: timeout notes.md`"}
    assert (tmp_path / "Error: timeout notes.md").read_text(encoding="utf-8") == "kept"


def _bin_file(tmp_path, rel, data="x"):
    path = tmp_path / ".trash" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return path


def test_the_bin_lists_and_restores_every_file_a_deleted_folder_held(profiles_dir, tmp_path):
    """Issue #100: attachments were unlisted, so a deleted folder's images could not be recovered."""
    _bin_file(tmp_path, "Trip/Plan.md")
    _bin_file(tmp_path, "Trip/img/map.png", "png")
    assert sorted(r["trash_path"] for r in th.list_trash("samantha")["items"]) == ["Trip/Plan.md", "Trip/img/map.png"]
    result = th.restore_trash(TrashRestore(path="Trip/img/map.png", persona="samantha"))
    assert result["path"] == "Trip/img/map.png" and (tmp_path / "Trip" / "img" / "map.png").read_text() == "png"


def test_emptying_the_bin_removes_every_file_and_says_how_many_items(profiles_dir, tmp_path):
    _bin_file(tmp_path, "Trip/Plan.md")
    _bin_file(tmp_path, "Trip/img/map.png")
    _bin_file(tmp_path, "Trip/.DS_Store")
    assert th.empty_trash(TrashEmpty(persona="samantha")) == {"count": 2, "detail": "Emptied the bin (2 items)."}
    assert not any(p.is_file() for p in (tmp_path / ".trash").rglob("*"))
    _bin_file(tmp_path, "One.png")
    assert th.empty_trash(TrashEmpty(persona="samantha"))["detail"] == "Emptied the bin (1 item)."


def test_a_restore_onto_an_occupied_path_says_it_is_a_file_not_a_note(profiles_dir, tmp_path):
    _bin_file(tmp_path, "map.png", "bin")
    (tmp_path / "map.png").write_text("here", encoding="utf-8")
    with pytest.raises(HTTPException) as exc_info:
        th.restore_trash(TrashRestore(path="map.png", persona="samantha"))
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Something already occupies that file's original location."
