"""Where a change of hers may sit in a table (docs/decisions/069, the 2026-10-05 amendment): inside one cell's own words,
with a replacement that stays in that cell. Anything else is refused, since the editor cannot draw it."""

import pytest

from sympose import note_changes as nc
from sympose import note_changes_store as store
from sympose import table_spans as ts

TABLE = "| Item | Qty | Note |\n|------|-----|------|\n| Carrots | 3 | sow early |\n| Beets | 5 | sow late |\n"
NOTE = f"The beds are raised.\n\n{TABLE}\nDone.\n"


def at(text: str, words: str) -> tuple[int, int]:
    start = text.index(words)
    return start, start + len(words)


def problem(find: str, replace: str, text: str = NOTE) -> str | None:
    start, end = at(text, find)
    return ts.problem(text, start, end, replace)


def test_a_change_outside_any_table_is_left_alone():
    assert problem("raised", "sunken") is None
    assert problem("Done.", "Finished.") is None


@pytest.mark.parametrize("find, replace", [("Carrots", "Parsnips"), ("sow early", "sow in March"), ("Item", "Thing"), ("3", "4"), ("sow", "plant")])
def test_words_inside_one_cell_with_a_replacement_inside_it_are_allowed(find, replace):
    assert problem(find, replace) is None


def test_the_header_row_counts_as_cells_and_the_delimiter_row_does_not():
    assert problem("Qty", "Amount") is None
    assert problem("------", "-----") is not None


@pytest.mark.parametrize("find", ["Carrots | 3", "3 | sow early", "| Carrots", "Carrots |", "| Carrots | 3 | sow early |"])
def test_words_that_run_over_a_cell_border_are_refused(find):
    assert "one cell" in (problem(find, "x") or "")


def test_words_that_run_over_a_line_are_refused():
    assert problem("early |\n| Beets", "x") is not None
    assert problem("Done.", "x", NOTE) is None
    assert "one cell" in (problem("sow late |\n\nDone", "x") or "")
    assert "one cell" in (problem("raised.\n\n| Item", "x") or "")


def test_whitespace_around_the_words_belongs_to_the_padding_and_is_refused():
    text = "| Item  | Qty |\n|-------|-----|\n| Carrots  | 3 |\n"
    assert problem("Carrots  ", "x", text) is not None
    assert problem("Carrots", "x", text) is None


@pytest.mark.parametrize("replace", ["a | b", "two\nlines", "a |"])
def test_a_replacement_that_would_split_the_cell_or_the_row_is_refused(replace):
    assert "cell" in (problem("Carrots", replace) or "")


def test_an_escaped_pipe_in_a_replacement_stays_in_its_cell():
    assert problem("Carrots", r"a \| b") is None


def test_a_replacement_with_a_pipe_is_fine_outside_a_table():
    assert problem("raised", "a | b") is None


def test_a_line_with_a_pipe_but_no_delimiter_row_is_not_a_table():
    text = "a | b | c\njust text | here\n"
    assert problem("a | b", "x", text) is None


def test_a_header_whose_cell_count_differs_from_the_delimiter_is_not_a_table():
    text = "| a | b | c |\n|---|---|\n| 1 | 2 | 3 |\n"
    assert problem("1 | 2", "x", text) is None


def test_a_table_inside_a_code_fence_is_not_a_table():
    text = f"```\n{TABLE}```\n"
    assert problem("Carrots | 3", "x", text) is None


def test_a_table_ends_at_the_first_blank_line():
    text = f"{TABLE}\nafter | the | table\n"
    assert problem("after | the", "x", text) is None


def test_a_table_without_outer_pipes_is_found():
    text = "Item | Qty\n--- | ---\nCarrots | 3\n"
    assert problem("Carrots", "x", text) is None
    assert problem("Carrots | 3", "x", text) is not None


def test_propose_edit_refuses_a_change_across_cells_and_saves_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    (tmp_path / "samantha").mkdir()
    with pytest.raises(nc.CannotAnchor, match="one cell"):
        nc.propose_edit("samantha", "Plan.md", NOTE, find="Carrots | 3", replace="x", say="")
    assert store.read("samantha", "Plan.md")["proposals"] == []


