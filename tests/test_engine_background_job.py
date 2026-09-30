"""sympose.engine.background_job: one background run per persona at a time."""

import threading

from sympose.engine import background_job


def runner():
    return background_job.Runner("test", "Test job")


def test_a_started_job_runs_and_is_no_longer_running_afterwards():
    r, ran = runner(), threading.Event()
    assert r.start("samantha", ran.set) is True
    assert ran.wait(2) and r.wait("samantha", 2) is True
    assert r.is_running("samantha") is False


def test_a_second_start_for_the_same_handle_is_refused_while_one_runs():
    r, release, started = runner(), threading.Event(), threading.Event()

    def work():
        started.set()
        release.wait(2)

    assert r.start("samantha", work) is True
    started.wait(2)
    assert r.is_running("samantha") is True
    assert r.start("samantha", lambda: None) is False
    release.set()
    r.wait("samantha", 2)


def test_each_handle_runs_on_its_own():
    r, release, started = runner(), threading.Event(), threading.Event()
    r.start("samantha", lambda: (started.set(), release.wait(2)))
    started.wait(2)
    assert r.start("aria", lambda: None) is True
    release.set()
    r.wait("samantha", 2)


def test_waiting_gives_up_when_the_job_outlasts_the_timeout():
    r, release, started = runner(), threading.Event(), threading.Event()
    r.start("samantha", lambda: (started.set(), release.wait(2)))
    started.wait(2)
    assert r.wait("samantha", 0.01) is False
    release.set()
    r.wait("samantha", 2)


def test_waiting_with_nothing_running_returns_at_once():
    assert runner().wait("samantha", 0) is True


def test_a_job_that_raises_is_logged_and_frees_the_handle(caplog):
    r = runner()

    def boom():
        raise RuntimeError("no model")

    assert r.start("samantha", boom) is True
    r.wait("samantha", 2)
    assert r.is_running("samantha") is False
    assert "Test job for samantha failed: no model" in caplog.text
    assert r.start("samantha", lambda: None) is True
