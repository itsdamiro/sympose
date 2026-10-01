"""Live compaction (docs/decisions/055): what is folded and when, what the model is asked, what is kept
when the call goes wrong, and the whole path through `run_turn`."""

import threading

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import budget, compaction, followup, session, session_compaction, turn
from sympose.engine.model import EngineModelError, ModelReply, ReplyLimitError
from sympose.engine.compaction_text import NOTES_LABEL

CLOUD = "gemini/test-model"  # a window nobody knows here: nothing is sized, so only the compaction logic is tested


@pytest.fixture(autouse=True)
def no_local_server(monkeypatch):
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(followup, "enabled", lambda: False)


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(base)


@pytest.fixture
def asked(monkeypatch):
    """Every request the compaction makes; the reply is what `asked.reply` holds."""
    calls = []

    class Fake(list):
        reply: object = ModelReply("The user is building a recipe site called Pantry.", 5)

    fake = Fake(calls)

    def call(messages, model=None, **limits):
        fake.append({"messages": messages, "model": model, **limits})
        if isinstance(fake.reply, Exception):
            raise fake.reply
        return fake.reply

    monkeypatch.setattr(compaction.model_mod, "call_model", call)
    return fake


def _session(turns: int, sid: str = "s1", user="question {}", reply="answer {}") -> str:
    for i in range(turns):
        session.append_turn("samantha", sid, user.format(i), reply.format(i))
    return sid


def _loaded(sid="s1"):
    return session.load_session("samantha", sid)


# -- what is folded ----------------------------------------------------------


def test_a_request_folds_everything_but_the_newest_turns(sessions_root, asked):
    sid = _session(10)
    outcome = compaction.compact_now("samantha", sid, CLOUD)
    assert outcome.status == compaction.DONE and outcome.covered == 10 - compaction.KEEP_TURNS
    assert session_compaction.covered(_loaded()) == 7
    assert session_compaction.notes(_loaded()) == outcome.text


def test_the_model_is_given_the_users_words_and_never_the_personas_replies(sessions_root, asked):
    sid = _session(6, reply="I have saved your birthday, March 3rd")
    compaction.compact_now("samantha", sid, CLOUD)
    body = asked[0]["messages"][1]["content"]
    assert "User: question 0" in body and "March" not in body and "saved" not in body
    assert asked[0]["messages"][0]["content"] == compaction.INSTRUCTIONS


def test_a_second_compaction_starts_from_the_notes_and_covers_more(sessions_root, asked):
    sid = _session(8)
    compaction.compact_now("samantha", sid, CLOUD)
    for i in range(8, 14):
        session.append_turn("samantha", sid, f"question {i}", f"answer {i}")
    asked.reply = ModelReply("Updated: Pantry, and what came after.", 5)
    outcome = compaction.compact_now("samantha", sid, CLOUD)
    body = asked[1]["messages"][1]["content"]
    assert "Notes so far:\nThe user is building a recipe site called Pantry." in body
    assert "User: question 5" in body and "User: question 0" not in body  # only what the notes did not cover
    assert outcome.covered == 14 - compaction.KEEP_TURNS
    assert session_compaction.notes(_loaded()) == "Updated: Pantry, and what came after."


def test_too_few_turns_are_not_folded(sessions_root, asked):
    sid = _session(compaction.KEEP_TURNS)
    assert compaction.compact_now("samantha", sid, CLOUD).status == compaction.NOTHING
    assert asked == []


def test_a_session_that_does_not_exist_has_nothing_to_fold(sessions_root, asked):
    assert compaction.compact_now("samantha", "nope", CLOUD).status == compaction.NOTHING
    assert asked == []


# -- when the call goes wrong ------------------------------------------------


@pytest.mark.parametrize("failure", [EngineModelError("down"), ReplyLimitError("too small")])
def test_a_failed_call_writes_nothing(sessions_root, asked, failure):
    sid = _session(8)
    asked.reply = failure
    assert compaction.compact_now("samantha", sid, CLOUD).status == compaction.FAILED
    assert _loaded()["compaction"] is None


def test_an_empty_reply_writes_nothing(sessions_root, asked):
    sid = _session(8)
    asked.reply = ModelReply("  \n ", 5)
    assert compaction.compact_now("samantha", sid, CLOUD).status == compaction.FAILED
    assert _loaded()["compaction"] is None


def test_a_reply_cut_at_the_limit_keeps_its_last_whole_sentence(sessions_root, asked):
    sid = _session(8)
    asked.reply = ModelReply("The user plans a site. They chose SQLite. They are unsure about hos", 5, truncated=True)
    compaction.compact_now("samantha", sid, CLOUD)
    assert session_compaction.notes(_loaded()) == "The user plans a site. They chose SQLite."


