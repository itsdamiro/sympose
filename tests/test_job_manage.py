"""Settings' jobs (docs/decisions/091, slice 3): the list with how each last ran, the on/off switch that touches one
property and nothing else, a new job from the template, and a job's file opened in the editor by the persona-file routes."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import job_manage, job_state
from sympose.server import create_app

GOOD = "---\nschedule: weekly sun 18:00\nmodel: ollama/gemma4:e4b\n---\nDraft a weekly note.\n"


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    (directory / "jobs").mkdir()
    return directory


@pytest.fixture
def client(home):
    return TestClient(create_app())


def _write(home, name, text):
    (home / "jobs" / f"{name}.md").write_bytes(text.encode())


def test_the_list_has_each_job_with_its_last_run(home):
    _write(home, "weekly", GOOD)
    _write(home, "broken", "---\nschedule: whenever\n---\nx\n")
    from datetime import datetime

    job_state.record("samantha", "weekly", datetime(2026, 10, 18, 18, 0), "s1", error="model offline")
    rows = {r["name"]: r for r in job_manage.listing("samantha")}
    weekly = rows["weekly"]
    assert (weekly["schedule"], weekly["model"], weekly["cloud"], weekly["enabled"], weekly["problem"]) == ("weekly sun 18:00", "ollama/gemma4:e4b", False, True, None)
    assert (weekly["outcome"], weekly["last_run"], weekly["detail"], weekly["session_id"], weekly["file"]) == ("failed", "2026-10-18T18:00:00", "model offline", "s1", "jobs/weekly.md")
    assert rows["broken"]["problem"] and rows["broken"]["last_run"] is None


def test_a_mechanical_job_has_no_model(home):
    _write(home, "check", "---\nschedule: daily 07:30\nkind: health\nmodel: gpt-5\n---\n")
    row = job_manage.listing("samantha")[0]
    assert row["mechanical"] is True and row["model"] is None and row["cloud"] is False


def test_a_cloud_model_is_marked(home):
    _write(home, "weekly", GOOD.replace("ollama/gemma4:e4b", "gemini/gemini-2.5-flash"))
    assert job_manage.listing("samantha")[0]["cloud"] is True


@pytest.mark.parametrize(
    "before, after",
    [
        ("---\nschedule: daily 07:30\n---\nbody\n", "---\nschedule: daily 07:30\nenabled: false\n---\nbody\n"),
        ("---\nschedule: daily 07:30\nenabled: true\nkind: ask\n---\nbody\n", "---\nschedule: daily 07:30\nenabled: false\nkind: ask\n---\nbody\n"),
        ("---\r\nschedule: daily 07:30\r\n---\r\nbody\r\n", "---\r\nschedule: daily 07:30\r\nenabled: false\r\n---\r\nbody\r\n"),
        ("body only\n", "---\nenabled: false\n---\nbody only\n"),
    ],
)
def test_switching_off_changes_one_property(home, before, after):
    _write(home, "j", before)
    row = job_manage.set_enabled("samantha", "j", False)
    assert (home / "jobs" / "j.md").read_bytes().decode() == after
    assert row["enabled"] is False
    assert (home / "jobs" / "j.md.bak").read_bytes().decode() == before


def test_a_byte_order_mark_is_kept(home):
    _write(home, "j", "\ufeff" + GOOD)
    job_manage.set_enabled("samantha", "j", False)
    assert (home / "jobs" / "j.md").read_bytes().decode() == "\ufeff" + GOOD.replace("---\nDraft", "enabled: false\n---\nDraft")


def test_switching_to_what_it_already_is_writes_nothing(home):
    _write(home, "j", GOOD)
    job_manage.set_enabled("samantha", "j", True)
    assert (home / "jobs" / "j.md").read_text() == GOOD and not (home / "jobs" / "j.md.bak").exists()


def test_switching_on_lifts_a_pause(home):
    from datetime import datetime

    _write(home, "j", GOOD.replace("---\nDraft", "enabled: false\n---\nDraft"))
    for minute in range(3):
        job_state.record("samantha", "j", datetime(2026, 10, 18, 18, minute), None, error="x")
    assert job_manage.listing("samantha")[0]["paused"] is True
    row = job_manage.set_enabled("samantha", "j", True)
    assert row["enabled"] is True and row["paused"] is False and row["failures"] == 0


def test_an_unclosed_front_matter_is_refused_and_left_alone(home):
    _write(home, "j", "---\nschedule: daily 07:30\nbody\n")
    with pytest.raises(job_manage.JobRefused):
        job_manage.set_enabled("samantha", "j", False)
    assert (home / "jobs" / "j.md").read_text() == "---\nschedule: daily 07:30\nbody\n"


def test_no_such_job_or_persona_is_missing(home):
    with pytest.raises(job_manage.JobMissing):
        job_manage.set_enabled("samantha", "nope", True)
    with pytest.raises(job_manage.JobMissing):
        job_manage.listing("nobody")


def test_a_new_job_is_off_and_takes_the_first_free_name(home):
    first = job_manage.create("samantha")
    second = job_manage.create("samantha")
    assert (first["name"], second["name"]) == ("new-job", "new-job-2")
    assert first["enabled"] is False and first["problem"] is None
    assert "Samantha" in (home / "jobs" / "new-job.md").read_text()


def test_the_routes_list_create_and_switch(client, home):
    created = client.post("/api/personas/samantha/jobs").json()["job"]
    assert created["name"] == "new-job"
    assert [j["name"] for j in client.get("/api/personas/samantha/jobs").json()["jobs"]] == ["new-job"]
    on = client.put("/api/personas/samantha/jobs/new-job", json={"enabled": True})
    assert on.status_code == 200 and on.json()["job"]["enabled"] is True
    assert client.put("/api/personas/samantha/jobs/nope", json={"enabled": True}).status_code == 404
    assert client.get("/api/personas/nobody/jobs").status_code == 404
    assert client.put("/api/personas/samantha/jobs/..%2Fpersona", json={"enabled": True}).status_code == 404


def test_a_jobs_file_opens_and_saves_through_the_persona_file_routes(client, home):
    _write(home, "weekly", GOOD)
    opened = client.get("/api/personas/samantha/files/jobs/weekly.md").json()
    assert opened["content"] == GOOD and opened["mtime"] == (home / "jobs" / "weekly.md").stat().st_mtime
    saved = client.put("/api/personas/samantha/files/jobs/weekly.md", json={"content": GOOD + "More.\n", "expected_mtime": opened["mtime"]})
    assert saved.status_code == 200
    assert (home / "jobs" / "weekly.md").read_text() == GOOD + "More.\n"
    assert (home / "jobs" / "weekly.md.bak").read_text() == GOOD
    stale = client.put("/api/personas/samantha/files/jobs/weekly.md", json={"content": "x", "expected_mtime": opened["mtime"] - 5})
    assert stale.status_code == 409


def test_only_a_job_that_exists_and_has_a_plain_name_is_reachable(client, home):
    assert client.get("/api/personas/samantha/files/jobs/nope.md").status_code == 404
    assert client.put("/api/personas/samantha/files/jobs/nope.md", json={"content": "x"}).status_code == 404
    assert not (home / "jobs" / "nope.md").exists()
    # files that exist but are not a job's: another folder's, a name that is not a plain job name, a way back out
    (home / "other").mkdir()
    (home / "other" / "x.md").write_text("not a job")
    (home / "soul.md").write_text("voice")
    _write(home, "Upper", GOOD)
    (home / "jobs" / "x.md.bak").write_text("backup")
    for hidden in ("other/x.md", "jobs/Upper.md", "jobs/x.md.bak", "jobs%2F..%2Fsoul.md"):
        assert client.get(f"/api/personas/samantha/files/{hidden}").status_code == 404, hidden
        assert client.put(f"/api/personas/samantha/files/{hidden}", json={"content": "x"}).status_code == 404, hidden
    assert (home / "soul.md").read_text() == "voice" and (home / "other" / "x.md").read_text() == "not a job"
    for bad in ("jobs/..%2Fpersona.yaml", "jobs/.state/x.md", "jobs/x.md.bak", "jobs/Upper.md", "other/x.md", "jobs/a/b.md"):
        assert client.get(f"/api/personas/samantha/files/{bad}").status_code == 404, bad
    assert (home / "persona.yaml").read_text().startswith("name: Samantha")
    # the pending route for a real file keeps its own path
    assert client.get("/api/personas/samantha/files/profile.md/pending").status_code == 404


def test_a_renamed_job_takes_its_file_backup_and_record_along(client, home):
    from datetime import datetime

    _write(home, "weekly", GOOD)
    (home / "jobs" / "weekly.md.bak").write_text("older")
    job_state.record("samantha", "weekly", datetime(2026, 10, 18, 18, 0), "s1")
    reply = client.post("/api/personas/samantha/jobs/weekly/rename", json={"name": "  Weekly Review "})
    assert reply.status_code == 200 and reply.json()["job"]["name"] == "weekly-review"
    assert reply.json()["job"]["file"] == "jobs/weekly-review.md" and reply.json()["job"]["last_run"] == "2026-10-18T18:00:00"
    assert (home / "jobs" / "weekly-review.md").read_text() == GOOD and (home / "jobs" / "weekly-review.md.bak").read_text() == "older"
    assert not (home / "jobs" / "weekly.md").exists() and not (home / "jobs" / "weekly.md.bak").exists()
    assert job_state.read("samantha", "weekly").last_run is None
    assert [j["name"] for j in client.get("/api/personas/samantha/jobs").json()["jobs"]] == ["weekly-review"]


def test_a_rename_that_cannot_be_done_changes_nothing(client, home):
    _write(home, "weekly", GOOD)
    _write(home, "daily", GOOD)
    taken = client.post("/api/personas/samantha/jobs/weekly/rename", json={"name": "daily"})
    assert taken.status_code == 422 and "already" in taken.json()["detail"]
    for bad in ("", "a/b", "..", "weekly!", ".hidden"):
        assert client.post("/api/personas/samantha/jobs/weekly/rename", json={"name": bad}).status_code == 422, bad
    assert client.post("/api/personas/samantha/jobs/nope/rename", json={"name": "x"}).status_code == 404
    assert (home / "jobs" / "weekly.md").read_text() == GOOD and (home / "jobs" / "daily.md").read_text() == GOOD
    same = client.post("/api/personas/samantha/jobs/weekly/rename", json={"name": "weekly"})
    assert same.status_code == 200 and same.json()["job"]["name"] == "weekly"


def test_a_deleted_job_is_gone_from_the_list_but_its_text_is_kept(client, home):
    from datetime import datetime

    _write(home, "weekly", GOOD)
    job_state.record("samantha", "weekly", datetime(2026, 10, 18, 18, 0), "s1")
    assert client.delete("/api/personas/samantha/jobs/weekly").status_code == 200
    assert client.get("/api/personas/samantha/jobs").json()["jobs"] == []
    assert not (home / "jobs" / "weekly.md").exists() and (home / "jobs" / "weekly.md.bak").read_text() == GOOD
    assert job_state.read("samantha", "weekly").last_run is None
    assert client.delete("/api/personas/samantha/jobs/weekly").status_code == 404
    assert client.delete("/api/personas/samantha/jobs/..%2Fpersona").status_code == 404
    assert (home / "persona.yaml").exists()


def test_a_job_that_is_running_is_neither_renamed_nor_deleted(client, home):
    _write(home, "weekly", GOOD)
    with job_state.claim("samantha", "weekly") as mine:
        assert mine
        renamed = client.post("/api/personas/samantha/jobs/weekly/rename", json={"name": "other"})
        deleted = client.delete("/api/personas/samantha/jobs/weekly")
    assert renamed.status_code == 422 and deleted.status_code == 422 and "running" in deleted.json()["detail"]
    assert (home / "jobs" / "weekly.md").read_text() == GOOD


@pytest.mark.parametrize(
    "before, model, after",
    [
        ("---\nschedule: daily 07:30\n---\nbody\n", "gpt-5", "---\nschedule: daily 07:30\nmodel: gpt-5\n---\nbody\n"),
        ("---\nschedule: daily 07:30\nmodel: ollama/gemma4:e4b\nkind: ask\n---\nbody\n", "gpt-5", "---\nschedule: daily 07:30\nmodel: gpt-5\nkind: ask\n---\nbody\n"),
        ("---\nschedule: daily 07:30\nmodel: ollama/gemma4:e4b\nkind: ask\n---\nbody\n", None, "---\nschedule: daily 07:30\nkind: ask\n---\nbody\n"),
        ("---\r\nschedule: daily 07:30\r\n---\r\nbody\r\n", "gpt-5", "---\r\nschedule: daily 07:30\r\nmodel: gpt-5\r\n---\r\nbody\r\n"),
        ("body only\n", "gpt-5", "---\nmodel: gpt-5\n---\nbody only\n"),
    ],
)
def test_choosing_a_model_changes_one_property(home, before, model, after):
    _write(home, "j", before)
    row = job_manage.set_model("samantha", "j", model)
    assert (home / "jobs" / "j.md").read_bytes().decode() == after
    assert row["own_model"] == model
    assert (home / "jobs" / "j.md.bak").read_bytes().decode() == before


def test_clearing_a_model_the_job_never_had_writes_nothing(home):
    _write(home, "j", "---\nschedule: daily 07:30\n---\nbody\n")
    row = job_manage.set_model("samantha", "j", None)
    assert row["own_model"] is None and not (home / "jobs" / "j.md.bak").exists()


def test_a_model_with_a_line_break_is_refused_and_the_file_left_alone(home):
    _write(home, "j", GOOD)
    with pytest.raises(job_manage.JobRefused):
        job_manage.set_model("samantha", "j", "gpt-5\nenabled: false")
    assert (home / "jobs" / "j.md").read_text() == GOOD


def test_an_unclosed_front_matter_is_refused_for_a_model_too(home):
    _write(home, "j", "---\nschedule: daily 07:30\nbody\n")
    with pytest.raises(job_manage.JobRefused):
        job_manage.set_model("samantha", "j", "gpt-5")


def test_a_mechanical_job_reports_no_own_model(home):
    _write(home, "check", "---\nschedule: daily 07:30\nkind: health\nmodel: gpt-5\n---\n")
    assert job_manage.listing("samantha")[0]["own_model"] is None


def test_the_model_route_takes_a_listed_model_or_none(client, home):
    from sympose.engine.model_options import MODEL_OPTIONS

    _write(home, "weekly", GOOD)
    listed = MODEL_OPTIONS[0].id
    chosen = client.put("/api/personas/samantha/jobs/weekly/model", json={"model": listed})
    assert chosen.status_code == 200 and chosen.json()["job"]["own_model"] == listed and f"model: {listed}\n" in (home / "jobs" / "weekly.md").read_text()
    cleared = client.put("/api/personas/samantha/jobs/weekly/model", json={"model": None})
    assert cleared.status_code == 200 and cleared.json()["job"]["own_model"] is None and "model:" not in (home / "jobs" / "weekly.md").read_text()


def test_the_model_route_refuses_what_is_not_offered_and_what_is_not_there(client, home):
    _write(home, "weekly", GOOD)
    assert client.put("/api/personas/samantha/jobs/weekly/model", json={"model": "made-up/model"}).status_code == 422
    assert (home / "jobs" / "weekly.md").read_text() == GOOD
    assert client.put("/api/personas/samantha/jobs/nope/model", json={"model": None}).status_code == 404
    assert client.put("/api/personas/nobody/jobs/weekly/model", json={"model": None}).status_code == 404
    assert client.put("/api/personas/samantha/jobs/..%2Fpersona/model", json={"model": None}).status_code == 404
