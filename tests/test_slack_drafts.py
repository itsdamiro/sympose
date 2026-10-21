"""What a persona proposed, shown under its Slack reply (docs/decisions/093): built from the draft as it waits, escaped for Slack,
cut at a limit worked out from the room the reply leaves, and never past what Slack takes in one message."""

import pytest

from sympose import note_changes, slack_drafts
from sympose.slack_text import LIMIT, MAX_CHARS, to_mrkdwn

H = "samantha"
FENCE = "```"


def draft(name="Seeds", text="# Seeds\n\nSow in March.\n", folder=None) -> dict:
    return {"kind": "create", "name": name, "text": text, **({"folder": folder} if folder else {})}


def test_a_note_is_shown_whole_in_a_code_block_under_the_reply_with_one_line_on_where_it_waits():
    shown = slack_drafts.under("Here it is.", [draft()])

    assert shown == f"Here it is.\n\n*New note: Seeds*\n{FENCE}\n# Seeds\n\nSow in March.\n{FENCE}\n\n{slack_drafts.FOOTER}"
    assert "web app" in slack_drafts.FOOTER and "Drafts" in slack_drafts.FOOTER


def test_a_reply_that_proposed_nothing_is_left_exactly_as_it_is():
    assert slack_drafts.under("Just talking.", []) == "Just talking."


def test_the_folder_it_was_asked_for_is_said():
    assert "*New note: Seeds* in Projects/Garden\n" in slack_drafts.under("ok", [draft(folder="Projects/Garden")])


def test_two_notes_are_shown_one_after_the_other():
    shown = slack_drafts.under("ok", [draft("One", "First."), draft("Two", "Second.")])

    assert shown.index("*New note: One*") < shown.index("First.") < shown.index("*New note: Two*") < shown.index("Second.")
    assert shown.endswith(slack_drafts.FOOTER) and shown.count(slack_drafts.FOOTER) == 1


def test_what_slack_reads_as_its_own_marks_is_escaped_inside_the_code_too():
    shown = slack_drafts.under("ok", [draft("A <b> & c", "Use <!channel> & a > b.")])

    assert "Use &lt;!channel&gt; &amp; a &gt; b." in shown and "*New note: A &lt;b&gt; &amp; c*" in shown
    assert "<!channel>" not in shown


def test_a_fence_in_the_note_cannot_close_ours():
    shown = slack_drafts.under("ok", [draft(text=f"Run:\n{FENCE}\nls\n{FENCE}\nThen stop.")])
    body = shown.split(f"\n{FENCE}\n", 1)[1].rsplit(f"\n{FENCE}", 1)[0]

    assert FENCE not in body and "ls" in body and "Then stop." in body


def test_a_title_cannot_break_the_bold_line_or_run_on():
    shown = slack_drafts.under("ok", [draft("*Big*\nidea  with %s and %d")])

    assert "*New note: Big idea with %s and %d*\n" in shown


def test_a_long_title_is_shortened():
    shown = slack_drafts.under("ok", [draft("w" * 200)])

    assert "*New note: " + "w" * 59 + "…*" in shown


def test_an_untitled_draft_is_called_so():
    assert "*New note: Untitled*" in slack_drafts.under("ok", [{"kind": "create", "text": "x"}])


def test_a_note_too_long_for_the_room_is_cut_at_a_line_and_says_how_much_was_left_and_where_to_read_it():
    lines = [f"Line {i} of the note." for i in range(3000)]
    text = "\n".join(lines)
    reply = "ok"

    shown = slack_drafts.under(reply, [draft(text=text)])

    kept = shown.split(f"{FENCE}\n", 1)[1].split(f"\n{FENCE}", 1)[0]
    assert len(shown) <= LIMIT and len(shown) > LIMIT - 1500  # it uses the room, not a made-up figure
    assert kept.splitlines()[-1] in lines and text.startswith(kept)  # a whole line, from the start
    assert f"Cut here: {len(text) - len(kept)} more characters" in shown and "Drafts in the web app" in shown
    assert shown.endswith(slack_drafts.FOOTER)


