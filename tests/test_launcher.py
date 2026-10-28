"""The `sympose` command (docs/decisions/028)."""

import pytest

from sympose import job_launchd, launcher


class _ImmediateTimer:
    """Stands in for `threading.Timer` so `--open`'s delayed browser launch runs synchronously."""

    def __init__(self, interval, function):
        self.function = function

    def start(self) -> None:
        self.function()


@pytest.fixture
def ran(monkeypatch):
    calls = {}
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.update(web=kw))
    from sympose import job_timer

    monkeypatch.setattr(job_timer, "start", lambda *a, **kw: calls.update(timer=calls.get("timer", 0) + 1))  # never a real pass over real jobs
    import sympose.cli.__main__ as cli_main

    monkeypatch.setattr(cli_main, "main", lambda: calls.update(cli=True))
    monkeypatch.delenv("PORT", raising=False)
    return calls


def test_with_no_command_it_lists_the_two(capsys):
    assert launcher.main([]) == 0

    out = capsys.readouterr().out
    assert "cli" in out and "web" in out and "usage: sympose" in out


def test_help_lists_them_and_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["-h"])

    assert stop.value.code == 0 and "terminal" in capsys.readouterr().out


def test_an_unknown_command_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["dashboard"])

    assert stop.value.code == 2


def test_cli_starts_the_terminal_chat(ran):
    assert launcher.main(["cli"]) == 0
    assert ran == {"cli": True}


def test_web_serves_on_this_machine_only_on_port_8000_by_default(ran, capsys):
    assert launcher.main(["web"]) == 0

    assert ran["web"] == {"host": "127.0.0.1", "port": 8000}
    assert "http://127.0.0.1:8000" in capsys.readouterr().out


def test_web_starts_the_jobs_timer_before_it_serves(ran):
    launcher.main(["web"])
    assert ran["timer"] == 1


def test_web_takes_its_port_from_the_flag_before_the_environment(ran, monkeypatch, capsys):
    monkeypatch.setenv("PORT", "9100")
    launcher.main(["web"])
    assert ran["web"]["port"] == 9100

    launcher.main(["web", "--port", "9200"])
    assert ran["web"]["port"] == 9200
    assert "http://127.0.0.1:9200" in capsys.readouterr().out


def test_web_has_no_way_to_listen_beyond_this_machine(ran, capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["web", "--host", "0.0.0.0"])

    assert stop.value.code == 2 and "host" not in ran


def test_a_port_that_is_not_a_number_is_said_plainly(ran, monkeypatch, capsys):
    monkeypatch.setenv("PORT", "eight")

    assert launcher.main(["web"]) == 1
    assert "PORT must be a number" in capsys.readouterr().err and "web" not in ran


def test_web_without_a_built_app_says_so_and_does_not_start(ran, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sympose.web_static.WEBUI_DIR", str(tmp_path))

    assert launcher.main(["web"]) == 1
    assert "no built web app" in capsys.readouterr().err and "web" not in ran


def test_web_open_opens_the_browser_once_it_has_started(ran, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    monkeypatch.setattr("threading.Timer", _ImmediateTimer)

    assert launcher.main(["web", "--open"]) == 0

    assert opened == ["http://127.0.0.1:8000"]


def test_web_without_open_does_not_touch_the_browser(ran, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)

    assert launcher.main(["web"]) == 0

    assert opened == []


def test_web_open_does_not_fail_the_server_when_no_browser_can_open(ran, monkeypatch):
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda url: (_ for _ in ()).throw(webbrowser.Error("no browser")))
    monkeypatch.setattr("threading.Timer", _ImmediateTimer)

    assert launcher.main(["web", "--open"]) == 0
    assert ran["web"] == {"host": "127.0.0.1", "port": 8000}


def test_web_mounts_the_app_after_the_api_so_the_api_wins(ran, monkeypatch):
    import uvicorn

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app))
    launcher.main(["web"])

    paths = [getattr(route, "path", "") for route in seen["app"].routes]
    assert paths.index("/health") < paths.index("/{path:path}")
    assert paths.index("/api/vaults") < paths.index("/{path:path}")
    assert paths[-1] == "/{path:path}"


