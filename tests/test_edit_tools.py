"""The persona's edit tool in its two shapes, one parser (docs/decisions/072): a tool call for a model that can call
tools, a marked block in the reply for one that cannot. Both end in `note_changes`, which refuses a passage not found
exactly once. Nothing here writes the vault."""

import json

import pytest

from sympose import note_changes as nc
from sympose import note_changes_store as store
from sympose.engine import edit_tools as et

H = "samantha"
PATH = "Garden plan.md"
NOTE = "I run three times a week.\n\n- Pack charger\n- Phone\n\n- Pack charger\n"


def marker(**fields) -> str:
    return f"<!-- propose_edit: {json.dumps(fields)} -->"


def proposals() -> list[dict]:
    return store.read(H, PATH)["proposals"] if store.read(H, PATH) else []


def test_a_marker_becomes_a_proposal_and_leaves_the_reply():
    reply = "I will change the count.\n" + marker(find="three times", replace="four times", say="Changed the count.")

    shown, records = et.apply_marker(H, PATH, NOTE, reply)

    assert shown == "I will change the count."
    (p,) = proposals()
    assert (p["find"], p["replace"], p["say"]) == ("three times", "four times", "Changed the count.")
    assert records == [{"tool": "propose_edit", "saved": True}]


def test_a_reply_with_no_marker_is_returned_exactly_as_given():
    reply = "The beds hold carrots.\n\n\n\nAnd leeks."

    assert et.apply_marker(H, PATH, NOTE, reply) == (reply, [])
    assert proposals() == []


def test_several_markers_make_several_proposals():
    reply = marker(find="three times", replace="four times", say="a") + "\n" + marker(find="- Phone", replace="- Phone, keys", say="b")

    _, records = et.apply_marker(H, PATH, NOTE, reply)

    assert len(proposals()) == 2 and [r["saved"] for r in records] == [True, True]


def test_a_passage_found_twice_is_refused_and_the_user_is_told():
    reply = "Done.\n" + marker(find="- Pack charger", replace="- Charger", say="x")

    shown, records = et.apply_marker(H, PATH, NOTE, reply)

    assert proposals() == []
    assert records[0]["saved"] is False and "more than once" in records[0]["reason"]
    assert "could not be placed" in shown and "more than once" in shown


def test_a_marker_that_is_not_valid_json_is_removed_and_reported():
    shown, records = et.apply_marker(H, PATH, NOTE, "Ok.\n<!-- propose_edit: {find: nope} -->")

    assert "<!--" not in shown and "could not be placed" in shown
    assert records[0]["saved"] is False and proposals() == []


def test_a_marker_missing_a_field_is_refused():
    _, records = et.apply_marker(H, PATH, NOTE, marker(find="three times", say="x"))

    assert records[0]["saved"] is False and proposals() == []


def test_a_marker_with_no_open_note_proposes_nothing_and_says_why():
    shown, records = et.apply_marker(H, None, None, marker(find="a", replace="b", say="x"))

    assert records[0]["saved"] is False and "no note is open" in records[0]["reason"].lower()
    assert "could not be placed" in shown


def test_a_marker_for_a_new_note_is_a_draft():
    reply = '<!-- propose_note: {"text": "# Seeds\\n\\nSow in March.", "title": "Seed list", "say": "A new note."} -->'

    shown, records = et.apply_marker(H, None, None, reply)

    assert shown == "A new note."
    (draft,) = nc.drafts(H)
    assert draft["is_new"] and draft["name"] == "Seed list"
    assert records == [{"tool": "propose_note", "saved": True}]


def test_a_marker_only_reply_is_never_blank():
    shown, _ = et.apply_marker(H, PATH, NOTE, marker(find="three times", replace="four times", say="Changed the count."))

    assert shown == "Changed the count."


def test_a_tool_call_makes_the_same_proposal():
    result = et.run(H, PATH, NOTE, "propose_edit", {"find": "three times", "replace": "four times", "say": "s"})

    assert result is not None and result.lookup == {"tool": "propose_edit", "saved": True}
    assert len(proposals()) == 1