def test_the_room_is_what_the_reply_leaves_so_a_longer_reply_shows_less_of_the_note():
    text = "\n".join(f"Line {i} of the note." for i in range(3000))

    short_reply = slack_drafts.under("ok", [draft(text=text)])
    long_reply = slack_drafts.under("word " * 4000, [draft(text=text)])

    assert len(long_reply) <= LIMIT and len(short_reply) <= LIMIT
    assert long_reply.count("Line ") < short_reply.count("Line ") - 500


def test_one_long_line_is_cut_inside_the_line_when_there_is_no_line_to_cut_at():
    text = "a" * (LIMIT * 2)

    shown = slack_drafts.under("ok", [draft(text=text)])

    assert len(shown) <= LIMIT and "a" * 30000 in shown and "more characters" in shown


def test_an_early_line_end_is_not_a_place_to_cut_when_the_next_line_runs_on():
    text = "A short first line.\n" + "b" * (LIMIT * 2)

    shown = slack_drafts.under("ok", [draft(text=text)])

    assert len(shown) <= LIMIT and "b" * 30000 in shown


def test_a_cut_never_splits_an_escaped_mark():
    text = "&" * (LIMIT * 2)

    shown = slack_drafts.under("ok", [draft(text=text)])
    body = shown.split(f"{FENCE}\n", 1)[1].split(f"\n{FENCE}", 1)[0]

    assert len(shown) <= LIMIT and body.replace("&amp;", "") == ""


def test_a_reply_at_its_own_cap_still_leaves_room_for_a_short_look_at_the_note():
    reply = to_mrkdwn("word " * 20000)

    shown = slack_drafts.under(reply, [draft(text="Some words " * 300)])

    assert len(shown) <= LIMIT and shown.startswith(reply) and "Some words" in shown and "more characters" in shown


def test_a_note_after_a_long_one_is_named_not_squeezed_in():
    text = "\n".join(f"Line {i} of the note." for i in range(3000))

    shown = slack_drafts.under("ok", [draft("Long", text), draft("Second one", "Short.")])

    assert len(shown) <= LIMIT
    assert "*New note: Second one*" not in shown and "Short." not in shown
    assert "Too long to show here" in shown and "Second one" in shown


def test_a_note_too_long_to_show_is_named_and_a_short_one_after_it_is_still_shown():
    shown = slack_drafts.under("r" * 39_500, [draft("Big", "x " * 2000), draft("Small", "hi")])

    assert "*New note: Small*\n```\nhi\n```" in shown and "Too long to show here" in shown and "Big" in shown.split("Too long")[1]


def test_when_the_reply_leaves_too_little_room_every_note_is_named_and_the_message_still_fits():
    reply = "r" * 39_500  # a reply close to what Slack takes leaves under what a cut note needs

    shown = slack_drafts.under(reply, [draft("First", "Some words " * 300), draft("Second", "More words " * 300)])

    assert len(shown) <= LIMIT and shown.startswith(reply)
    assert "Some words" not in shown and "First, Second" in shown and shown.endswith(slack_drafts.FOOTER)


def test_many_long_names_are_counted_not_all_listed():
    many = [draft(f"Note number {i}", "x " * 2000) for i in range(9)]

    shown = slack_drafts.under("r" * 39_500, many)

    assert len(shown) <= LIMIT and "Note number 0, Note number 1, Note number 2 and 6 more" in shown and "Note number 5" not in shown


@pytest.mark.parametrize("reply_length", [0, 1000, 20000, 38000, MAX_CHARS, MAX_CHARS + 120])
@pytest.mark.parametrize("size", [0, 100, 5000, 45000, 120000])
@pytest.mark.parametrize("count", [1, 2, 5])
def test_whatever_the_sizes_the_message_fits_in_one_slack_message_and_the_reply_is_untouched(reply_length, size, count):
    reply = "r" * reply_length
    notes = [draft(f"Note {i}", ("<&> line\n" * size)[:size]) for i in range(count)]

    shown = slack_drafts.under(reply, notes)

    assert len(shown) <= LIMIT and shown.startswith(reply)


