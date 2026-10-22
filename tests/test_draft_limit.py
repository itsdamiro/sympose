"""The cap on the new-note drafts an unattended source leaves waiting (docs/decisions/091 and 093, amended 2026-10-23): the tag a
draft carries, the limit each source has and where it is set, and the refusal at the limit."""

import threading

import pytest
from helpers import write_persona

from sympose import draft_limit, jobs, note_changes as nc, settings_store

H = "samantha"
JOB = "---\nschedule: daily 02:00\n{extra}---\nDo it.\n"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    (directory / "jobs").mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return directory


def _note(i: int, source: str | None = None) -> dict:
    text = f"# Note {i}\n\nWords {i}.\n"
    if source is None:
        return nc.propose_create(H, f"new/{i}", text, say="")
    with nc.from_source(source):
        return nc.propose_create(H, f"new/{i}", text, say="")


def _job(home, name="weekly", extra=""):
    (home / "jobs" / f"{name}.md").write_text(JOB.format(extra=extra))


def test_the_defaults_are_five_for_a_job_and_ten_for_slack():
    assert (draft_limit.job_default(), draft_limit.slack_limit()) == (5, 10)


def test_the_limits_come_from_the_settings():
    settings_store.set(draft_limit.JOB_SETTING, 2)
    settings_store.set(draft_limit.SLACK_SETTING, 3)
    assert (draft_limit.job_default(), draft_limit.slack_limit()) == (2, 3)


@pytest.mark.parametrize("bad", [0, 101, -1, 2.5, "3", True, None])
def test_a_value_that_is_not_a_whole_number_in_range_is_ignored(bad):
    settings_store.set(draft_limit.JOB_SETTING, bad)
    settings_store.set(draft_limit.SLACK_SETTING, bad)
    assert (draft_limit.job_default(), draft_limit.slack_limit()) == (5, 10)


def test_the_ends_of_the_range_are_allowed():
    settings_store.set(draft_limit.JOB_SETTING, 1)
    settings_store.set(draft_limit.SLACK_SETTING, 100)
    assert (draft_limit.job_default(), draft_limit.slack_limit()) == (1, 100)


def test_a_job_file_overrides_the_default_for_that_job_only(home):
    _job(home, "tight", "max_waiting_drafts: 2\n")
    _job(home, "plain")
    source = draft_limit.job_source
    assert (draft_limit.limit(H, source("tight")), draft_limit.limit(H, source("plain"))) == (2, 5)


def test_a_job_that_is_gone_has_the_default_and_an_unknown_source_has_none():
    assert draft_limit.limit(H, draft_limit.job_source("gone")) == 5
    assert draft_limit.limit(H, "elsewhere") is None


def test_a_draft_made_inside_a_source_is_tagged_with_it():
    assert _note(1, "slack")["source"] == "slack"
    assert _note(2, draft_limit.job_source("weekly"))["source"] == "job:weekly"
    assert "source" not in _note(3)


def test_only_the_drafts_of_a_source_count_for_it():
    _note(1, "slack")
    _note(2, "slack")
    _note(3, draft_limit.job_source("weekly"))
    _note(4)
    assert (draft_limit.waiting(H, "slack"), draft_limit.waiting(H, "job:weekly"), draft_limit.waiting(H, "job:other")) == (2, 1, 0)


def test_a_source_at_its_limit_files_no_more_and_says_why():
    settings_store.set(draft_limit.SLACK_SETTING, 2)
    _note(1, "slack")
    _note(2, "slack")
    with pytest.raises(nc.CannotAnchor, match="2 drafts from Slack are waiting"):
        _note(3, "slack")
    assert draft_limit.waiting(H, "slack") == 2


def test_a_job_at_its_limit_says_it_is_the_job():
    settings_store.set(draft_limit.JOB_SETTING, 1)
    _note(1, "job:weekly")
    with pytest.raises(nc.CannotAnchor, match="1 draft from this job is waiting"):
        _note(2, "job:weekly")


def test_one_below_the_limit_is_still_filed():
    settings_store.set(draft_limit.SLACK_SETTING, 2)
    _note(1, "slack")
    assert _note(2, "slack")["source"] == "slack"


def test_the_refusal_is_in_the_plural_only_for_more_than_one():
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    first = _note(1, "slack")
    assert draft_limit.refusal(H, "slack") == "1 draft from Slack is waiting to be accepted or declined, which is the limit, so no new one was made."
    settings_store.set(draft_limit.SLACK_SETTING, 2)
    _note(2, "slack")
    assert draft_limit.refusal(H, "slack") == "2 drafts from Slack are waiting to be accepted or declined, which is the limit, so no new one was made."
    nc.discard_proposal(H, "new/1", first["id"])
    assert draft_limit.refusal(H, "slack") is None


def test_a_source_with_no_limit_is_tagged_and_never_refused():
    for i in range(20):
        assert _note(i, "elsewhere")["source"] == "elsewhere"


def test_a_source_over_its_limit_does_not_stop_another_source_or_the_web_chat():
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    _note(1, "slack")
    _note(2, "job:weekly")
    _note(3)
    assert [draft_limit.waiting(H, s) for s in ("slack", "job:weekly")] == [1, 1]


def test_deciding_a_draft_makes_room():
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    first = _note(1, "slack")
    with pytest.raises(nc.CannotAnchor):
        _note(2, "slack")
    nc.discard_proposal(H, "new/1", first["id"])
    assert _note(2, "slack")["source"] == "slack"


def test_a_draft_already_waiting_with_no_tag_is_not_counted():
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    _note(1)
    assert _note(2, "slack")["source"] == "slack"


def test_a_lowered_limit_does_not_remove_drafts_already_waiting():
    for i in range(3):
        _note(i, "slack")
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    assert draft_limit.waiting(H, "slack") == 3
    with pytest.raises(nc.CannotAnchor):
        _note(9, "slack")


def test_the_source_is_forgotten_after_the_block_and_when_the_block_fails():
    with pytest.raises(RuntimeError), nc.from_source("slack"):
        raise RuntimeError("boom")
    assert "source" not in _note(1)


def test_a_block_inside_another_returns_to_the_outer_source():
    with nc.from_source("slack"):
        with nc.from_source("job:weekly"):
            assert nc.propose_create(H, "new/1", "# One\n\nOne.\n", say="")["source"] == "job:weekly"
        assert nc.propose_create(H, "new/2", "# Two\n\nTwo.\n", say="")["source"] == "slack"


def test_the_source_belongs_to_the_thread_that_set_it():
    made = []
    with nc.from_source("slack"):
        other = threading.Thread(target=lambda: made.append(nc.propose_create(H, "new/1", "# One\n\nOne.\n", say="")))
        other.start()
        other.join()
    assert "source" not in made[0]


def test_a_job_file_can_set_its_own_limit_and_a_bad_value_is_a_problem(home):
    _job(home, "good", "max_waiting_drafts: 3\n")
    assert jobs.load(H, "good").max_waiting_drafts == 3
    for bad in ("0", "true", "two", "-1"):
        _job(home, "bad", f"max_waiting_drafts: {bad}\n")
        assert "max_waiting_drafts" in jobs.load(H, "bad").problem
    _job(home, "plain")
    assert jobs.load(H, "plain").max_waiting_drafts is None