def test_a_tool_call_given_arguments_as_json_text_works():
    args = json.dumps({"find": "three times", "replace": "four", "say": "s"})

    assert et.run(H, PATH, NOTE, "propose_edit", args).lookup["saved"] is True


def test_a_tool_call_on_a_passage_found_twice_tells_the_model_why():
    result = et.run(H, PATH, NOTE, "propose_edit", {"find": "- Pack charger", "replace": "x", "say": ""})

    assert result.lookup["saved"] is False and "more than once" in result.text
    assert proposals() == []


def test_a_tool_call_to_propose_a_note_files_a_draft():
    result = et.run(H, None, None, "propose_note", {"text": "# Seeds\n\nSow.", "title": "Seeds", "say": "s"})

    assert result.lookup["saved"] is True and nc.drafts(H)[0]["name"] == "Seeds"


def test_another_tool_name_is_not_ours():
    assert et.run(H, PATH, NOTE, "remember", {"text": "x"}) is None


def test_the_tools_are_named_and_the_descriptions_carry_no_marker_text():
    names = [t["function"]["name"] for t in et.TOOLS]

    assert names == ["propose_edit", "propose_note", "comment_on", "show_note"]
    assert "<!--" not in json.dumps(et.TOOLS)


def comments() -> list[dict]:
    entry = store.read(H, PATH)
    return entry["annotations"] if entry else []


def comment_marker(**fields) -> str:
    return f"<!-- comment_on: {json.dumps(fields)} -->"


def test_a_comment_marker_files_a_comment_of_hers_on_the_passage_and_leaves_the_reply():
    reply = "A thought on the count.\n" + comment_marker(find="three times", text="Is this still true in winter?")

    shown, records = et.apply_marker(H, PATH, NOTE, reply)

    assert shown == "A thought on the count."
    (c,) = comments()
    assert (c["author"], c["quote"], c["text"], c["state"]) == ("persona", "three times", "Is this still true in winter?", "open")
    assert records == [{"tool": "comment_on", "saved": True}] and proposals() == []


def test_her_comment_on_words_the_user_already_commented_on_is_an_answer_under_theirs():
    mine = nc.annotate(H, PATH, NOTE, quote="three times", text="Delete this.", author="user")

    et.run(H, PATH, NOTE, "comment_on", {"find": "three times", "text": "I cannot do that in one change."})

    roots = [c for c in comments() if not c["reply_to"]]
    (answer,) = [c for c in comments() if c["reply_to"]]
    assert [r["id"] for r in roots] == [mine["id"]]
    assert answer["author"] == "persona" and answer["reply_to"] == mine["id"] and answer["text"] == "I cannot do that in one change."


def test_her_comment_on_other_words_is_a_comment_of_its_own():
    nc.annotate(H, PATH, NOTE, quote="three times", text="Delete this.", author="user")

    et.run(H, PATH, NOTE, "comment_on", {"find": "Phone", "text": "A phone?"})

    assert [c["reply_to"] for c in comments()] == [None, None]


def test_her_comment_does_not_go_under_a_resolved_one_on_the_same_words():
    done = nc.annotate(H, PATH, NOTE, quote="three times", text="Old.", author="user")
    nc.set_annotation_state(H, PATH, done["id"], nc.RESOLVED)

    et.run(H, PATH, NOTE, "comment_on", {"find": "three times", "text": "New thought."})

    assert [c["reply_to"] for c in comments()] == [None, None]


def test_a_comment_on_a_passage_found_twice_is_refused_and_told():
    shown, records = et.apply_marker(H, PATH, NOTE, "Hm.\n" + comment_marker(find="- Pack charger", text="Twice?"))

    assert comments() == [] and records[0]["saved"] is False
    assert "could not be placed" in shown and "more than once" in shown


def test_a_comment_with_no_open_note_is_refused():
    _, records = et.apply_marker(H, None, None, comment_marker(find="a", text="b"))

    assert records[0]["saved"] is False and "no note is open" in records[0]["reason"].lower()


