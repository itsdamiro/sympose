"""The open comments on the note that travel with the user's message (docs/decisions/069): the ones still open and still
on a passage of the text, each with the answers under it, the newest within a cap, nothing when a cloud model may not
have them."""

import pytest

from sympose import note_changes as nc
from sympose import settings_store
from sympose.engine import edit_turn, open_comments, sharing
from sympose.engine.edit_turn import OpenNote

H, PATH = "samantha", "Garden plan.md"
TEXT = "I run three times a week. The beds are raised.\n"
NOTE = OpenNote(PATH, TEXT)


def add(quote, text, author="user", **kw):
    return nc.annotate(H, PATH, TEXT, quote=quote, text=text, author=author, **kw)


def test_an_open_comment_is_gathered_with_its_passage_and_who_said_it():
    add("three times", "Is this still true?")

    (c,) = open_comments.gather(H, NOTE).items

    assert (c.quote, c.thread) == ("three times", (("user", "Is this still true?"),))


def test_the_answers_under_a_comment_come_with_it_in_order():
    root = add("three times", "Why?")
    nc.reply(H, PATH, root["id"], text="Because winter.", author="persona")

    (c,) = open_comments.gather(H, NOTE).items

    assert c.thread == (("user", "Why?"), ("persona", "Because winter."))


def test_a_resolved_comment_does_not_travel():
    root = add("three times", "Done now")
    nc.set_annotation_state(H, PATH, root["id"], nc.RESOLVED)

    assert open_comments.gather(H, NOTE).items == ()


def test_a_comment_whose_passage_is_gone_from_the_text_does_not_travel():
    add("three times", "Is this still true?")

    assert open_comments.gather(H, OpenNote(PATH, "I run daily.\n")).items == ()


def test_no_note_no_comments():
    assert open_comments.gather(H, None).items == ()


def test_only_the_newest_within_the_cap_travel_and_the_rest_are_counted():
    settings_store.set(open_comments.CAP_SETTING, 2)
    for word in ("three", "times", "week"):
        add(word, f"about {word}")

    found = open_comments.gather(H, NOTE)

    assert [c.quote for c in found.items] == ["times", "week"] and found.left_out == 1


@pytest.mark.parametrize("value", [None, 0, -1, "x", True])
def test_an_unusable_cap_is_the_default(value):
    if value is not None:
        settings_store.set(open_comments.CAP_SETTING, value)

    assert open_comments.cap() == open_comments.DEFAULT_CAP


def test_the_block_names_the_passage_the_user_and_her_by_name():
    root = add("three times", "Why?")
    nc.reply(H, PATH, root["id"], text="Because winter.", author="persona")

    text = open_comments.block(open_comments.gather(H, NOTE), "Samantha")

    assert "three times" in text and "the user: Why?" in text and "Samantha: Because winter." in text


def test_a_cloud_model_is_not_given_the_comments_until_the_user_approves_them():
    add("three times", "Why?")
    persona = {"handle": H}

    held = edit_turn.resolve(persona, False, NOTE, comments_from=H, may_see_comments=False)
    sent = edit_turn.resolve(persona, False, NOTE, comments_from=H)

    assert held.comments == () and held.comments_withheld == 1
    assert len(sent.comments) == 1 and sent.comments_withheld == 0
    assert "Why?" in edit_turn.message(sent, "x") and "Why?" not in edit_turn.message(held, "x")
    assert "not allowed" in edit_turn.message(held, "x")


def test_the_comments_category_is_one_a_cloud_model_does_not_get_until_approved():
    assert sharing.ANNOTATIONS in sharing.CATEGORIES
    assert sharing.ANNOTATIONS not in sharing.allowed("gemini/gemini-flash-latest")
    assert sharing.categories_of([], [], annotations=True) == [sharing.ANNOTATIONS]


# -- new since the last message (docs/decisions/069, amended) --------------------------------------------------------

BEFORE, SINCE, AFTER = "2026-10-05T10:00:00+00:00", "2026-10-05T11:00:00+00:00", "2026-10-05T12:00:00+00:00"


def add_at(when, monkeypatch, quote, text, author="user"):
    monkeypatch.setattr(nc, "_now", lambda: when)
    return add(quote, text, author=author)


def test_with_no_earlier_message_nothing_is_called_new_or_old(monkeypatch):
    add_at(BEFORE, monkeypatch, "three times", "Why?")

    (c,) = open_comments.gather(H, NOTE).items

    assert c.new is None
    assert "since your last reply" not in open_comments.block(open_comments.Found((c,)), "Samantha")


def test_a_comment_made_after_the_last_message_is_new_and_one_made_before_it_is_not(monkeypatch):
    add_at(BEFORE, monkeypatch, "three times", "Old question")
    add_at(AFTER, monkeypatch, "raised", "New question")

    found = {c.quote: c.new for c in open_comments.gather(H, NOTE, since=SINCE).items}

    assert found == {"three times": False, "raised": True}


def test_an_answer_added_after_the_last_message_makes_the_whole_comment_new(monkeypatch):
    root = add_at(BEFORE, monkeypatch, "three times", "Why?")
    monkeypatch.setattr(nc, "_now", lambda: AFTER)
    nc.reply(H, PATH, root["id"], text="Because winter.", author="user")

    (c,) = open_comments.gather(H, NOTE, since=SINCE).items

    assert c.new is True


def test_her_own_comment_made_during_the_last_turn_is_not_new(monkeypatch):
    add_at(BEFORE, monkeypatch, "three times", "A doubt of mine", author="persona")

    (c,) = open_comments.gather(H, NOTE, since=SINCE).items

    assert c.new is False


def test_a_time_with_fractions_of_a_second_is_compared_as_a_time_not_as_text(monkeypatch):
    add_at("2026-10-05T11:00:00+00:00", monkeypatch, "three times", "Same second, earlier")

    (c,) = open_comments.gather(H, NOTE, since="2026-10-05T11:00:00.500000+00:00").items

    assert c.new is False


def test_the_block_says_which_comments_are_new_and_which_were_there_before(monkeypatch):
    add_at(BEFORE, monkeypatch, "three times", "Old question")
    add_at(AFTER, monkeypatch, "raised", "New question")

    text = open_comments.block(open_comments.gather(H, NOTE, since=SINCE), "Samantha")

    assert "On “raised” (new since your last reply):" in text
    assert "On “three times” (from before your last reply):" in text


def test_the_turn_carries_the_label_through(monkeypatch):
    add_at(AFTER, monkeypatch, "three times", "New question")

    edit = edit_turn.resolve({"handle": H}, False, NOTE, comments_from=H, since=SINCE)

    assert [c.new for c in edit.comments] == [True]
    assert "(new since your last reply)" in edit_turn.message(edit, "x")


def test_a_comment_made_at_the_very_moment_of_the_last_message_is_not_new(monkeypatch):
    add_at(SINCE, monkeypatch, "three times", "At the same moment")

    assert open_comments.gather(H, NOTE, since=SINCE).items[0].new is False


def test_a_comment_with_an_unreadable_time_is_not_called_new(monkeypatch):
    add_at("garbage", monkeypatch, "three times", "Odd")

    assert open_comments.gather(H, NOTE, since=SINCE).items[0].new is False
