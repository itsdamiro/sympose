"""The Slack conversation map and the deliveries seen (docs/decisions/093)."""

import json

import pytest
from helpers import write_persona

from sympose import slack_sessions


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


def test_a_key_keeps_its_conversation_and_another_key_has_its_own(home):
    a = slack_sessions.session_for("samantha", "dm:D1")
    assert slack_sessions.session_for("samantha", "dm:D1") == a
    assert slack_sessions.session_for("samantha", "thread:C1:1.1") != a


def test_the_map_is_a_hidden_file_in_the_personas_folder_and_survives_a_restart(home):
    a = slack_sessions.session_for("samantha", "dm:D1")
    assert json.loads((home / ".slack" / "sessions.json").read_text()) == {"dm:D1": a}
    assert slack_sessions.session_for("samantha", "dm:D1") == a  # read back from the file


def test_each_persona_has_its_own_map(home, tmp_path):
    write_persona(tmp_path / "profiles", "archia", "name: Archia\n")
    assert slack_sessions.session_for("samantha", "dm:D1") != slack_sessions.session_for("archia", "dm:D1")
    assert (tmp_path / "profiles" / "archia" / ".slack" / "sessions.json").exists()


def test_start_over_gives_another_conversation_and_keeps_it(home):
    old = slack_sessions.session_for("samantha", "dm:D1")
    new = slack_sessions.start_over("samantha", "dm:D1")
    assert new != old
    assert slack_sessions.session_for("samantha", "dm:D1") == new


def test_a_map_that_cannot_be_read_starts_empty_instead_of_failing(home):
    (home / ".slack").mkdir()
    (home / ".slack" / "sessions.json").write_text("{not json")
    assert slack_sessions.session_for("samantha", "dm:D1")


def test_a_map_of_the_wrong_shape_is_ignored(home):
    (home / ".slack").mkdir()
    (home / ".slack" / "sessions.json").write_text(json.dumps({"dm:D1": 5, "ok": "id"}))
    assert slack_sessions._read("samantha") == {"ok": "id"}


def test_a_delivery_is_new_once():
    seen = slack_sessions.Seen()
    assert seen.first_time("Ev1")
    assert not seen.first_time("Ev1")
    assert seen.first_time("Ev2")


def test_a_delivery_without_an_id_is_always_new():
    seen = slack_sessions.Seen()
    assert seen.first_time(None) and seen.first_time(None)


def test_the_oldest_ids_are_forgotten_beyond_the_limit():
    seen = slack_sessions.Seen(limit=2)
    for event_id in ("a", "b", "c"):
        seen.first_time(event_id)
    assert seen.first_time("a")  # forgotten
    assert not seen.first_time("c")
