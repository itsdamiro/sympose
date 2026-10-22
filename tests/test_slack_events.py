"""Which Slack events a persona answers and how a message is told apart (docs/decisions/093)."""

import pytest
from slack_shapes import BOT, OWNER, dm, mention, shared

from sympose.slack_events import SlackFile, conversation_key, parse


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
    dm(subtype="message_deleted"),
    dm(subtype="thread_broadcast", files=[shared()]),
    dm(subtype="file_share", text="", files=[]),
    dm(subtype="file_share", text=None),
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


# --- files shared with a message (docs/decisions/093, "files attached in Slack") -------------------
def test_a_file_share_is_a_message_with_its_files():
    m = parse(dm("read this", subtype="file_share", files=[shared("notes.pdf", 2000)]), BOT)
    assert m.text == "read this"
    assert m.files == (SlackFile("notes.pdf", 2000, "https://files.slack.com/files-pri/T1-F1/download/notes.pdf"),)


def test_a_file_shared_with_no_words_is_a_message():
    body = dm(subtype="file_share", files=[shared()])
    del body["event"]["text"]
    m = parse(body, BOT)
    assert m.text == "" and len(m.files) == 1


def test_a_file_shared_with_a_mention_and_no_other_words_is_a_message():
    body = mention(f"<@{BOT}>")
    body["event"]["files"] = [shared()]
    m = parse(body, BOT)
    assert m.text == "" and m.direct is False and len(m.files) == 1


def test_a_message_without_files_has_none():
    assert parse(dm(), BOT).files == ()


def test_the_download_address_falls_back_to_the_private_one():
    item = shared()
    del item["url_private_download"]
    assert parse(dm(files=[item]), BOT).files[0].url == item["url_private"]


def test_a_file_from_another_workspace_has_no_address_but_is_not_lost():
    m = parse(dm(files=[shared(file_access="check_file_info")]), BOT)
    assert m.files == (SlackFile("notes.pdf", 2000, ""),)


def test_a_file_with_no_name_or_size_is_still_one():
    m = parse(dm(files=[{"url_private": "https://files.slack.com/x"}, "junk", {"name": "a.pdf", "size": "big"}]), BOT)
    assert [(f.name, f.size) for f in m.files] == [("file", 0), ("a.pdf", 0)]


def test_files_that_are_not_a_list_are_none():
    assert parse(dm(files="notes.pdf"), BOT).files == ()


def test_a_file_with_no_name_is_called_by_its_title_then_just_file():
    m = parse(dm(files=[{"title": "Quarterly plan", "url_private": "https://files.slack.com/x"}]), BOT)
    assert m.files[0].name == "Quarterly plan"
