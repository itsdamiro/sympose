"""`sympose vault --health` (docs/decisions/034): the four checks, the grouping of the report, and that nothing is
ever written. Everything runs in a temporary vault and settings file."""

import os

import pytest

from sympose import vault_health as vh
from sympose import vault_health_report as report
from sympose import vault_paths

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


def tree(vault):
    return {os.path.join(d, f): open(os.path.join(d, f), "rb").read() for d, _, files in os.walk(vault) for f in files}


def found(check, profile=ALL):
    scope, results = vh.scan(profile)
    return [f for c, fs in results if c.run is check for f in fs]


# --- empty notes ----------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["", "  \n\n", "---\n---\n", "---\n---", "﻿\n"])
def test_a_note_with_no_text_and_no_properties_is_empty(scratch, text):
    put(scratch, "Inbox/Empty.md", text)

    assert [f.note for f in found(vh.check_empty_notes)] == ["Inbox/Empty.md"]


@pytest.mark.parametrize("text", ["A word.", "# Heading\n", "---\nrole: boss\n---\n", "---\nrole: boss\n---\nText."])
def test_a_note_with_any_text_or_any_property_is_not_empty(scratch, text):
    put(scratch, "Inbox/Card.md", text)

    assert found(vh.check_empty_notes) == []


# --- titles ---------------------------------------------------------------------------------
def test_a_declared_title_that_is_not_the_file_name_is_reported(scratch):
    put(scratch, "People/Anna.md", "---\ntitle: Anna Ruiz\n---\nHi.")

    [finding] = found(vh.check_titles)

    assert finding.note == "People/Anna.md" and finding.folder == "People"
    assert finding.message == 'the title "Anna Ruiz" is not the file name'


def test_a_title_that_matches_the_file_name_ignoring_case_and_spacing_is_not_reported(scratch):
    put(scratch, "A/My note.md", "---\ntitle: My  Note\n---\nx")
    put(scratch, "A/Same.md", "---\nname: Same\n---\nx")

    assert found(vh.check_titles) == []


@pytest.mark.parametrize("front", ["", "title:\n", "title: ''\n", "title: [a, b]\n", "title: true\n", "aliases: [X]\n"])
def test_a_note_with_no_usable_title_falls_back_to_its_file_name_and_is_not_a_finding(scratch, front):
    put(scratch, "A/Plain.md", f"---\n{front}---\nx" if front else "x")

    assert found(vh.check_titles) == []


def test_the_name_property_is_the_title_when_there_is_no_title_property(scratch):
    put(scratch, "A/One.md", "---\nname: Other\n---\nx")

    assert [f.note for f in found(vh.check_titles)] == ["A/One.md"]


def test_an_unusable_title_does_not_block_a_usable_name(scratch):
    put(scratch, "A/One.md", "---\ntitle: [Amy, Bob]\nname: Other\n---\nx")

    [finding] = found(vh.check_titles)

    assert finding.note == "A/One.md" and finding.message == 'the title "Other" is not the file name'


def test_an_unquoted_date_title_is_compared_as_the_text_it_was_written_as(scratch):
    put(scratch, "Daily/2026-01-05.md", "---\ntitle: 2026-01-05\n---\nx")

    assert found(vh.check_titles) == []


def test_a_title_a_file_name_cannot_hold_is_reported_as_one_that_cannot_match(scratch):
    put(scratch, "A/Budget.md", "---\ntitle: 'Re: budget?'\n---\nx")
    put(scratch, "A/Long.md", "---\ntitle: " + "w" * 300 + "\n---\nx")

    messages = {f.note: f.message for f in found(vh.check_titles)}

    assert "cannot be one: a file name cannot hold ':'" in messages["A/Budget.md"]
    assert "cannot be one: it is too long" in messages["A/Long.md"] and len(messages["A/Long.md"]) < 150


# --- links ----------------------------------------------------------------------------------
def test_a_wikilink_to_no_note_is_reported_once_per_note_and_target(scratch):
    put(scratch, "A/Source.md", "[[Missing]] and [[Missing]] and [[Real]] and [[missing|again]].")
    put(scratch, "A/Real.md", "x")

    [finding] = found(vh.check_broken_links)

    assert finding.note == "A/Source.md" and finding.message == "links to [[Missing]], which is not a note"


def test_a_link_to_an_attachment_or_a_case_variant_of_a_note_is_not_broken(scratch):
    put(scratch, "A/Source.md", "![[photo.png]] [[real]] [[Real.md]]")
    put(scratch, "A/Real.md", "x")

    assert found(vh.check_broken_links) == []


def test_a_link_to_a_note_the_persona_cannot_see_is_not_broken(scratch):
    put(scratch, "Open/Source.md", "[[Hidden]]")
    put(scratch, "Closed/Hidden.md", "x")

    assert found(vh.check_broken_links, {**ALL, "vault_folders": ["Open"]}) == []
    assert [f.note for f in found(vh.check_broken_links)] == []


