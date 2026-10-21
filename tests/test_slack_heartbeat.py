"""Whether a persona is connected to Slack now (docs/decisions/093): the heartbeat file and the thread that keeps it."""

import os
import time

import pytest
from helpers import write_persona

from sympose import server_persona_handlers as ph
from sympose import slack_heartbeat
from sympose.slack_heartbeat import FRESH_SECONDS


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return base


def test_a_persona_that_never_beat_is_not_connected(home):
    assert slack_heartbeat.connected("samantha") is False


def test_a_beat_says_connected_and_stop_says_not(home):
    slack_heartbeat.beat("samantha")
    assert slack_heartbeat.connected("samantha") is True
    slack_heartbeat.stop("samantha")
    assert slack_heartbeat.connected("samantha") is False


def test_the_file_is_in_the_personas_own_folder_out_of_the_vault(home):
    slack_heartbeat.beat("samantha")
    assert (home / "samantha" / ".slack" / "heartbeat").is_file()


def test_a_beat_is_fresh_up_to_the_limit_and_stale_after_it(home):
    slack_heartbeat.beat("samantha")
    then = os.path.getmtime(home / "samantha" / ".slack" / "heartbeat")
    assert slack_heartbeat.connected("samantha", now=then + FRESH_SECONDS) is True
    assert slack_heartbeat.connected("samantha", now=then + FRESH_SECONDS + 1) is False


def test_a_beat_stays_fresh_for_a_minute_and_not_much_longer(home):
    slack_heartbeat.beat("samantha")
    then = os.path.getmtime(home / "samantha" / ".slack" / "heartbeat")
    assert slack_heartbeat.connected("samantha", now=then + 59) is True
    assert slack_heartbeat.connected("samantha", now=then + 61) is False


def test_a_second_beat_makes_an_old_file_fresh_again(home):
    slack_heartbeat.beat("samantha")
    path = home / "samantha" / ".slack" / "heartbeat"
    os.utime(path, (1, 1))
    assert slack_heartbeat.connected("samantha") is False
    slack_heartbeat.beat("samantha")
    assert slack_heartbeat.connected("samantha") is True


def test_stopping_a_persona_that_never_beat_is_quiet(home):
    slack_heartbeat.stop("samantha")


def test_a_handle_that_is_not_one_is_not_connected_and_beating_it_raises_nothing(home):
    assert slack_heartbeat.connected("../x") is False


class _Client:
    def __init__(self, up):
        self.up = up

    def is_connected(self):
        if isinstance(self.up, Exception):
            raise self.up
        return self.up


class _Handler:
    def __init__(self, up):
        self.client = _Client(up)


def test_the_thread_beats_for_a_connection_that_is_up_and_not_for_one_that_is_down(home):
    write_persona(home, "archia", "name: Archia\n")
    finish = slack_heartbeat.keep({"samantha": _Handler(True), "archia": _Handler(False)})
    try:
        assert slack_heartbeat.connected("samantha") is True
        assert slack_heartbeat.connected("archia") is False
    finally:
        finish()


def test_a_connection_that_cannot_say_is_not_shown_as_connected(home):
    finish = slack_heartbeat.keep({"samantha": _Handler(RuntimeError("boom"))})
    try:
        assert slack_heartbeat.connected("samantha") is False
    finally:
        finish()


def test_a_connection_that_drops_stops_being_shown(home, monkeypatch):
    monkeypatch.setattr(slack_heartbeat, "EVERY_SECONDS", 0.05)
    handler = _Handler(True)
    finish = slack_heartbeat.keep({"samantha": handler})
    try:
        assert slack_heartbeat.connected("samantha") is True
        handler.client.up = False
        for _ in range(100):
            if not (home / "samantha" / ".slack" / "heartbeat").exists():
                break
            time.sleep(0.02)
        assert slack_heartbeat.connected("samantha") is False
    finally:
        finish()


def test_finishing_clears_the_file(home):
    finish = slack_heartbeat.keep({"samantha": _Handler(True)})
    assert slack_heartbeat.connected("samantha") is True
    finish()
    assert slack_heartbeat.connected("samantha") is False


def test_the_route_says_whether_the_persona_is_connected(home):
    assert ph.get_slack("samantha") == {"connected": False}
    slack_heartbeat.beat("samantha")
    assert ph.get_slack("samantha") == {"connected": True}


def test_the_route_does_not_know_a_persona_that_is_not_there(home):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        ph.get_slack("nobody")
    assert e.value.status_code == 404