def test_a_comment_marker_only_reply_is_never_blank():
    shown, _ = et.apply_marker(H, PATH, NOTE, comment_marker(find="three times", text="Still true?"))

    assert shown == "Commented."


def test_a_comment_missing_its_text_is_refused():
    _, records = et.apply_marker(H, PATH, NOTE, comment_marker(find="three times"))

    assert records[0]["saved"] is False and comments() == []


def test_a_tool_call_comments_the_same_way():
    result = et.run(H, PATH, NOTE, "comment_on", {"find": "three times", "text": "Still true?"})

    assert result.lookup == {"tool": "comment_on", "saved": True} and comments()[0]["author"] == "persona"


def test_a_comment_and_a_change_in_one_reply_are_both_made():
    reply = comment_marker(find="three times", text="Why three?") + "\n" + marker(find="- Phone", replace="- Phone, keys", say="b")

    _, records = et.apply_marker(H, PATH, NOTE, reply)

    assert [r["saved"] for r in records] == [True, True] and len(comments()) == 1 and len(proposals()) == 1


def test_a_new_note_proposed_with_a_folder_keeps_it_and_one_without_does_not():
    et.run(H, None, None, "propose_note", {"text": "# Plan\n", "say": "A plan.", "title": "Plan", "folder": "Projects/Sympose"})
    et.run(H, None, None, "propose_note", {"text": "# Other\n", "say": "Another."})

    folders = sorted((d["name"], d["folder"]) for d in nc.drafts(H))

    assert folders == [("Other", None), ("Plan", "Projects/Sympose")]


def test_the_new_note_tool_offers_a_folder_but_does_not_require_one():
    (tool,) = [t["function"] for t in et.TOOLS if t["function"]["name"] == "propose_note"]

    assert "folder" in tool["parameters"]["properties"] and "folder" not in tool["parameters"]["required"]



# show_note: opening a note for the user writes nothing and names the note's path for the web app to open.


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Projects" / "Atlas.md").write_text("# Atlas\nbody", encoding="utf-8")
    (root / "People").mkdir()
    (root / "People" / "Priya.md").write_text("private", encoding="utf-8")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return {"vault_folders": ["Projects"]}


def test_show_note_names_the_note_by_its_path_or_its_name(vault):
    for given in ("Projects/Atlas.md", "atlas"):
        result = et.run(H, None, None, "show_note", {"path": given}, vault)

        assert result.lookup == {"tool": "show_note", "saved": True, "path": "Projects/Atlas.md"}, given
    assert proposals() == [] and nc.drafts(H) == []


def test_show_note_refuses_a_note_that_is_missing_or_outside_her_folders(vault):
    for given in ("Projects/Nope.md", "People/Priya.md"):
        result = et.run(H, None, None, "show_note", {"path": given}, vault)

        assert result.lookup == {"tool": "show_note", "saved": False}, given
        assert "nothing was opened" in result.text


def test_show_note_with_unreadable_arguments_is_a_result_not_an_error(vault):
    assert et.run(H, None, None, "show_note", {"path": 3}, vault).lookup["saved"] is False
    assert et.run(H, None, None, "show_note", "{not json", vault).lookup["saved"] is False


def test_a_show_note_marker_opens_the_note_and_leaves_the_reply(vault):
    reply = 'Here it is.\n<!-- show_note: {"path": "Projects/Atlas.md"} -->'

    shown, records = et.apply_marker(H, None, None, reply, vault)

    assert shown == "Here it is."
    assert records == [{"tool": "show_note", "saved": True, "path": "Projects/Atlas.md"}]


def test_a_show_note_marker_alone_leaves_a_short_line_and_a_failed_one_says_why(vault):
    shown, _ = et.apply_marker(H, None, None, '<!-- show_note: {"path": "Atlas"} -->', vault)
    assert shown == "Opened."

    shown, records = et.apply_marker(H, None, None, '<!-- show_note: {"path": "Missing"} -->', vault)
    assert records[0]["saved"] is False and "nothing was opened" in shown
