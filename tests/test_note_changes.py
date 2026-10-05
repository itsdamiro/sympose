"""The per-note store of a persona's proposals and annotations (docs/decisions/070): one JSON file per note in the
persona's own folder, never in the vault; a proposal anchored by the passage it quoted; statuses worked out from the
note's current text, not stored."""

import json
import os
import threading

import pytest

from sympose import note_changes as nc
from sympose import note_changes_store as store
from sympose.persona_files import persona_dir

NOTE = "I run three times a week. The beds are raised.\n\n- Pack charger\n- Phone\n\n- Pack charger\n"
H = "samantha"


def files(handle: str = H) -> list[str]:
    folder = os.path.join(persona_dir(handle), store.NOTES_DIR)
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


def test_a_proposal_is_kept_in_the_persona_folder_not_in_a_vault(tmp_path):
    nc.propose_edit(H, "Garden plan.md", NOTE, find="three times", replace="four times", say="Changed the count.")

    assert len(files()) == 1
    assert files()[0].endswith(".json")
    assert not os.path.exists(tmp_path / "Garden plan.md")


def test_the_entry_holds_the_path_the_passage_and_what_replaces_it():
    nc.propose_edit(H, "Garden plan.md", NOTE, find="three times", replace="four times", say="Changed the count.")

    entry = store.read(H, "Garden plan.md")

    assert entry["path"] == "Garden plan.md"
    (p,) = entry["proposals"]
    assert (p["kind"], p["find"], p["replace"], p["say"]) == ("edit", "three times", "four times", "Changed the count.")
    assert p["before"] == "I run " and p["after"].startswith(" a week")
    assert p["id"] and p["time"]


def test_a_passage_not_in_the_note_cannot_be_proposed():
    with pytest.raises(nc.CannotAnchor, match="not in the note"):
        nc.propose_edit(H, "n.md", NOTE, find="nowhere", replace="x", say="")
    assert files() == []


def test_a_passage_that_occurs_twice_cannot_be_proposed_without_telling_them_apart():
    with pytest.raises(nc.CannotAnchor, match="more than once"):
        nc.propose_edit(H, "n.md", NOTE, find="- Pack charger", replace="x", say="")


def test_a_longer_passage_that_is_unique_can_be_proposed():
    nc.propose_edit(H, "n.md", NOTE, find="- Pack charger\n- Phone", replace="- Phone", say="")

    assert len(store.read(H, "n.md")["proposals"]) == 1


def test_a_proposal_is_pending_while_its_passage_is_there_once_and_outdated_when_not():
    p = nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="")

    assert nc.status(p, NOTE) == nc.PENDING
    assert nc.status(p, "XX " + NOTE) == nc.PENDING
    assert nc.status(p, NOTE.replace("three times", "five times")) == nc.OUTDATED


def test_a_proposal_stays_pending_when_the_same_words_turn_up_elsewhere_but_its_own_surroundings_still_fit():
    p = nc.propose_edit(H, "n.md", NOTE, find="beds", replace="plots", say="")

    assert nc.status(p, NOTE + "More beds here.\n") == nc.PENDING


def test_a_proposal_whose_passage_became_ambiguous_is_outdated_not_guessed():
    p = nc.propose_edit(H, "n.md", NOTE, find="beds", replace="plots", say="")

    assert nc.status(p, NOTE + NOTE) == nc.OUTDATED


def test_a_comment_can_be_placed_on_one_of_two_identical_passages_by_where_it_starts():
    start = NOTE.rindex("- Pack charger")

    a = nc.annotate(H, "n.md", NOTE, quote="- Pack charger", text="this one", author="user", start=start)

    assert nc.annotation_status(a, NOTE) == nc.ATTACHED
    with pytest.raises(nc.CannotAnchor):
        nc.annotate(H, "n.md", NOTE, quote="- Pack charger", text="which?", author="user")
    with pytest.raises(nc.CannotAnchor):
        nc.annotate(H, "n.md", NOTE, quote="- Phone", text="wrong place", author="user", start=0)