def test_the_console_script_and_the_shipped_files_are_declared():
    import tomllib

    with open("pyproject.toml", "rb") as f:
        project = tomllib.load(f)

    assert project["project"]["scripts"] == {"sympose": "sympose.launcher:main"}
    data = project["tool"]["setuptools"]["package-data"]["sympose"]
    assert "webui/*" in data and "webui/assets/*" in data and "reference/*.md" in data


def test_only_this_machines_own_names_may_address_the_web_server(ran, monkeypatch):
    import uvicorn
    from fastapi.testclient import TestClient

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app))
    launcher.main(["web"])
    client = TestClient(seen["app"])

    for host in ("127.0.0.1:8000", "localhost:8000", "localhost", "127.0.0.1"):
        assert client.get("/health", headers={"host": host}).status_code == 200
    for host in ("evil.example", "evil.example:8000", "localhost.evil.example", "127.0.0.1.evil.example", "testserver"):
        assert client.get("/health", headers={"host": host}).status_code == 400
        assert client.get("/", headers={"host": host}).status_code == 400


def _scratch_env(monkeypatch, tmp_path, **variables):
    """A working folder holding a `.env` with `variables`, and an environment where none of them is set
    (`monkeypatch.setenv` first, so the value `load_dotenv` writes later is removed at the end of the test)."""
    for name in variables:
        monkeypatch.setenv(name, "unset")
        monkeypatch.delenv(name)
    (tmp_path / ".env").write_text("".join(f"{k}={v}\n" for k, v in variables.items()))
    monkeypatch.chdir(tmp_path)


def test_web_reads_the_env_file_of_the_folder_it_runs_in(ran, monkeypatch, tmp_path):
    _scratch_env(monkeypatch, tmp_path, PORT="9300")

    launcher.main(["web"])

    assert ran["web"]["port"] == 9300


# -- sympose run (docs/decisions/091) ---------------------------------------------------------------


@pytest.fixture
def jobs_run(monkeypatch, tmp_path):
    from sympose import job_run

    monkeypatch.setenv("SYMPOSE_LOG_DIR", str(tmp_path / "Logs"))  # a run of --due sets a big log aside: never the real one

    calls = []
    monkeypatch.setattr(job_run, "run_due", lambda: calls.append("due") or [job_run.Outcome("samantha/a", job_run.RAN, "Done.")])
    monkeypatch.setattr(
        job_run, "run", lambda handle, name, manual=False: calls.append((handle, name, manual)) or job_run.Outcome(f"{handle}/{name}", job_run.FAILED, "down"),
    )
    return calls


def test_run_due_runs_what_is_due_and_says_so(jobs_run, capsys):
    assert launcher.main(["run", "--due"]) == 0
    assert jobs_run == ["due"] and capsys.readouterr().out == "samantha/a: ran (Done.)\n"


def test_run_due_sets_a_big_log_aside_before_running(jobs_run, tmp_path, monkeypatch):
    from sympose import job_run

    log = tmp_path / "Logs" / "jobs.log"
    log.parent.mkdir()
    log.write_text("x" * (job_launchd.LOG_LIMIT + 1))

    seen = []
    monkeypatch.setattr(job_run, "run_due", lambda: seen.append(log.exists()) or [])

    launcher.main(["run", "--due"])

    assert seen == [False]  # set aside before the jobs start, not after
    assert not log.exists() and (tmp_path / "Logs" / "jobs.log.1").stat().st_size == job_launchd.LOG_LIMIT + 1


def test_run_with_a_job_runs_it_now_and_exits_one_when_it_did_not_run(jobs_run, capsys):
    assert launcher.main(["run", "samantha/weekly"]) == 1
    assert jobs_run == [("samantha", "weekly", True)] and capsys.readouterr().out == "samantha/weekly: failed (down)\n"


def test_run_needs_a_persona_and_a_name(jobs_run, capsys):
    assert launcher.main(["run", "weekly"]) == 1
    assert "persona/job" in capsys.readouterr().err and not jobs_run


def test_run_alone_or_with_both_prints_help_and_runs_nothing(jobs_run, capsys):
    assert launcher.main(["run"]) == 0
    assert launcher.main(["run", "--due", "samantha/weekly"]) == 1
    assert "--due" in capsys.readouterr().out and not jobs_run
