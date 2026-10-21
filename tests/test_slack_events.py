"""Which Slack events a persona answers and how a message is told apart (docs/decisions/093)."""

import pytest
from slack_shapes import BOT, OWNER, dm, mention

from sympose.slack_events import conversation_key, parse


def test_a_direct_message_is_parsed():
    m = parse(dm("hello there"), BOT)
    assert (m.user, m.channel, m.text, m.direct, m.thread_ts, m.event_id) == (OWNER, "D0DM", "hello there", True, None, "Ev1")


def test_a_mention_loses_the_mention_and_is_not_direct():
    m = parse(mention(), BOT)
    assert (m.text, m.direct, m.channel) == ("what is in my notes?", False, "C0CHAN")


def test_a_mention_in_the_middle_leaves_one_space():
    assert parse(mention(f"look <@{BOT}>  up Rust"), BOT).text == "look up Rust"


def test_a_mention_of_someone_else_stays():
    assert "<@U0OTHER>" in parse(mention(f"<@{BOT}> tell <@U0OTHER>"), BOT).text


@pytest.mark.parametrize("body", [
    dm(subtype="message_changed"),
    dm(subtype="file_share"),
    dm(bot_id="B1"),
    dm(text="   "),
    mention(f"<@{BOT}>"),
    {"event": {"type": "reaction_added", "user": OWNER}},
    {"event": {"type": "message", "channel_type": "channel", "channel": "C1", "user": OWNER, "text": "hi", "ts": "1.1"}},
    {"event": {"type": "message", "channel_type": "im", "channel": "D1", "text": "no user", "ts": "1.1"}},
    {"event": {"type": "message", "channel_type": "im", "channel": "D1", "user": OWNER, "text": 5, "ts": "1.1"}},
    {"event": "not an object"},
    {},
])
def test_what_a_persona_does_not_answer_is_none(body):
    assert parse(body, BOT) is None


def test_a_missing_event_id_is_none_not_an_error():
    body = dm()
    del body["event_id"]
    assert parse(body, BOT).event_id is None


def test_a_direct_message_is_one_conversation_whatever_its_thread():
    first = parse(dm(ts="1.1"), BOT)
    later = parse(dm(ts="2.2", thread_ts="1.1"), BOT)
    assert conversation_key(first) == conversation_key(later) == "dm:D0DM"


def test_a_channel_thread_is_a_conversation_and_its_first_message_names_it():
    first = parse(mention(ts="5.5"), BOT)
    reply = parse(mention(ts="6.6", thread_ts="5.5"), BOT)
    other = parse(mention(ts="7.7"), BOT)
    assert conversation_key(first) == conversation_key(reply) == "thread:C0CHAN:5.5"
    assert conversation_key(other) != conversation_key(first)
