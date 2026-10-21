"""Running scheduled jobs (docs/decisions/091): when one is due, what a run does and records, the daily cap, the pause
after failures, and that one job's failure does not stop the next. The turn and the model are fakes."""

import contextlib
import os
from datetime import datetime, timedelta

import pytest
from helpers import write_persona

from sympose import job_run, job_state, jobs, note_changes
from sympose.engine import semantic_refresh, session, turn
from sympose.engine.turn_result import TurnResult

LOCAL = "ollama_chat/gemma4:e4b"
CLOUD = "gemini/gemini-2.5-flash"
SUN_NIGHT = datetime(2026, 10, 25, 18, 30)  # a Sunday after 18:00
JOB = "---\nschedule: weekly sun 18:00\n{extra}---\nDraft my weekly note.\n"


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    (directory / "jobs").mkdir()
    vault = tmp_path / "vault"
    (vault / "Journal").mkdir(parents=True)
    (vault / "Journal" / "Day.md").write_text("Some words.")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return directory


@pytest.fixture
def turns(monkeypatch):
    """Every `run_turn` call, as `(handle, message, session_id, model, edits)`; set `.fail` to make the next ones raise."""
    class Turns(list):
        fail = None
        withheld = ()

    seen = Turns()

    def fake(handle, message, session_id=None, model=None, edits=False, **_):
        seen.append((handle, message, session_id, model, edits))
        if seen.fail:
            raise seen.fail
        return TurnResult(reply="Done.", session_id=session_id, withheld=list(seen.withheld))

    monkeypatch.setattr(turn, "run_turn", fake)
    return seen


def _job(home, name="weekly", extra="", model=None):
    extra = (f"model: {model}\n" if model else "") + extra
    (home / "jobs" / f"{name}.md").write_text(JOB.format(extra=extra))
    old = (SUN_NIGHT - timedelta(days=30)).timestamp()
    os.utime(home / "jobs" / f"{name}.md", (old, old))  # written long before, so its first time has come


# --- when a job is due -------------------------------------------------------------------------
def test_a_job_is_due_when_its_time_has_passed_since_it_was_written(home):
    _job(home)
    assert job_run.due(jobs.load("samantha", "weekly"), SUN_NIGHT)
    job = jobs.load("samantha", "weekly")
    job_state.record("samantha", "weekly", SUN_NIGHT, None)
    assert not job_run.due(job, SUN_NIGHT + timedelta(hours=1))
    assert job_run.due(job, SUN_NIGHT + timedelta(days=7))


@pytest.mark.parametrize("extra", ["enabled: false\n", "kind: dream\n"])
def test_a_switched_off_or_misunderstood_job_is_not_due(home, extra):
    _job(home, extra=extra)
    assert not job_run.due(jobs.load("samantha", "weekly"), SUN_NIGHT)


def test_a_paused_job_is_not_due(home):
    _job(home)
    for _ in range(3):
        job_state.record("samantha", "weekly", SUN_NIGHT - timedelta(days=8), None, error="x")
    assert not job_run.due(jobs.load("samantha", "weekly"), SUN_NIGHT)


def test_a_job_written_after_this_weeks_time_waits_for_the_next(home):
    _job(home)
    os.utime(home / "jobs" / "weekly.md", (SUN_NIGHT.timestamp(), SUN_NIGHT.timestamp()))
    job = jobs.load("samantha", "weekly")
    assert not job_run.due(job, SUN_NIGHT + timedelta(minutes=5))
    assert job_run.due(job, SUN_NIGHT + timedelta(days=7))


# --- the daily cap -------------------------------------------------------------------------------
def test_a_cloud_job_runs_once_a_day_by_default_and_a_local_job_has_no_limit(home):
    _job(home, "cloud", model=CLOUD)
    _job(home, "local", model=LOCAL)
    cloud, local = jobs.load("samantha", "cloud"), jobs.load("samantha", "local")
    persona = {"model": None}
    assert (job_run.daily_cap(cloud, persona), job_run.daily_cap(local, persona)) == (1, None)


def test_the_persona_model_decides_when_the_job_names_none(home, monkeypatch):
    _job(home)
    job = jobs.load("samantha", "weekly")
    assert job_run.daily_cap(job, {"model": CLOUD}) == 1 and job_run.daily_cap(job, {"model": LOCAL}) is None


