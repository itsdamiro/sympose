"""The persona's earlier conversations, word for word (docs/decisions/056): what the reader finds, what it
leaves out, how the gate and the prompt treat it, and that a turn records it by id and never by text. What the
real model does with an exchange is checked by `live_prompt_cases.py` and the measurements in the ADR."""

import json
import os

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import followup, grounding, past_chats, prompt, session, sharing, turn
from sympose.engine.model import ModelReply

CLOUD = "anthropic/claude-sonnet-5"
NEW = "20260924T090000-aaaaaaaa"
OLD = "20260923T090000-bbbbbbbb"
OLDER = "20260922T090000-cccccccc"
PERSONA = {"handle": "samantha", "name": "Samantha"}


@pytest.fixture(autouse=True)
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(followup, "enabled", lambda: False)
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(past_chats, "_CACHE", {})
    return base


def _auto():
    settings_store.set("past_chats", "auto")


def _talk(sid, *pairs):
    for user, reply in pairs:
        session.append_turn("samantha", sid, user, reply)


def test_it_is_off_by_default_and_an_unusable_value_is_off():
    assert past_chats.mode() == "off"
    for value in ("asks", "yes", 3, None, True):
        settings_store.set("past_chats", value)
        assert past_chats.mode() == "off"


def test_ask_is_a_mode_and_attaches_only_when_the_tools_are_not_in_use():
    _talk(OLD, ("the Atlas database choice", "SQLite for Atlas."))
    settings_store.set("past_chats", "ask")

    assert past_chats.mode() == "ask"
    assert past_chats.find("samantha", "the Atlas database choice", NEW, tools=True) == []
    assert len(past_chats.find("samantha", "the Atlas database choice", NEW, tools=False)) == 1  # a model without tools


def test_off_finds_nothing_even_when_an_exchange_matches():
    _talk(OLD, ("the Atlas database choice", "SQLite for Atlas."))

    assert past_chats.find("samantha", "what about the Atlas database?", NEW) == []


def test_it_finds_the_exchange_a_question_is_about_with_both_sides():
    _auto()
    _talk(
        OLD,
        ("I am choosing a database for Atlas", "I would pick SQLite for Atlas, it needs no server."),
        ("what should I cook tonight", "Maybe a pasta with garlic."),
    )

    found = past_chats.find("samantha", "what did you say about the Atlas database last time?", NEW)

    assert [(x["session"], x["turn"]) for x in found] == [(OLD, 1)]
    assert found[0]["user"] == "I am choosing a database for Atlas"
    assert found[0]["assistant"] == "I would pick SQLite for Atlas, it needs no server."
    assert found[0]["date"] == "2026-09-23"


def test_the_conversation_in_progress_is_never_searched():
    _auto()
    _talk(NEW, ("the Atlas database choice", "SQLite for Atlas."))

    assert past_chats.find("samantha", "the Atlas database choice", NEW) == []
    assert len(past_chats.find("samantha", "the Atlas database choice", OLD)) == 1


def test_a_conversation_in_the_bin_is_never_searched():
    _auto()
    _talk(OLD, ("the Atlas database choice", "SQLite for Atlas."))
    trash = os.path.join(session.sessions_dir("samantha"), ".trash")
    os.makedirs(trash)
    os.replace(session.session_path("samantha", OLD), os.path.join(trash, f"{OLD}.jsonl"))

    assert past_chats.find("samantha", "the Atlas database choice", NEW) == []


def test_one_ordinary_word_in_common_is_not_a_match():
    _auto()
    _talk(OLD, ("the Atlas database choice", "SQLite for Atlas."))

    assert past_chats.find("samantha", "which database engines are popular for dashboards", NEW) == []


def test_one_specific_word_is_enough_when_the_message_says_it_is_about_the_past():
    _auto()
    _talk(OLD, ("planning a trip to Lisbon", "Book the flights early."), ("what should I cook", "Pasta."))

    assert len(past_chats.find("samantha", "which flights did you suggest last time?", NEW)) == 1
    assert past_chats.find("samantha", "which flights are cheapest?", NEW) == []  # one word and no word of the past


