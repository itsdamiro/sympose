"""The job routes' handlers (docs/decisions/091, slice 3): a persona's scheduled jobs listed with how their last run went,
one switched on or off, a new one started from the template, one renamed and one deleted. The rules are `job_manage`'s; a request it refuses is a
422 with the reason, and an unknown persona or job a 404. Editing a job's file goes through the persona-file routes."""

from typing import Any

from fastapi import HTTPException

from sympose import job_manage
from sympose import profile as profile_mod
from sympose.engine import model as model_mod
from sympose.engine.model_options import offered
from sympose.server_models import JobModelChoice, JobRename, JobSwitch


def _refused(error: job_manage.JobRefused) -> HTTPException:
    return HTTPException(status_code=404 if isinstance(error, job_manage.JobMissing) else 422, detail=str(error))


def list_jobs(handle: str) -> dict[str, Any]:
    try:
        return {"jobs": job_manage.listing(handle)}
    except job_manage.JobRefused as e:
        raise _refused(e) from None


def post_job(handle: str) -> dict[str, Any]:
    try:
        return {"job": job_manage.create(handle)}
    except job_manage.JobRefused as e:
        raise _refused(e) from None


def put_job(handle: str, name: str, body: JobSwitch) -> dict[str, Any]:
    try:
        return {"job": job_manage.set_enabled(handle, name, body.enabled)}
    except job_manage.JobRefused as e:
        raise _refused(e) from None


def put_job_model(handle: str, name: str, body: JobModelChoice) -> dict[str, Any]:
    """Only a listed model is accepted (as for a persona's, ADR 044), or the one the job already has or the persona's own."""
    try:
        row = next((r for r in job_manage.listing(handle) if r["name"] == name), None)
        if row is None:
            raise job_manage.JobMissing("There is no such job.")
        own = (profile_mod.resolve_profile(handle) or {}).get("model") or None
        in_use = [model_mod.resolve_model(own), row["own_model"]]
        if body.model is not None and body.model not in {m.id for m in offered(*in_use)}:
            raise job_manage.JobRefused("Pick a model from the list.")
        return {"job": job_manage.set_model(handle, name, body.model)}
    except job_manage.JobRefused as e:
        raise _refused(e) from None


def rename_job(handle: str, name: str, body: JobRename) -> dict[str, Any]:
    try:
        return {"job": job_manage.rename(handle, name, body.name)}
    except job_manage.JobRefused as e:
        raise _refused(e) from None


def delete_job(handle: str, name: str) -> dict[str, Any]:
    try:
        job_manage.delete(handle, name)
    except job_manage.JobRefused as e:
        raise _refused(e) from None
    return {"deleted": name}