def test_a_cap_in_the_file_wins_and_a_mechanical_job_has_none_by_default(home):
    _job(home, "cloud", extra="max_runs_per_day: 3\n", model=CLOUD)
    _job(home, "upkeep", extra="kind: health\n", model=CLOUD)
    assert job_run.daily_cap(jobs.load("samantha", "cloud"), {}) == 3
    assert job_run.daily_cap(jobs.load("samantha", "upkeep"), {}) is None


def test_a_cloud_job_that_ran_today_is_not_run_again(home, turns):
    _job(home, model=CLOUD)
    assert job_run.run("samantha", "weekly", SUN_NIGHT, manual=True).status == job_run.RAN
    again = job_run.run("samantha", "weekly", SUN_NIGHT + timedelta(hours=1), manual=True)
    assert again.status == job_run.SKIPPED and "limit" in again.detail and len(turns) == 1
    assert job_run.run("samantha", "weekly", SUN_NIGHT + timedelta(days=1), manual=True).status == job_run.RAN


def test_a_failed_run_counts_toward_the_cap(home, turns):
    _job(home, model=CLOUD)
    turns.fail = RuntimeError("down")
    assert job_run.run("samantha", "weekly", SUN_NIGHT, manual=True).status == job_run.FAILED
    assert job_run.run("samantha", "weekly", SUN_NIGHT, manual=True).status == job_run.SKIPPED


# --- what a run does -----------------------------------------------------------------------------
def test_a_job_turn_is_told_it_is_unattended(home, monkeypatch):
    _job(home, model=LOCAL)
    kinds = []

    def fake(handle, message, session_id=None, model=None, edits=False, unattended=False, **_):
        kinds.append(unattended)
        return TurnResult(reply="Done.", session_id=session_id)

    monkeypatch.setattr(turn, "run_turn", fake)
    job_run.run("samantha", "weekly", SUN_NIGHT)
    assert kinds == [True]


def test_a_run_is_a_new_marked_conversation_with_edits_on_and_the_jobs_model(home, turns):
    _job(home, model=LOCAL)
    first = job_run.run("samantha", "weekly", SUN_NIGHT)
    second = job_run.run("Samantha", "weekly", SUN_NIGHT, manual=True)
    assert (first.status, first.detail) == (job_run.RAN, "Done.")
    assert [t[:2] + t[3:] for t in turns] == [("samantha", "Draft my weekly note.", LOCAL, True)] * 2
    assert first.session_id and second.session_id and first.session_id != second.session_id == turns[1][2]
    assert session.load_session("samantha", first.session_id)["meta"]["job"] == "weekly"
    state = job_state.read("samantha", "weekly")
    assert (state.last_run, state.outcome, state.session_id) == (SUN_NIGHT, "ok", second.session_id)


def test_a_job_with_no_model_runs_on_the_personas(home, turns):
    _job(home)
    job_run.run("samantha", "weekly", SUN_NIGHT)
    assert turns[0][3] is None


def test_what_was_held_back_from_a_cloud_model_is_recorded(home, turns):
    _job(home, model=CLOUD)
    turns.withheld = ("notes", "recaps")
    outcome = job_run.run("samantha", "weekly", SUN_NIGHT)
    assert outcome.status == job_run.RAN and "notes, recaps" in outcome.detail
    assert job_state.read("samantha", "weekly").held == ["notes", "recaps"]


def test_a_run_that_fails_is_recorded_and_three_in_a_row_pause_the_job(home, turns):
    _job(home, model=LOCAL)
    turns.fail = RuntimeError("the model is not running")
    for n in range(3):
        outcome = job_run.run("samantha", "weekly", SUN_NIGHT + timedelta(days=7 * n))
        assert (outcome.status, outcome.detail) == (job_run.FAILED, "the model is not running")
    assert job_state.read("samantha", "weekly").paused
    assert not job_run.due(jobs.load("samantha", "weekly"), SUN_NIGHT + timedelta(days=30))
    assert job_run.run("samantha", "weekly", SUN_NIGHT + timedelta(days=30)).status == job_run.SKIPPED


