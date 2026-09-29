"""The prompt when the persona looks up notes itself (docs/decisions/040): how she is told it works, that no
notes block claims "nothing matched" for a search that was never made, and that the default prompt is untouched."""

from sympose.engine import prompt
from sympose.engine.prompt_text import (
    ANSWER_FROM_NOTES, GROUNDING_RULE, GROUNDING_RULE_ASK, HOW_YOU_WORK, HOW_YOU_WORK_ASK, NO_NOTES,
)

PERSONA = {"handle": "nobody", "name": "Ada"}
LIBRARY_PERSONA = {**PERSONA, "sympose_reference": True}
NOTE = {"rel_path": "Atlas.md", "title": "Atlas", "heading": "Atlas", "text": "We use SQLite.", "kind": "text"}


def test_she_is_told_she_decides_and_which_tools_she_has():
    assert "search_notes" in HOW_YOU_WORK_ASK and "open_note" in HOW_YOU_WORK_ASK
    assert "Sympose does not search the user's vault for you" in HOW_YOU_WORK_ASK
    assert "you decide when to use them" in HOW_YOU_WORK_ASK
    assert "the notes your tools found for the current message" in HOW_YOU_WORK_ASK
    assert "That search is automatic and already done" not in HOW_YOU_WORK_ASK
    assert "run tools" in HOW_YOU_WORK and "run tools" not in HOW_YOU_WORK_ASK  # she has tools now...
    assert "can't create or change notes" in HOW_YOU_WORK_ASK  # ...and still cannot change anything


def test_the_rest_of_the_rules_are_the_same_text_as_the_default_and_cannot_drift():
    tail = "Of earlier conversations you know only"
    assert HOW_YOU_WORK_ASK.split(tail)[1].replace("the notes your tools found", "the notes found") == HOW_YOU_WORK.split(tail)[1]
    assert GROUNDING_RULE_ASK.endswith(GROUNDING_RULE[GROUNDING_RULE.index("When you use a note") :])


def test_the_grounding_rule_says_to_look_first_and_never_to_guess():
    assert "backed by notes you found or opened with your tools" in GROUNDING_RULE_ASK
    assert "look first" in GROUNDING_RULE_ASK and "rather than guessing" in GROUNDING_RULE_ASK


def test_the_system_prompt_carries_the_form_the_mode_chose():
    asking = prompt.build_system_prompt(PERSONA, lookup=True)
    default = prompt.build_system_prompt(PERSONA)

    assert HOW_YOU_WORK_ASK in asking and GROUNDING_RULE_ASK in asking
    assert HOW_YOU_WORK not in asking and GROUNDING_RULE not in asking
    assert HOW_YOU_WORK in default and GROUNDING_RULE in default and "search_notes" not in default
    assert default == prompt.build_system_prompt(PERSONA, lookup=False)


def test_a_turn_that_searched_nothing_does_not_say_nothing_matched():
    turn = prompt.build_user_turn("what did we decide?", [], lookup=True)

    assert NO_NOTES not in turn and "matched" not in turn and ANSWER_FROM_NOTES not in turn
    assert turn == "User's message: what did we decide?"


def test_the_default_turn_still_says_when_nothing_matched_or_what_was_found():
    assert NO_NOTES in prompt.build_user_turn("what did we decide?", [])
    assert "We use SQLite." in prompt.build_user_turn("what did we decide?", [NOTE])


def test_the_vault_map_and_the_reference_still_come_with_the_message_when_she_looks_things_up_herself():
    turn = prompt.build_user_turn(
        "how do I add a vault?", [], reference=True, vault_map="17 notes in 9 folders", lookup=True
    )

    assert "17 notes in 9 folders" in turn and "Sympose reference" in turn and turn.endswith("User's message: how do I add a vault?")
    assert NO_NOTES not in turn


def test_build_messages_passes_the_mode_to_both_parts():
    messages = prompt.build_messages(PERSONA, [], [], "hello", lookup=True)

    assert "search_notes" in messages[0]["content"] and "matched" not in messages[-1]["content"]
    assert prompt.build_messages(PERSONA, [], [], "hello")[-1]["content"].startswith(NO_NOTES.split(".")[0])
