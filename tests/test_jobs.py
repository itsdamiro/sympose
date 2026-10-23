"""A persona's job files (docs/decisions/091): read from `<persona>/jobs/`, a bad file still listed with its problem,
and nothing outside the folder reachable by a name."""

import os
from datetime import datetime

import pytest
from helpers import write_persona

from sympose import jobs

GOOD = """---
schedule: weekly sun 18:00
model: gemma4:e4b
max_runs_per_day: 2
---
Look at the notes I changed this week and draft a weekly note.
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    (directory / "jobs").mkdir()
    return directory


def _job(home, name, text):
    (home / "jobs" / f"{name}.md").write_text(text)


def test_a_job_file_is_read(home):
    _job(home, "weekly-review", GOOD)
    job = jobs.load("Samantha", "weekly-review")
    assert (job.handle, job.name, job.kind, job.model, job.enabled, job.max_runs_per_day) == ("samantha", "weekly-review", "ask", "gemma4:e4b", True, 2)
    assert job.prompt == "Look at the notes I changed this week and draft a weekly note."
    assert job.schedule.kind == "weekly" and job.problem is None and job.runnable() and not job.mechanical
    assert isinstance(job.changed, datetime)


def test_the_settings_have_defaults(home):
    _job(home, "nightly", "---\nschedule: daily 02:00\n---\nDo it.\n")
    job = jobs.load("samantha", "nightly")
    assert (job.model, job.kind, job.enabled, job.max_runs_per_day) == (None, "ask", True, None)


def test_a_job_file_with_the_old_per_job_draft_limit_is_still_a_job_and_the_line_is_ignored(home):
    _job(home, "old", "---\nschedule: daily 02:00\nmax_waiting_drafts: 2\n---\nDo it.\n")
    job = jobs.load("samantha", "old")
    assert job.problem is None and job.runnable()


def test_a_mechanical_job_needs_no_prompt(home):
    _job(home, "upkeep", "---\nschedule: monthly 1 09:00\nkind: health\n---\n")
    job = jobs.load("samantha", "upkeep")
    assert job.problem is None and job.mechanical and job.runnable()


@pytest.mark.parametrize("text, said", [
    ("---\nschedule: sometimes\n---\nDo it.\n", "not a schedule"),
    ("---\n---\nDo it.\n", "no schedule"),
    ("---\nschedule: daily 02:00\nkind: dream\n---\nDo it.\n", "not a kind"),
    ("---\nschedule: daily 02:00\nenabled: maybe\n---\nDo it.\n", "true or false"),
    ("---\nschedule: daily 02:00\nmax_runs_per_day: 0\n---\nDo it.\n", "whole number"),
    ("---\nschedule: daily 02:00\n---\n\n", "no prompt"),
    ("just words, no properties", "no schedule"),
])
def test_a_bad_file_is_a_job_with_a_problem_that_never_runs(home, text, said):
    _job(home, "bad", text)
    job = jobs.load("samantha", "bad")
    assert job is not None and said in job.problem and not job.runnable()


def test_a_switched_off_job_does_not_run(home):
    _job(home, "off", "---\nschedule: daily 02:00\nenabled: false\n---\nDo it.\n")
    job = jobs.load("samantha", "off")
    assert job.problem is None and not job.enabled and not job.runnable()


def test_the_list_is_by_name_and_skips_what_is_not_a_job_file(home):
    _job(home, "b-second", GOOD)
    _job(home, "a-first", GOOD)
    (home / "jobs" / "notes.txt").write_text("x")
    (home / "jobs" / "a-first.md.bak").write_text("x")
    _job(home, "Not A Name", GOOD)
    assert [j.name for j in jobs.list_jobs("samantha")] == ["a-first", "b-second"]


def test_no_folder_or_no_persona_is_an_empty_list(home, tmp_path):
    assert jobs.list_jobs("nobody") == []
    os.rmdir(home / "jobs")
    assert jobs.list_jobs("samantha") == []
    assert jobs.list_jobs("..") == []


@pytest.mark.parametrize("name", ["../persona", "a/b", "", ".hidden", "Upper", "a b", "soul.local"])
def test_a_name_that_is_not_plain_reaches_nothing(home, name):
    (home / "persona.yaml").write_text("schedule: daily 02:00\n")
    assert jobs.load("samantha", name) is None


def test_an_unreadable_file_is_a_job_with_a_problem(home):
    (home / "jobs" / "binary.md").write_bytes(b"\xff\xfe\x00bad")
    job = jobs.load("samantha", "binary")
    assert job is not None and "could not be read" in job.problem and not job.runnable()


def test_a_true_is_not_a_cap_of_one(home):
    _job(home, "capped", "---\nschedule: daily 02:00\nmax_runs_per_day: true\n---\nDo it.\n")
    assert "whole number" in jobs.load("samantha", "capped").problem


def test_a_jobs_folder_that_leads_outside_the_profiles_is_not_read(home, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "stolen.md").write_text(GOOD)
    os.rmdir(home / "jobs")
    os.symlink(elsewhere, home / "jobs")
    assert jobs.jobs_dir("samantha") is None
    assert jobs.list_jobs("samantha") == [] and jobs.load("samantha", "stolen") is None
