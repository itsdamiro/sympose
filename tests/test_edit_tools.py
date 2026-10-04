"""The persona's edit tool in its two shapes, one parser (docs/decisions/072): a tool call for a model that can call
tools, a marked block in the reply for one that cannot. Both end in `note_changes`, which refuses a passage not found
exactly once. Nothing here writes the vault."""

import json

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


def test_the_tools_are_the_pair_and_the_descriptions_carry_no_marker_text():
    names = [t["function"]["name"] for t in et.TOOLS]

    assert names == ["propose_edit", "propose_note"]
    assert "<!--" not in json.dumps(et.TOOLS)