def test_notes_no_shorter_than_what_they_replace_are_not_kept(sessions_root, asked):
    sid = _session(8, user="hi", reply="ok")
    asked.reply = ModelReply("The user said hi. " * 30, 5)
    assert compaction.compact_now("samantha", sid, CLOUD).status == compaction.TOO_SMALL
    assert _loaded()["compaction"] is None


def test_what_the_request_cannot_hold_waits_for_the_next_compaction(sessions_root, asked, monkeypatch):
    settings_store.set("context_window", 2048)
    sid = _session(10, user="word " * 200)
    model = "ollama_chat/test"
    outcome = compaction.compact_now("samantha", sid, model)
    assert outcome.status == compaction.DONE and 0 < outcome.covered < 10 - compaction.KEEP_TURNS
    assert budget.count_tokens(asked[0]["messages"], model) <= budget.budget_for(model).prompt_tokens


def test_a_second_request_while_one_runs_is_told_it_is_busy(sessions_root, asked, monkeypatch):
    sid = _session(8)
    entered, release = threading.Event(), threading.Event()

    def slow(messages, model=None, **limits):
        entered.set()
        release.wait(5)
        return ModelReply("notes about Pantry", 5)

    monkeypatch.setattr(compaction.model_mod, "call_model", slow)
    first = threading.Thread(target=compaction.compact_now, args=("samantha", sid, CLOUD))
    first.start()
    assert entered.wait(5)
    assert compaction.compact_now("samantha", sid, CLOUD).status == compaction.BUSY
    release.set()
    first.join(5)
    assert session_compaction.notes(_loaded()) == "notes about Pantry"


# -- how much, and when ------------------------------------------------------


def test_the_percentages_fall_back_when_they_are_not_usable():
    for bad in (True, 5, 99, "50", 12.5):
        settings_store.set(compaction.AT_SETTING, bad)
        assert compaction.at_percent() == compaction.DEFAULT_AT
    settings_store.set(compaction.AT_SETTING, 70)
    assert compaction.at_percent() == 70


def test_it_always_lands_below_where_it_starts():
    settings_store.set(compaction.AT_SETTING, 60)
    settings_store.set(compaction.TO_SETTING, 50)
    assert compaction.to_percent() == 50
    settings_store.set(compaction.TO_SETTING, 60)  # not below: refused
    assert compaction.to_percent() == 30
    settings_store.remove(compaction.TO_SETTING)
    assert compaction.to_percent() == 30
    settings_store.remove(compaction.AT_SETTING)
    assert compaction.to_percent() == compaction.DEFAULT_TO


def _turns(count):
    return [{"user": "u", "assistant": "a"}] * count


def test_it_folds_the_fewest_turns_that_land_at_the_low_mark(monkeypatch):
    monkeypatch.setattr(compaction, "_turn_tokens", lambda turn, model: 100)
    # low mark 40% of 1000, less 250 for the notes = 150: 900 - 100 * 8 <= 150 < 900 - 100 * 7
    assert compaction._fold_count(_turns(12), 900, 1000, CLOUD) == 8


def test_it_leaves_the_newest_turns_even_when_the_mark_cannot_be_reached(monkeypatch):
    monkeypatch.setattr(compaction, "_turn_tokens", lambda turn, model: 1)
    assert compaction._fold_count(_turns(12), 900, 1000, CLOUD) == 12 - compaction.KEEP_TURNS


def test_the_turns_beyond_the_history_cap_are_always_folded(monkeypatch):
    monkeypatch.setattr(compaction, "_turn_tokens", lambda turn, model: 1)
    count = session.HISTORY_TURNS + 5
    assert compaction._fold_count(_turns(count), 10, 1000, CLOUD) == 5


def _saved(turns, through=0):
    saved = {"meta": {}, "turns": _turns(turns), "compaction": {"through": through, "text": "n"} if through else None}
    return saved


def test_a_reply_is_followed_by_a_compaction_at_the_high_mark_and_not_before():
    assert not compaction.wanted(_saved(10), 790, 1000)
    assert compaction.wanted(_saved(10), 800, 1000)


def test_more_turns_than_the_history_cap_sends_call_for_one_whatever_the_size():
    assert compaction.wanted(_saved(session.HISTORY_TURNS + 1), 10, 1000)
    assert not compaction.wanted(_saved(session.HISTORY_TURNS), 10, 1000)


def test_turns_the_notes_already_stand_for_do_not_count():
    assert not compaction.wanted(_saved(session.HISTORY_TURNS + 1, through=session.HISTORY_TURNS), 10, 1000)


