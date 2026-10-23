"""What a persona proposed, shown under its Slack reply (docs/decisions/093): built from the draft as it waits, escaped for Slack,
shown whole or only named, and never past what Slack takes in one message."""

import pytest

from sympose import note_changes, slack_drafts
from sympose.draft_limit import Filing
from sympose.slack_text import LIMIT, MAX_CHARS

H = "samantha"
FENCE = "```"


def under(reply, drafts):
    return slack_drafts.compose(reply, drafts)[0]


def draft(name="Seeds", text="# Seeds\n\nSow in March.\n", folder=None) -> dict:
    return {"kind": "create", "name": name, "text": text, **({"folder": folder} if folder else {})}


def test_a_note_is_shown_whole_in_a_code_block_under_the_reply_with_one_line_on_where_it_waits():
    shown = under("Here it is.", [draft()])

    assert shown == f"Here it is.\n\n*New note: Seeds*\n{FENCE}\n# Seeds\n\nSow in March.\n{FENCE}\n\n{slack_drafts.FOOTER}"
    assert "web app" in slack_drafts.FOOTER and "Drafts" in slack_drafts.FOOTER


def test_a_reply_that_proposed_nothing_is_left_exactly_as_it_is():
    assert under("Just talking.", []) == "Just talking."


def test_the_folder_it_was_asked_for_is_said():
    assert "*New note: Seeds* in Projects/Garden\n" in under("ok", [draft(folder="Projects/Garden")])


def test_two_notes_are_shown_one_after_the_other():
    shown = under("ok", [draft("One", "First."), draft("Two", "Second.")])

    assert shown.index("*New note: One*") < shown.index("First.") < shown.index("*New note: Two*") < shown.index("Second.")
    assert shown.endswith(slack_drafts.FOOTER) and shown.count(slack_drafts.FOOTER) == 1


def test_what_slack_reads_as_its_own_marks_is_escaped_inside_the_code_too():
    shown = under("ok", [draft("A <b> & c", "Use <!channel> & a > b.")])

    assert "Use &lt;!channel&gt; &amp; a &gt; b." in shown and "*New note: A &lt;b&gt; &amp; c*" in shown
    assert "<!channel>" not in shown


def test_a_fence_in_the_note_cannot_close_ours():
    shown = under("ok", [draft(text=f"Run:\n{FENCE}\nls\n{FENCE}\nThen stop.")])
    body = shown.split(f"\n{FENCE}\n", 1)[1].rsplit(f"\n{FENCE}", 1)[0]

    assert FENCE not in body and "ls" in body and "Then stop." in body


def test_a_title_cannot_break_the_bold_line_or_run_on():
    shown = under("ok", [draft("*Big*\nidea  with %s and %d")])

    assert "*New note: Big idea with %s and %d*\n" in shown


def test_a_long_title_is_shortened():
    shown = under("ok", [draft("w" * 200)])

    assert "*New note: " + "w" * 59 + "…*" in shown


def test_an_untitled_draft_is_called_so():
    assert "*New note: Untitled*" in under("ok", [{"kind": "create", "text": "x"}])


def test_a_note_too_long_for_the_room_is_named_not_cut_and_says_where_to_read_it():
    text = "\n".join(f"Line {i} of the note." for i in range(3000))

    shown = under("ok", [draft("Long", text)])

    assert len(shown) <= LIMIT and "Line 0 of" not in shown
    assert "Too long to show here" in shown and "Long" in shown and "Drafts in the web app" in shown
    assert shown.endswith(slack_drafts.FOOTER_WEB)


def test_the_room_is_what_the_reply_leaves_so_a_longer_reply_names_a_note_a_shorter_one_shows():
    text = "Line of the note.\n" * 1000

    short_reply = under("ok", [draft(text=text)])
    long_reply = under("word " * 7000, [draft(text=text)])

    assert "Line of the note." in short_reply and "Too long to show here" not in short_reply
    assert "Line of the note." not in long_reply and "Too long to show here" in long_reply and len(long_reply) <= LIMIT


