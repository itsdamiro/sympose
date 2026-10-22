"""What Settings does with a persona's jobs (docs/decisions/091, slice 3): list them with how the last run went, switch
one on or off, start a new one from a template, rename one and delete one. Editing a job is the editor's (`persona_editable` serves
`jobs/<name>.md`); running one is `job_run`. A refusal is a `JobRefused` whose message is for the user."""

import os
import re
import threading
from typing import Any, Callable

from sympose import draft_limit, job_state, jobs
from sympose import profile as profile_mod
from sympose.atomic_write import write_atomic_text
from sympose.engine import model as model_mod
from sympose.engine import sharing

_LOCK = threading.Lock()  # a switch reads the file and writes it back: two at once must not lose one
_ENABLED = re.compile(r"^enabled[ \t]*:[^\r\n]*", re.MULTILINE)
_MODEL = re.compile(r"^model[ \t]*:[^\r\n]*(\r?\n)?", re.MULTILINE)
_OPEN = re.compile(r"\A---[ \t]*\r?\n")
_CLOSE = re.compile(r"^---[ \t]*\r?$", re.MULTILINE)
NEW_NAME = "new-job"
# Off until the user has written what it should do: a template that ran on its own would act on a placeholder.
TEMPLATE = """---
schedule: weekly sun 18:00
kind: ask
enabled: false
---
Write here what {persona} should do each time. A run can draft new notes for you to accept; it never changes your notes by itself.
"""


class JobRefused(ValueError):
    """A request the job cannot satisfy; the message says why, plainly."""


class JobMissing(JobRefused):
    """The persona or the job asked for is not there."""


def _persona(handle: str) -> dict[str, Any]:
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        raise JobMissing(f"There is no persona called {handle}.")
    return persona


def _row(job: jobs.Job, persona: dict[str, Any]) -> dict[str, Any]:
    state = job_state.read(job.handle, job.name)
    source = draft_limit.job_source(job.name)
    model = job.model or model_mod.resolve_model(persona.get("model"))
    return {
        "name": job.name,
        "file": f"jobs/{job.name}.md",
        "schedule": job.schedule_text,
        "kind": job.kind,
        "mechanical": job.mechanical,
        "model": None if job.mechanical else model,
        "own_model": None if job.mechanical else job.model,
        "cloud": not job.mechanical and not sharing.is_local(model),
        "enabled": job.enabled,
        "problem": job.problem,
        "paused": state.paused,
        "failures": state.failures,
        "last_run": state.last_run.isoformat(timespec="seconds") if state.last_run else None,
        "outcome": state.outcome,
        "detail": state.detail,
        "session_id": state.session_id,
        "drafts": draft_limit.waiting(job.handle, source),
        "draft_cap": draft_limit.limit(job.handle, source),
    }


def listing(handle: str) -> list[dict[str, Any]]:
    persona = _persona(handle)
    return [_row(job, persona) for job in jobs.list_jobs(persona["handle"])]


def _with_enabled(text: str, enabled: bool) -> str | None:
    """`text` with its `enabled:` property set, the rest untouched (a job with none is on, so switching it on writes nothing);
    `None` when it opens a front matter it never closes."""
    value = "true" if enabled else "false"
    opening = _OPEN.match(text)
    if opening is None:
        return text if enabled else f"---\nenabled: {value}\n---\n{text}"
    closing = _CLOSE.search(text, opening.end())
    if closing is None:
        return None
    newline = "\r\n" if opening.group(0).endswith("\r\n") else "\n"
    block = text[opening.end() : closing.start()]
    if _ENABLED.search(block):
        block = _ENABLED.sub(lambda m: f"enabled: {value}", block, count=1)
    elif not enabled:
        block = block + ("" if block == "" or block.endswith("\n") else newline) + f"enabled: {value}{newline}"
    return text[: opening.end()] + block + text[closing.start() :]


def _with_model(text: str, model: str | None) -> str | None:
    """`text` with its `model:` property set to `model`, or taken out for `None`, the rest untouched; `None` when it opens a
    front matter it never closes."""
    opening = _OPEN.match(text)
    if opening is None:
        return text if model is None else f"---\nmodel: {model}\n---\n{text}"
    closing = _CLOSE.search(text, opening.end())
    if closing is None:
        return None
    newline = "\r\n" if opening.group(0).endswith("\r\n") else "\n"
    block = text[opening.end() : closing.start()]
    if model is None:
        block = _MODEL.sub("", block, count=1)
    elif _MODEL.search(block):
        block = _MODEL.sub(lambda m: f"model: {model}{m.group(1) or ''}", block, count=1)
    else:
        block = block + ("" if block == "" or block.endswith("\n") else newline) + f"model: {model}{newline}"
    return text[: opening.end()] + block + text[closing.start() :]


def _edit(job: jobs.Job, change: Callable[[str], str | None]) -> None:
    """Rewrite the job's file with `change` (its backup beside it first), writing nothing when the text stays as it is."""
    with _LOCK:
        try:
            with open(job.path, "r", encoding="utf-8", newline="") as f:
                text = f.read()
            bom, text = ("\ufeff", text[1:]) if text.startswith("\ufeff") else ("", text)  # an editor's mark, kept as it was
            changed = change(text)
            if changed is None:
                raise JobRefused("The properties at the top of that job are not closed with a line of three dashes. Fix them in the editor first.")
            if changed != text:
                write_atomic_text(job.path + ".bak", bom + text, newline="")
                write_atomic_text(job.path, bom + changed, newline="")
        except (OSError, UnicodeDecodeError):
            raise JobRefused("The job's file could not be saved.")


