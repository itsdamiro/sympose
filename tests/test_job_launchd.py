"""The operating system's part of scheduled runs (docs/decisions/091, slice 4): the launchd entry, `sympose schedule`,
Settings' switch and the web app's timer. `launchctl` is never run: it is replaced by a recorder."""

import plistlib
import subprocess
import threading

import pytest
from fastapi.testclient import TestClient

from sympose import job_launchd, job_timer, launcher
from sympose.server import create_app


class Recorder:
    def __init__(self):
        self.calls: list[tuple[str, ...]] = []
        self.refuse_bootstrap: str | None = None

    def __call__(self, *args):
        self.calls.append(args)
        failing = args[0] == "bootstrap" and self.refuse_bootstrap is not None
        return subprocess.CompletedProcess(args, 5 if failing else 0, "", self.refuse_bootstrap or "")


@pytest.fixture(autouse=True)
def never_the_real_launchctl(tmp_path, monkeypatch):
    """A test that forgets to stand in for `launchctl` must fail, not load a service into the real login session; the
    folders the entry and its log go to are the test's own for the same reason."""

    def real(*args):
        raise AssertionError(f"launchctl {args} would have run for real")

    monkeypatch.setattr(job_launchd, "_launchctl", real)
    monkeypatch.setenv("SYMPOSE_LAUNCH_AGENTS_DIR", str(tmp_path / "LaunchAgents"))
    monkeypatch.setenv("SYMPOSE_LOG_DIR", str(tmp_path / "Logs"))


