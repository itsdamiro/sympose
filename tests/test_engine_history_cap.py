"""`history_tokens`: an optional cap on the earlier turns a prompt carries (docs/decisions/055, update of 2026-10-02)."""

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import history_cap, session, turn
from sympose.engine.model import ModelReply

MODEL = "unknown/model"


def pairs(n: int, words: int = 100) -> list[dict[str, str]]:
    out = []
    for i in range(n):
        out += [{"role": "user", "content": f"q{i} " + "word " * words}, {"role": "assistant", "content": f"a{i} " + "word " * words}]
    return out


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


def test_with_no_cap_nothing_is_dropped():
    history = pairs(6)
    assert history_cap.apply(history, MODEL) == (history, 0)


def test_the_oldest_turns_go_first_until_the_rest_is_within_the_cap():
    history = pairs(6)  # each pair is a few hundred tokens
    settings_store.set("history_tokens", 1200)
    kept, dropped = history_cap.apply(history, MODEL)
    assert dropped > 0 and len(kept) == len(history) - 2 * dropped
    assert kept == history[2 * dropped:]  # the newest are kept, in order
    assert history_cap.budget.count_tokens(kept, MODEL) <= 1200


def test_the_newest_turn_stays_even_when_it_alone_is_over_the_cap():
    history = pairs(3, words=900)
    settings_store.set("history_tokens", 500)
    kept, dropped = history_cap.apply(history, MODEL)
    assert kept == history[-2:] and dropped == 2


def test_a_cap_above_the_history_drops_nothing():
    history = pairs(2)
    settings_store.set("history_tokens", 100000)
    assert history_cap.apply(history, MODEL) == (history, 0)


@pytest.mark.parametrize("value", [0, 499, -1, 800.5, "800", True, None, [900]])
def test_an_unusable_cap_is_no_cap(value):
    settings_store.set("history_tokens", value)
    assert history_cap.chosen() is None
    assert history_cap.apply(pairs(4), MODEL)[1] == 0


def test_the_smallest_cap_is_accepted():
    settings_store.set("history_tokens", 500)
    assert history_cap.chosen() == 500


def test_a_turn_sends_only_the_turns_within_the_cap_and_counts_the_rest_as_dropped(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    sent = []
    monkeypatch.setattr(
        turn.model_mod, "call_model", lambda messages, model=None, **_: sent.append(messages) or ModelReply("ok", 5)
    )
    sid = session.new_session_id()
    for i in range(6):
        session.append_turn("samantha", sid, f"q{i} " + "word " * 100, f"a{i} " + "word " * 100)

    uncapped = turn.run_turn("samantha", "hello", session_id=sid, model=MODEL)
    assert uncapped.history_dropped == 0 and len(sent[-1]) == 1 + 12 + 1

    settings_store.set("history_tokens", 1000)
    capped = turn.run_turn("samantha", "again", session_id=sid, model=MODEL)
    pairs_sent = (len(sent[-1]) - 2) // 2
    assert 0 < pairs_sent < 7
    assert capped.history_dropped == 7 - pairs_sent  # seven earlier turns by now
    texts = [f"q{i}" for i in range(6)] + ["hello"]
    assert sent[-1][1]["content"].startswith(texts[7 - pairs_sent])  # the oldest turn still sent is the right one
    assert len(session.load_session("samantha", sid)["turns"]) == 8  # nothing is deleted from the record