def test_a_new_note_is_a_proposal_that_is_always_pending():
    p = nc.propose_create(H, "Compost.md", "# Compost\n\nIn autumn.\n", say="A new note.")

    assert (p["kind"], p["text"]) == ("create", "# Compost\n\nIn autumn.\n")
    assert nc.status(p, "") == nc.PENDING


def test_a_working_name_for_a_new_note_is_her_title_else_the_first_heading_else_the_first_five_words():
    assert nc.working_name("# Compost heap plan\n\nbody", title="Soil notes") == "Soil notes"
    assert nc.working_name("intro\n\n# Compost heap plan\n\nbody") == "Compost heap plan"
    assert nc.working_name("The soil needs compost in the autumn and spring.") == "The soil needs compost in"
    assert nc.working_name("   \n") == "Untitled"


def test_an_annotation_remembers_its_passage_and_who_wrote_it():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="why raised?", author="user")

    assert (a["quote"], a["text"], a["author"], a["state"]) == ("raised", "why raised?", "user", "open")
    assert a["before"].endswith("are ")
    assert nc.annotation_status(a, NOTE) == nc.ATTACHED
    assert nc.annotation_status(a, NOTE.replace("raised", "sunken")) == nc.DETACHED


def test_a_reply_points_at_the_comment_it_answers():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="why raised?", author="user")

    r = nc.annotate(H, "n.md", NOTE, quote="raised", text="Drainage.", author="persona", reply_to=a["id"])

    assert r["reply_to"] == a["id"] and r["author"] == "persona"


def test_a_comment_can_be_resolved_and_reopened_and_deleted():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")

    nc.set_annotation_state(H, "n.md", a["id"], "resolved")
    assert store.read(H, "n.md")["annotations"][0]["state"] == "resolved"
    nc.set_annotation_state(H, "n.md", a["id"], "open")
    assert store.read(H, "n.md")["annotations"][0]["state"] == "open"
    nc.delete_annotation(H, "n.md", a["id"])
    assert files() == []


def test_a_state_other_than_open_or_resolved_is_refused():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")

    with pytest.raises(ValueError):
        nc.set_annotation_state(H, "n.md", a["id"], "pending")


def test_an_unknown_comment_is_an_error_not_a_silent_no_op():
    nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")

    with pytest.raises(KeyError):
        nc.set_annotation_state(H, "n.md", "nope", "resolved")


def test_declining_a_proposal_removes_it_and_the_file_goes_when_nothing_is_left():
    p = nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="")

    nc.discard_proposal(H, "n.md", p["id"])

    assert files() == []


def test_declining_one_of_two_keeps_the_other_and_the_comment():
    p1 = nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="")
    p2 = nc.propose_edit(H, "n.md", NOTE, find="raised", replace="sunken", say="")
    nc.annotate(H, "n.md", NOTE, quote="beds", text="q", author="user")

    nc.discard_proposal(H, "n.md", p1["id"])

    entry = store.read(H, "n.md")
    assert [p["id"] for p in entry["proposals"]] == [p2["id"]]
    assert len(entry["annotations"]) == 1


def test_drafts_list_notes_with_a_proposal_waiting_or_an_open_comment_with_both_counts():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit(H, "a.md", NOTE, find="raised", replace="sunken", say="")
    nc.propose_create(H, "New.md", "# New\n", say="")
    nc.annotate(H, "only-comments.md", NOTE, quote="raised", text="q", author="user")
    nc.annotate(H, "a.md", NOTE, quote="three", text="why?", author="persona")

    drafts = {d["path"]: d for d in nc.drafts(H)}

    assert set(drafts) == {"a.md", "New.md", "only-comments.md"}
    assert (drafts["a.md"]["count"], drafts["a.md"]["comments"], drafts["a.md"]["is_new"]) == (2, 1, False)
    assert (drafts["New.md"]["count"], drafts["New.md"]["comments"], drafts["New.md"]["is_new"]) == (1, 0, True)
    assert (drafts["only-comments.md"]["count"], drafts["only-comments.md"]["comments"]) == (0, 1)
    assert drafts["a.md"]["time"] and drafts["only-comments.md"]["time"]