def test_a_word_in_several_conversations_is_not_specific_but_one_in_a_single_conversation_is():
    _auto()
    _talk(OLD, *[(f"the trip day {n}", "Lisbon is lovely.") for n in range(5)])  # one conversation, many exchanges
    assert len(past_chats.find("samantha", "what did I say about Lisbon last time?", NEW)) == 3

    _talk(OLDER, ("my sister lives in Lisbon", "How nice."))  # now two conversations hold the word
    assert past_chats.find("samantha", "what did I say about Lisbon last time?", NEW) == []


def test_the_words_of_asking_about_the_past_are_not_evidence():
    _auto()
    _talk(OLD, ("we talked last time about earlier things", "Yes, a conversation before."))

    assert past_chats.find("samantha", "what did we talk about last time, in our earlier conversation?", NEW) == []


def test_at_most_three_exchanges_come_back_in_the_order_they_were_held():
    _auto()
    _talk(OLDER, ("Atlas database one", "a"), ("Atlas database two", "b"))
    _talk(OLD, ("Atlas database three", "c"), ("Atlas database four", "d"), ("Atlas database five", "e"))

    found = past_chats.find("samantha", "the Atlas database", NEW)

    assert len(found) == 3
    assert [(x["session"], x["turn"]) for x in found] == sorted((x["session"], x["turn"]) for x in found)


def test_exchanges_are_ordered_by_conversation_first_then_by_message():
    _auto()
    _talk(OLDER, ("something else entirely", "ok"), ("the Atlas database choice", "SQLite."))
    _talk(OLD, ("the Atlas database again", "Still SQLite."))

    found = past_chats.find("samantha", "the Atlas database", NEW)

    assert [(x["session"], x["turn"]) for x in found] == [(OLDER, 2), (OLD, 1)]


def test_each_side_is_cut_to_its_limit():
    _auto()
    _talk(OLD, ("Atlas database " + "u" * 900, "Atlas database " + "r" * 900))

    (found,) = past_chats.find("samantha", "the Atlas database", NEW)

    assert len(found["user"]) == len(found["assistant"]) == past_chats.SIDE_CHARS


def test_a_conversation_that_grows_is_read_again():
    _auto()
    _talk(OLD, ("planning a trip to Lisbon", "Book early."))
    assert len(past_chats.find("samantha", "Lisbon trip", NEW)) == 1

    _talk(OLD, ("the Lisbon trip hotel budget", "Under 120 a night."))

    assert len(past_chats.find("samantha", "Lisbon trip hotel", NEW)) == 2