def test_a_note_that_fills_the_room_exactly_is_shown_and_one_character_more_is_named():
    reply = "ok"
    room = LIMIT - len(reply) - len(slack_drafts.FOOTER) - 2 * len(slack_drafts._GAP) - slack_drafts._RESERVED
    overhead = len(slack_drafts._show(draft(text=""), LIMIT))

    fits = under(reply, [draft(text="y" * (room - overhead))])
    over = under(reply, [draft(text="y" * (room - overhead + 1))])

    assert "y" * (room - overhead) in fits and "Too long to show here" not in fits
    assert "yyy" not in over and "Too long to show here" in over


def test_the_blank_line_between_two_notes_is_counted_in_the_room():
    room = LIMIT - len("ok") - len(slack_drafts.FOOTER) - 2 * len(slack_drafts._GAP) - slack_drafts._RESERVED
    first = draft("One", "y" * 100)
    left = room - len(slack_drafts._show(first, LIMIT)) - len(slack_drafts._GAP)
    second = lambda size: draft("Two", "z" * size)  # noqa: E731
    fits_at = left - len(slack_drafts._show(second(0), LIMIT))

    fits, over = under("ok", [first, second(fits_at)]), under("ok", [first, second(fits_at + 1)])

    assert "z" * fits_at in fits and "Too long to show here" not in fits
    assert "zzz" not in over and "Too long to show here" in over


def test_a_mark_in_a_note_that_is_shown_is_escaped_whole():
    shown = under("ok", [draft(text="&" * 1000)])

    assert shown.split(f"{FENCE}\n", 1)[1].split(f"\n{FENCE}", 1)[0] == "&amp;" * 1000


def test_a_note_too_long_to_show_is_named_and_a_short_one_after_it_is_still_shown():
    shown = under("r" * 39_500, [draft("Big", "x " * 2000), draft("Small", "hi")])

    assert "*New note: Small*\n```\nhi\n```" in shown and "Too long to show here" in shown and "Big" in shown.split("Too long")[1]


def test_when_the_reply_leaves_too_little_room_every_note_is_named_and_the_message_still_fits():
    reply = "r" * 39_500  # a reply close to what Slack takes leaves no room for a note of this size

    shown = under(reply, [draft("First", "Some words " * 300), draft("Second", "More words " * 300)])

    assert len(shown) <= LIMIT and shown.startswith(reply)
    assert "Some words" not in shown and "First, Second" in shown and shown.endswith(slack_drafts.FOOTER_WEB)


def test_many_long_names_are_counted_not_all_listed():
    many = [draft(f"Note number {i}", "x " * 2000) for i in range(9)]

    shown = under("r" * 39_500, many)

    assert len(shown) <= LIMIT and "Note number 0, Note number 1, Note number 2 and 6 more" in shown and "Note number 5" not in shown


@pytest.mark.parametrize("reply_length", [0, 1000, 20000, 38000, MAX_CHARS, MAX_CHARS + 120])
@pytest.mark.parametrize("size", [0, 100, 5000, 45000, 120000])
@pytest.mark.parametrize("count", [1, 2, 5])
def test_whatever_the_sizes_the_message_fits_in_one_slack_message_and_the_reply_is_untouched(reply_length, size, count):
    reply = "r" * reply_length
    notes = [draft(f"Note {i}", ("<&> line\n" * size)[:size]) for i in range(count)]

    shown = under(reply, notes)

    assert len(shown) <= LIMIT and shown.startswith(reply)


def test_a_draft_that_is_waiting_is_read_from_the_store_as_it_is_now_not_as_it_was_filed():
    made = Filing()
    note_changes.propose_create(H, "new/1", "# Seeds\n\nFirst words.\n", say="", title="Seeds", folder="Garden", filing=made)
    ((path, proposal_id),) = made.made
    note_changes.edit_draft(H, path, "# Seeds\n\nSettled words.\n")  # e.g. a source added at the end of the turn

    (found,) = slack_drafts.waiting(H, made.made)

    assert found["text"] == "# Seeds\n\nSettled words.\n" and found["name"] == "Seeds" and found["folder"] == "Garden"
    assert proposal_id == found["id"]


