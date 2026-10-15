"""What a note may be renamed to (docs/decisions/084): one set of rules for the health report and the repair."""

import pytest

from sympose.vault_file_names import LONGEST, why_not_a_file_name


@pytest.mark.parametrize(
    "title",
    ["Better name", "Version 2.0", "90's music", "Dots.in.the.middle", "Console", "Comfort zone", "Aux cable", "Café", "x" * LONGEST, "Part (2)"],
)
def test_a_title_that_makes_a_good_name_has_no_reason_against_it(title):
    assert why_not_a_file_name(title) is None


@pytest.mark.parametrize(
    "title, reason",
    [
        ("Re: budget?", "a file name cannot hold ':'"),
        ("a\nb", "a file name cannot hold '\\n'"),
        ("x" * (LONGEST + 1), "too long"),
        ("Part #2", "a link to it could not hold '#'"),
        ("Part [2]", "a link to it could not hold '['"),
        ("Ends with a dot.", "end with a dot"),
        (" Leading space", "start or end with a space"),
        (".NET notes", "starts with a dot"),
        ("..", "dot"),
        ("'90s music", "apostrophe"),
        ("Her notes'", "apostrophe"),
        ("CON", "Windows"),
        ("con", "Windows"),
        ("Com3", "Windows"),
        ("lpt9.txt", "Windows"),
        ("Nul .notes", "Windows"),
    ],
)
def test_a_title_a_note_cannot_be_renamed_to_says_why(title, reason):
    assert reason in why_not_a_file_name(title)
