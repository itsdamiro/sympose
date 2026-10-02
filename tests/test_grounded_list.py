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

    assert "  1. Projects/Atlas.md (found by the persona's search)" in lines
    assert "  2. Projects/Atlas.md (opened by the persona)" in lines
    assert 'The persona looked up: searched "Atlas database" (1 found); opened "Projects/Atlas.md" (1 found).' in lines


def test_a_lookup_that_found_nothing_is_still_shown_when_nothing_grounded_the_reply():
    sent = {**_SENT, "mode": "ask", "lookups": [{"tool": "search_notes", "query": "tax deadline", "found": 0}]}

    assert grounded_list.render(sent) == [
        "Nothing from the vault grounded the last reply.",
        'The persona looked up: searched "tax deadline" (0 found).',
    ]


def test_ask_with_no_lookup_says_nothing_was_looked_up():
    lines = grounded_list.render({**_SENT, "mode": "ask", "lookups": []})

    assert lines[-1] == "The persona looked nothing up for this message."


def test_ask_that_ran_as_auto_says_why_the_search_happened():
    lines = grounded_list.render({**_SENT, "mode": "auto", "lookups": []})

    assert lines[-1] == "You chose ask, but this model can't call tools, so Sympose searched for the message."


def test_without_the_setting_nothing_is_said_about_lookups():
    assert grounded_list.render(_SENT) == ["Nothing from the vault grounded the last reply."]


def test_the_persona_is_named_not_called_she():
    sent = _sent(mode="ask", lookups=[])
    assert grounded_list.render(sent, "Aria")[-1] == "Aria looked nothing up for this message."


def test_a_remember_call_is_said_plainly_and_never_printed_as_a_query():
    saved = grounded_list.render(_sent(lookups=[{"tool": "remember", "saved": True}]), "Aria")
    failed = grounded_list.render(_sent(lookups=[{"tool": "remember", "saved": False}]), "Aria")
    assert saved[-1] == "Aria remembered something."
    assert failed[-1] == "Aria tried to remember something and could not save it."
    assert not any("None" in line for line in saved + failed)


def test_a_reply_grounded_only_in_memory_says_which_memory_files_reached_it():
    lines = grounded_list.render(_sent(memory=["profile", "decisions"]))
    assert lines == ["Nothing from the vault grounded the last reply.", "Also sent: the persona's memory (profile.md, decisions.md)."]
    with_notes = grounded_list.render(_sent(notes=[{"path": "A.md", "heading": "", "source": "vault"}], memory=["context"]))
    assert "Also sent: the persona's memory (context.md)." in with_notes
    assert grounded_list.render(_sent(memory=[])) == ["Nothing from the vault grounded the last reply."]


def test_a_search_and_a_remember_in_one_turn_each_get_their_line():
    sent = _sent(mode="ask", lookups=[{"tool": "search_notes", "query": "x", "found": 2}, {"tool": "remember", "saved": True}])
    assert grounded_list.render(sent, "Aria")[-2:] == ['Aria looked up: searched "x" (2 found).', "Aria remembered something."]


def test_earlier_conversation_exchanges_get_a_line_even_when_nothing_else_was_sent():
    chat = {"session": "20260923T090000-bbbbbbbb", "turn": 2, "how": "auto"}

    assert grounded_list.render(_sent(chats=[chat]))[-1] == (
        "Also sent: 1 exchange from earlier conversations, word for word."
    )
    assert "Also sent: 2 exchanges from" in grounded_list.render(_sent(chats=[chat, chat]))[-1]
    assert grounded_list.render(_sent()) == ["Nothing from the vault grounded the last reply."]
