"""How many new-note drafts one unattended source may leave waiting (docs/decisions/091 and 093, amended 2026-10-23).

A job runs and a Slack message arrives with nobody at the Mac, and whatever they propose waits in Drafts for the user's Accept.
Each such draft is tagged with its `source` (`job:<name>` or `slack`); a source with the limit already waiting files no more
until some are decided. The limit is one setting, `waiting_drafts`, for each job and for Slack alike. A draft counts while it is in
Drafts, so Accept and Decline free the room and nothing else is kept."""

from collections import Counter
from dataclasses import dataclass, field

from sympose import settings_store
from sympose import note_changes_store as store

SETTING = "waiting_drafts"
DEFAULT = 5
RANGE = (1, 100)
SLACK = "slack"
_JOB = "job:"


def job_source(name: str) -> str:
    return _JOB + name


@dataclass
class Filing:
    """What one turn's drafts are filed as, passed down to whatever files them: `source` is `SLACK` or `job_source(name)`, `None`
    for the web chat's, which is never counted or refused; `made` fills with `(draft path, proposal id)` for each new note filed, in
    the order they were made, so it is exactly this turn's drafts and never another conversation's."""

    source: str | None = None
    made: list[tuple[str, str]] = field(default_factory=list)


def limit() -> int:
    """The drafts one source may leave waiting (`waiting_drafts`, 1 to 100, default 5)."""
    value = settings_store.get(SETTING)
    ok = isinstance(value, int) and not isinstance(value, bool) and RANGE[0] <= value <= RANGE[1]
    return value if ok else DEFAULT


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
    if (count := waiting(handle, source, entries)) < limit():
        return None
    whose = "from Slack" if source == SLACK else "from this job"
    many = count != 1
    return f"{count} draft{'s' if many else ''} {whose} {'are' if many else 'is'} waiting to be accepted or declined, which is the limit, so no new one was made."
