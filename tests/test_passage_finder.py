"""Finding a quoted passage in a note again (docs/decisions/070): by the passage and the text around it, never by a
position, so an edit elsewhere cannot move it and an edit to the passage itself is noticed."""

from sympose import passage_finder as finder

NOTE = "I run three times a week. The beds are raised.\n\n- Pack charger\n- Phone\n\n## Electronics\n\n- Pack charger\n"


def test_a_passage_that_occurs_once_is_found_where_it_is():
    found = finder.locate(NOTE, "three times")

    assert (found.status, NOTE[found.start:found.end]) == (finder.ONE, "three times")


def test_a_passage_that_is_not_in_the_note_is_none():
    assert finder.locate(NOTE, "four times").status == finder.NONE


def test_an_empty_quote_is_none_not_everywhere():
    assert finder.locate(NOTE, "").status == finder.NONE


def test_a_passage_twice_with_no_context_is_many():
    assert finder.locate(NOTE, "- Pack charger").status == finder.MANY


def test_context_before_the_passage_picks_which_of_two_it_was():
    before, after = finder.capture_context(NOTE, NOTE.rindex("- Pack charger"), NOTE.rindex("- Pack charger") + 14)

    found = finder.locate(NOTE, "- Pack charger", before, after)

    assert (found.status, found.start) == (finder.ONE, NOTE.rindex("- Pack charger"))


def test_context_still_picks_the_right_one_after_text_is_typed_before_both():
    start = NOTE.index("- Pack charger")
    before, after = finder.capture_context(NOTE, start, start + 14)
    edited = "XX " + NOTE

    found = finder.locate(edited, "- Pack charger", before, after)

    assert (found.status, found.start) == (finder.ONE, edited.index("- Pack charger"))


def test_context_that_fits_both_equally_is_still_many():
    twin = "alpha\nsame\nalpha\nsame\n"

    assert finder.locate(twin, "same", "alpha\n", "\n").status == finder.MANY


def test_context_that_fits_neither_is_many_not_a_guess():
    assert finder.locate(NOTE, "- Pack charger", "unrelated", "unrelated").status == finder.MANY


def test_the_better_fitting_context_wins_even_if_neither_is_perfect():
    start = NOTE.rindex("- Pack charger")
    before, after = finder.capture_context(NOTE, start, start + 14)
    edited = NOTE.replace("## Electronics", "## Gadgets")

    found = finder.locate(edited, "- Pack charger", before, after)

    assert (found.status, found.start) == (finder.ONE, edited.rindex("- Pack charger"))


def test_overlapping_occurrences_are_counted_as_many():
    assert finder.locate("aaa", "aa").status == finder.MANY


def test_context_is_taken_from_either_side_and_bounded():
    text = "0123456789" * 20

    before, after = finder.capture_context(text, 100, 105, size=7)

    assert (before, after) == (text[93:100], text[105:112])


def test_context_at_the_edges_of_the_note_is_short_not_an_error():
    assert finder.capture_context("abc", 0, 3, size=10) == ("", "")


def test_a_passage_edited_in_place_is_none():
    start = NOTE.index("three times")
    before, after = finder.capture_context(NOTE, start, start + 11)
    edited = NOTE.replace("three times", "five times")

    assert finder.locate(edited, "three times", before, after).status == finder.NONE


def test_context_near_the_top_of_the_note_keeps_what_there_is():
    assert finder.capture_context("abcdefgh", 3, 5, size=10) == ("abc", "fgh")


def test_a_passage_at_the_very_start_is_not_compared_with_the_end_of_the_note():
    # Counting back from the start must stop at the start, not wrap round to the last characters.
    assert finder.locate("a b a z", "a", "z", "").status == finder.MANY


def test_starts_within_lists_only_the_occurrences_that_lie_wholly_inside_a_span():
    text = "aa bb aa bb aa"

    assert finder.starts_within(text, "aa", [(0, 5)]) == [0]
    assert finder.starts_within(text, "aa", [(0, 14)]) == [0, 6, 12]
    assert finder.starts_within(text, "aa", [(1, 5)]) == []  # starts before the span
    assert finder.starts_within(text, "aa", []) == [] and finder.starts_within(text, "", [(0, 14)]) == []