def test_a_draft_that_is_gone_by_the_time_the_reply_is_built_is_not_shown():
    made = Filing()
    note_changes.propose_create(H, "new/1", "# One\n\nFirst.\n", say="", title="One", filing=made)
    note_changes.propose_create(H, "new/2", "# Two\n\nSecond.\n", say="", title="Two", filing=made)
    note_changes.forget(H, "new/1")

    assert [p["name"] for p in slack_drafts.waiting(H, made.made)] == ["Two"]


def test_nothing_made_shows_nothing():
    assert slack_drafts.waiting(H, []) == []


# --- review of slice 2 (2026-10-22) ---------------------------------------------------------------
def test_a_note_with_a_code_block_says_that_the_block_is_marked_and_a_note_without_one_does_not():
    with_block = under("ok", [draft(text=f"Run:\n{FENCE}\nls\n{FENCE}")])
    without = under("ok", [draft(text="Plain words.")])

    assert slack_drafts.MARKED_FENCE in with_block
    assert slack_drafts.MARKED_FENCE not in without


def test_the_note_about_a_marked_code_block_sits_under_that_note_and_not_the_other_one():
    shown = under("ok", [draft("One", "Plain."), draft("Two", f"{FENCE}\nx\n{FENCE}")])

    assert shown.index("*New note: Two*") < shown.index(slack_drafts.MARKED_FENCE) < shown.index(slack_drafts.FOOTER)
    assert shown.count(slack_drafts.MARKED_FENCE) == 1


def test_the_marked_block_note_is_counted_in_the_room():
    room = LIMIT - len("ok") - len(slack_drafts.FOOTER) - 2 * len(slack_drafts._GAP) - slack_drafts._RESERVED
    fenced = lambda size: draft(text=f"{FENCE}\n" + "y" * size + f"\n{FENCE}")  # noqa: E731
    fits_at = room - len(slack_drafts._show(fenced(0), LIMIT))

    fits, over = under("ok", [fenced(fits_at)]), under("ok", [fenced(fits_at + 1)])

    assert len(fits) <= LIMIT and slack_drafts.MARKED_FENCE in fits and fits.endswith(slack_drafts.FOOTER)
    assert slack_drafts.MARKED_FENCE not in over and over.endswith(slack_drafts.FOOTER_WEB)


@pytest.mark.parametrize("mark", ["*", "_", "~", "`"])
def test_a_title_or_folder_cannot_start_formatting_of_its_own(mark):
    shown = under("ok", [draft(f"a{mark}b{mark}c", folder=f"x{mark}y{mark}z")])

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

    assert len(under("r" * reply_length, drafts)) <= LIMIT


@pytest.mark.parametrize("reply_length", [MAX_CHARS - 150, MAX_CHARS - 100, MAX_CHARS - 1, MAX_CHARS, MAX_CHARS + 49])
@pytest.mark.parametrize("beyond", [-2, -1, 0, 1, 2])
def test_a_block_that_fills_its_room_to_the_character_leaves_the_message_within_the_limit_with_the_line_of_names(reply_length, beyond):
    # The footer's own blank line was not reserved: a block filling the room to the character, followed by the line naming a
    # thousand drafts left out (a longer count than the room reserved for in the sweep above), went over by up to two characters.
    room = LIMIT - reply_length - len(slack_drafts.FOOTER) - 2 * len(slack_drafts._GAP) - slack_drafts._RESERVED
    size = room - len(slack_drafts._show(draft("N" * 70 + "0"), LIMIT)) + beyond
    drafts = [draft("N" * 70 + str(i), "y" * max(size, 0)) for i in range(1000)]  # one line, no escapes: the first block is at the room's edge

    assert len(under("r" * reply_length, drafts)) <= LIMIT


# --- Accept and Decline in Slack (ADR 093, amendment of 2026-10-23) -------------------------------
def waiting_draft(name="Seeds", text="# Seeds\n\nSow in March.\n", folder="Inbox", path="new/abc", id="p1") -> dict:
    return {**draft(name, text, folder), "path": path, "id": id}