# --- other files ----------------------------------------------------------------------------
def test_a_file_that_is_not_a_note_or_an_attachment_is_clutter(scratch):
    for rel in ("A/list.txt", "A/old.markdown", "A/Shouting.MD", "A/LICENSE", "B/data.json", "top.docx"):
        put(scratch, rel)

    messages = {f.note: f.message for f in found(vh.check_other_files)}

    assert sorted(messages) == ["A/LICENSE", "A/Shouting.MD", "A/list.txt", "A/old.markdown", "B/data.json", "top.docx"]
    assert messages["A/list.txt"] == "is not a note (Sympose reads only .md files) or an attachment (.txt)"
    assert "(no extension)" in messages["A/LICENSE"]


def test_notes_attachments_obsidians_own_files_and_hidden_things_are_not_clutter(scratch):
    for rel in ("A/Note.md", "A/photo.PNG", "A/paper.pdf", "A/Board.canvas", "A/Table.base", "A/.DS_Store", ".hidden/x.txt",
                ".obsidian/app.json", "Attachments/notes.txt", ".git/HEAD.txt", "A/.cache/y.txt"):
        put(scratch, rel)

    assert found(vh.check_other_files) == []


def test_only_the_folders_a_persona_may_read_are_searched_for_clutter(scratch):
    put(scratch, "Open/a.txt")
    put(scratch, "Closed/b.txt")

    assert [f.note for f in found(vh.check_other_files, {**ALL, "vault_folders": ["Open"]})] == ["Open/a.txt"]


def test_clutter_is_listed_after_the_problems_and_is_not_one(scratch):
    put(scratch, "A/list.txt")
    put(scratch, "A/Empty.md", "")

    scope, results = vh.scan(ALL)
    text = "\n".join(report.render(scope, results))

    assert report.problem_count(results) == 1 and "1 problem(s) found." in text
    assert text.index("Empty notes") < text.index("Other files (clutter) (1)")
    assert "\n  A: 1 file\n" in text.split("Other files")[1]  # files, not "of N notes": a stray file is not a note


# --- folders due ----------------------------------------------------------------------------
def test_a_folder_with_enough_notes_and_no_definition_is_offered_with_the_command(scratch):
    for n in range(5):
        put(scratch, f"My People/P{n}.md", f"---\nrole: x\n---\nText {n}.")

    [finding] = found(vh.check_due_folders)

    assert "5 notes and no definition" in finding.message
    assert "`sympose vault --draft 'My People'`" in finding.message


def test_a_due_folder_is_reported_without_a_confusing_of_n_notes_header(scratch):
    for n in range(5):
        put(scratch, f"People/P{n}.md", f"---\nrole: x\n---\nText {n}.")

    scope, results = vh.scan(ALL)
    text = "\n".join(report.render(scope, results))

    assert "  People: 5 notes and no definition" in text
    assert "of 5 notes" not in text and "1 file" not in text.split("Folders due")[1]


# --- the report -----------------------------------------------------------------------------
def test_a_folder_where_every_note_is_affected_is_one_line_with_the_first_three_notes(scratch):
    for n in range(6):
        put(scratch, f"Daily/D{n}.md", f"---\ntitle: Day {n}\n---\nx")
    put(scratch, "Daily/Fine.md", "x")

    scope, results = vh.scan(ALL)
    text = "\n".join(report.render(scope, results))

    assert "Titles that are not the file name (6)" in text
    assert "  Daily: 6 of 7 notes" in text
    assert text.count('the title "Day') == 3 and "    and 3 more" in text


def test_a_root_note_is_listed_under_the_vault_root(scratch):
    put(scratch, "Loose.md", "")

    scope, results = vh.scan(ALL)

    assert "  (vault root): 1 of 1 notes" in "\n".join(report.render(scope, results))


def test_an_offer_is_not_a_problem_and_is_listed_after_the_problems(scratch):
    for n in range(5):
        put(scratch, f"People/P{n}.md", f"---\nrole: x\n---\nText {n}.")
    put(scratch, "Inbox/Empty.md", "")

    scope, results = vh.scan(ALL)
    text = "\n".join(report.render(scope, results))

    assert report.problem_count(results) == 1 and "1 problem(s) found." in text
    assert text.index("Empty notes") < text.index("Folders due a definition")


def test_a_vault_with_nothing_wrong_says_so_and_a_missing_vault_gives_none(scratch, monkeypatch):
    put(scratch, "A/Fine.md", "Words.")
    scope, results = vh.scan(ALL)

    text = "\n".join(report.render(scope, results))
    assert "Nothing wrong found." in text and "(0)" not in text and "Empty notes" not in text
    monkeypatch.setattr(vault_paths, "resolve_sandbox", lambda profile: None)
    assert vh.scan(ALL) is None


def test_scanning_and_rendering_write_nothing(scratch):
    put(scratch, "A/Empty.md", "")
    put(scratch, "A/T.md", "---\ntitle: Other\n---\n[[Nowhere]]")
    for n in range(5):
        put(scratch, f"People/P{n}.md", f"---\nrole: x\n---\nText {n}.")
    before = tree(scratch)

    scope, results = vh.scan(ALL)
    report.render(scope, results)

    assert tree(scratch) == before