def test_propose_edit_allows_a_change_inside_a_cell(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    (tmp_path / "samantha").mkdir()
    nc.propose_edit("samantha", "Plan.md", NOTE, find="Carrots", replace="Parsnips", say="")
    assert [p["find"] for p in store.read("samantha", "Plan.md")["proposals"]] == ["Carrots"]


def test_words_that_end_where_the_table_starts_or_begin_where_it_ends_do_not_touch_it():
    assert problem("raised.\n\n", "x") is None
    text = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert ts.problem(text, len(text), len(text) + 1, "x") is None


def test_a_single_pipe_row_over_a_dash_line_is_a_heading_not_a_table():
    assert problem("a |\n---", "x", "| a |\n---\nstuff\n") is None


def test_nothing_quoted_inside_a_cell_is_refused():
    start, _ = at(NOTE, "Carrots")
    assert ts.problem(NOTE, start, start, "x") is not None


CRLF = NOTE.replace("\n", "\r\n")
QUOTED = "> A quote.\n>\n> | Item | Qty |\n> |------|-----|\n> | Carrots | 3 |\n\nDone.\n"
DEEP = "1. Step\n\n    | Item | Qty |\n    |------|-----|\n    | Carrots | 3 |\n"


@pytest.mark.parametrize("find", ["Carrots | 3", "| Carrots", "3 | sow early"])
def test_a_note_with_windows_line_endings_is_read_the_same(find):
    assert "one cell" in (problem(find, "x", CRLF) or "")


def test_windows_line_endings_do_not_get_in_the_way_of_a_change_inside_a_cell():
    assert problem("Carrots", "Parsnips", CRLF) is None
    assert problem("sow early", "x", CRLF) is None
    assert problem("raised", "sunken", CRLF) is None


def test_a_line_break_in_a_replacement_is_refused_in_a_cell_however_the_note_ends_its_lines():
    assert problem("Carrots", "a\r\nb", CRLF) is not None


def test_a_table_inside_a_blockquote_is_a_table():
    assert "one cell" in (problem("Carrots | 3", "x", QUOTED) or "")
    assert "one cell" in (problem("> | Carrots", "x", QUOTED) or "")
    assert problem("Carrots", "Parsnips", QUOTED) is None
    assert problem("A quote.", "x", QUOTED) is None


def test_a_table_indented_under_a_list_item_is_a_table():
    assert "one cell" in (problem("Carrots | 3", "x", DEEP) or "")
    assert problem("Carrots", "Parsnips", DEEP) is None


def test_a_table_in_a_fence_inside_a_blockquote_is_not_a_table():
    text = "> ```\n> | a | b |\n> |---|---|\n> | Carrots | 3 |\n> ```\n"
    assert problem("Carrots | 3", "x", text) is None


def test_a_table_inside_a_nested_blockquote_is_a_table():
    text = "> > | a | b |\n> > |---|---|\n> > | Carrots | 3 |\n"
    assert "one cell" in (problem("Carrots | 3", "x", text) or "")
    assert problem("Carrots", "Parsnips", text) is None


def test_a_table_inside_a_tilde_fence_is_not_a_table():
    text = "~~~\n| a | b |\n|---|---|\n| Carrots | 3 |\n~~~\n"
    assert problem("Carrots | 3", "x", text) is None


def test_a_line_that_only_looks_like_a_fence_does_not_swallow_the_table_after_it():
    # a backtick fence's info string cannot hold a backtick, so this line is inline code, not an opening fence
    text = "```inline``` text\n\n| a | b |\n|---|---|\n| Carrots | 3 |\n"
    assert "one cell" in (problem("Carrots | 3", "x", text) or "")


def test_a_fence_closes_only_with_its_own_character_and_at_least_its_own_length():
    text = "````\n```\n~~~\n| a | b |\n|---|---|\n| Carrots | 3 |\n````\n\n| c | d |\n|---|---|\n| Beets | 5 |\n"
    assert problem("Carrots | 3", "x", text) is None  # all of it is inside the four-backtick fence
    assert "one cell" in (problem("Beets | 5", "x", text) or "")  # and the table after the fence is found


def test_a_table_whose_header_starts_with_a_list_marker_is_a_table():
    bullet = "- | a | b |\n  |---|---|\n  | Carrots | 3 |\n"
    numbered = "1. | a | b |\n   |---|---|\n   | Carrots | 3 |\n"
    for text in (bullet, numbered):
        assert "one cell" in (problem("Carrots | 3", "x", text) or "")
        assert problem("Carrots", "Parsnips", text) is None
    assert problem("a | b", "x", bullet) is not None


def test_a_bullet_line_that_is_not_over_a_delimiter_row_is_not_a_table():
    text = "- one | two\n- three | four\n"
    assert problem("one | two", "x", text) is None


def test_a_replacement_ending_in_a_backslash_would_escape_the_pipe_after_it_and_is_refused():
    compact = "|Carrots|3|\n|-|-|\n|Beets|5|\n"
    assert "one cell" in (problem("Carrots", "x\\", compact) or "")
    assert problem("Carrots", "x", compact) is None


def test_a_tilde_fence_is_not_closed_by_backticks_inside_it():
    text = "~~~\n```\n| a | b |\n|---|---|\n| Carrots | 3 |\n~~~\n"
    assert problem("Carrots | 3", "x", text) is None


def test_a_fence_may_close_with_spaces_after_it():
    text = "```\ncode\n```   \n\n| a | b |\n|---|---|\n| Carrots | 3 |\n"
    assert "one cell" in (problem("Carrots | 3", "x", text) or "")


def test_the_header_row_after_a_list_marker_keeps_its_own_cells():
    bullet = "- | a | b |\n  |---|---|\n  | Carrots | 3 |\n"
    assert problem("b", "x", bullet) is None
    assert problem("a", "x", bullet) is None


def test_a_table_ends_where_a_code_fence_opens_even_without_a_blank_line():
    text = "| a | b |\n|---|---|\n| 1 | 2 |\n```\ncode | x\n```\n"
    assert problem("code | x", "y", text) is None
