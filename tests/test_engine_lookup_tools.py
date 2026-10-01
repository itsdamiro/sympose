"""The two tools a persona has when it looks up notes itself (docs/decisions/040): what `search_notes` and
`open_note` return from a real (temporary) vault, that a name outside the persona's scope finds nothing,
that a cloud model is told what was held back instead of being sent it, and that a tool never raises."""

import os

import pytest

from sympose import settings_store
from sympose.engine import lookup_tools

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


def put(vault, rel, text=""):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


ATLAS = "---\nstatus: active\n---\n# Atlas\nWe chose SQLite for the Atlas prototype database."


def test_a_search_returns_the_passage_with_its_note(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    result = lookup_tools.search_notes(ALL, LOCAL, "Atlas database")

    assert "SQLite" in result.text and "Projects/Atlas.md" in result.text
    assert result.lookup == {"found": 1}
    assert {hit["rel_path"] for hit in result.hits} == {"Projects/Atlas.md"}
    assert all(hit["via"] == "search" for hit in result.hits if hit["kind"] == "text")


def test_a_search_brings_the_notes_properties_as_a_turns_own_search_does(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    result = lookup_tools.search_notes(ALL, LOCAL, "Atlas database")

    assert "status: active" in result.text


def test_a_search_that_finds_nothing_says_so(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    result = lookup_tools.search_notes(ALL, LOCAL, "zebra migration")

    assert "found no notes" in result.text
    assert result.hits == [] and result.lookup == {"found": 0}


def test_a_search_with_no_vault_finds_nothing(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")

    assert lookup_tools.search_notes(ALL, LOCAL, "Atlas").hits == []


def test_a_cloud_model_is_told_the_notes_were_held_back_and_gets_none_of_them(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    result = lookup_tools.search_notes(ALL, CLOUD, "Atlas database")

    assert "SQLite" not in result.text and "active" not in result.text
    assert "/share" in result.text and "has nothing" in result.text  # ("Don't say the vault has nothing on it")
    assert result.hits == [] and result.withheld["notes"] >= 1 and result.lookup == {"found": 0}


def test_a_cloud_model_gets_the_notes_when_the_user_approved_them_but_not_the_properties(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)
    settings_store.set("cloud_share", ["notes"])

    result = lookup_tools.search_notes(ALL, CLOUD, "Atlas database")

    assert "SQLite" in result.text and "status: active" not in result.text
    assert result.withheld == {"properties": 1} and "/share" in result.text


def test_a_note_is_opened_by_its_path_with_or_without_the_extension_in_any_case(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    for name in ("Projects/Atlas.md", "projects/atlas", "/Projects/Atlas.md", " Projects/Atlas "):
        result = lookup_tools.open_note(ALL, LOCAL, name)
        assert "We chose SQLite" in result.text, name
        assert result.lookup == {"found": 1}
        assert result.hits[0]["via"] == "opened"


def test_a_note_is_opened_by_its_title_or_file_name_when_only_one_has_it(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)
    put(scratch, "People/Priya.md", "---\ntitle: Priya Shah\n---\nA colleague.")

    assert "We chose SQLite" in lookup_tools.open_note(ALL, LOCAL, "Atlas").text
    assert "A colleague" in lookup_tools.open_note(ALL, LOCAL, "Priya Shah").text


def test_a_name_shared_by_two_notes_opens_neither(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)
    put(scratch, "Archive/Atlas.md", "an old one")

    result = lookup_tools.open_note(ALL, LOCAL, "Atlas")

    assert "No note called" in result.text and result.hits == []


def test_a_note_outside_the_personas_folders_is_not_found(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)
    put(scratch, "People/Priya.md", "A colleague, private.")
    persona = {"vault_folders": ["Projects"]}

    for name in ("People/Priya.md", "Priya", "../People/Priya.md"):
        result = lookup_tools.open_note(persona, LOCAL, name)
        assert "private" not in result.text and result.hits == [], name
    assert "We chose SQLite" in lookup_tools.open_note(persona, LOCAL, "Atlas").text


@pytest.mark.parametrize("name", ["../secret.md", "/etc/passwd", "..", "Projects/../../secret.md", "Projects"])
def test_a_path_that_leaves_the_vault_or_is_not_a_note_finds_nothing(scratch, name):
    put(scratch, "Projects/Atlas.md", ATLAS)
    with open(os.path.join(os.path.dirname(scratch), "secret.md"), "w") as f:
        f.write("outside the vault")

    result = lookup_tools.open_note(ALL, LOCAL, name)

    assert "outside the vault" not in result.text and result.hits == []


def test_a_link_to_a_file_outside_the_vault_is_not_a_note_the_tool_can_open(scratch):
    outside = os.path.join(os.path.dirname(scratch), "secret.md")
    with open(outside, "w") as f:
        f.write("outside the vault")
    os.symlink(outside, os.path.join(scratch, "Linked.md"))

    result = lookup_tools.open_note(ALL, LOCAL, "Linked.md")

    assert "outside the vault" not in result.text


def test_an_empty_note_is_shown_as_empty(scratch):
    put(scratch, "Ideas.md", "---\naliases: [Sparks]\n---\n")

    result = lookup_tools.open_note(ALL, LOCAL, "Ideas")

    assert "empty" in result.text and "Sparks" in result.text


def test_a_long_note_is_cut_with_a_marker(scratch):
    put(scratch, "Long.md", "word " * (lookup_tools.MAX_NOTE_CHARS // 4))

    text = lookup_tools.open_note(ALL, LOCAL, "Long").text

    assert "the rest was left out" in text and len(text) < lookup_tools.MAX_NOTE_CHARS + 400


def test_opening_a_note_a_cloud_model_may_not_have_says_so_and_sends_nothing(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    result = lookup_tools.open_note(ALL, CLOUD, "Atlas")

    assert "SQLite" not in result.text and "/share" in result.text and result.hits == []


def test_a_note_found_through_open_carries_its_connections(scratch):
    put(scratch, "Projects/Atlas.md", "# Atlas\nSee [[Priya]].")
    put(scratch, "People/Priya.md", "A colleague.")

    assert "Priya" in lookup_tools.open_note(ALL, LOCAL, "Atlas").text.split("Connected to")[-1]


def test_run_gives_the_model_the_result_and_the_record_the_call(scratch):
    put(scratch, "Projects/Atlas.md", ATLAS)

    searched = lookup_tools.run(ALL, LOCAL, "search_notes", '{"query": "Atlas database"}')
    opened = lookup_tools.run(ALL, LOCAL, "open_note", {"path": "Atlas"})

    assert searched.lookup == {"tool": "search_notes", "query": "Atlas database", "found": 1}
    assert opened.lookup == {"tool": "open_note", "path": "Atlas", "found": 1}


@pytest.mark.parametrize("arguments", ["", "{}", "not json", '{"query": 3}', '{"query": "  "}', "[1]", None, '{"path": "x"}'])
def test_unreadable_arguments_are_a_result_the_model_can_answer_never_an_exception(scratch, arguments):
    result = lookup_tools.run(ALL, LOCAL, "search_notes", arguments)

    assert "could not be read" in result.text and result.hits == []
    assert result.lookup == {"tool": "search_notes", "found": 0}


def test_an_unknown_tool_is_a_result_too(scratch):
    result = lookup_tools.run(ALL, LOCAL, "delete_note", '{"path": "Atlas"}')

    assert "no tool called delete_note" in result.text and "search_notes" in result.text and "open_note" in result.text and "list_notes" in result.text


def test_the_tools_are_read_only_and_named_as_the_engine_runs_them():
    names = [tool["function"]["name"] for tool in lookup_tools.TOOLS]

    assert names == ["search_notes", "open_note", "list_notes"]
    assert all(tool["function"]["parameters"]["required"] for tool in lookup_tools.TOOLS)
