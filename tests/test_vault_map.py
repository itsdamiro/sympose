"""The vault map (docs/decisions/035): folder counts and definitions, tag counts, the folder-truncation
line, and that a scoped persona never reads a definition outside its own folders. Everything runs in a
temporary vault and settings file."""

import os

import pytest

from sympose import vault_map

ALL = {"name": "Samantha", "handle": "samantha", "vault_folders": ["*"]}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def put(vault, rel, text="Some words."):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_no_vault_or_no_notes_is_an_empty_map():
    assert vault_map.build(ALL) == ""


def test_a_note_that_cannot_have_a_definition_still_counts_toward_the_total(scratch):
    put(scratch, "Templates/Note template.md")  # `Templates` gets no folder line, but is still a real note

    text = vault_map.build(ALL)

    assert "1 notes." in text
    assert "Templates" not in text


def test_a_folder_and_its_count(scratch):
    for n in range(3):
        put(scratch, f"People/P{n}.md")

    text = vault_map.build(ALL)

    assert "3 notes in 1 top-level folders." in text
    assert "- People (3 notes)." in text


def test_a_folders_own_definition_note_does_not_count_toward_its_own_folder_line(scratch):
    put(scratch, "People/People.md", "# People\n\nNotes about people.\n\n## Template\n\n```yaml\n```\n")
    put(scratch, "People/Anna.md")

    text = vault_map.build(ALL)

    assert "2 notes in 1 top-level folders." in text  # the definition note is a real note, counted in the total
    assert "- People (1 note): Notes about people." in text  # but not toward its own folder's count


def test_no_definition_note_shows_the_count_with_no_purpose(scratch):
    put(scratch, "Movies/Up.md")

    assert "- Movies (1 note)." in vault_map.build(ALL)


def test_a_definition_with_no_purpose_paragraph_shows_the_count_only(scratch):
    put(scratch, "Movies/Movies.md", "# Movies\n\n## Template\n\n```yaml\n```\n")
    put(scratch, "Movies/Up.md")

    text = vault_map.build(ALL)

    assert "- Movies (1 note)." in text


def test_root_and_ignored_folders_count_toward_the_total_but_have_no_line(scratch):
    put(scratch, "Loose.md")
    put(scratch, "Templates/Note template.md")
    put(scratch, "People/Anna.md")

    text = vault_map.build(ALL)

    assert "3 notes in 1 top-level folders." in text
    assert "Templates" not in text
    assert "Loose" not in text


def test_folders_are_sorted_by_count_then_by_name(scratch):
    for n in range(3):
        put(scratch, f"People/P{n}.md")
    put(scratch, "Bin/Trash.md")
    put(scratch, "Movies/Up.md")

    text = vault_map.build(ALL)
    lines = [line for line in text.splitlines() if line.startswith("-")]

    assert lines == ["- People (3 notes).", "- Bin (1 note).", "- Movies (1 note)."]


def test_more_folders_than_the_cap_are_summarized(scratch, monkeypatch):
    monkeypatch.setattr(vault_map, "MAX_FOLDERS_SHOWN", 2)
    for name in ("Alpha", "Beta", "Gamma"):
        put(scratch, f"{name}/Note.md")

    text = vault_map.build(ALL)

    assert "(1 more folders not shown.)" in text
    assert "Gamma" not in text  # sorted by count then name; Alpha and Beta win the tie


def test_the_most_common_tags_are_listed_most_common_first(scratch):
    put(scratch, "A.md", "---\ntags: [x, y]\n---\n")
    put(scratch, "B.md", "---\ntags: [x]\n---\n")
    put(scratch, "C.md", "---\ntags: [z]\n---\n")

    text = vault_map.build(ALL)

    assert "Most common tags: x, y, z." in text or "Most common tags: x, z, y." in text
    assert text.split("Most common tags: ")[1].startswith("x")  # x (2 notes) before a 1-note tag


def test_no_tags_at_all_adds_no_tag_line(scratch):
    put(scratch, "People/Anna.md")

    assert "tags" not in vault_map.build(ALL).lower()


def test_a_scoped_persona_never_reads_a_definition_outside_its_folders(scratch):
    put(scratch, "Secret/Secret.md", "# Secret\n\nA private folder.\n\n## Template\n\n```yaml\n```\n")
    put(scratch, "Secret/Note.md")
    put(scratch, "People/Anna.md")
    scoped = {"vault_folders": ["People"]}

    text = vault_map.build(scoped)

    assert "Secret" not in text
    assert "1 notes in 1 top-level folders." in text


def test_a_persona_scoped_below_a_top_folder_cannot_read_its_definition(scratch):
    put(scratch, "People/People.md", "# People\n\nNotes about people.\n\n## Template\n\n```yaml\n```\n")
    put(scratch, "People/Sub/Anna.md")
    scoped = {"vault_folders": ["People/Sub"]}

    text = vault_map.build(scoped)

    assert "- People (1 note)." in text  # visible, but with no purpose: the definition is out of scope
    assert "Notes about people." not in text


def test_the_map_reflects_a_vault_change_and_is_not_served_stale(scratch):
    put(scratch, "People/Anna.md")
    first = vault_map.build(ALL)

    put(scratch, "People/Ben.md")

    assert "1 notes in 1 top-level folders." in first
    assert "2 notes in 1 top-level folders." in vault_map.build(ALL)
