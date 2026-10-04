"""What a turn gives a persona to act on a note (docs/decisions/072): the mode that counts for her, whether she gets
the tool or the marker, the open note and the rules sent with the user's message, the cap on the note's text."""

import pytest

from sympose import settings_store
from sympose.engine import edit_mode, edit_turn
from sympose.engine.edit_turn import OpenNote

NOTE = OpenNote("Garden plan.md", "I run three times a week.\n")
SAMANTHA = {"handle": "samantha"}


def persona(mode: str | None) -> dict:
    return {"handle": "samantha", **({"edit_mode": mode} if mode else {})}


def test_manual_is_the_default_and_gets_the_note_and_the_marker_for_a_model_without_tools():
    edit = edit_turn.resolve(SAMANTHA, can_call_tools=False, open_note=NOTE)

    assert (edit.mode, edit.tool, edit.note) == ("manual", False, NOTE)


def test_a_model_that_can_call_tools_gets_the_tool_not_the_marker():
    assert edit_turn.resolve(SAMANTHA, can_call_tools=True, open_note=NOTE).tool is True


@pytest.mark.parametrize("mode", ["manual", "accept", "auto"])
def test_every_mode_but_plan_is_active(mode):
    assert edit_turn.resolve(persona(mode), False, NOTE).active is True


def test_plan_sends_no_note_and_gives_no_tool():
    edit = edit_turn.resolve(persona("plan"), True, NOTE)

    assert (edit.active, edit.note, edit.tool) == (False, None, False)


def test_her_own_mode_beats_the_global_one():
    settings_store.set(edit_mode.SETTING, "auto")

    assert edit_turn.resolve(persona("plan"), False, NOTE).mode == "plan"
    assert edit_turn.resolve(SAMANTHA, False, NOTE).mode == "auto"


def test_with_no_note_open_she_can_still_propose_a_new_note_but_is_sent_no_note():
    edit = edit_turn.resolve(SAMANTHA, False, None)

    assert edit.active and edit.note is None


def test_the_message_puts_the_note_then_the_request_then_the_rules_last():
    edit = edit_turn.resolve(SAMANTHA, False, NOTE)

    text = edit_turn.message(edit, "make it four")

    note_at, request_at, rules_at = text.index("three times"), text.index("make it four"), text.index("propose_edit")
    assert note_at < request_at < rules_at
    assert "````" in text and "Garden plan.md" in text


def test_the_marker_rules_show_the_marker_form_and_the_tool_rules_do_not():
    marker = edit_turn.message(edit_turn.resolve(SAMANTHA, False, NOTE), "x")
    tool = edit_turn.message(edit_turn.resolve(SAMANTHA, True, NOTE), "x")

    assert "<!-- propose_edit:" in marker
    assert "<!--" not in tool and "propose_edit" in tool


def test_manual_does_not_push_her_to_propose_unasked_and_auto_does():
    manual = edit_turn.message(edit_turn.resolve(persona("manual"), False, NOTE), "x")
    auto = edit_turn.message(edit_turn.resolve(persona("auto"), False, NOTE), "x")

    assert "even if the user did not ask" in auto and "even if the user did not ask" not in manual
    assert "propose nothing" in manual


def test_plan_tells_her_she_cannot_change_notes_and_names_no_marker():
    text = edit_turn.message(edit_turn.resolve(persona("plan"), False, NOTE), "make it four")

    assert text.startswith("make it four") and "cannot change" in text
    assert "<!--" not in text and "three times" not in text


def test_with_no_note_the_message_offers_only_a_new_note():
    text = edit_turn.message(edit_turn.resolve(SAMANTHA, False, None), "write me a seed list")

    assert "propose_note" in text and "propose_edit" not in text and "write me a seed list" in text


def test_a_note_longer_than_the_cap_is_cut_and_she_is_told():
    settings_store.set(edit_turn.CAP_SETTING, 40)
    long = OpenNote("a.md", "word " * 100)

    edit = edit_turn.resolve(SAMANTHA, False, long)
    text = edit_turn.message(edit, "x")

    assert len(edit.note.text) <= 40 and edit.cut
    assert "only the first" in text and "word " * 20 not in text


def test_a_short_note_is_sent_whole_and_not_called_cut():
    edit = edit_turn.resolve(SAMANTHA, False, NOTE)

    assert edit.note.text == NOTE.text and not edit.cut


@pytest.mark.parametrize("value", [None, 0, -5, "many", True, 10])
def test_a_missing_or_unusable_cap_is_the_default(value):
    if value is not None:
        settings_store.set(edit_turn.CAP_SETTING, value)

    assert edit_turn.cap() == edit_turn.DEFAULT_CAP


def test_a_cap_the_user_set_is_used():
    settings_store.set(edit_turn.CAP_SETTING, 5000)

    assert edit_turn.cap() == 5000


def test_a_note_that_is_a_fence_of_backticks_does_not_close_ours():
    tricky = OpenNote("a.md", "```python\nx = 1\n```\n")

    text = edit_turn.message(edit_turn.resolve(SAMANTHA, False, tricky), "x")

    assert "````\n```python" in text


def test_a_note_with_a_longer_run_of_backticks_gets_a_longer_fence():
    tricky = OpenNote("a.md", "````\ninner\n````\n")

    text = edit_turn.message(edit_turn.resolve(SAMANTHA, False, tricky), "x")

    assert "`````\n````\ninner" in text