def test_a_waiting_draft_carries_the_path_it_waits_under():
    made = Filing()
    note_changes.propose_create(H, "new/1", "# One\n\nFirst.\n", say="", title="One", filing=made)
    ((path, _),) = made.made

    assert [p["path"] for p in slack_drafts.waiting(H, made.made)] == [path]


def test_the_footer_says_where_a_draft_can_be_accepted():
    assert "buttons" in slack_drafts.FOOTER and "web app" in slack_drafts.FOOTER


def test_a_draft_shown_is_offered_buttons_and_one_only_named_is_not():
    short, long = waiting_draft("Short", "Sow in March."), waiting_draft("Long", "word " * 20000)

    text, shown = slack_drafts.compose("ok", [short, long])

    assert shown == [short] and "Too long to show here" in text


def test_a_draft_that_cannot_be_shown_is_named_and_not_offered_buttons():
    text, shown = slack_drafts.compose("r" * 39_500, [waiting_draft("Big", "Some words " * 300)])

    assert shown == [] and "Too long to show here" in text and "Big" in text


def test_a_reply_that_proposed_nothing_is_offered_no_buttons():
    assert slack_drafts.compose("Just talking.", []) == ("Just talking.", [])


def test_the_footer_promises_buttons_only_when_a_draft_is_shown():
    short, long = waiting_draft("Short", "Sow in March."), waiting_draft("Long", "word " * 20000)

    assert slack_drafts.compose("ok", [short, long])[0].endswith(slack_drafts.FOOTER)
    assert slack_drafts.compose("ok", [long])[0].endswith(slack_drafts.FOOTER_WEB)
    assert slack_drafts.compose("r" * 39_500, [waiting_draft("Big", "Some words " * 300)])[0].endswith(slack_drafts.FOOTER_WEB)
    assert "buttons" not in slack_drafts.FOOTER_WEB and "web app" in slack_drafts.FOOTER_WEB


def test_the_message_of_buttons_names_the_note_and_its_folder_and_has_an_accept_and_a_decline():
    shown = slack_drafts.prompt(waiting_draft(folder="Projects/Garden"))

    assert shown["text"] == "Save *Seeds* to Projects/Garden?"
    section, actions = shown["blocks"]
    assert section == {"type": "section", "text": {"type": "mrkdwn", "text": shown["text"]}}
    accept, decline = actions["elements"]
    assert (accept["action_id"], accept["text"]["text"], accept["style"]) == (slack_drafts.ACCEPT, "Accept", "primary")
    assert (decline["action_id"], decline["text"]["text"], "style" in decline) == (slack_drafts.DECLINE, "Decline", False)
    assert actions["type"] == "actions" and accept["type"] == decline["type"] == "button"


def test_the_buttons_carry_the_path_and_the_id_and_nothing_of_the_text():
    import json

    accept, decline = slack_drafts.prompt(waiting_draft(text="A secret sentence.", path="new/q9", id="p7"))["blocks"][1]["elements"]

    assert json.loads(accept["value"]) == ["new/q9", "p7"] == json.loads(decline["value"])
    assert "secret" not in accept["value"]


def test_a_draft_with_no_folder_is_asked_without_one():
    assert slack_drafts.prompt(waiting_draft(folder=None))["text"] == "Save *Seeds*?"


def test_a_title_cannot_start_formatting_in_the_question():
    assert slack_drafts.prompt(waiting_draft("a*b_c", folder="x_y"))["text"] == "Save *abc* to xy?"


def test_what_replaces_the_buttons_is_one_line_with_no_buttons():
    assert slack_drafts.outcome("Done.") == {"text": "Done.", "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Done."}}]}


def test_the_line_for_a_saved_note_names_it_and_its_path_escaped():
    assert slack_drafts.saved("Seeds", "Inbox/Seeds.md") == "Saved *Seeds* as `Inbox/Seeds.md`."
    assert slack_drafts.saved("a*b", "Inbox/R&D <1>`x`.md") == "Saved *ab* as `Inbox/R&amp;D &lt;1&gt;'x'.md`."


def test_the_line_for_a_declined_note_says_nothing_was_saved():
    assert slack_drafts.declined("Seeds") == "Declined *Seeds*; nothing was saved."
