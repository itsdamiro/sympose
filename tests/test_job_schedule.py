"""When a scheduled job is due (docs/decisions/091): the plain-word schedules, the latest time one names, and a run
that was missed several times being due once."""

from datetime import datetime, time

import pytest

from sympose import job_schedule as js

SUN_EVENING = datetime(2026, 10, 25, 18, 30)  # a Sunday


@pytest.mark.parametrize("text, expected", [
    ("daily 07:30", js.Schedule("daily", at=time(7, 30))),
    ("  Daily   7:05 ", js.Schedule("daily", at=time(7, 5))),
    ("weekdays 23:59", js.Schedule("weekdays", at=time(23, 59))),
    ("weekly sun 18:00", js.Schedule("weekly", at=time(18, 0), day=6)),
    ("weekly Monday 00:00", js.Schedule("weekly", at=time(0, 0), day=0)),
    ("monthly 28 09:00", js.Schedule("monthly", at=time(9, 0), day=28)),
    ("every 6 hours", js.Schedule("hours", hours=6)),
    ("every 1 hour", js.Schedule("hours", hours=1)),
])
def test_a_schedule_in_words_is_read(text, expected):
    assert js.parse(text) == expected


@pytest.mark.parametrize("text", [
    "", "   ", "sometimes", "daily", "daily 25:00", "daily 07:60", "daily 7", "daily 07:30 extra", "weekly 18:00",
    "weekly funday 18:00", "monthly 0 09:00", "monthly 29 09:00", "monthly first 09:00", "monthly \u00b2 09:00", "every \u00b2 hours", "every 0 hours", "every 169 hours",
    "every 6 minutes", "every hours", "0 7 * * *",
])
def test_text_that_is_not_a_schedule_is_refused_with_a_reason(text):
    with pytest.raises(js.BadSchedule) as refused:
        js.parse(text)
    assert str(refused.value)


def test_the_latest_time_is_today_when_it_has_passed_and_the_last_one_when_not():
    daily = js.parse("daily 07:30")
    assert daily.latest(datetime(2026, 10, 21, 8, 0)) == datetime(2026, 10, 21, 7, 30)
    assert daily.latest(datetime(2026, 10, 21, 7, 29)) == datetime(2026, 10, 20, 7, 30)
    assert daily.latest(datetime(2026, 10, 21, 7, 30)) == datetime(2026, 10, 21, 7, 30)


def test_weekdays_skip_the_weekend_and_weekly_names_its_day():
    assert js.parse("weekdays 07:30").latest(datetime(2026, 10, 25, 12, 0)) == datetime(2026, 10, 23, 7, 30)  # Sunday: Friday's
    assert js.parse("weekly sun 18:00").latest(SUN_EVENING) == datetime(2026, 10, 25, 18, 0)
    assert js.parse("weekly sun 18:00").latest(datetime(2026, 10, 25, 17, 59)) == datetime(2026, 10, 18, 18, 0)


def test_monthly_names_its_day_across_a_short_month():
    monthly = js.parse("monthly 28 09:00")
    assert monthly.latest(datetime(2026, 3, 1, 0, 0)) == datetime(2026, 2, 28, 9, 0)
    assert monthly.latest(datetime(2026, 3, 28, 8, 59)) == datetime(2026, 2, 28, 9, 0)


def test_a_job_is_due_when_a_time_has_passed_since_it_last_ran():
    daily = js.parse("daily 07:30")
    assert daily.due(since=datetime(2026, 10, 20, 7, 31), now=datetime(2026, 10, 21, 7, 30))
    assert not daily.due(since=datetime(2026, 10, 21, 7, 31), now=datetime(2026, 10, 21, 12, 0))
    assert not daily.due(since=datetime(2026, 10, 21, 7, 30), now=datetime(2026, 10, 21, 7, 30))


def test_a_missed_week_is_due_once_and_a_new_job_waits_for_its_first_time():
    weekly = js.parse("weekly sun 18:00")
    since = datetime(2026, 10, 4, 18, 1)
    assert weekly.due(since=since, now=datetime(2026, 10, 25, 18, 30))
    ran = datetime(2026, 10, 25, 18, 30)  # it ran at the first check after the miss
    assert not weekly.due(since=ran, now=datetime(2026, 10, 25, 18, 35))
    just_written = datetime(2026, 10, 25, 19, 0)  # a job written after this Sunday's time
    assert not weekly.due(since=just_written, now=datetime(2026, 10, 25, 19, 5))
    assert weekly.due(since=just_written, now=datetime(2026, 11, 1, 18, 0))


def test_every_n_hours_counts_from_the_last_run():
    every = js.parse("every 6 hours")
    assert not every.due(since=datetime(2026, 10, 21, 6, 0), now=datetime(2026, 10, 21, 11, 59))
    assert every.due(since=datetime(2026, 10, 21, 6, 0), now=datetime(2026, 10, 21, 12, 0))
    assert every.latest(datetime(2026, 10, 21, 12, 0)) is None
