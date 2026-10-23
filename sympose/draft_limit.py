"""How many new-note drafts one unattended source may leave waiting (docs/decisions/091 and 093, amended 2026-10-23).

A job runs and a Slack message arrives with nobody at the Mac, and whatever they propose waits in Drafts for the user's Accept.
Each such draft is tagged with its `source` (`job:<name>` or `slack`); a source with its limit already waiting files no more
until some are decided. A draft counts while it is in Drafts, so Accept and Decline free the room and nothing else is kept."""

from collections import Counter

from sympose import jobs, settings_store
from sympose import note_changes_store as store

JOB_SETTING, SLACK_SETTING = "job_waiting_drafts", "slack_waiting_drafts"
DEFAULT_JOB, DEFAULT_SLACK = 5, 10
RANGE = (1, 100)
SLACK = "slack"
_JOB = "job:"


def job_source(name: str) -> str:
    return _JOB + name


def _whole(key: str, default: int) -> int:
    value = settings_store.get(key)
    ok = isinstance(value, int) and not isinstance(value, bool) and RANGE[0] <= value <= RANGE[1]
    return value if ok else default


def job_default() -> int:
    """The drafts a job may leave waiting unless its own file says otherwise (`job_waiting_drafts`, 1 to 100, default 5)."""
    return _whole(JOB_SETTING, DEFAULT_JOB)


def slack_limit() -> int:
    """The drafts from Slack that may wait, all together (`slack_waiting_drafts`, 1 to 100, default 10)."""
    return _whole(SLACK_SETTING, DEFAULT_SLACK)


def limit(handle: str, source: str) -> int | None:
    """The most drafts `source` may leave waiting; `None` for a source with no limit."""
    if source == SLACK:
        return slack_limit()
    if source.startswith(_JOB):
        job = jobs.load(handle, source[len(_JOB):])
        return (job.max_waiting_drafts if job is not None else None) or job_default()
    return None


def counts(handle: str, entries: list[dict] | None = None) -> Counter[str]:
    """How many new-note drafts wait now from each source. `entries` is the store as already read, when the caller has it."""
    found = store.entries(handle) if entries is None else entries
    return Counter(p["source"] for entry in found for p in entry["proposals"] if p.get("source"))


def waiting(handle: str, source: str, entries: list[dict] | None = None) -> int:
    """How many new-note drafts from `source` wait now."""
    return counts(handle, entries)[source]


def rename_job(handle: str, old: str, new: str) -> None:
    """A job was renamed: the drafts it left waiting follow it, so they still count against it."""
    def retag(entry: dict) -> None:
        for p in entry["proposals"]:
            if p.get("source") == job_source(old):
                p["source"] = job_source(new)

    for entry in store.entries(handle):
        if any(p.get("source") == job_source(old) for p in entry["proposals"]):
            store.update(handle, entry["path"], retag)


def refusal(handle: str, source: str, entries: list[dict] | None = None) -> str | None:
    """Why `source` may not file another draft, or `None` when it may."""
    cap = limit(handle, source)
    if cap is None or (count := waiting(handle, source, entries)) < cap:
        return None
    whose = "from Slack" if source == SLACK else "from this job"
    many = count != 1
    return f"{count} draft{'s' if many else ''} {whose} {'are' if many else 'is'} waiting to be accepted or declined, which is the limit, so no new one was made."
