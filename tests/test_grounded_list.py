"""`/grounded`'s rendering of the last turn's `sent` record (docs/decisions/025, #26)."""

from sympose.cli import grounded_list


def _sent(**over):
    base = {"notes": [], "recaps": [], "searched": None, "history_dropped": 0, "rewrite": False}
    return {**base, **over}


def test_no_reply_yet_this_session():
    assert grounded_list.render(None) == ["No reply yet this session to show what grounded it."]


def test_a_turn_with_nothing_attached():
    assert grounded_list.render(_sent()) == ["Nothing from the vault grounded the last reply."]


def test_a_note_found_by_meaning_shows_its_similarity():
    sent = _sent(notes=[{"path": "Atlas.md", "heading": "", "source": "vault", "via": "embedding", "similarity": 0.81}])
    assert grounded_list.render(sent) == ["Grounded the last reply:", "  1. Atlas.md (by meaning, similarity 0.81)"]


def test_a_note_named_in_full_has_no_similarity_to_show():
    sent = _sent(notes=[{"path": "Atlas.md", "heading": "", "source": "vault", "via": "name"}])
    assert grounded_list.render(sent) == ["Grounded the last reply:", "  1. Atlas.md (named in full)"]


def test_a_plain_keyword_hit_names_only_the_note():
    sent = _sent(notes=[{"path": "Atlas.md", "heading": "Plans", "source": "vault"}])
    assert grounded_list.render(sent) == ["Grounded the last reply:", "  1. Atlas.md — Plans"]


def test_a_reference_library_note_says_so():
    sent = _sent(notes=[{"path": "Sympose reference/Not built yet.md", "heading": "Memory", "source": "sympose"}])
    assert grounded_list.render(sent)[1] == "  1. Sympose reference/Not built yet.md — Memory (the Sympose reference library)"


def test_recaps_a_rewrite_dropped_turns_and_cloud_categories_each_get_their_own_line():
    sent = _sent(
        recaps=["20260101T000000-aaaaaaaa", "20260102T000000-bbbbbbbb"],
        searched="why we picked SQLite",
        history_dropped=3,
        cloud=["notes", "recaps"],
        withheld=["properties"],
    )
    lines = grounded_list.render(sent)
    assert "Also sent: 2 earlier-conversation recaps." in lines
    assert 'A follow-up rewrite searched: "why we picked SQLite".' in lines
    assert "3 older turns left out of context." in lines
    assert "Sent to the cloud model: notes, recaps." in lines
    assert "Held back from it: properties." in lines


def test_one_recap_and_one_dropped_turn_are_singular():
    sent = _sent(recaps=["20260101T000000-aaaaaaaa"], history_dropped=1)
    lines = grounded_list.render(sent)
    assert "Also sent: 1 earlier-conversation recap." in lines
    assert "1 older turn left out of context." in lines


def test_recaps_alone_with_no_notes_still_render():
    sent = _sent(recaps=["20260101T000000-aaaaaaaa"])
    assert grounded_list.render(sent) == ["Also sent: 1 earlier-conversation recap."]


# -- what the persona looked up herself (docs/decisions/040) --

_SENT = {"notes": [], "recaps": [], "searched": None, "history_dropped": 0}


def test_lookups_are_listed_as_they_were_made_and_notes_they_found_say_who_found_them():
    sent = {
        **_SENT,
        "mode": "ask",
        "notes": [
            {"path": "Projects/Atlas.md", "heading": "", "source": "vault", "via": "search"},
            {"path": "Projects/Atlas.md", "heading": "", "source": "vault", "via": "opened"},
        ],
        "lookups": [
            {"tool": "search_notes", "query": "Atlas database", "found": 1},
            {"tool": "open_note", "path": "Projects/Atlas.md", "found": 1},
        ],
    }

    lines = grounded_list.render(sent)

    assert "  1. Projects/Atlas.md (found by her search)" in lines
    assert "  2. Projects/Atlas.md (opened by her)" in lines
    assert 'She looked up: searched "Atlas database" (1 found); opened "Projects/Atlas.md" (1 found).' in lines


def test_a_lookup_that_found_nothing_is_still_shown_when_nothing_grounded_the_reply():
    sent = {**_SENT, "mode": "ask", "lookups": [{"tool": "search_notes", "query": "tax deadline", "found": 0}]}

    assert grounded_list.render(sent) == [
        "Nothing from the vault grounded the last reply.",
        'She looked up: searched "tax deadline" (0 found).',
    ]


def test_ask_with_no_lookup_says_she_looked_nothing_up():
    lines = grounded_list.render({**_SENT, "mode": "ask", "lookups": []})

    assert lines[-1] == "She looked nothing up for this message."


def test_ask_that_ran_as_auto_says_why_the_search_happened():
    lines = grounded_list.render({**_SENT, "mode": "auto", "lookups": []})

    assert lines[-1] == "You chose ask, but this model can't call tools, so Sympose searched for the message."


def test_without_the_setting_nothing_is_said_about_lookups():
    assert grounded_list.render(_SENT) == ["Nothing from the vault grounded the last reply."]
