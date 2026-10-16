"""Changing one part of a definition note and leaving the rest as it was (docs/decisions/087). Pure text."""

import pytest

from sympose import folder_definitions as defs
from sympose import folder_settings_text as t

NOTE = "---\ntype: folder\nicon: old\n---\n# Movies\n\nFilms I watched.\n\n## Template\n\n```yaml\nrole:\n```\n\nAfter the block.\n"


# --- with_look ------------------------------------------------------------------------------


def test_a_key_the_note_sets_is_replaced_in_place_and_the_others_stay():
    assert t.with_look(NOTE, {"icon": "film-roll"}) == NOTE.replace("icon: old", "icon: film-roll")


def test_a_new_key_goes_at_the_end_of_the_frontmatter_in_the_order_given():
    got = t.with_look(NOTE, {"accent": "#be123c", "accent_dark": "#f2889b"})
    assert got.startswith("---\ntype: folder\nicon: old\naccent: '#be123c'\naccent_dark: '#f2889b'\n---\n# Movies")


def test_a_key_set_to_none_is_removed_with_its_continuation_lines_and_no_other_line():
    note = "---\nicon: a\n  b\ntype: x\n---\nBody\n"
    assert t.with_look(note, {"icon": None}) == "---\ntype: x\n---\nBody\n"


def test_clearing_a_key_the_note_never_set_changes_nothing():
    assert t.with_look(NOTE, {"accent": None}) == NOTE


def test_a_note_without_frontmatter_gets_a_block_and_keeps_its_text():
    assert t.with_look("# Movies\n", {"icon": "film-roll"}) == "---\nicon: film-roll\n---\n# Movies\n"


def test_nothing_to_set_on_a_note_without_frontmatter_makes_no_block():
    assert t.with_look("# Movies\n", {"icon": None}) == "# Movies\n"


def test_a_note_that_opens_a_block_it_never_closes_is_not_repaired():
    assert t.with_look("---\nicon: a\n# Movies\n", {"icon": "b"}) is None


def test_a_key_that_only_starts_with_the_name_is_not_the_key():
    note = "---\nicon_style: round\n---\n"
    assert t.with_look(note, {"icon": "book"}) == "---\nicon_style: round\nicon: book\n---\n"


def test_an_indented_line_called_like_the_key_is_not_the_key():
    note = "---\nmeta:\n  icon: nested\n---\n"
    assert t.with_look(note, {"icon": "book"}) == "---\nmeta:\n  icon: nested\nicon: book\n---\n"


def test_a_replaced_line_keeps_its_crlf_and_the_rest_is_byte_for_byte():
    note = "---\r\nicon: old\r\ntype: x\r\n---\r\n# A\r\n"
    assert t.with_look(note, {"icon": "book"}) == "---\r\nicon: book\r\ntype: x\r\n---\r\n# A\r\n"


def test_a_frontmatter_only_note_with_no_final_line_break_still_closes():
    assert t.with_look("---\ntype: x\n---", {"icon": "book"}) == "---\ntype: x\nicon: book\n---"


def test_an_empty_frontmatter_block_takes_the_key():
    assert t.with_look("---\n---\nBody\n", {"icon": "book"}) == "---\nicon: book\n---\nBody\n"


def test_a_byte_order_mark_before_the_rule_is_kept():
    assert t.with_look("\ufeff---\nicon: a\n---\n", {"icon": "b"}) == "\ufeff---\nicon: b\n---\n"


# --- with_purpose ---------------------------------------------------------------------------


def test_the_purpose_is_replaced_between_the_title_and_the_template_heading():
    assert t.with_purpose(NOTE, "Films and series.") == NOTE.replace("Films I watched.", "Films and series.")


def test_a_cleared_purpose_leaves_the_title_and_one_blank_line_before_the_template():
    got = t.with_purpose(NOTE, "  ")
    assert got == NOTE.replace("Films I watched.\n\n", "") and defs.read_purpose(got) is None


def test_a_purpose_added_to_a_note_that_had_none():
    note = "# Movies\n\n## Template\n\n```yaml\n```\n"
    got = t.with_purpose(note, "Films.")
    assert got == "# Movies\n\nFilms.\n\n## Template\n\n```yaml\n```\n" and defs.read_purpose(got) == "Films."


def test_a_purpose_in_a_note_with_no_template_heading_replaces_the_whole_body_after_the_title():
    assert t.with_purpose("---\nicon: a\n---\n# Movies\n\nold\n", "new") == "---\nicon: a\n---\n# Movies\n\nnew\n"


def test_a_note_with_no_title_gets_no_leading_blank_line():
    assert t.with_purpose("Old.\n\n## Template\n\n```\n```\n", "New.") == "New.\n\n## Template\n\n```\n```\n"


def test_a_title_with_no_final_line_break_gets_one_when_something_follows():
    assert t.with_purpose("# Movies", "Films.") == "# Movies\n\nFilms.\n"


def test_what_follows_the_template_block_is_not_touched():
    assert t.with_purpose(NOTE, "x").endswith("```\n\nAfter the block.\n")


def test_the_frontmatter_is_not_read_as_the_purpose():
    assert t.with_purpose("---\nicon: a\n---\n# M\n\nold\n\n## Template\n\n```\n```\n", "new").startswith("---\nicon: a\n---\n# M\n\nnew\n")


@pytest.mark.parametrize("purpose", ["Films.", "Two\nlines.", ""])
def test_what_is_written_reads_back_as_the_purpose(purpose):
    assert (defs.read_purpose(t.with_purpose(NOTE, purpose)) or "") == purpose


# --- with_template --------------------------------------------------------------------------


def test_the_lines_inside_the_block_are_replaced_and_the_fences_stay():
    got = t.with_template(NOTE, ["role:", "email: x"])
    assert got == NOTE.replace("role:\n", "role:\nemail: x\n") and defs.read_template(got) == "role:\nemail: x"


def test_a_cleared_template_leaves_an_empty_block():
    got = t.with_template(NOTE, [])
    assert "```yaml\n```\n\nAfter the block." in got and defs.read_template(got) is None


def test_a_block_that_is_never_closed_is_closed_with_its_own_fence():
    got = t.with_template("## Template\n\n~~~\na:\n", ["b:"])
    assert got == "## Template\n\n~~~\nb:\n~~~\n"


def test_a_block_whose_opening_fence_is_the_last_line_still_gets_its_lines_on_their_own_lines():
    assert t.with_template("## Template\n\n```", ["a:"]) == "## Template\n\n```\na:\n```\n"


def test_a_note_without_the_section_gets_one_at_its_end():
    got = t.with_template("# A\n\nhi\n", ["a:", "b:"])
    assert got == "# A\n\nhi\n\n## Template\n\n```yaml\na:\nb:\n```\n" and defs.read_template(got) == "a:\nb:"


def test_a_note_without_the_section_and_no_lines_is_left_alone():
    assert t.with_template("# A\n", []) == "# A\n"


def test_a_note_of_only_frontmatter_gets_the_section_after_it():
    assert t.with_template("---\nicon: a\n---\n", ["a:"]) == "---\nicon: a\n---\n## Template\n\n```yaml\na:\n```\n"


def test_the_frontmatter_stays_when_the_template_changes():
    assert t.with_template(NOTE, ["x:"]).startswith("---\ntype: folder\nicon: old\n---\n# Movies")