def test_a_run_that_failed_is_tried_again_after_a_short_wait_not_at_the_next_time(home, turns):
    _job(home, model=LOCAL)
    turns.fail = RuntimeError("the model is not running")
    assert job_run.run("samantha", "weekly", SUN_NIGHT).status == job_run.FAILED
    job = jobs.load("samantha", "weekly")
    assert not job_run.due(job, SUN_NIGHT + job_run.RETRY_AFTER[0] - timedelta(minutes=1))
    assert job_run.due(job, SUN_NIGHT + job_run.RETRY_AFTER[0])
    turns.fail = None
    assert job_run.run("samantha", "weekly", SUN_NIGHT + job_run.RETRY_AFTER[0]).status == job_run.RAN
    assert not job_run.due(job, SUN_NIGHT + timedelta(days=1))  # it worked: back to the weekly time


def test_the_second_retry_waits_longer_and_a_paused_job_is_not_retried(home, turns):
    _job(home, model=LOCAL)
    turns.fail = RuntimeError("down")
    job_run.run("samantha", "weekly", SUN_NIGHT)
    second = SUN_NIGHT + job_run.RETRY_AFTER[0]
    job_run.run("samantha", "weekly", second)
    job = jobs.load("samantha", "weekly")
    assert not job_run.due(job, second + job_run.RETRY_AFTER[1] - timedelta(minutes=1))
    assert job_run.due(job, second + job_run.RETRY_AFTER[1])
    job_run.run("samantha", "weekly", second + job_run.RETRY_AFTER[1])
    assert job_state.read("samantha", "weekly").paused
    assert not job_run.due(job, second + timedelta(hours=40))


def test_a_run_with_nothing_to_do_waits_for_its_next_time_instead_of_retrying(home):
    _job(home, "health", model=LOCAL)
    job_state.record("samantha", "health", SUN_NIGHT, None, error="A report is waiting already.")
    assert not job_run.due(jobs.load("samantha", "health"), SUN_NIGHT + timedelta(hours=6))


def test_a_cloud_job_that_failed_is_not_retried_past_its_daily_limit(home, turns):
    _job(home, model=CLOUD)
    turns.fail = RuntimeError("down")
    job_run.run("samantha", "weekly", SUN_NIGHT)
    later = SUN_NIGHT + job_run.RETRY_AFTER[0]
    assert job_run.run("samantha", "weekly", later).status == job_run.SKIPPED and len(turns) == 1


def test_a_job_whose_record_cannot_be_saved_is_not_run(home, turns):
    _job(home, model=LOCAL)
    state_folder = home / "jobs" / job_state.STATE_FOLDER
    state_folder.mkdir()
    state_folder.chmod(0o500)
    try:
        if os.access(state_folder, os.W_OK):
            pytest.skip("this account can write anywhere")
        outcome = job_run.run("samantha", "weekly", SUN_NIGHT)
    finally:
        state_folder.chmod(0o700)
    assert outcome.status == job_run.FAILED and "record" in outcome.detail and turns == []


def test_a_manual_run_that_works_lifts_a_pause(home, turns):
    _job(home)
    for _ in range(3):
        job_state.record("samantha", "weekly", SUN_NIGHT - timedelta(days=9), None, error="x")
    assert job_run.run("samantha", "weekly", SUN_NIGHT, manual=True).status == job_run.RAN
    assert not job_state.read("samantha", "weekly").paused


def test_a_manual_run_ignores_the_off_switch_but_not_a_file_it_cannot_read(home, turns):
    _job(home, "off", extra="enabled: false\n")
    _job(home, "broken", extra="kind: dream\n")
    assert job_run.run("samantha", "off", SUN_NIGHT, manual=True).status == job_run.RAN
    assert job_run.run("samantha", "off", SUN_NIGHT + timedelta(days=1)).status == job_run.SKIPPED
    broken = job_run.run("samantha", "broken", SUN_NIGHT, manual=True)
    assert broken.status == job_run.SKIPPED and "not a kind" in broken.detail


def test_no_such_job_or_persona_is_skipped_not_raised(home, turns):
    assert job_run.run("samantha", "nope", SUN_NIGHT, manual=True).status == job_run.SKIPPED
    assert job_run.run("nobody", "weekly", SUN_NIGHT, manual=True).status == job_run.SKIPPED
    assert not turns


def test_a_job_another_caller_holds_is_not_run(home, turns):
    _job(home)
    with job_state.claim("samantha", "weekly"):
        outcome = job_run.run("samantha", "weekly", SUN_NIGHT, manual=True)
    assert outcome.status == job_run.SKIPPED and "already" in outcome.detail and not turns


