"""When a scheduled job is due (docs/decisions/091). A schedule is written in plain words, not cron:
`daily 07:30`, `weekdays 07:30`, `weekly sun 18:00`, `monthly 1 09:00`, `every 6 hours`. Times are the user's own
clock, so every datetime here is naive local time (the hour an hour-long DST jump skips is not worked around).

A calendar schedule has a latest time that has already passed; the job is due when that time is after the moment it
last ran (or, for a job that never ran, was last changed). A run that was missed several times is therefore due once,
not once for each miss. `every N hours` is due N hours after the last run."""

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_DAY_ALIASES = {full: short for short, full in zip(DAYS, ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"))}
MAX_MONTH_DAY = 28  # a day every month has
MAX_HOURS = 168
_EXAMPLES = "daily 07:30, weekdays 07:30, weekly sun 18:00, monthly 1 09:00 or every 6 hours"
_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class BadSchedule(ValueError):
    """The text is not a schedule; the message says what is wrong, in words for the person who wrote it."""


@dataclass(frozen=True)
class Schedule:
    kind: str  # daily, weekdays, weekly, monthly or hours
    at: time | None = None
    day: int | None = None  # weekly: 0 is Monday; monthly: the day of the month
    hours: int | None = None

    def latest(self, now: datetime) -> datetime | None:
        """The most recent time at or before `now` this schedule names; `None` for `every N hours`, which has none."""
        if self.at is None:
            return None
        for back in range(32):
            day = (now - timedelta(days=back)).date()
            if self._on(day.weekday(), day.day):
                slot = datetime.combine(day, self.at)
                if slot <= now:
                    return slot
        return None

    def _on(self, weekday: int, month_day: int) -> bool:
        if self.kind == "daily":
            return True
        if self.kind == "weekdays":
            return weekday < 5
        if self.kind == "weekly":
            return weekday == self.day
        return month_day == self.day

    def due(self, since: datetime, now: datetime) -> bool:
        """`since` is when the job last ran, or, for one that never ran, when its file was last changed."""
        if self.hours is not None:
            return now - since >= timedelta(hours=self.hours)
        slot = self.latest(now)
        return slot is not None and slot > since


def _time(word: str) -> time:
    found = _TIME.match(word)
    if not found:
        raise BadSchedule(f"'{word}' is not a time like 07:30 (24-hour clock).")
    return time(int(found.group(1)), int(found.group(2)))


def parse(text: str) -> Schedule:
    words = str(text).lower().split()
    if not words:
        raise BadSchedule(f"There is no schedule. Write one like {_EXAMPLES}.")
    kind, rest = words[0], words[1:]
    if kind in ("daily", "weekdays"):
        if len(rest) != 1:
            raise BadSchedule(f"'{kind}' takes a time, like '{kind} 07:30'.")
        return Schedule(kind, at=_time(rest[0]))
    if kind == "weekly":
        if len(rest) != 2 or _DAY_ALIASES.get(rest[0], rest[0]) not in DAYS:
            raise BadSchedule("'weekly' takes a day and a time, like 'weekly sun 18:00'.")
        return Schedule(kind, at=_time(rest[1]), day=DAYS.index(_DAY_ALIASES.get(rest[0], rest[0])))
    if kind == "monthly":
        if len(rest) != 2 or not rest[0].isdecimal() or not 1 <= int(rest[0]) <= MAX_MONTH_DAY:
            raise BadSchedule(f"'monthly' takes a day from 1 to {MAX_MONTH_DAY} and a time, like 'monthly 1 09:00'.")
        return Schedule(kind, at=_time(rest[1]), day=int(rest[0]))
    if kind == "every":
        if len(rest) != 2 or not rest[0].isdecimal() or rest[1] not in ("hour", "hours") or not 1 <= int(rest[0]) <= MAX_HOURS:
            raise BadSchedule(f"'every' takes a number of hours from 1 to {MAX_HOURS}, like 'every 6 hours'.")
        return Schedule("hours", hours=int(rest[0]))
    raise BadSchedule(f"'{words[0]}' is not a schedule. Write one like {_EXAMPLES}.")
