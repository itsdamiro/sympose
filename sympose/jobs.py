"""A persona's scheduled jobs (docs/decisions/091): one Markdown file each in `<persona>/jobs/`, outside the vault.
The front matter holds the settings and the body is the prompt. This reads them; running one is `job_run`.

A file that cannot be understood is still a job, with a `problem` the Settings row shows: it never runs, and the user
fixes it in the editor. Nothing here raises for a bad file."""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sympose import job_schedule
from sympose.persona_files import persona_dir, profiles_dir
from sympose.security import is_safe_path
from sympose.vault_snapshot import parse_frontmatter

log = logging.getLogger(__name__)

JOBS_FOLDER = "jobs"
ASK, HEALTH, REFRESH = "ask", "health", "refresh"
KINDS = (ASK, HEALTH, REFRESH)  # `ask` is a model turn; the others are mechanical and call no model
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class Job:
    handle: str
    name: str  # the file's name without `.md`
    path: str
    schedule_text: str
    schedule: job_schedule.Schedule | None
    kind: str
    model: str | None  # `None`: the persona's own
    enabled: bool
    max_runs_per_day: int | None  # `None`: the default for the model the run resolves (docs/decisions/091)
    max_waiting_drafts: int | None  # `None`: the `job_waiting_drafts` setting (docs/decisions/091, amended 2026-10-23)
    prompt: str
    changed: datetime  # when the file was last changed: where "due" counts from for a job that never ran
    problem: str | None = None

    @property
    def mechanical(self) -> bool:
        return self.kind != ASK

    def runnable(self) -> bool:
        return self.enabled and self.problem is None


def jobs_dir(handle: str) -> str | None:
    """`<persona>/jobs/`, or `None` for a handle that is not one persona's folder."""
    try:
        folder = os.path.join(persona_dir(handle), JOBS_FOLDER)
    except ValueError:
        return None
    return folder if is_safe_path(folder, profiles_dir()) else None


def valid_name(name: str) -> bool:
    return bool(_NAME.match(name))


def _settings(meta: dict[str, Any], body: str) -> tuple[dict[str, Any], str | None]:
    """The fields of a job and the first thing wrong with them."""
    found: dict[str, Any] = {"schedule_text": "", "schedule": None, "kind": ASK, "model": None, "enabled": True, "max_runs_per_day": None, "max_waiting_drafts": None}
    text = meta.get("schedule")
    found["schedule_text"] = "" if text is None else str(text).strip()
    kind = str(meta.get("kind", ASK)).strip().lower()
    found["kind"] = kind
    if isinstance(meta.get("model"), str) and meta["model"].strip():
        found["model"] = meta["model"].strip()
    problem = None
    if kind not in KINDS:
        problem = f"'{kind}' is not a kind of job. Use {', '.join(KINDS)}."
    try:
        found["schedule"] = job_schedule.parse(found["schedule_text"])
    except job_schedule.BadSchedule as e:
        problem = problem or str(e)
    enabled = meta.get("enabled", True)
    if isinstance(enabled, bool):
        found["enabled"] = enabled
    else:
        problem = problem or "'enabled' is true or false."
    cap = meta.get("max_runs_per_day")
    if cap is not None:
        if isinstance(cap, int) and not isinstance(cap, bool) and cap >= 1:
            found["max_runs_per_day"] = cap
        else:
            problem = problem or "'max_runs_per_day' is a whole number of 1 or more."
    waiting = meta.get("max_waiting_drafts")
    if waiting is not None:
        if isinstance(waiting, int) and not isinstance(waiting, bool) and waiting >= 1:
            found["max_waiting_drafts"] = waiting
        else:
            problem = problem or "'max_waiting_drafts' is a whole number of 1 or more."
    if kind == ASK and not body.strip():
        problem = problem or "There is no prompt: write what the persona should do under the properties."
    return found, problem


def load(handle: str, name: str) -> Job | None:
    """The job named `name`, or `None` when there is no such file. The persona's handle is the canonical one."""
    folder = jobs_dir(handle)
    if folder is None or not valid_name(name):
        return None
    path = os.path.join(folder, name + ".md")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()
        changed = datetime.fromtimestamp(os.path.getmtime(path))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as e:
        log.warning("Couldn't read the job %s: %s", path, e)
        return Job(handle.lower(), name, path, "", None, ASK, None, False, None, None, "", datetime.now(), f"The file could not be read ({e}).")
    meta, body = parse_frontmatter(text)
    fields, problem = _settings(meta, body)
    return Job(handle.lower(), name, path, prompt=body.strip(), changed=changed, problem=problem, **fields)


def list_jobs(handle: str) -> list[Job]:
    """All the persona's jobs, by name. A file whose name is not a plain job name is left out, so what the list shows
    can all be reached by `load`."""
    folder = jobs_dir(handle)
    if folder is None:
        return []
    try:
        names = sorted(f[:-3] for f in os.listdir(folder) if f.endswith(".md"))
    except FileNotFoundError:
        return []
    return [job for name in names if (job := load(handle, name)) is not None]
