"""`parallel_replies` (docs/decisions/057): when replies of one persona in different conversations run at once."""

import pytest

from sympose import settings_store
from sympose.engine import parallel

LOCAL, CLOUD = "ollama_chat/gemma2:9b", "gemini/gemini-flash-latest"


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def test_by_default_a_cloud_model_runs_side_by_side_and_a_local_one_one_after_the_other():
    assert parallel.mode() == parallel.AUTO
    assert parallel.side_by_side(CLOUD) is True
    assert parallel.side_by_side(LOCAL) is False


def test_on_runs_side_by_side_whatever_the_model():
    settings_store.set(parallel.SETTING, "on")
    assert parallel.side_by_side(LOCAL) and parallel.side_by_side(CLOUD)


def test_off_always_runs_one_at_a_time():
    settings_store.set(parallel.SETTING, "off")
    assert not parallel.side_by_side(LOCAL) and not parallel.side_by_side(CLOUD)


@pytest.mark.parametrize("value", ["yes", 3, None, True, ["on"]])
def test_a_malformed_value_is_auto(value):
    settings_store.set(parallel.SETTING, value)
    assert parallel.mode() == parallel.AUTO
