"""Tests for sympose.cli.background_status: which one background job to show (recap, memory,
or indexing) when more than one might be running, and the setting that turns the line off."""

import pytest

from sympose import settings_store
from sympose.cli import background_status
from sympose.engine import memory_refresh, recap_refresh, semantic_refresh, status_phrases, turn_status


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def _running(monkeypatch, recap=False, memory=False, index_percent=None):
    monkeypatch.setattr(recap_refresh, "is_running", lambda handle: recap)
    monkeypatch.setattr(memory_refresh, "is_running", lambda handle: memory)
    monkeypatch.setattr(semantic_refresh, "progress", lambda: index_percent)


def test_enabled_by_default():
    assert background_status.enabled() is True
    settings_store.set(background_status.SETTING, False)
    assert background_status.enabled() is False


def test_nothing_running_is_no_activity(monkeypatch):
    _running(monkeypatch)
    assert background_status.activity("samantha") == (None, "")


def test_a_recap_refresh_shows_as_recap(monkeypatch):
    _running(monkeypatch, recap=True)
    assert background_status.activity("samantha") == ("recap", "")


def test_a_memory_refresh_shows_as_memory(monkeypatch):
    _running(monkeypatch, memory=True)
    assert background_status.activity("samantha") == ("memory", "")


def test_indexing_shows_as_index_with_its_percent(monkeypatch):
    _running(monkeypatch, index_percent=40)
    assert background_status.activity("samantha") == ("index", " 40%")


def test_recap_takes_priority_over_memory_and_indexing(monkeypatch):
    _running(monkeypatch, recap=True, memory=True, index_percent=10)
    assert background_status.activity("samantha")[0] == "recap"


def test_memory_takes_priority_over_indexing(monkeypatch):
    _running(monkeypatch, memory=True, index_percent=10)
    assert background_status.activity("samantha")[0] == "memory"


def test_status_phrase_generation_shows_up_too(monkeypatch):
    _running(monkeypatch)
    monkeypatch.setattr(status_phrases, "is_running", lambda handle: True)
    assert background_status.activity("samantha") == ("phrases", "")


def test_phrase_generation_takes_priority_over_indexing_but_not_memory(monkeypatch):
    _running(monkeypatch, memory=True, index_percent=10)
    monkeypatch.setattr(status_phrases, "is_running", lambda handle: True)
    assert background_status.activity("samantha")[0] == "memory"

    _running(monkeypatch, index_percent=10)
    monkeypatch.setattr(status_phrases, "is_running", lambda handle: True)
    assert background_status.activity("samantha")[0] == "phrases"


def test_the_turns_own_real_phase_takes_priority_over_every_background_job(monkeypatch):
    """The reply the user is actually waiting on matters more than housekeeping (docs/decisions/043's
    follow-up): searching/reading/asking outranks recap, memory, phrase generation and indexing."""
    _running(monkeypatch, recap=True, memory=True, index_percent=10)
    monkeypatch.setattr(status_phrases, "is_running", lambda handle: True)
    turn_status.set_phase("samantha", turn_status.SEARCHING)
    try:
        assert background_status.activity("samantha") == (turn_status.SEARCHING, "")
    finally:
        turn_status.set_phase("samantha", None)


def test_recaps_own_phrase_shows_through_once_the_turn_clears_its_phase(monkeypatch):
    """`turn.py` clears its own phase for the exact window it's blocked on `recap_refresh.wait_for_refresh`
    (docs/decisions/023) -- with no phase set, the recap job's own reason for the wait shows instead."""
    _running(monkeypatch, recap=True)
    assert turn_status.phase("samantha") is None
    assert background_status.activity("samantha") == ("recap", "")


def test_a_different_personas_turn_does_not_show_up_for_this_one(monkeypatch):
    _running(monkeypatch)
    turn_status.set_phase("aria", turn_status.READING)
    try:
        assert background_status.activity("samantha") == (None, "")
    finally:
        turn_status.set_phase("aria", None)