def test_a_file_that_cannot_be_read_is_skipped_not_a_failure():
    _auto()
    path = session.session_path("samantha", OLD)
    os.makedirs(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(b"\xff\xfe not json")
    _talk(OLDER, ("the Atlas database choice", "SQLite."))

    assert len(past_chats.find("samantha", "the Atlas database", NEW)) == 1


def test_chats_are_a_category_a_cloud_model_must_be_allowed():
    chat = {"session": OLD, "date": "2026-09-23", "turn": 1, "user": "u", "assistant": "a"}

    held = sharing.gate(CLOUD, [], [], [chat])
    assert held.chats == [] and held.withheld == {"chats": 1}

    settings_store.set("cloud_share", ["recaps"])  # allowing summaries does not allow word-for-word chats
    assert sharing.gate(CLOUD, [], [], [chat]).chats == []

    settings_store.set("cloud_share", ["chats"])
    assert sharing.gate(CLOUD, [], [], [chat]).chats == [chat]
    assert sharing.gate("ollama_chat/gemma2:9b", [], [], [chat]).chats == [chat]
    assert "chats" in sharing.DESCRIPTIONS and sharing.categories_of([], [], chats=True) == ["chats"]


def test_the_prompt_marks_her_side_as_hers_and_possibly_wrong():
    chat = {"session": OLD, "date": "2026-09-23", "turn": 2, "user": "which server?", "assistant": "Caddy."}

    system = prompt.build_system_prompt(PERSONA, chats=[chat])

    assert "User: which server?" in system and "You: Caddy." in system
    assert "2026-09-23" in system and "message 2" in system
    assert "never something the user said" in system


def test_a_withheld_chat_is_said_with_the_message_not_to_mean_there_was_no_talk():
    turn_text = prompt.build_user_turn("what did you say about Atlas?", [], chats_withheld=True)

    assert "Don't say you never talked about it" in turn_text and "/share" in turn_text
    assert turn_text.endswith("User's message: what did you say about Atlas?")
    assert "Don't say you never talked about it" not in prompt.build_user_turn("hi", [])
    assert prompt.CHATS_LABEL not in prompt.build_system_prompt(PERSONA)


def test_a_turn_attaches_the_exchange_and_records_ids_never_text(monkeypatch):
    _auto()
    _talk(OLD, ("I am choosing a database for Atlas", "I would pick SQLite for Atlas."))
    seen = {}

    def call_model(messages, model=None, **_):
        seen["system"] = messages[0]["content"]
        return ModelReply("You asked about Atlas.", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW)

    assert "You: I would pick SQLite for Atlas." in seen["system"]
    assert result.sent["chats"] == [{"session": OLD, "turn": 1, "how": "auto"}]
    with open(session.session_path("samantha", NEW)) as f:
        record = [json.loads(line) for line in f if '"type": "turn"' in line][0]
    assert record["sent"]["chats"] == [{"session": OLD, "turn": 1, "how": "auto"}]
    assert "SQLite" not in json.dumps(record["sent"])


def test_a_turn_does_not_attach_its_own_conversation(monkeypatch):
    _auto()
    _talk(NEW, ("I am choosing a database for Atlas", "I would pick SQLite for Atlas."))
    seen = {}

    def call_model(messages, model=None, **_):
        seen["system"] = messages[0]["content"]
        return ModelReply("ok", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW)

    assert prompt.CHATS_LABEL not in seen["system"] and "chats" not in result.sent


def test_a_cloud_turn_with_the_category_allowed_sends_it_and_says_so(monkeypatch):
    _auto()
    settings_store.set("cloud_share", ["chats"])
    _talk(OLD, ("I am choosing a database for Atlas", "I would pick SQLite for Atlas."))
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("ok", 5))

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW, model=CLOUD)

    assert "chats" in result.cloud and "chats" not in result.withheld


def test_a_cloud_turn_without_the_category_withholds_it_and_says_so(monkeypatch):
    _auto()
    _talk(OLD, ("I am choosing a database for Atlas", "I would pick SQLite for Atlas."))
    seen = {}

    def call_model(messages, model=None, **_):
        seen["system"], seen["user"] = messages[0]["content"], messages[-1]["content"]
        return ModelReply("ok", 5)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW, model=CLOUD)

    assert "SQLite" not in seen["system"] + seen["user"] and "Don't say you never talked about it" in seen["user"]
    assert "chats" in result.withheld and "chats" not in result.sent["cloud"]
    assert "chats" not in result.sent


def test_off_a_turn_carries_no_chats_key(monkeypatch):
    _talk(OLD, ("I am choosing a database for Atlas", "I would pick SQLite for Atlas."))
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: ModelReply("ok", 5))

    result = turn.run_turn("samantha", "what did you say about the Atlas database?", session_id=NEW)

    assert "chats" not in result.sent


def test_settings_row_tells_which_mode_suits_which_model():
    from sympose.engine.settings_registry import SETTINGS

    summary = next(s.summary for s in SETTINGS if s.key == past_chats.SETTING)
    assert "auto: local" in summary and "ask: cloud" in summary