@pytest.mark.parametrize("saved,used,limit", [(None, 900, 1000), (_saved(10), None, 1000), (_saved(10), 900, None), (_saved(3), 990, 1000)])
def test_nothing_is_wanted_without_a_figure_or_enough_turns(saved, used, limit):
    assert not compaction.wanted(saved, used, limit)


# -- automatic ---------------------------------------------------------------


def _finish(sid="s1"):
    assert compaction._JOBS.wait(f"samantha/{sid}", 5)


def test_it_is_off_when_the_setting_says_so(sessions_root, asked):
    settings_store.set(compaction.SETTING, False)
    sid = _session(8)
    assert not compaction.start_if_wanted("samantha", sid, CLOUD, _loaded(), 900, 1000)
    assert asked == []


def test_it_runs_in_the_background_and_folds_down_to_the_low_mark(sessions_root, asked, monkeypatch):
    settings_store.set(compaction.SETTING, True)
    monkeypatch.setattr(compaction, "_turn_tokens", lambda turn, model: 100)
    sid = _session(12)
    assert compaction.start_if_wanted("samantha", sid, CLOUD, _loaded(), 900, 1000)
    _finish()
    assert session_compaction.covered(_loaded()) == 8


def test_an_attempt_that_wrote_nothing_is_not_repeated_every_turn(sessions_root, asked):
    settings_store.set(compaction.SETTING, True)
    sid = _session(8)
    asked.reply = EngineModelError("down")
    assert compaction.start_if_wanted("samantha", sid, CLOUD, _loaded(), 900, 1000)
    _finish()
    assert len(asked) == 1
    session.append_turn("samantha", sid, "one more", "ok")
    assert not compaction.start_if_wanted("samantha", sid, CLOUD, _loaded(), 900, 1000)  # too soon after the failure
    for i in range(compaction._RETRY_AFTER_TURNS):
        session.append_turn("samantha", sid, f"more {i}", "ok")
    asked.reply = ModelReply("The user is building Pantry.", 5)
    assert compaction.start_if_wanted("samantha", sid, CLOUD, _loaded(), 900, 1000)
    _finish()
    assert session_compaction.notes(_loaded()) == "The user is building Pantry."


# -- through a turn ----------------------------------------------------------


def _chat(monkeypatch, replies):
    sent = []

    def call(messages, model=None, **limits):
        sent.append(messages)
        return ModelReply(replies(messages), 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call)
    monkeypatch.setattr(compaction.model_mod, "call_model", call)
    return sent


def test_the_notes_replace_the_turns_they_stand_for_in_the_prompt(sessions_root, monkeypatch):
    sid = _session(8)
    session_compaction.append("samantha", sid, 5, "The user is building a recipe site called Pantry.", "m")
    sent = _chat(monkeypatch, lambda m: "ok")
    result = turn.run_turn("samantha", "what is next?", session_id=sid, model=CLOUD)
    messages = sent[-1]
    assert NOTES_LABEL in messages[0]["content"]
    assert "The user is building a recipe site called Pantry." in messages[0]["content"]
    history = [m["content"] for m in messages[1:-1]]
    assert history == ["question 5", "answer 5", "question 6", "answer 6", "question 7", "answer 7"]
    assert result.condensed == 5
    assert len(_loaded()["turns"]) == 9  # the record keeps every turn


def test_a_conversation_without_notes_says_nothing_about_them(sessions_root, monkeypatch):
    sent = _chat(monkeypatch, lambda m: "ok")
    result = turn.run_turn("samantha", "hello", model=CLOUD)
    assert NOTES_LABEL not in sent[-1][0]["content"] and result.condensed == 0


def test_a_long_chat_is_condensed_after_a_reply_and_the_next_turn_uses_the_notes(sessions_root, monkeypatch):
    settings_store.set(compaction.SETTING, True)
    settings_store.set("context_window", 2048)  # small on purpose: the conversation fills it quickly
    notes = "The user is working on Pantry."

    def replies(messages):
        return notes if messages[0]["content"] == prompt_instructions else "answer " * 120

    prompt_instructions = compaction.INSTRUCTIONS
    sent = _chat(monkeypatch, replies)
    sid = None
    for i in range(8):
        sid = turn.run_turn("samantha", f"question {i}", session_id=sid, model="ollama_chat/test").session_id
        compaction._JOBS.wait(f"samantha/{sid}", 5)
    assert session_compaction.notes(_loaded(sid)) == notes
    last = turn.run_turn("samantha", "and now?", session_id=sid, model="ollama_chat/test")
    assert last.condensed > 0
    assert notes in sent[-1][0]["content"]