def test_a_draft_that_is_waiting_is_read_from_the_store_as_it_is_now_not_as_it_was_filed():
    with note_changes.new_notes_made() as made:
        note_changes.propose_create(H, "new/1", "# Seeds\n\nFirst words.\n", say="", title="Seeds", folder="Garden")
    ((path, proposal_id),) = made
    note_changes.edit_draft(H, path, "# Seeds\n\nSettled words.\n")  # e.g. a source added at the end of the turn

    (found,) = slack_drafts.waiting(H, made)

    assert found["text"] == "# Seeds\n\nSettled words.\n" and found["name"] == "Seeds" and found["folder"] == "Garden"
    assert proposal_id == found["id"]


def test_a_draft_that_is_gone_by_the_time_the_reply_is_built_is_not_shown():
    with note_changes.new_notes_made() as made:
        note_changes.propose_create(H, "new/1", "# One\n\nFirst.\n", say="", title="One")
        note_changes.propose_create(H, "new/2", "# Two\n\nSecond.\n", say="", title="Two")
    note_changes.forget(H, "new/1")

    assert [p["name"] for p in slack_drafts.waiting(H, made)] == ["Two"]


def test_nothing_made_shows_nothing():
    assert slack_drafts.waiting(H, []) == []


# --- review of slice 2 (2026-10-22) ---------------------------------------------------------------
def test_a_note_with_a_code_block_says_that_the_block_is_marked_and_a_note_without_one_does_not():
    with_block = slack_drafts.under("ok", [draft(text=f"Run:\n{FENCE}\nls\n{FENCE}")])
    without = slack_drafts.under("ok", [draft(text="Plain words.")])

    assert slack_drafts.MARKED_FENCE in with_block
    assert slack_drafts.MARKED_FENCE not in without


def test_the_note_about_a_marked_code_block_sits_under_that_note_and_not_the_other_one():
    shown = slack_drafts.under("ok", [draft("One", "Plain."), draft("Two", f"{FENCE}\nx\n{FENCE}")])

    assert shown.index("*New note: Two*") < shown.index(slack_drafts.MARKED_FENCE) < shown.index(slack_drafts.FOOTER)
    assert shown.count(slack_drafts.MARKED_FENCE) == 1


def test_the_marked_block_note_is_counted_in_the_room():
    text = (f"{FENCE}\n" + "code\n" * 50 + f"{FENCE}\n") * 1000

    shown = slack_drafts.under("ok", [draft(text=text)])

    assert len(shown) <= LIMIT and slack_drafts.MARKED_FENCE in shown and shown.endswith(slack_drafts.FOOTER)


@pytest.mark.parametrize("mark", ["*", "_", "~", "`"])
def test_a_title_or_folder_cannot_start_formatting_of_its_own(mark):
    shown = slack_drafts.under("ok", [draft(f"a{mark}b{mark}c", folder=f"x{mark}y{mark}z")])

    assert "*New note: abc* in xyz\n" in shown


def test_the_room_kept_for_the_names_of_drafts_left_out_is_the_line_at_its_longest():
    longest = slack_drafts.NOT_SHOWN.format(names=", ".join(["x" * 60] * 3) + " and 999 more")

    assert slack_drafts._RESERVED == len(longest) + 2


@pytest.mark.parametrize("reply_length", [0, 20000, 38000, MAX_CHARS, MAX_CHARS + 120])
@pytest.mark.parametrize("count", [1, 2, 5, 40])
@pytest.mark.parametrize("size", [0, 100, 600, 5000, 45000])
def test_the_whole_message_never_passes_the_limit_whatever_is_proposed(reply_length, count, size):
    names = ["N" * 120 + str(i) for i in range(count)]
    drafts = [draft(name, ("&" * size) + f"\n{FENCE}\n" + "y" * 10) for name in names]

    assert len(slack_drafts.under("r" * reply_length, drafts)) <= LIMIT
