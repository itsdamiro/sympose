"""A deleted folder in the bin (docs/decisions/050, #118): recorded at the delete, shown as one folder, restored as a
unit without overwriting anything."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import vault_trash, vault_trash_unit, vault_write_delete
from sympose.server import create_app

ALL = {"vault_folders": ["*"]}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return tmp_path


def write(vault, rel, text="x"):
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def trip(vault):
    for name in ("a.md", "b.md", "photos/one.png", "photos/two.png"):
        write(vault, f"Trip/{name}", name)


def listing(vault, allowed=None):
    return vault_trash.list_trashed(str(vault), allowed or [str(vault)])


def test_deleting_a_folder_records_what_it_held_and_the_listing_groups_those_files(vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    rows = listing(vault)
    assert sorted(r["original_path"] for r in rows) == ["Trip/a.md", "Trip/b.md", "Trip/photos/one.png", "Trip/photos/two.png"]
    assert {r["folder"] for r in rows} == {"Trip"}
    (summary,) = vault_trash_unit.summarize(str(vault), rows)
    assert summary["trash_dir"] == "Trip" and summary["original_path"] == "Trip" and summary["count"] == 4


def test_a_note_deleted_on_its_own_is_not_part_of_a_folder(vault):
    write(vault, "Loose/one.md")
    vault_write_delete.delete_note(ALL, "Loose/one")
    (row,) = listing(vault)
    assert "folder" not in row and vault_trash_unit.summarize(str(vault), [row]) == []


def test_a_note_deleted_later_into_a_folders_bin_directory_stays_loose(vault):
    """The old folder `Trip` is in the bin; a new `Trip` is made and one of its notes is deleted on its own: it lands in
    the same bin directory, and must not look like part of the first deletion."""
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    write(vault, "Trip/later.md")
    vault_write_delete.delete_note(ALL, "Trip/later")
    by_path = {r["original_path"]: r for r in listing(vault)}
    assert "folder" not in by_path["Trip/later.md"] and by_path["Trip/a.md"]["folder"] == "Trip"


def test_restoring_a_folder_puts_everything_back_where_it_was(vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    restored, skipped = vault_trash_unit.restore_folder(str(vault), [str(vault)], "Trip")
    assert sorted(restored) == ["Trip/a.md", "Trip/b.md", "Trip/photos/one.png", "Trip/photos/two.png"] and skipped == []
    assert (vault / "Trip" / "photos" / "two.png").read_text() == "photos/two.png"
    assert listing(vault) == [] and not (vault / ".trash" / ".trash-folders.json").exists()


def test_a_taken_spot_is_skipped_and_named_and_nothing_is_overwritten(vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    write(vault, "Trip/a.md", "a newer note")  # made since the folder was deleted
    restored, skipped = vault_trash_unit.restore_folder(str(vault), [str(vault)], "Trip")
    assert skipped == [{"path": "Trip/a.md", "reason": "already exists"}]
    assert len(restored) == 3 and (vault / "Trip" / "a.md").read_text() == "a newer note"
    (left,) = listing(vault)  # the skipped one is still in the bin, loose to be dealt with
    assert left["original_path"] == "Trip/a.md"


def test_files_already_restored_or_deleted_one_by_one_are_left_out_of_the_folder_restore(vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    assert vault_trash.restore(str(vault), [str(vault)], "Trip/a.md")[1] == "Trip/a.md"
    assert vault_trash.purge(str(vault), [str(vault)], "Trip/b.md") == ""
    restored, skipped = vault_trash_unit.restore_folder(str(vault), [str(vault)], "Trip")
    assert sorted(restored) == ["Trip/photos/one.png", "Trip/photos/two.png"] and skipped == []


def test_a_folder_deleted_twice_under_the_same_name_keeps_two_groups_with_their_own_places(vault):
    write(vault, "Stuff/one.md", "1")
    vault_write_delete.delete_folder(ALL, "Stuff")
    write(vault, "Stuff/two.md", "2")
    vault_write_delete.delete_folder(ALL, "Stuff")
    folders = vault_trash_unit.summarize(str(vault), listing(vault))
    assert len(folders) == 2 and {f["original_path"] for f in folders} == {"Stuff"} and len({f["trash_dir"] for f in folders}) == 2
    second = next(f["trash_dir"] for f in folders if f["trash_dir"] != "Stuff")
    restored, skipped = vault_trash_unit.restore_folder(str(vault), [str(vault)], second)
    assert restored == ["Stuff/two.md"] and skipped == [] and (vault / "Stuff" / "two.md").read_text() == "2"


def test_a_nested_folder_is_restored_to_its_own_path(vault):
    write(vault, "Projects/Old/x.md")
    vault_write_delete.delete_folder(ALL, "Projects/Old")
    (summary,) = vault_trash_unit.summarize(str(vault), listing(vault))
    assert summary["original_path"] == "Projects/Old"
    assert vault_trash_unit.restore_folder(str(vault), [str(vault)], summary["trash_dir"])[0] == ["Projects/Old/x.md"]


def test_a_folder_with_files_outside_the_personas_folders_restores_only_the_rest(vault):
    write(vault, "Shared/Open/a.md")
    write(vault, "Shared/Closed/b.md")
    vault_write_delete.delete_folder(ALL, "Shared")
    restored, skipped = vault_trash_unit.restore_folder(str(vault), [str(vault / "Shared" / "Open")], "Shared")
    assert restored == ["Shared/Open/a.md"]
    assert skipped == [{"path": "Shared/Closed/b.md", "reason": "outside this persona's folders"}]
    assert (vault / ".trash" / "Shared" / "Closed" / "b.md").exists()


def test_an_unknown_folder_is_not_found_and_an_old_bin_without_records_lists_loose_files(vault):
    assert vault_trash_unit.restore_folder(str(vault), [str(vault)], "Nope") == "__note_not_found__"
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    os.remove(vault / ".trash" / ".trash-folders.json")  # a folder deleted before the record existed
    rows = listing(vault)
    assert len(rows) == 4 and all("folder" not in r for r in rows)


def test_emptying_the_bin_removes_the_record_and_does_not_count_it(vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    assert vault_trash.purge_all(str(vault), [str(vault)]) == 4
    assert not (vault / ".trash" / ".trash-folders.json").exists()


def test_a_damaged_record_file_is_ignored_and_loses_nothing(vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    (vault / ".trash" / ".trash-folders.json").write_text("{not json")
    rows = listing(vault)
    assert len(rows) == 4 and all("folder" not in r for r in rows)


# -- the routes --------------------------------------------------------------


@pytest.fixture
def client(vault, tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return TestClient(create_app())


def test_the_listing_route_returns_folders_and_the_restore_route_says_what_it_skipped(client, vault):
    trip(vault)
    vault_write_delete.delete_folder(ALL, "Trip")
    body = client.get("/api/vault/trash", params={"persona": "samantha"}).json()
    assert len(body["items"]) == 4 and body["folders"][0]["count"] == 4 and body["folders"][0]["trash_dir"] == "Trip"
    write(vault, "Trip/a.md", "newer")
    r = client.post("/api/vault/trash/restore-folder", json={"path": "Trip", "persona": "samantha"})
    assert r.status_code == 200
    out = r.json()
    assert len(out["restored"]) == 3 and out["skipped"][0]["path"] == "Trip/a.md"
    assert out["detail"] == "Restored 3 of 4 files. Skipped 1: a.md."
    assert client.post("/api/vault/trash/restore-folder", json={"path": "Nope", "persona": "samantha"}).status_code == 404
