"""Links whose folder no longer matches (docs/decisions/084) and the rewrite that repairs one."""

import os

import pytest

from sympose import vault_health_links as links
from sympose.vault_write_relink import retarget_link


def note(rel, text=""):
    return {"rel_path": rel, "file_name": os.path.basename(rel), "full_content": text}


def stale(*notes):
    return links.stale_folder_links(list(notes))


def test_a_qualifier_that_names_no_folder_of_the_note_is_stale_and_points_at_its_folder():
    found = stale(note("Ideas/Idea.md"), note("Log/Day.md", "[[Projects/Idea]]"))

    assert [(s, o, n) for s, _, o, n in found] == [("Log/Day.md", "Projects/Idea", "Ideas/Idea")]


@pytest.mark.parametrize("link", ["Ideas/Idea", "ideas/idea", "Ideas/Idea.md", "Idea", "Idea.md", "Idea#Part", "Ideas/Idea|alias", "/Ideas/Idea"])
def test_a_link_that_finds_its_note_is_not_stale(link):
    assert stale(note("Ideas/Idea.md"), note("Log/Day.md", f"[[{link}]]")) == []


def test_a_qualifier_that_is_the_end_of_a_deeper_path_is_not_stale():
    assert stale(note("Work/Projects/Idea.md"), note("Log/Day.md", "[[Projects/Idea]]")) == []


def test_the_qualifier_keeps_as_many_folders_as_the_link_had():
    deep = note("Archive/2020/Ideas/Idea.md")

    assert stale(deep, note("L.md", "[[Old/Idea]]"))[0][3] == "Ideas/Idea"
    assert stale(deep, note("L.md", "[[Old/Folder/Idea]]"))[0][3] == "2020/Ideas/Idea"
    assert stale(deep, note("L.md", "[[A/B/C/D/Idea]]"))[0][3] == "Archive/2020/Ideas/Idea"
    assert stale(note("Idea.md"), note("L.md", "[[Old/Idea]]"))[0][3] == "Idea"


def test_several_notes_of_the_name_get_no_target_and_say_how_many():
    found = stale(note("A/Idea.md"), note("B/Idea.md"), note("L.md", "[[Old/Idea]]"))

    assert len(found) == 1 and found[0][3] is None and "2 notes have that name" in found[0][1]


def test_a_name_no_note_has_and_an_attachment_are_left_to_other_checks():
    assert stale(note("L.md", "[[Old/Missing]] ![[Old/pic.png]] [[Old/doc.pdf]]"), note("A/pic.png.md")) == []


def test_one_finding_per_link_target_per_note_and_a_dotted_name_is_kept_whole():
    found = stale(note("Tech/Node.js.md"), note("L.md", "[[Old/Node.js]] [[Old/Node.js]] [[Old/Node.js.md]]"))

    assert [(o, n) for _, _, o, n in found] == [("Old/Node.js", "Tech/Node.js"), ("Old/Node.js.md", "Tech/Node.js.md")]


def test_a_note_the_persona_cannot_read_is_not_a_target():
    assert stale(note("L.md", "[[Old/Idea]]")) == []


# --- retarget_link --------------------------------------------------------------------------
@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return tmp_path


ALL = {"handle": "samantha", "vault_folders": ["*"]}


def test_only_the_exact_target_is_rewritten_and_heading_alias_and_embed_stay(vault):
    (vault / "L.md").write_bytes(b"[[Old/Idea]] [[Old/Idea#H|a]] ![[Old/Idea]] [[Old/Idea2]] [[Idea]] `x`\r\nend\r\n")

    assert retarget_link(ALL, "L.md", "Old/Idea", "New/Idea") == 3

    assert (vault / "L.md").read_bytes() == b"[[New/Idea]] [[New/Idea#H|a]] ![[New/Idea]] [[Old/Idea2]] [[Idea]] `x`\r\nend\r\n"


def test_a_link_that_is_not_there_changes_nothing_and_a_missing_or_outside_note_is_none(vault, tmp_path):
    (vault / "L.md").write_text("[[Other]]", encoding="utf-8")
    before = os.stat(vault / "L.md").st_mtime_ns

    assert retarget_link(ALL, "L.md", "Old/Idea", "New/Idea") == 0
    assert os.stat(vault / "L.md").st_mtime_ns == before
    assert retarget_link(ALL, "Nope.md", "a/b", "c/b") is None
    assert retarget_link(ALL, "../outside.md", "a/b", "c/b") is None


def test_a_note_the_persona_may_not_write_is_not_touched(vault):
    (vault / "A").mkdir()
    (vault / "B").mkdir()
    (vault / "B" / "L.md").write_text("[[Old/Idea]]", encoding="utf-8")

    assert retarget_link({"handle": "x", "vault_folders": ["A"]}, "B/L.md", "Old/Idea", "New/Idea") is None
    assert (vault / "B" / "L.md").read_text(encoding="utf-8") == "[[Old/Idea]]"
