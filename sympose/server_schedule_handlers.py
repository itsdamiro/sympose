"""The schedule route's handlers (docs/decisions/091, slice 4): whether the operating system runs the jobs while the web app
is closed, and switching that on or off. The rules are `job_launchd`'s; a refusal is a 422 with the reason."""

from typing import Any

from fastapi import HTTPException

from sympose import job_launchd
from sympose.server_models import ScheduleSwitch


def _state() -> dict[str, Any]:
    return {"supported": job_launchd.supported(), "installed": job_launchd.installed()}


def get_schedule() -> dict[str, Any]:
    return _state()


def put_schedule(body: ScheduleSwitch) -> dict[str, Any]:
    try:
        job_launchd.install() if body.installed else job_launchd.remove()
    except job_launchd.ScheduleRefused as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return _state()
