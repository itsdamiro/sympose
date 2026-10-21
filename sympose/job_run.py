"""Running a persona's jobs without anyone at the keyboard (docs/decisions/091). `run` is one job, now; `run_due` is every
job whose time has passed, one after another. Both are what `sympose run` and the open web app call.

A job never writes the vault: its turn is the ordinary one (`turn.run_turn` with edits on), so whatever it wants to
change waits in Drafts. It has no note open, so it can draft new notes and cannot edit an existing one. Whatever goes
wrong is recorded and does not stop the next job."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sympose import job_mechanical, job_state, jobs
from sympose import profile as profile_mod
from sympose.engine import model as model_mod
from sympose.engine import session, sharing

log = logging.getLogger(__name__)

RAN, FAILED, SKIPPED = "ran", "failed", "skipped"
RETRY_AFTER = (timedelta(minutes=30), timedelta(hours=2))  # after the first and the second failure in a row; the third pauses
CLOUD_RUNS_PER_DAY = 1  # a cloud model costs money and nobody is watching; a local model costs time only
HISTORY_TURNS = 6  # of the job's one conversation, sent word for word: the last few runs and the user's replies, not all of them


@dataclass(frozen=True)
class Outcome:
    job: str  # `handle/name`
    status: str
    detail: str = ""
    session_id: str | None = None


def _model(job: jobs.Job, persona: dict) -> str:
    return job.model or model_mod.resolve_model(persona.get("model"))


def daily_cap(job: jobs.Job, persona: dict) -> int | None:
    """The most runs a day: the job's own, else one for a cloud model and none for a local one or a mechanical job."""
    if job.max_runs_per_day is not None:
        return job.max_runs_per_day
    return None if job.mechanical or sharing.is_local(_model(job, persona)) else CLOUD_RUNS_PER_DAY


def _conversation(job: jobs.Job) -> str | None:
    """The conversation this job keeps adding to (docs/decisions/091, amended): the one its last run used, if it is still
    there and still this job's. A new one is opened otherwise, and it is then the job's."""
    last = job_state.read(job.handle, job.name).session_id
    found = session.load_session(job.handle, last) if last else None
    if found is not None and found["meta"].get("job") == job.name:
        return last
    new = session.new_session_id()
    return new if session.start_session(job.handle, new, job.name) else None


def due(job: jobs.Job, now: datetime) -> bool:
    """Whether the time has come for `job`: enabled, understood, not paused, and its time passed since it last ran (or was
    written). The daily cap is looked at by `run`, once it holds the job."""
    state = job_state.read(job.handle, job.name)
    persona = profile_mod.resolve_profile(job.handle)
    if not job.runnable() or state.paused or persona is None or job.schedule is None:
        return False
    if job.schedule.due(state.last_run or job.changed, now):
        return True
    # A failure the next try may mend is tried again soon, not at the next scheduled time (a weekly job would wait a week).
    return bool(state.retry and state.last_run and 1 <= state.failures <= len(RETRY_AFTER) and now - state.last_run >= RETRY_AFTER[state.failures - 1])


def run(handle: str, name: str, now: datetime | None = None, *, manual: bool = False) -> Outcome:
    """Run one job. A manual run ignores the schedule, the off switch and a pause (a run that works lifts the pause), but
    not the daily cap or a file that cannot be understood."""
    now = now or datetime.now()
    key = f"{handle.lower()}/{name}"
    job = jobs.load(handle, name)
    persona = profile_mod.resolve_profile(handle)
    if job is None or persona is None:
        return Outcome(key, SKIPPED, "There is no such job.")
    if job.problem:
        return Outcome(key, SKIPPED, job.problem)
    with job_state.claim(job.handle, name) as mine:
        if not mine:
            return Outcome(key, SKIPPED, "It is running already.")
        if not job_state.can_record(job.handle, name):
            return Outcome(key, FAILED, "Its record cannot be saved, so it was not run.")
        # Looked at again now that this caller holds the job: another process may have run it since the caller last looked.
        if not manual and not due(job, now):
            return Outcome(key, SKIPPED, "Not due.")
        cap = daily_cap(job, persona)
        if cap is not None and job_state.read(job.handle, name).runs_on(now) >= cap:
            return Outcome(key, SKIPPED, f"It has already run {cap} time{'s' if cap != 1 else ''} today, its limit.")
        return _execute(job, persona, now)


def _execute(job: jobs.Job, persona: dict, now: datetime) -> Outcome:
    key = f"{job.handle}/{job.name}"
    session_id = None
    held: list[str] = []
    try:
        if job.kind == jobs.HEALTH:
            detail = job_mechanical.health(persona, now.date())
        elif job.kind == jobs.REFRESH:
            detail = job_mechanical.refresh(persona)
        else:
            from sympose.engine import turn  # imported here: it brings in litellm, a few seconds

            session_id = _conversation(job)
            if session_id is None:
                raise job_mechanical.NothingToDo("The conversation could not be started.")
            result = turn.run_turn(
                job.handle, job.prompt, session_id, model=job.model, edits=True, unattended=True, history_turns=HISTORY_TURNS,
            )
            held = list(result.withheld)
            detail = "Held back from the model: " + ", ".join(held) + "." if held else "Done."
    except job_mechanical.NothingToDo as e:
        job_state.record(job.handle, job.name, now, session_id, error=str(e))
        return Outcome(key, FAILED, str(e), session_id)
    except Exception as e:  # a job must not stop the ones after it, whatever the model or the disk did
        log.warning("Job %s failed: %s", key, e)
        job_state.record(job.handle, job.name, now, session_id, error=str(e) or type(e).__name__, retry=True)
        return Outcome(key, FAILED, str(e) or type(e).__name__, session_id)
    job_state.record(job.handle, job.name, now, session_id, held=held)
    return Outcome(key, RAN, detail, session_id)


def run_due(now: datetime | None = None) -> list[Outcome]:
    """Every job of every persona whose time has come, by persona and name. Only the ones that ran are returned."""
    now = now or datetime.now()
    outcomes = []
    for persona in profile_mod.list_profiles():
        for job in jobs.list_jobs(persona["handle"]):
            try:
                if due(job, now):
                    outcome = run(job.handle, job.name, now)
                    if outcome.status != SKIPPED:
                        outcomes.append(outcome)
            except Exception as e:  # one job that cannot be looked at must not stop the ones after it
                log.warning("Job %s/%s could not be checked: %s", job.handle, job.name, e)
    return outcomes
