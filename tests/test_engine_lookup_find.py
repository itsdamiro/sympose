"""`find_notes`, the fourth tool of `ask` (docs/decisions/058): the notes matching filters on tags, properties,
links, folder and text, only the matches returned, inside the persona's scope, and gated for a cloud model."""

import os
import re

import pytest

from sympose import settings_store
from sympose.engine import lookup_find, lookup_tools

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


def films(vault):
    put(vault, "Films/Dune.md", "---\nwatched: no\ntags: [scifi, favourite]\n---\nSand and spice. See [[Arrival]].")
    put(vault, "Films/Arrival.md", "---\nwatched: yes\ntags: [scifi]\n---\nLanguage and time.")
    put(vault, "Films/Heat.md", "---\nwatched: no\ntags: crime\n---\nA heist film.")
    put(vault, "Notes/Plan.md", "---\nstatus: active\ntags: [idea/new]\n---\nWatch Dune this weekend. Mentions backups too.")


def find(model=LOCAL, **filters):
    return lookup_find.find_notes(ALL, model, filters)


def names(result):
    return [re.sub(r"^\d+\. ", "", line).split(" (")[0] for line in result.text.splitlines() if re.match(r"\d+\. ", line)]


def test_a_tag_finds_the_notes_that_have_it_and_counts_them(scratch):
    films(scratch)

    result = find(tag="scifi")

    assert result.text.startswith("2 notes match") and names(result) == ["Arrival", "Dune"]
    assert result.lookup == {"filters": ["tag"], "found": 2}


def test_a_tag_is_read_without_the_hash_in_any_case_and_a_nested_tag_matches_its_parent(scratch):
    films(scratch)

    assert names(find(tag="#SciFi")) == ["Arrival", "Dune"]
    assert names(find(tag="idea")) == ["Plan"]


def test_a_property_value_finds_notes_and_shows_the_value(scratch):
    films(scratch)

    result = find(property="watched", value="no")

    assert names(result) == ["Dune", "Heat"]
    assert "(Films/Dune.md), watched: false" in result.text


def test_yes_and_no_are_the_booleans_they_are_read_as(scratch):
    films(scratch)

    assert names(find(property="watched", value="yes")) == ["Arrival"]
    assert names(find(property="watched", value="false")) == ["Dune", "Heat"]


def test_a_property_alone_finds_every_note_that_has_it(scratch):
    films(scratch)

    assert names(find(property="status")) == ["Plan"]


def test_an_entry_of_a_list_property_matches(scratch):
    films(scratch)

    assert names(find(property="tags", value="favourite")) == ["Dune"]


def test_links_to_finds_the_notes_that_link_to_a_note_and_linked_from_the_ones_it_links_to(scratch):
    films(scratch)

    assert names(find(links_to="Arrival")) == ["Dune"]
    assert names(find(linked_from="Dune")) == ["Arrival"]


def test_a_note_that_is_not_there_is_not_found(scratch):
    films(scratch)

    assert "No note called 'Nothing'" in find(links_to="Nothing").text


def test_text_finds_the_notes_that_contain_it_exactly_ignoring_case(scratch):
    films(scratch)

    result = find(text="BACKUPS")

    assert names(result) == ["Plan"] and result.lookup["found"] == 1


def test_a_folder_limits_the_others_and_filters_are_combined(scratch):
    films(scratch)

    assert names(find(folder="Films", tag="scifi", property="watched", value="no")) == ["Dune"]
    assert "No notes match" in find(folder="Notes", tag="scifi").text


def test_a_filter_that_matches_nothing_says_so(scratch):
    films(scratch)

    result = find(tag="western")

    assert result.text.startswith("No notes match") and result.lookup["found"] == 0


def test_the_notes_come_alphabetically_by_file_name_and_a_long_list_is_cut(scratch):
    for n in range(130):
        put(scratch, f"Big/note{n:03d}.md", "---\ntags: bulk\n---\nx")

    result = find(tag="bulk")

    assert result.text.startswith("130 notes match") and "100. note099" in result.text
    assert "101." not in result.text and "...and 30 more" in result.text


def test_a_note_outside_the_personas_folders_is_never_matched(scratch):
    films(scratch)
    put(scratch, "Private/Diary.md", "---\ntags: scifi\n---\nsecret")

    result = lookup_find.find_notes({"vault_folders": ["Films"]}, LOCAL, {"tag": "scifi"})

    assert "Diary" not in result.text and names(result) == ["Arrival", "Dune"]


def test_a_cloud_model_that_may_not_receive_notes_gets_no_names(scratch):
    films(scratch)

    result = find(model=CLOUD, text="Sand")

    assert "Dune" not in result.text and "/share" in result.text
    assert result.withheld == {"notes": 1} and result.lookup["found"] == 0


def test_a_filter_on_a_property_or_tag_needs_properties_allowed_as_well(scratch):
    films(scratch)
    settings_store.set("cloud_share", ["notes"])

    assert names(find(model=CLOUD, text="Sand")) == ["Dune"]  # notes alone are enough for a text filter
    held = find(model=CLOUD, tag="scifi")
    assert "Dune" not in held.text and held.withheld == {"properties": 2}

    settings_store.set("cloud_share", ["notes", "properties"])
    assert names(find(model=CLOUD, tag="scifi")) == ["Arrival", "Dune"]


def test_through_run_the_call_is_recorded_with_its_filters_and_never_its_values(scratch):
    films(scratch)

    result = lookup_tools.run(ALL, LOCAL, "find_notes", '{"tag": "scifi", "folder": "Films"}')

    assert result.lookup == {"tool": "find_notes", "filters": ["folder", "tag"], "found": 2}


@pytest.mark.parametrize("raw", ["{}", '{"tag": ""}', '{"tag": 5}', "not json", '{"value": "no"}'])
def test_arguments_that_give_no_usable_filter_are_a_result_the_model_can_correct(scratch, raw):
    result = lookup_tools.run(ALL, LOCAL, "find_notes", raw)

    assert result.hits == [] and result.lookup["found"] == 0
    assert "filter" in result.text or "property" in result.text


def test_a_result_names_the_properties_its_notes_have_unless_one_was_already_asked_for(scratch):
    films(scratch)

    assert "Properties these notes have: tags (3), watched (3)." in find(folder="Films").text
    assert "Properties these notes have" not in find(folder="Films", property="watched").text


def test_a_cloud_model_that_may_not_receive_properties_is_not_told_their_names(scratch):
    films(scratch)
    settings_store.set("cloud_share", ["notes"])

    assert "Properties these notes have" not in find(model=CLOUD, folder="Films").text
