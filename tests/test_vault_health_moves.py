"""The two observations a folder move or merge can leave behind (docs/decisions/074): a note named after a folder that is
no longer top-level, and a numbered twin beside its original. Observations: never a problem, and nothing is written."""

import os

import pytest

from sympose import vault_health as vh
from sympose import vault_health_report as report

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


def found(check):
    _, results = vh.scan(ALL)
    return [f for c, fs in results if c.run is check for f in fs]


def test_a_note_named_after_its_folder_below_the_top_is_reported_as_a_description_that_stopped_applying(scratch):
    put(scratch, "Projects/Garden/Garden.md")

    [finding] = found(vh.check_stale_definitions)

    assert finding.note == "Projects/Garden/Garden.md" and finding.folder == "Projects"
    assert "`Garden` is not a top-level folder" in finding.message


@pytest.mark.parametrize("rel", ["Garden/Garden.md", "Projects/Garden/Rose.md", "Projects/Garden.md", "Garden.md"])
def test_a_real_definition_and_other_notes_are_not_reported(scratch, rel):
    put(scratch, rel)

    assert found(vh.check_stale_definitions) == []


def test_the_name_is_compared_ignoring_case(scratch):
    put(scratch, "Projects/Garden/garden.md")

    assert [f.note for f in found(vh.check_stale_definitions)] == ["Projects/Garden/garden.md"]


def test_a_numbered_note_beside_its_original_is_a_twin(scratch):
    put(scratch, "People/Anna.md")
    put(scratch, "People/Anna (2).md")
    put(scratch, "People/Anna (13).md")

    twins = found(vh.check_numbered_twins)

    assert sorted(f.note for f in twins) == ["People/Anna (13).md", "People/Anna (2).md"]
    assert all("`Anna.md`" in f.message for f in twins)


def test_a_numbered_note_with_no_original_in_its_folder_is_not_a_twin(scratch):
    put(scratch, "People/Anna (2).md")
    put(scratch, "Other/Anna.md")  # an original in another folder does not count
    put(scratch, "People/Report (final).md")  # parentheses that are not a number
    put(scratch, "People/Report.md")

    assert found(vh.check_numbered_twins) == []


def test_a_number_below_two_is_not_a_merge_twin(scratch):
    put(scratch, "People/Meeting.md")
    put(scratch, "People/Meeting (1).md")
    put(scratch, "People/Meeting (0).md")

    assert found(vh.check_numbered_twins) == []


def test_the_original_is_found_whatever_its_case(scratch):
    put(scratch, "People/anna.md")
    put(scratch, "People/Anna (2).md")

    assert [f.note for f in found(vh.check_numbered_twins)] == ["People/Anna (2).md"]


def test_both_are_observations_so_they_are_no_problem_and_come_after_the_problems(scratch):
    put(scratch, "Projects/Garden/Garden.md")
    put(scratch, "People/Anna.md")
    put(scratch, "People/Anna (2).md")
    put(scratch, "People/Empty.md", "")

    scope, results = vh.scan(ALL)
    text = "\n".join(report.render(scope, results))

    assert report.problem_count(results) == 1 and "1 problem(s) found." in text
    assert text.index("Empty notes") < text.index("Folder notes inside sub-folders") < text.index("Possible duplicate notes (name (2))")


def test_looking_changes_nothing(scratch):
    put(scratch, "Projects/Garden/Garden.md")
    put(scratch, "People/Anna.md")
    put(scratch, "People/Anna (2).md")
    before = {os.path.join(d, f): open(os.path.join(d, f), "rb").read() for d, _, files in os.walk(scratch) for f in files}

    scope, results = vh.scan(ALL)
    report.render(scope, results)

    assert {os.path.join(d, f): open(os.path.join(d, f), "rb").read() for d, _, files in os.walk(scratch) for f in files} == before