def test_a_run_another_process_finished_meanwhile_is_not_repeated(home, turns, monkeypatch):
    _job(home)

    @contextlib.contextmanager
    def other_got_there_first(handle, name):
        job_state.record(handle, name, SUN_NIGHT, None)
        yield True

    monkeypatch.setattr(job_state, "claim", other_got_there_first)
    outcome = job_run.run("samantha", "weekly", SUN_NIGHT)
    assert (outcome.status, outcome.detail) == (job_run.SKIPPED, "Not due.") and not turns


# --- the jobs that call no model -------------------------------------------------------------------
def test_the_health_job_drafts_its_report_as_a_new_note(home, turns):
    _job(home, "upkeep", extra="kind: health\n")
    outcome = job_run.run("samantha", "upkeep", SUN_NIGHT)
    assert (outcome.status, outcome.detail) == (job_run.RAN, "Drafted Vault health 2026-10-25.") and not turns
    drafts = [p for e in note_changes.store.entries("samantha") for p in e["proposals"]]
    assert len(drafts) == 1 and drafts[0]["kind"] == "create" and drafts[0]["folder"] == "Jobs"
    assert "Vault health" in drafts[0]["text"] and drafts[0]["name"] == "Vault health 2026-10-25"


def test_a_second_health_report_while_the_first_waits_is_a_failure_the_user_can_read(home):
    _job(home, "upkeep", extra="kind: health\n")
    job_run.run("samantha", "upkeep", SUN_NIGHT)
    again = job_run.run("samantha", "upkeep", SUN_NIGHT, manual=True)
    assert again.status == job_run.FAILED and "already waiting" in again.detail


def test_the_refresh_job_rebuilds_the_index_and_says_when_there_was_nothing_to_do(home, monkeypatch):
    _job(home, "index", extra="kind: refresh\n")
    monkeypatch.setattr(semantic_refresh, "refresh", lambda handle: True)
    assert job_run.run("samantha", "index", SUN_NIGHT).detail == "Rebuilt the search index."
    monkeypatch.setattr(semantic_refresh, "refresh", lambda handle: False)
    assert "Nothing to rebuild" in job_run.run("samantha", "index", SUN_NIGHT, manual=True).detail


# --- every job that is due -----------------------------------------------------------------------
def test_run_due_runs_the_due_jobs_and_one_failure_does_not_stop_the_next(home, turns, monkeypatch):
    _job(home, "a-bad")
    _job(home, "b-good")
    _job(home, "c-waiting", extra="enabled: false\n")
    attempts = []

    def fake(handle, message, session_id=None, model=None, edits=False, **_):
        attempts.append(session_id)
        if len(attempts) == 1:
            raise RuntimeError("down")
        return TurnResult(reply="ok", session_id=session_id)

    monkeypatch.setattr(turn, "run_turn", fake)
    outcomes = job_run.run_due(SUN_NIGHT)
    assert [(o.job, o.status) for o in outcomes] == [("samantha/a-bad", job_run.FAILED), ("samantha/b-good", job_run.RAN)]
    assert job_run.run_due(SUN_NIGHT + timedelta(minutes=5)) == []


def test_run_due_leaves_out_a_job_that_was_due_but_at_its_limit(home, turns):
    (home / "jobs" / "hourly.md").write_text("---\nschedule: every 1 hours\nmodel: " + CLOUD + "\n---\nCheck.\n")
    old = (SUN_NIGHT - timedelta(days=3)).timestamp()
    os.utime(home / "jobs" / "hourly.md", (old, old))
    assert [o.status for o in job_run.run_due(SUN_NIGHT)] == [job_run.RAN]
    assert job_run.run_due(SUN_NIGHT + timedelta(hours=2)) == [] and len(turns) == 1  # due again, but a cloud job runs once a day


def test_run_due_goes_on_to_the_next_job_when_one_cannot_be_looked_at(home, turns, monkeypatch):
    _job(home, "a-odd")
    _job(home, "b-good")
    real = job_run.due

    def due(job, now):
        if job.name == "a-odd":
            raise ValueError("invalid literal")
        return real(job, now)

    monkeypatch.setattr(job_run, "due", due)
    assert [(o.job, o.status) for o in job_run.run_due(SUN_NIGHT)] == [("samantha/b-good", job_run.RAN)]
