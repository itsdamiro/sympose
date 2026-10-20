"""The job routes' handlers (docs/decisions/091, slice 3): a persona's scheduled jobs listed with how their last run went,
one switched on or off, and a new one started from the template. The rules are `job_manage`'s; a request it refuses is a
422 with the reason, and an unknown persona or job a 404. Editing a job's file goes through the persona-file routes."""

from typing import Any

from fastapi import HTTPException

from sympose import job_manage
from sympose.server_models import JobSwitch


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