@pytest.fixture
def launchctl(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_LAUNCH_AGENTS_DIR", str(tmp_path / "LaunchAgents"))
    monkeypatch.setenv("SYMPOSE_LOG_DIR", str(tmp_path / "Logs"))
    monkeypatch.setattr(job_launchd, "supported", lambda: True)
    recorder = Recorder()
    monkeypatch.setattr(job_launchd, "_launchctl", recorder)
    return recorder


def test_install_writes_an_entry_that_runs_the_due_jobs_every_five_minutes(launchctl, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    job_launchd.install()
    entry = plistlib.loads(job_launchd.plist_path().read_bytes())
    assert entry["Label"] == "com.sympose.jobs" and entry["StartInterval"] == 300 and entry["RunAtLoad"] is False
    assert entry["ProgramArguments"][1:] == ["-m", "sympose.launcher", "run", "--due"]
    assert entry["WorkingDirectory"] == str(tmp_path)  # where its .env is read from
    assert entry["StandardOutPath"] == str(tmp_path / "Logs" / "jobs.log") and (tmp_path / "Logs").is_dir()


def test_a_log_over_the_limit_is_set_aside_replacing_the_older_copy(tmp_path):
    log = tmp_path / "Logs" / "jobs.log"
    log.parent.mkdir()
    log.write_text("new" * 10)
    (tmp_path / "Logs" / "jobs.log.1").write_text("old")

    job_launchd.rotate_log(limit=29)

    assert not log.exists() and (tmp_path / "Logs" / "jobs.log.1").read_text() == "new" * 10


def test_a_log_at_the_limit_or_missing_is_left_alone(tmp_path):
    job_launchd.rotate_log(limit=10)  # no log at all: nothing to do, nothing raised
    log = tmp_path / "Logs" / "jobs.log"
    log.parent.mkdir()
    log.write_text("x" * 10)

    job_launchd.rotate_log(limit=10)

    assert log.read_text() == "x" * 10 and not (tmp_path / "Logs" / "jobs.log.1").exists()


def test_a_log_that_cannot_be_moved_does_not_stop_the_run(tmp_path, monkeypatch):
    log = tmp_path / "Logs" / "jobs.log"
    log.parent.mkdir()
    log.write_text("x" * 20)
    monkeypatch.setattr(job_launchd.os, "replace", lambda *a: (_ for _ in ()).throw(PermissionError("no")))

    job_launchd.rotate_log(limit=10)

    assert log.read_text() == "x" * 20


def test_install_loads_the_entry_after_unloading_an_old_one(launchctl):
    job_launchd.install()
    assert [c[0] for c in launchctl.calls] == ["bootout", "bootstrap"]
    assert launchctl.calls[1][2] == str(job_launchd.plist_path())
    assert job_launchd.installed()


def test_the_entry_keeps_only_the_settings_that_point_at_sympose_folders(launchctl, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", "/v")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.delenv("SYMPOSE_PROFILES_DIR", raising=False)
    monkeypatch.delenv("SYMPOSE_SETTINGS_PATH", raising=False)
    job_launchd.install()
    assert plistlib.loads(job_launchd.plist_path().read_bytes())["EnvironmentVariables"] == {"VAULT_PATHS": "/v"}


def test_with_no_such_settings_the_entry_has_no_environment(launchctl, monkeypatch):
    for name in ("VAULT_PATHS", "SYMPOSE_PROFILES_DIR", "SYMPOSE_SETTINGS_PATH"):
        monkeypatch.delenv(name, raising=False)
    job_launchd.install()
    assert "EnvironmentVariables" not in plistlib.loads(job_launchd.plist_path().read_bytes())


def test_a_refused_load_leaves_no_entry_and_says_why(launchctl):
    launchctl.refuse_bootstrap = "Bootstrap failed: 5: Input/output error"
    with pytest.raises(job_launchd.ScheduleRefused, match="Input/output error"):
        job_launchd.install()
    assert not job_launchd.plist_path().exists() and not job_launchd.installed()


def test_a_setting_the_env_file_gives_is_left_to_it_so_an_edit_of_the_file_applies(launchctl, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("VAULT_PATHS=/from-file\nSYMPOSE_PROFILES_DIR=/p-file\n")
    monkeypatch.setenv("VAULT_PATHS", "/from-file")  # what load_env put there
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", "/p-shell")  # exported in the shell, so it won over the file
    monkeypatch.delenv("SYMPOSE_SETTINGS_PATH", raising=False)
    job_launchd.install()
    assert plistlib.loads(job_launchd.plist_path().read_bytes())["EnvironmentVariables"] == {"SYMPOSE_PROFILES_DIR": "/p-shell"}


def test_a_refused_reinstall_puts_the_working_entry_back_and_loads_it(launchctl, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    job_launchd.install()
    before = job_launchd.plist_path().read_bytes()
    monkeypatch.setenv("VAULT_PATHS", "/changed")
    launchctl.refuse_bootstrap = "Bootstrap failed: 5: Input/output error"
    launchctl.calls.clear()
    with pytest.raises(job_launchd.ScheduleRefused, match="Input/output error"):
        job_launchd.install()
    assert job_launchd.plist_path().read_bytes() == before and job_launchd.installed()
    assert [c[0] for c in launchctl.calls] == ["bootout", "bootstrap", "bootstrap"]  # the old one is loaded again


def test_remove_unloads_and_deletes_and_is_fine_when_nothing_is_there(launchctl):
    job_launchd.remove()
    job_launchd.install()
    job_launchd.remove()
    assert not job_launchd.plist_path().exists() and launchctl.calls[-1][0] == "bootout"


def test_where_launchd_does_not_exist_install_is_refused_and_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_LAUNCH_AGENTS_DIR", str(tmp_path / "LaunchAgents"))
    monkeypatch.setattr(job_launchd, "supported", lambda: False)
    with pytest.raises(job_launchd.ScheduleRefused, match="macOS"):
        job_launchd.install()
    assert not (tmp_path / "LaunchAgents").exists() and not job_launchd.installed()


def test_a_leftover_file_does_not_count_as_installed_where_launchd_does_not_exist(launchctl, monkeypatch):
    job_launchd.install()
    monkeypatch.setattr(job_launchd, "supported", lambda: False)
    assert job_launchd.plist_path().exists() and not job_launchd.installed()


def test_settings_reads_and_switches_the_schedule(launchctl):
    client = TestClient(create_app())
    assert client.get("/api/schedule").json() == {"supported": True, "installed": False}
    assert client.put("/api/schedule", json={"installed": True}).json() == {"supported": True, "installed": True}
    assert client.put("/api/schedule", json={"installed": False}).json() == {"supported": True, "installed": False}


def test_settings_shows_a_refusal_as_it_is(launchctl):
    launchctl.refuse_bootstrap = "no way"
    answer = TestClient(create_app()).put("/api/schedule", json={"installed": True})
    assert answer.status_code == 422 and "no way" in answer.json()["detail"]


def test_the_command_installs_removes_and_reports(launchctl, capsys):
    assert launcher.main(["schedule", "status"]) == 0 and "Not installed" in capsys.readouterr().out
    assert launcher.main(["schedule", "install"]) == 0 and "every 5 minutes" in capsys.readouterr().out
    assert launcher.main(["schedule", "status"]) == 0 and "Installed" in capsys.readouterr().out
    assert launcher.main(["schedule", "remove"]) == 0 and not job_launchd.installed()


def test_the_command_says_so_where_it_cannot_work(monkeypatch, capsys):
    monkeypatch.setattr(job_launchd, "supported", lambda: False)
    assert launcher.main(["schedule", "install"]) == 1 and "macOS" in capsys.readouterr().err


def test_the_command_exits_one_with_the_reason_when_launchd_refuses(launchctl, capsys):
    launchctl.refuse_bootstrap = "no way"
    assert launcher.main(["schedule", "install"]) == 1 and "no way" in capsys.readouterr().err


def test_the_timer_looks_for_due_jobs_at_once_and_again_each_interval(monkeypatch):
    passes = threading.Semaphore(0)
    monkeypatch.setattr(job_timer.job_run, "run_due", lambda: passes.release() or [])
    stop = job_timer.start(every=0.01)
    try:
        assert all(passes.acquire(timeout=5) for _ in range(3))
    finally:
        stop.set()


def test_the_first_pass_is_at_once_not_after_an_interval(monkeypatch):
    first = threading.Event()
    monkeypatch.setattr(job_timer.job_run, "run_due", lambda: first.set() or [])
    stop = job_timer.start(every=3600)
    try:
        assert first.wait(5)  # a job missed while the app was closed runs now
    finally:
        stop.set()


def test_the_timer_waits_out_the_interval_between_passes(monkeypatch):
    count = []
    first = threading.Event()
    monkeypatch.setattr(job_timer.job_run, "run_due", lambda: count.append(1) or first.set() or [])
    stop = job_timer.start(every=3600)
    try:
        assert first.wait(5)
        threading.Event().wait(0.2)
        assert len(count) == 1
    finally:
        stop.set()


def test_one_failed_pass_does_not_end_the_timer(monkeypatch):
    seen = []
    done = threading.Event()

    def run_due():
        seen.append(1)
        if len(seen) == 1:
            raise RuntimeError("disk gone")
        done.set()
        return []

    monkeypatch.setattr(job_timer.job_run, "run_due", run_due)
    stop = job_timer.start(every=0.01)
    try:
        assert done.wait(5)
    finally:
        stop.set()


def test_stopping_the_timer_stops_the_passes(monkeypatch):
    count = []
    twice = threading.Event()

    def run_due():
        count.append(1)
        if len(count) >= 2:
            twice.set()
        return []

    monkeypatch.setattr(job_timer.job_run, "run_due", run_due)
    stop = job_timer.start(every=0.01)
    assert twice.wait(5)
    stop.set()
    threading.Event().wait(0.1)
    settled = len(count)
    threading.Event().wait(0.1)
    assert len(count) == settled
