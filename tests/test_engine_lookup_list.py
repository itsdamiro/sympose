"""`list_notes`, the third tool of `ask` (docs/decisions/040, amendment of 2026-10-02): the notes of one folder,
numbered in a stated order, inside the persona's scope, and only for a cloud model that may receive notes."""

import os

import pytest

from sympose import settings_store
from sympose.engine import lookup_list, lookup_tools

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
ALL = {"vault_folders": ["*"]}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def put(vault, rel, text="# note\nbody"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_the_notes_of_a_folder_are_numbered_alphabetically_ignoring_case_and_say_so(scratch):
    for name in ("zulu", "Alpha", "bravo", "Charlie"):
        put(scratch, f"Movies/{name}.md")

    result = lookup_list.list_notes(ALL, LOCAL, "Movies")

    lines = result.text.splitlines()
    assert "alphabetical order by file name" in lines[0] and "4" in lines[0]
    assert [line.split(" (")[0] for line in lines[1:5]] == ["1. Alpha", "2. bravo", "3. Charlie", "4. zulu"]
    assert "(Movies/Charlie.md)" in lines[3]
    assert result.lookup == {"folder": "Movies", "found": 4}


def test_a_note_is_listed_by_its_title_when_it_has_one(scratch):
    put(scratch, "Movies/300.md", "---\ntitle: Three Hundred\n---\nbody")

    assert "1. Three Hundred (Movies/300.md)" in lookup_list.list_notes(ALL, LOCAL, "Movies").text


def test_a_folder_name_is_read_in_any_case_and_with_slashes(scratch):
    put(scratch, "Movies/300.md")

    assert "300" in lookup_list.list_notes(ALL, LOCAL, "/movies/").text


def test_only_the_notes_directly_in_the_folder_are_numbered_and_its_folders_are_named(scratch):
    put(scratch, "Projects/Atlas.md")
    put(scratch, "Projects/Archive/Old.md")
    put(scratch, "Projects/Archive/Older.md")

    text = lookup_list.list_notes(ALL, LOCAL, "Projects").text

    assert "1. Atlas" in text and "Old" not in text.split("Folders inside it")[0]
    assert "Folders inside it: Archive (2 notes)" in text


def test_an_empty_folder_name_is_the_top_of_the_vault(scratch):
    put(scratch, "Inbox.md")
    put(scratch, "Movies/300.md")

    result = lookup_tools.run(ALL, LOCAL, "list_notes", '{"folder": ""}')

    assert "the top of the vault" in result.text and "1. Inbox" in result.text and "Movies (1 notes)" in result.text


def test_a_call_with_no_folder_at_all_lists_the_top_too(scratch):
    put(scratch, "Inbox.md")

    assert "1. Inbox" in lookup_tools.run(ALL, LOCAL, "list_notes", "{}").text


def test_a_folder_that_is_not_there_is_not_found(scratch):
    put(scratch, "Movies/300.md")

    result = lookup_list.list_notes(ALL, LOCAL, "Music")

    assert "No folder called 'Music'" in result.text and result.lookup["found"] == 0


def test_a_folder_outside_the_personas_folders_is_not_found_and_not_told_apart(scratch):
    put(scratch, "Projects/Atlas.md")
    put(scratch, "Private/Diary.md")

    result = lookup_list.list_notes({"vault_folders": ["Projects"]}, LOCAL, "Private")

    assert "Diary" not in result.text and "No folder called" in result.text


def test_a_long_folder_is_cut_at_a_hundred_names_and_the_rest_counted(scratch):
    for n in range(130):
        put(scratch, f"Big/note{n:03d}.md")

    text = lookup_list.list_notes(ALL, LOCAL, "Big").text

    assert "100. note099" in text and "101." not in text and "...and 30 more" in text


def test_a_cloud_model_that_may_not_receive_notes_gets_no_names(scratch):
    put(scratch, "Movies/300.md")

    result = lookup_list.list_notes(ALL, CLOUD, "Movies")

    assert "300" not in result.text and "/share" in result.text
    assert result.withheld == {"notes": 1} and result.lookup["found"] == 0


def test_a_cloud_model_that_may_receive_notes_gets_the_names(scratch):
    put(scratch, "Movies/300.md")
    settings_store.set("cloud_share", ["notes"])

    assert "1. 300 (Movies/300.md)" in lookup_list.list_notes(ALL, CLOUD, "Movies").text


def test_a_call_through_run_is_recorded_with_its_tool_and_folder(scratch):
    put(scratch, "Movies/300.md")

    result = lookup_tools.run(ALL, LOCAL, "list_notes", '{"folder": "Movies"}')

    assert result.lookup == {"tool": "list_notes", "folder": "Movies", "found": 1}


def test_a_folder_that_is_not_text_is_a_result_the_model_can_correct(scratch):
    result = lookup_tools.run(ALL, LOCAL, "list_notes", '{"folder": 5}')

    assert "could not be read" in result.text


def test_a_listing_names_the_properties_its_notes_have_so_a_filter_is_known_to_exist(scratch):
    put(scratch, "Films/Dune.md", "---\nwatched: no\nyear: 2021\n---\nbody")
    put(scratch, "Films/Heat.md", "---\nwatched: yes\n---\nbody")

    text = lookup_list.list_notes(ALL, LOCAL, "Films").text

    assert "Properties these notes have: watched (2), year (1)." in text and "find_notes" in text


def test_a_listing_names_no_properties_when_the_notes_have_none(scratch):
    put(scratch, "Films/Dune.md")

    assert "Properties these notes have" not in lookup_list.list_notes(ALL, LOCAL, "Films").text


def test_a_cloud_model_that_may_receive_notes_but_not_properties_is_not_told_their_names(scratch):
    put(scratch, "Films/Dune.md", "---\nwatched: no\n---\nbody")
    settings_store.set("cloud_share", ["notes"])

    text = lookup_list.list_notes(ALL, CLOUD, "Films").text

    assert "1. Dune" in text and "watched" not in text