def _load(handle: str, name: str) -> tuple[dict[str, Any], jobs.Job]:
    persona = _persona(handle)
    job = jobs.load(persona["handle"], name)
    if job is None:
        raise JobMissing("There is no such job.")
    return persona, job


def set_enabled(handle: str, name: str, enabled: bool) -> dict[str, Any]:
    """Switch a job on or off. Switching it on also takes a pause off, so a job that stopped after failing is tried again."""
    persona, job = _load(handle, name)
    _edit(job, lambda text: _with_enabled(text, enabled))
    if enabled:
        job_state.resume(job.handle, name)
    return _row(jobs.load(job.handle, name) or job, persona)


def set_model(handle: str, name: str, model: str | None) -> dict[str, Any]:
    """Give a job a model of its own, or take it off (`None`) so the job uses the persona's. Which models are allowed is the
    route's rule; this only writes the one property."""
    persona, job = _load(handle, name)
    if model is not None and (not model.strip() or "\n" in model or "\r" in model):
        raise JobRefused("Pick a model from the list.")
    _edit(job, lambda text: _with_model(text, model))
    return _row(jobs.load(job.handle, name) or job, persona)


def create(handle: str) -> dict[str, Any]:
    """A new job file from the template, off, under the first free name `new-job`, `new-job-2`, and so on."""
    persona = _persona(handle)
    folder = jobs.jobs_dir(persona["handle"])
    if folder is None:
        raise JobRefused("This persona has nowhere to keep jobs.")
    with _LOCK:
        try:
            os.makedirs(folder, exist_ok=True)
            name = NEW_NAME
            number = 2
            while os.path.exists(os.path.join(folder, name + ".md")):
                name = f"{NEW_NAME}-{number}"
                number += 1
            write_atomic_text(os.path.join(folder, name + ".md"), TEMPLATE.format(persona=persona.get("name") or "the persona"))
        except OSError:
            raise JobRefused("The job could not be made.")
    job = jobs.load(persona["handle"], name)
    if job is None:
        raise JobRefused("The job could not be made.")
    return _row(job, persona)


def _clean_name(raw: str) -> str:
    """What the user typed as a job name, as a file name: lower case, runs of spaces as one dash, `.md` dropped."""
    name = re.sub(r"[\s]+", "-", raw.strip().lower())
    return name[:-3] if name.endswith(".md") else name


def _idle(job: jobs.Job) -> None:
    """Refuse while a run of the job is going: its file and record are in use."""
    with job_state.claim(job.handle, job.name) as free:
        if not free:
            raise JobRefused("This job is running now. Try again when it has finished.")


def rename(handle: str, name: str, new_name: str) -> dict[str, Any]:
    """Give a job another name: its file, its backup, its record (so a pause and the last run carry over) and the drafts it left waiting move together.
    The new name is made a file name (`Weekly review` becomes `weekly-review`); one that is taken or not usable is refused."""
    persona = _persona(handle)
    job = jobs.load(persona["handle"], name)
    if job is None:
        raise JobMissing("There is no such job.")
    target = _clean_name(new_name)
    if not jobs.valid_name(target):
        raise JobRefused("A job's name can use letters, numbers, dashes and underscores.")
    if target == name:
        return _row(job, persona)
    folder = os.path.dirname(job.path)
    with _LOCK:
        if os.path.exists(os.path.join(folder, target + ".md")):
            raise JobRefused(f"There is already a job called {target}.")
        _idle(job)
        try:
            os.rename(job.path, os.path.join(folder, target + ".md"))
            for parent, suffix in ((folder, ".md.bak"), (os.path.join(folder, job_state.STATE_FOLDER), ".json")):
                if os.path.exists(os.path.join(parent, name + suffix)):
                    os.replace(os.path.join(parent, name + suffix), os.path.join(parent, target + suffix))
        except OSError:
            raise JobRefused("The job could not be renamed.")
        _forget_lock(persona["handle"], name)
    draft_limit.rename_job(persona["handle"], name, target)
    renamed = jobs.load(persona["handle"], target)
    if renamed is None:
        raise JobRefused("The job could not be renamed.")
    return _row(renamed, persona)


def delete(handle: str, name: str) -> None:
    """Take a job away. Its file stays beside the others as `<name>.md.bak` (the same backup a switch keeps), so the text is
    not lost; its record goes."""
    persona = _persona(handle)
    job = jobs.load(persona["handle"], name)
    if job is None:
        raise JobMissing("There is no such job.")
    with _LOCK:
        _idle(job)
        try:
            os.replace(job.path, job.path + ".bak")
        except OSError:
            raise JobRefused("The job could not be deleted.")
        _remove(os.path.join(os.path.dirname(job.path), job_state.STATE_FOLDER, name + ".json"))
        _forget_lock(persona["handle"], name)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass  # a record or lock that is already gone is what was wanted


def _forget_lock(handle: str, name: str) -> None:
    folder = jobs.jobs_dir(handle)
    if folder is not None:
        _remove(os.path.join(folder, job_state.STATE_FOLDER, name + ".lock"))
