"""A job's record and the lock that keeps it from running twice (docs/decisions/091)."""

from datetime import datetime, timedelta

import pytest
from helpers import write_persona

from sympose import job_state as js

NOW = datetime(2026, 10, 21, 7, 30)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base / "samantha"


def test_a_job_that_never_ran_has_an_empty_record():
    assert js.read("samantha", "weekly") == js.State()


def test_a_run_is_recorded_and_read_back():
    js.record("samantha", "weekly", NOW, "abc", held=["notes"])
    state = js.read("samantha", "weekly")
    assert (state.last_run, state.outcome, state.session_id, state.runs_today, state.failures, state.paused) == (NOW, "ok", "abc", 1, 0, False)
    assert state.held == ["notes"] and state.detail == "notes"


def test_a_run_with_no_conversation_keeps_the_one_the_job_had():
    js.record("samantha", "weekly", NOW, "abc")
    js.record("samantha", "weekly", NOW + timedelta(hours=1), None, error="down")
    assert js.read("samantha", "weekly").session_id == "abc"
    js.record("samantha", "weekly", NOW + timedelta(hours=2), "def")
    assert js.read("samantha", "weekly").session_id == "def"


def test_runs_are_counted_for_the_day_and_start_again_the_next():
    js.record("samantha", "weekly", NOW, None)
    js.record("samantha", "weekly", NOW + timedelta(hours=2), None)
    assert js.read("samantha", "weekly").runs_on(NOW + timedelta(hours=3)) == 2
    assert js.read("samantha", "weekly").runs_on(NOW + timedelta(days=1)) == 0
    js.record("samantha", "weekly", NOW + timedelta(days=1), None)
    assert js.read("samantha", "weekly").runs_today == 1


def test_three_failures_in_a_row_pause_the_job_and_a_good_run_clears_them():
    for n in range(2):
        state = js.record("samantha", "weekly", NOW + timedelta(hours=n), None, error="model down")
    assert (state.failures, state.paused, state.outcome, state.detail) == (2, False, "failed", "model down")
    assert js.record("samantha", "weekly", NOW + timedelta(hours=3), None, error="model down").paused
    assert js.read("samantha", "weekly").paused
    healed = js.record("samantha", "weekly", NOW + timedelta(hours=4), None)
    assert (healed.failures, healed.paused) == (0, False)


def test_a_failure_then_a_good_run_then_a_failure_is_not_three_in_a_row():
    js.record("samantha", "weekly", NOW, None, error="x")
    js.record("samantha", "weekly", NOW, None, error="x")
    js.record("samantha", "weekly", NOW, None)
    assert not js.record("samantha", "weekly", NOW, None, error="x").paused


def test_resume_lifts_a_pause():
    for _ in range(3):
        js.record("samantha", "weekly", NOW, None, error="x")
    js.resume("samantha", "weekly")
    state = js.read("samantha", "weekly")
    assert (state.paused, state.failures, state.last_run) == (False, 0, NOW)


def test_a_record_that_cannot_be_read_is_taken_as_none(home):
    js.record("samantha", "weekly", NOW, None)
    (home / "jobs" / ".state" / "weekly.json").write_text("{not json")
    assert js.read("samantha", "weekly") == js.State()
    (home / "jobs" / ".state" / "weekly.json").write_text('{"last_run": "yesterday-ish"}')
    assert js.read("samantha", "weekly") == js.State()


def test_a_name_that_is_not_plain_has_no_record_and_saves_none(home):
    js.record("samantha", "../escape", NOW, None)
    assert js.read("samantha", "../escape") == js.State()
    assert not (home / "escape.json").exists() and not (home / "jobs").exists()


def test_only_one_caller_holds_a_job_at_a_time():
    with js.claim("samantha", "weekly") as first:
        with js.claim("samantha", "weekly") as second, js.claim("samantha", "other") as other:
            assert (first, second, other) == (True, False, True)
    with js.claim("samantha", "weekly") as again:
        assert again


def test_another_process_holding_the_lock_file_is_respected(home):
    import fcntl

    (home / "jobs" / ".state").mkdir(parents=True)
    with open(home / "jobs" / ".state" / "weekly.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with js.claim("samantha", "weekly") as taken:
            assert taken is False
        with js.claim("samantha", "weekly") as still:  # a refusal must not leave the job stuck in this process
            assert still is False
    with js.claim("samantha", "weekly") as free:
        assert free


def test_without_file_locks_one_process_still_holds_a_job_once(monkeypatch):
    monkeypatch.setattr(js, "_lock_file", lambda handle, name: None)  # where `fcntl` is missing
    with js.claim("samantha", "weekly") as first, js.claim("samantha", "weekly") as second:
        assert (first, second) == (True, False)
