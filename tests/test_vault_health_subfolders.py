"""The observation for a `subfolders` entry whose folder is gone (docs/decisions/090): never a problem, only said, and
nothing is written. Everything runs in a temporary vault."""

import os

import pytest

from sympose import vault_health as vh
from sympose import vault_health_report as report

ALL = {"name": "Samantha", "handle": "samantha", "vault_folders": ["*"]}
PROJECTS = (
    "---\nsubfolders:\n  sympose:\n    accent: '#7c3aed'\n  stylo:\n    icon: rocket\n  gone:\n    accent: '#be123c'\n"
    "  sympose/old:\n    icon: rocket\n---\n# Projects\n"
)


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


def found(profile=ALL):
    scope, results = vh.scan(profile)
    return [f for c, fs in results if c.run is vh.check_subfolder_looks for f in fs]


def test_an_entry_for_a_folder_that_is_gone_is_said_and_the_others_are_not(scratch):
    put(scratch, "Projects/Projects.md", PROJECTS)
    put(scratch, "Projects/sympose/Plan.md")
    put(scratch, "Projects/stylo/Plan.md")

    findings = found()

    assert [(f.folder, f.note) for f in findings] == [("Projects", "Projects/Projects.md")] * 2
    assert [f.message for f in findings] == [
        "gives `gone` a colour or icon in `subfolders`, but there is no folder `Projects/gone`",
        "gives `sympose/old` a colour or icon in `subfolders`, but there is no folder `Projects/sympose/old`",
    ]


def test_an_empty_folder_counts_as_there(scratch):
    put(scratch, "Projects/Projects.md", PROJECTS)
    for folder in ("sympose", "stylo", "gone", "sympose/old"):
        os.makedirs(os.path.join(scratch, "Projects", *folder.split("/")))
    assert found() == []


def test_a_vault_with_no_subfolder_entries_has_nothing_to_say(scratch):
    put(scratch, "Projects/Projects.md", "---\ntype: folder\n---\n# Projects\n")
    assert found() == []


def test_it_is_an_observation_not_a_problem_and_nothing_is_written(scratch):
    put(scratch, "Projects/Projects.md", PROJECTS)
    before = open(os.path.join(scratch, "Projects/Projects.md"), "rb").read()

    scope, results = vh.scan(ALL)
    text = "\n".join(report.render(scope, results))

    assert report.problem_count(results) == 0
    assert "Subfolder colours and icons for a folder that is gone" in text
    assert open(os.path.join(scratch, "Projects/Projects.md"), "rb").read() == before