def test_a_resolved_comment_does_not_list_a_note_and_answers_are_not_counted():
    root = nc.annotate(H, "a.md", NOTE, quote="raised", text="q", author="user")
    nc.reply(H, "a.md", root["id"], text="because", author="persona")
    assert [(d["path"], d["comments"]) for d in nc.drafts(H)] == [("a.md", 1)]

    nc.set_annotation_state(H, "a.md", root["id"], nc.RESOLVED)

    assert nc.drafts(H) == []


def test_a_note_with_comments_is_listed_by_the_latest_of_its_proposals_and_open_comments(monkeypatch):
    times = iter(["2026-10-04T10:00:00+00:00", "2026-10-04T12:00:00+00:00", "2026-10-04T11:00:00+00:00"])
    monkeypatch.setattr(nc, "_now", lambda: next(times))
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")
    nc.annotate(H, "b.md", NOTE, quote="raised", text="q", author="user")
    nc.annotate(H, "a.md", NOTE, quote="raised", text="q", author="user")

    drafts = nc.drafts(H)

    assert [d["path"] for d in drafts] == ["b.md", "a.md"]
    assert drafts[1]["time"] == "2026-10-04T11:00:00+00:00"


def test_each_persona_has_its_own_drafts_for_the_same_note():
    nc.propose_edit("samantha", "a.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("grace", "a.md", NOTE, find="raised", replace="sunken", say="")

    assert [p["find"] for p in store.read("samantha", "a.md")["proposals"]] == ["three times"]
    assert [p["find"] for p in store.read("grace", "a.md")["proposals"]] == ["raised"]
    assert [d["path"] for d in nc.drafts("samantha")] == ["a.md"]


def test_a_rename_carries_the_entry_to_the_new_path():
    nc.propose_edit(H, "old.md", NOTE, find="three times", replace="four times", say="")

    nc.rename(H, "old.md", "Sub/new.md")

    assert store.read(H, "old.md")["proposals"] == []
    entry = store.read(H, "Sub/new.md")
    assert entry["path"] == "Sub/new.md" and len(entry["proposals"]) == 1
    assert len(files()) == 1


def test_a_rename_of_a_note_with_no_entry_is_a_quiet_no_op():
    nc.rename(H, "none.md", "other.md")

    assert files() == []


def test_forgetting_a_note_removes_its_entry():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")

    nc.forget(H, "a.md")

    assert files() == []


def test_a_path_with_folders_stays_one_file_inside_the_notes_folder():
    nc.propose_edit(H, "Sub folder/Deeper/x.md", NOTE, find="three times", replace="four times", say="")

    assert len(files()) == 1
    assert store.read(H, "Sub folder/Deeper/x.md")["path"] == "Sub folder/Deeper/x.md"


@pytest.mark.parametrize("escaping", ["../x.md", "../../etc/passwd", "/abs/x.md", "A/../../x.md", "", "   ", ".", ".md", "A/.md", '""', "Garden plan.md/"])
def test_a_path_that_leaves_the_vault_or_names_no_note_is_refused_and_nothing_is_stored(escaping):
    with pytest.raises(ValueError):
        nc.propose_create(H, escaping, "# x\n", say="")

    assert files() == []


@pytest.mark.parametrize("form", ["Garden plan.md", "Garden plan", " Garden plan.md ", '"Garden plan"', "'Garden plan.md'", "./Garden plan.md", "Sub/../Garden plan.md"])
def test_every_way_of_writing_a_notes_path_is_the_same_entry(form):
    nc.propose_edit(H, "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    assert store.key(form) == "Garden plan.md"
    assert [p["find"] for p in store.read(H, form)["proposals"]] == ["three times"]
    assert len(files()) == 1


def test_a_proposal_written_one_way_and_a_comment_written_another_share_one_entry():
    nc.propose_edit(H, "Sub/Note", NOTE, find="three times", replace="four times", say="")
    nc.annotate(H, "./Sub/Note.md", NOTE, quote="raised", text="q", author="user")

    entry = store.read(H, "Sub/Note.md")

    assert len(files()) == 1 and entry["path"] == "Sub/Note.md"
    assert len(entry["proposals"]) == 1 and len(entry["annotations"]) == 1


def test_renaming_and_forgetting_work_whichever_form_names_the_note():
    nc.propose_edit(H, "old.md", NOTE, find="three times", replace="four times", say="")

    nc.rename(H, "old", "Sub/new")
    assert [d["path"] for d in nc.drafts(H)] == ["Sub/new.md"]

    nc.forget(H, "./Sub/new.md")
    assert files() == []


def test_a_name_with_dots_inside_it_keeps_them():
    assert store.key("v1.2 plan") == "v1.2 plan.md"
    assert store.key("notes/2026.10.04.md") == "notes/2026.10.04.md"


def test_a_very_long_path_still_gets_a_usable_file_name():
    long_path = "Folder/" + "a long note name " * 40 + ".md"

    nc.propose_edit(H, long_path, NOTE, find="three times", replace="four times", say="")

    assert len(files()[0]) < 200
    assert store.read(H, long_path)["path"] == long_path


def test_a_damaged_file_reads_as_empty_not_as_an_error():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")
    folder = os.path.join(persona_dir(H), store.NOTES_DIR)
    with open(os.path.join(folder, files()[0]), "w") as f:
        f.write("{ not json")

    assert store.read(H, "a.md")["proposals"] == []
    assert nc.drafts(H) == []


def test_two_proposals_added_at_the_same_moment_are_both_kept():
    n = 20
    barrier = threading.Barrier(n)

    def add(i: int) -> None:
        barrier.wait()
        nc.propose_create(H, "same.md", f"# {i}\n", say="")

    threads = [threading.Thread(target=add, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(store.read(H, "same.md")["proposals"]) == n


def test_the_file_is_plain_readable_json_with_a_version():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")
    folder = os.path.join(persona_dir(H), store.NOTES_DIR)

    with open(os.path.join(folder, files()[0]), encoding="utf-8") as f:
        raw = json.load(f)

    assert raw["version"] == 1 and raw["path"] == "a.md"


def test_two_paths_that_differ_only_by_a_slash_do_not_share_a_file():
    nc.propose_edit(H, "a/b.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit(H, "a_b.md", NOTE, find="raised", replace="sunken", say="")

    assert len(files()) == 2
    assert [p["find"] for p in store.read(H, "a/b.md")["proposals"]] == ["three times"]


def test_an_empty_path_is_refused_not_stored_under_a_nameless_file():
    with pytest.raises(ValueError):
        nc.propose_create(H, "", "# x\n", say="")


@pytest.mark.parametrize("junk", ["[]", '"text"', "null", '{"proposals": "oops", "annotations": {"a": 1}}', '{"proposals": [1, "x", {"id": "k"}]}', '{"proposals": null, "annotations": 5}'])
def test_a_file_of_the_wrong_shape_reads_as_an_empty_entry_with_only_real_items(junk):
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")
    folder = os.path.join(persona_dir(H), store.NOTES_DIR)
    with open(os.path.join(folder, files()[0]), "w") as f:
        f.write(junk)

    entry = store.read(H, "a.md")

    assert entry["annotations"] == []
    assert entry["proposals"] in ([], [{"id": "k"}])
    assert store.entries(H) in ([], [{"version": 1, "path": "a.md", "proposals": [{"id": "k"}], "annotations": []}])


def test_a_damaged_file_is_not_listed_among_the_entries():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")
    folder = os.path.join(persona_dir(H), store.NOTES_DIR)
    with open(os.path.join(folder, files()[0]), "w") as f:
        f.write("{ not json")

    assert store.entries(H) == []


def test_renaming_a_note_onto_its_own_path_changes_nothing():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")

    nc.rename(H, "a.md", "a.md")

    assert len(store.read(H, "a.md")["proposals"]) == 1


def test_a_rename_carries_comments_as_well_as_proposals_and_joins_what_is_already_there():
    nc.annotate(H, "old.md", NOTE, quote="raised", text="q", author="user")
    nc.propose_edit(H, "new.md", NOTE, find="three times", replace="four times", say="")

    nc.rename(H, "old.md", "new.md")

    entry = store.read(H, "new.md")
    assert len(entry["annotations"]) == 1 and len(entry["proposals"]) == 1
    assert store.read(H, "old.md")["annotations"] == []


def test_a_change_that_fails_saves_nothing():
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")

    def broken(entry):
        entry["proposals"].clear()
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        store.update(H, "a.md", broken)

    assert len(store.read(H, "a.md")["proposals"]) == 1


def test_deleting_a_comment_deletes_the_replies_to_it_and_nothing_else():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")
    nc.annotate(H, "n.md", NOTE, quote="raised", text="reply", author="persona", reply_to=a["id"])
    other = nc.annotate(H, "n.md", NOTE, quote="beds", text="other", author="user")

    nc.delete_annotation(H, "n.md", a["id"])

    assert [x["id"] for x in store.read(H, "n.md")["annotations"]] == [other["id"]]


def test_an_unknown_id_is_an_error_when_deleting_or_declining():
    nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="")
    nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")

    with pytest.raises(KeyError):
        nc.discard_proposal(H, "n.md", "nope")
    with pytest.raises(KeyError):
        nc.delete_annotation(H, "n.md", "nope")
    assert len(store.read(H, "n.md")["proposals"]) == 1 and len(store.read(H, "n.md")["annotations"]) == 1


def test_an_empty_quote_is_refused_even_at_a_given_place():
    with pytest.raises(nc.CannotAnchor):
        nc.annotate(H, "n.md", NOTE, quote="", text="q", author="user", start=3)


def test_drafts_come_newest_first_and_carry_the_time_of_the_latest_proposal(monkeypatch):
    times = iter(["2026-10-04T10:00:00+00:00", "2026-10-04T12:00:00+00:00", "2026-10-04T11:00:00+00:00"])
    monkeypatch.setattr(nc, "_now", lambda: next(times))
    nc.propose_edit(H, "old.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit(H, "newer.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit(H, "old.md", NOTE, find="raised", replace="sunken", say="")

    drafts = nc.drafts(H)

    assert [d["path"] for d in drafts] == ["newer.md", "old.md"]
    assert drafts[1]["time"] == "2026-10-04T11:00:00+00:00"


def test_a_new_note_in_the_drafts_carries_its_working_name():
    nc.propose_create(H, "New.md", "# Compost heap plan\n\nbody\n", say="")
    nc.propose_edit(H, "a.md", NOTE, find="three times", replace="four times", say="")

    drafts = {d["path"]: d for d in nc.drafts(H)}

    assert drafts["New.md"]["name"] == "Compost heap plan" and drafts["a.md"]["name"] is None


def test_a_comment_changes_its_text_and_state_together_or_not_at_all():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="keep", author="user")

    nc.change_annotation(H, "n.md", a["id"], text="new", state="resolved")
    assert (store.read(H, "n.md")["annotations"][0]["text"], store.read(H, "n.md")["annotations"][0]["state"]) == ("new", "resolved")

    with pytest.raises(ValueError):
        nc.change_annotation(H, "n.md", a["id"], text="lost", state="pending")
    assert store.read(H, "n.md")["annotations"][0]["text"] == "new"


def test_changing_only_the_text_leaves_the_state_and_changing_nothing_is_allowed():
    a = nc.annotate(H, "n.md", NOTE, quote="raised", text="keep", author="user")
    nc.set_annotation_state(H, "n.md", a["id"], "resolved")

    nc.change_annotation(H, "n.md", a["id"], text="edited")
    nc.change_annotation(H, "n.md", a["id"])

    stored = store.read(H, "n.md")["annotations"][0]
    assert (stored["text"], stored["state"]) == ("edited", "resolved")


def test_reading_a_note_with_no_entry_reports_the_canonical_path_whatever_was_asked():
    assert store.read(H, "Nope")["path"] == "Nope.md"
    assert store.read(H, " ./Sub/Nope ")["path"] == "Sub/Nope.md"


def test_a_comment_given_its_own_context_keeps_it_and_needs_no_passage_on_disk():
    a = nc.annotate(H, "n.md", "nothing here", quote="the unsaved words", text="q", author="user", context=("typed just ", " now"))

    assert (a["before"], a["after"], a["quote"]) == ("typed just ", " now", "the unsaved words")
    assert store.read(H, "n.md")["annotations"][0]["before"] == "typed just "


def test_a_comment_with_no_passage_is_refused_even_with_context():
    with pytest.raises(nc.CannotAnchor):
        nc.annotate(H, "n.md", NOTE, quote="", text="q", author="user", context=("a", "b"))
    assert files() == []


def test_a_reply_is_about_the_same_passage_as_the_comment_it_answers():
    root = nc.annotate(H, "n.md", NOTE, quote="raised", text="why raised?", author="user")

    answer = nc.reply(H, "n.md", root["id"], text="Drainage.", author="persona")

    assert (answer["reply_to"], answer["quote"], answer["before"], answer["after"], answer["author"], answer["state"]) == (
        root["id"], "raised", root["before"], root["after"], "persona", "open")


def test_a_reply_to_a_reply_goes_under_the_comment_it_is_in():
    root = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")
    first = nc.reply(H, "n.md", root["id"], text="a", author="persona")

    second = nc.reply(H, "n.md", first["id"], text="b", author="user")

    assert second["reply_to"] == root["id"]


def test_a_reply_to_an_unknown_comment_is_an_error_and_saves_nothing():
    nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")

    with pytest.raises(KeyError):
        nc.reply(H, "n.md", "nope", text="a", author="persona")
    assert len(store.read(H, "n.md")["annotations"]) == 1


def test_a_reply_to_a_resolved_comment_is_resolved_too():
    root = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")
    nc.set_annotation_state(H, "n.md", root["id"], "resolved")

    assert nc.reply(H, "n.md", root["id"], text="late", author="persona")["state"] == "resolved"


def test_resolving_or_reopening_a_comment_does_the_same_to_the_answers_under_it_and_to_nothing_else():
    root = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")
    answer = nc.reply(H, "n.md", root["id"], text="a", author="persona")
    other = nc.annotate(H, "n.md", NOTE, quote="beds", text="o", author="user")

    nc.set_annotation_state(H, "n.md", root["id"], "resolved")
    states = {x["id"]: x["state"] for x in store.read(H, "n.md")["annotations"]}
    assert states == {root["id"]: "resolved", answer["id"]: "resolved", other["id"]: "open"}

    nc.set_annotation_state(H, "n.md", root["id"], "open")
    assert {x["state"] for x in store.read(H, "n.md")["annotations"]} == {"open"}


def test_resolving_one_answer_leaves_the_comment_it_is_under_open():
    root = nc.annotate(H, "n.md", NOTE, quote="raised", text="q", author="user")
    answer = nc.reply(H, "n.md", root["id"], text="a", author="persona")

    nc.set_annotation_state(H, "n.md", answer["id"], "resolved")

    states = {x["id"]: x["state"] for x in store.read(H, "n.md")["annotations"]}
    assert states == {root["id"]: "open", answer["id"]: "resolved"}


def test_a_second_proposal_on_the_same_passage_is_refused_and_the_first_stays():
    nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="a")

    with pytest.raises(nc.CannotAnchor, match="already waiting"):
        nc.propose_edit(H, "n.md", NOTE, find="three times", replace="five times", say="b")

    (p,) = store.read(H, "n.md")["proposals"]
    assert p["replace"] == "four times"


def test_a_proposal_that_overlaps_a_waiting_one_is_refused():
    nc.propose_edit(H, "n.md", NOTE, find="run three times", replace="walk", say="a")

    with pytest.raises(nc.CannotAnchor, match="already waiting"):
        nc.propose_edit(H, "n.md", NOTE, find="three times a week", replace="daily", say="b")


def test_a_proposal_beside_a_waiting_one_is_kept_too():
    nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="a")
    nc.propose_edit(H, "n.md", NOTE, find="The beds are raised.", replace="The beds are low.", say="b")

    assert len(store.read(H, "n.md")["proposals"]) == 2


def test_an_outdated_proposal_does_not_block_a_new_one_on_that_passage():
    nc.propose_edit(H, "n.md", NOTE, find="three times", replace="four times", say="a")
    rewritten = NOTE.replace("three times", "often")

    nc.propose_edit(H, "n.md", rewritten, find="often", replace="daily", say="b")

    assert len(store.read(H, "n.md")["proposals"]) == 2
