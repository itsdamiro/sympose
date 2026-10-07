"""The pending-changes and annotation routes (docs/decisions/070), through the real app on a scratch vault and a
scratch profiles folder: they list, read and forget, and never write the vault."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import note_changes as nc
from sympose.server import create_app

NOTE = "I run three times a week. The beds are raised.\n\n- Pack charger\n- Phone\n\n- Pack charger\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Garden plan.md").write_text(NOTE)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "grace", "name: Grace\nvault_folders: '*'\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    return TestClient(create_app()), vault


def vault_files(vault) -> dict[str, str]:
    return {name: (vault / name).read_text() for name in sorted(os.listdir(vault))}


def test_reading_the_drafts_or_the_changes_quietly_deletes_the_comments_the_note_no_longer_has(env):
    client, vault = env
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="raised", text="q", author="user")

    def drafts():
        return client.get("/api/vault/drafts", params={"persona": "samantha"}).json()["drafts"]

    def changes():
        return changes_for(client, "Garden plan.md")

    assert [(d["path"], d["comments"]) for d in drafts()] == [("Garden plan.md", 1)]

    (vault / "Garden plan.md").write_text(NOTE.replace("raised", "sunken"))
    os.utime(vault / "Garden plan.md", (4_102_444_800, 4_102_444_800))  # written after the comment
    assert drafts() == []
    assert changes()["annotations"] == []
    assert nc.drafts("samantha") == []  # gone from storage, not only from the answer


def test_accepting_a_change_through_the_route_settles_the_comment_it_answered_and_declining_keeps_it(env):
    client, _ = env
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="three times", text="make this bold", author="user")
    change = nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="**three times**", say="Bold.")
    body = {"path": "Garden plan.md", "persona": "samantha", "ids": [change["id"]]}

    client.post("/api/vault/changes/resolve", json=body)  # declined
    assert [c["author"] for c in changes_for(client, "Garden plan.md")["annotations"] if not c["reply_to"]] == ["user"]

    change = nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="**three times**", say="Bold again.")
    client.post("/api/vault/changes/resolve", json={**body, "ids": [change["id"]], "accepted": True})

    assert changes_for(client, "Garden plan.md")["annotations"] == []


def test_the_drafts_route_counts_the_marks_on_the_note_once_each(env):
    client, _ = env
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="three times", text="make this bold", author="user")
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="**three times**", say="Bold.")
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="raised", text="why?", author="user")

    (draft,) = client.get("/api/vault/drafts", params={"persona": "samantha"}).json()["drafts"]

    assert (draft["count"], draft["comments"], draft["items"]) == (1, 1, 2)


def test_drafts_list_the_notes_with_a_proposal_for_the_asking_persona_only(env):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="Count.")
    nc.propose_create("samantha", "Compost.md", "# Compost\n", say="New.")
    nc.propose_edit("grace", "Garden plan.md", NOTE, find="raised", replace="sunken", say="Other voice.")

    mine = client.get("/api/vault/drafts", params={"persona": "samantha"}).json()["drafts"]
    hers = client.get("/api/vault/drafts", params={"persona": "grace"}).json()["drafts"]

    assert sorted(d["path"] for d in mine) == ["Compost.md", "Garden plan.md"]
    assert [d["path"] for d in hers] == ["Garden plan.md"]


def test_an_unknown_persona_is_404_on_every_route(env):
    client, _ = env
    calls = [
        client.get("/api/vault/drafts", params={"persona": "nobody"}),
        client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "nobody"}),
        client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "all": True, "persona": "nobody"}),
        client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "persona": "nobody"}),
        client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": "x", "state": "open", "persona": "nobody"}),
        client.delete("/api/vault/annotations", params={"path": "Garden plan.md", "id": "x", "persona": "nobody"}),
    ]

    assert [c.status_code for c in calls] == [404] * 6


def test_a_note_with_changes_reports_each_status_against_the_note_on_disk(env):
    client, vault = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="Count.")
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="raised", replace="sunken", say="Beds.")
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="Phone", text="which phone?", author="user")
    (vault / "Garden plan.md").write_text(NOTE.replace("three times", "five times"))

    body = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()

    assert body["exists"] is True and body["mtime"]
    assert {p["find"]: p["status"] for p in body["proposals"]} == {"three times": "outdated", "raised": "pending"}
    assert [(a["quote"], a["status"], a["author"]) for a in body["annotations"]] == [("Phone", "attached", "user")]


def test_a_new_note_that_is_not_on_disk_yet_is_still_readable_as_a_draft(env):
    client, vault = env
    nc.propose_create("samantha", "Compost.md", "# Compost\n\nIn autumn.\n", say="New.")

    body = client.get("/api/vault/changes", params={"path": "Compost.md", "persona": "samantha"}).json()

    assert body["exists"] is False and body["mtime"] is None
    assert [(p["kind"], p["status"], p["text"]) for p in body["proposals"]] == [("create", "pending", "# Compost\n\nIn autumn.\n")]
    assert not (vault / "Compost.md").exists()


def test_resolving_forgets_the_named_proposal_and_leaves_the_note_alone(env):
    client, vault = env
    before = vault_files(vault)
    a = nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    b = nc.propose_edit("samantha", "Garden plan.md", NOTE, find="raised", replace="sunken", say="")

    r = client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "ids": [a["id"]], "persona": "samantha"})

    assert r.status_code == 200 and r.json()["resolved"] == [a["id"]]
    left = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["proposals"]
    assert [p["id"] for p in left] == [b["id"]]
    assert vault_files(vault) == before


def test_resolving_all_forgets_every_proposal_but_keeps_the_comments(env):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="raised", replace="sunken", say="")
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="Phone", text="q", author="user")

    r = client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "all": True, "persona": "samantha"})

    body = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()
    assert len(r.json()["resolved"]) == 2 and body["proposals"] == [] and len(body["annotations"]) == 1


def test_resolving_something_already_forgotten_is_404_but_all_with_nothing_is_fine(env):
    client, _ = env

    gone = client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "ids": ["nope"], "persona": "samantha"})
    nothing = client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "all": True, "persona": "samantha"})

    assert gone.status_code == 404
    assert nothing.status_code == 200 and nothing.json()["resolved"] == []


def test_resolving_with_neither_ids_nor_all_forgets_nothing(env):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    r = client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "persona": "samantha"})

    assert r.status_code == 200 and r.json()["resolved"] == []
    assert len(client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["proposals"]) == 1


def test_a_comment_is_added_edited_and_deleted_through_the_routes(env):
    client, _ = env

    made = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "text": "why?", "persona": "samantha"})
    cid = made.json()["id"]
    assert made.status_code == 201 and made.json()["author"] == "user" and made.json()["state"] == "open"

    assert client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": cid, "text": "why raised?", "persona": "samantha"}).status_code == 200
    (c,) = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"]
    assert (c["state"], c["text"]) == ("open", "why raised?")

    assert client.delete("/api/vault/annotations", params={"path": "Garden plan.md", "id": cid, "persona": "samantha"}).status_code == 200
    assert client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"] == []


def test_a_comment_on_words_that_occur_twice_needs_to_say_where(env):
    client, _ = env
    quote = {"path": "Garden plan.md", "quote": "- Pack charger", "persona": "samantha"}

    ambiguous = client.post("/api/vault/annotations", json=quote)
    placed = client.post("/api/vault/annotations", json={**quote, "start": NOTE.rindex("- Pack charger")})

    assert ambiguous.status_code == 422 and "more than once" in ambiguous.json()["detail"]
    assert placed.status_code == 201


def test_a_comment_on_a_passage_that_is_not_there_or_on_a_missing_note_is_refused(env):
    client, _ = env

    absent = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "nowhere", "persona": "samantha"})
    nonote = client.post("/api/vault/annotations", json={"path": "Missing.md", "quote": "x", "persona": "samantha"})

    assert absent.status_code == 422 and nonote.status_code == 404


def test_changing_a_comment_needs_something_to_change_and_a_known_state_and_a_known_comment(env):
    client, _ = env
    cid = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "persona": "samantha"}).json()["id"]
    base = {"path": "Garden plan.md", "persona": "samantha"}

    assert client.patch("/api/vault/annotations", json={**base, "id": cid}).status_code == 400
    assert client.patch("/api/vault/annotations", json={**base, "id": cid, "state": "pending"}).status_code == 400
    assert client.patch("/api/vault/annotations", json={**base, "id": "nope", "state": "open"}).status_code == 404
    assert client.delete("/api/vault/annotations", params={**base, "id": "nope"}).status_code == 404


def test_a_bad_state_does_not_change_the_text_that_came_with_it(env):
    client, _ = env
    cid = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "text": "keep", "persona": "samantha"}).json()["id"]

    r = client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": cid, "state": "pending", "text": "lost", "persona": "samantha"})

    assert r.status_code == 400
    (c,) = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"]
    assert c["text"] == "keep"


def test_no_route_here_writes_the_vault(env):
    client, vault = env
    before = vault_files(vault)
    p = nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_create("samantha", "Compost.md", "# Compost\n", say="")
    client.get("/api/vault/drafts", params={"persona": "samantha"})
    client.get("/api/vault/changes", params={"path": "Compost.md", "persona": "samantha"})
    client.post("/api/vault/changes/resolve", json={"path": "Garden plan.md", "ids": [p["id"]], "persona": "samantha"})
    client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "persona": "samantha"})

    assert vault_files(vault) == before


def test_a_comment_whose_passage_was_rewritten_is_gone_quietly(env):
    client, vault = env
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="Phone", text="which phone?", author="user")
    (vault / "Garden plan.md").write_text(NOTE.replace("Phone", "Mobile"))
    os.utime(vault / "Garden plan.md", (4_102_444_800, 4_102_444_800))  # written after the comment

    assert client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"] == []


def test_a_comment_whose_passage_is_rewritten_while_it_is_still_new_is_reported_detached(env):
    """Made on words that are only in the editor so far: the file (written before it) cannot say it is gone."""
    client, vault = env
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="Phone", text="which phone?", author="user")
    (vault / "Garden plan.md").write_text(NOTE.replace("Phone", "Mobile"))

    (a,) = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"]

    assert a["status"] == "detached"


def changes_for(client, path, persona="samantha"):
    return client.get("/api/vault/changes", params={"path": path, "persona": persona}).json()


def test_renaming_a_note_moves_every_personas_changes_with_it(env):
    client, vault = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("grace", "Garden plan.md", NOTE, find="raised", replace="sunken", say="")
    nc.annotate("samantha", "Garden plan.md", NOTE, quote="Phone", text="q", author="user")

    r = client.patch("/api/vault/note", json={"path": "Garden plan.md", "new_path": "Allotment.md", "persona": "samantha"})

    assert r.status_code == 200 and (vault / "Allotment.md").exists()
    mine, hers = changes_for(client, "Allotment.md"), changes_for(client, "Allotment.md", "grace")
    assert [p["find"] for p in mine["proposals"]] == ["three times"] and len(mine["annotations"]) == 1
    assert [p["find"] for p in hers["proposals"]] == ["raised"]
    assert changes_for(client, "Garden plan.md")["proposals"] == []
    assert mine["proposals"][0]["status"] == "pending"


def test_a_rename_that_is_refused_leaves_the_changes_where_they_were(env):
    client, vault = env
    (vault / "Taken.md").write_text("x\n")
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    r = client.patch("/api/vault/note", json={"path": "Garden plan.md", "new_path": "Taken.md", "persona": "samantha"})

    assert r.status_code == 409
    assert len(changes_for(client, "Garden plan.md")["proposals"]) == 1
    assert changes_for(client, "Taken.md")["proposals"] == []


def test_deleting_a_note_to_the_bin_keeps_its_changes_and_restoring_it_brings_them_back(env):
    client, vault = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    assert client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"}).status_code == 200
    assert len(changes_for(client, "Garden plan.md")["proposals"]) == 1
    bin_path = client.get("/api/vault/trash", params={"persona": "samantha"}).json()["items"][0]["trash_path"]
    assert client.post("/api/vault/trash/restore", json={"path": bin_path, "persona": "samantha"}).status_code == 200

    body = changes_for(client, "Garden plan.md")
    assert body["exists"] is True and [p["status"] for p in body["proposals"]] == ["pending"]


def test_purging_a_note_from_the_bin_removes_every_personas_changes_for_it(env):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("grace", "Garden plan.md", NOTE, find="raised", replace="sunken", say="")
    nc.propose_create("samantha", "Compost.md", "# Compost\n", say="")
    client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"})
    bin_path = client.get("/api/vault/trash", params={"persona": "samantha"}).json()["items"][0]["trash_path"]

    assert client.delete("/api/vault/trash", params={"path": bin_path, "persona": "samantha"}).status_code == 200

    assert changes_for(client, "Garden plan.md")["proposals"] == []
    assert changes_for(client, "Garden plan.md", "grace")["proposals"] == []
    assert len(changes_for(client, "Compost.md")["proposals"]) == 1


def test_emptying_the_bin_removes_the_changes_of_what_it_held_and_only_that(env):
    client, vault = env
    (vault / "Other.md").write_text("other\n")
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("samantha", "Other.md", "other\n", find="other", replace="another", say="")
    client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"})

    emptied = client.post("/api/vault/trash/empty", json={"persona": "samantha"})

    assert emptied.status_code == 200
    assert changes_for(client, "Garden plan.md")["proposals"] == []
    assert len(changes_for(client, "Other.md")["proposals"]) == 1


def test_purging_a_deleted_copy_keeps_the_changes_of_a_note_made_again_under_that_name(env):
    client, vault = env
    client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"})
    (vault / "Garden plan.md").write_text(NOTE)
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    bin_path = client.get("/api/vault/trash", params={"persona": "samantha"}).json()["items"][0]["trash_path"]

    assert client.delete("/api/vault/trash", params={"path": bin_path, "persona": "samantha"}).status_code == 200

    assert len(changes_for(client, "Garden plan.md")["proposals"]) == 1


def test_purging_one_of_two_deleted_copies_keeps_the_changes_for_the_one_left(env):
    client, vault = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")
    client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"})
    (vault / "Garden plan.md").write_text(NOTE)
    client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"})
    items = client.get("/api/vault/trash", params={"persona": "samantha"}).json()["items"]
    assert len(items) == 2 and {i["original_path"] for i in items} == {"Garden plan.md"}

    # The older copy keeps its plain name; the newer one was given a timestamp suffix in the bin, so its place in the
    # bin and the note's own path differ. Purge the plain one first, then the suffixed one last.
    older, newer = sorted(items, key=lambda i: len(i["trash_path"]))
    client.delete("/api/vault/trash", params={"path": older["trash_path"], "persona": "samantha"})
    assert len(changes_for(client, "Garden plan.md")["proposals"]) == 1

    client.delete("/api/vault/trash", params={"path": newer["trash_path"], "persona": "samantha"})
    assert changes_for(client, "Garden plan.md")["proposals"] == []


def test_emptying_the_bin_keeps_the_changes_of_a_note_that_exists_again(env):
    client, vault = env
    client.delete("/api/vault/note", params={"path": "Garden plan.md", "persona": "samantha"})
    (vault / "Garden plan.md").write_text(NOTE)
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    assert client.post("/api/vault/trash/empty", json={"persona": "samantha"}).status_code == 200

    assert len(changes_for(client, "Garden plan.md")["proposals"]) == 1


@pytest.mark.parametrize("form", ["Garden plan", "Garden plan.md", " Garden plan ", "./Garden plan.md"])
def test_every_spelling_of_a_notes_path_reaches_the_same_changes_and_reports_one_path(env, form):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    body = changes_for(client, form)

    assert body["path"] == "Garden plan.md" and body["exists"] is True and len(body["proposals"]) == 1


def test_a_comment_added_under_one_spelling_is_seen_under_another_and_resolves_under_a_third(env):
    client, _ = env
    made = client.post("/api/vault/annotations", json={"path": "Garden plan", "quote": "raised", "text": "q", "persona": "samantha"})
    nc.propose_edit("samantha", "./Garden plan.md", NOTE, find="three times", replace="four times", say="")

    seen = changes_for(client, "Garden plan.md")
    cleared = client.post("/api/vault/changes/resolve", json={"path": " Garden plan ", "all": True, "persona": "samantha"}).json()

    assert made.json()["id"] in [a["id"] for a in seen["annotations"]] and len(seen["proposals"]) == 1
    assert cleared["path"] == "Garden plan.md" and len(cleared["resolved"]) == 1


def test_a_path_that_leaves_the_vault_is_a_bad_request_on_every_route_not_a_server_error(env):
    client, _ = env
    calls = [
        client.get("/api/vault/changes", params={"path": "../../etc/passwd", "persona": "samantha"}),
        client.post("/api/vault/changes/resolve", json={"path": "../x", "all": True, "persona": "samantha"}),
        client.post("/api/vault/annotations", json={"path": "../x", "quote": "q", "persona": "samantha"}),
        client.patch("/api/vault/annotations", json={"path": "../x", "id": "a", "state": "open", "persona": "samantha"}),
        client.delete("/api/vault/annotations", params={"path": "../x", "id": "a", "persona": "samantha"}),
    ]

    assert [c.status_code for c in calls] == [400] * 5


def test_renaming_with_an_extensionless_old_path_still_carries_the_changes(env):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    client.patch("/api/vault/note", json={"path": "Garden plan", "new_path": "Allotment", "persona": "samantha"})

    assert len(changes_for(client, "Allotment.md")["proposals"]) == 1


def folder_env(client, vault):
    (vault / "Garden").mkdir()
    (vault / "Garden" / "Beds.md").write_text(NOTE)
    (vault / "Garden" / "Deep").mkdir()
    (vault / "Garden" / "Deep" / "Seeds.md").write_text(NOTE)
    nc.propose_edit("samantha", "Garden/Beds.md", NOTE, find="three times", replace="four times", say="")
    nc.propose_edit("samantha", "Garden/Deep/Seeds.md", NOTE, find="raised", replace="sunken", say="")


def test_deleting_a_folder_keeps_the_changes_of_the_notes_in_it_and_restoring_it_brings_them_back(env):
    client, vault = env
    folder_env(client, vault)

    assert client.delete("/api/vault/folder", params={"path": "Garden", "persona": "samantha"}).status_code == 200
    assert not (vault / "Garden").exists()
    assert len(changes_for(client, "Garden/Beds.md")["proposals"]) == 1

    bin_folder = next(i for i in client.get("/api/vault/trash", params={"persona": "samantha"}).json()["items"] if i["original_path"] == "Garden/Beds.md")
    restored = client.post("/api/vault/trash/restore-folder", json={"path": bin_folder["folder"], "persona": "samantha"})

    assert restored.status_code == 200
    for note in ("Garden/Beds.md", "Garden/Deep/Seeds.md"):
        body = changes_for(client, note)
        assert body["exists"] is True and [p["status"] for p in body["proposals"]] == ["pending"]


def test_emptying_the_bin_after_a_folder_was_deleted_forgets_the_changes_of_every_note_in_it(env):
    client, vault = env
    folder_env(client, vault)
    client.delete("/api/vault/folder", params={"path": "Garden", "persona": "samantha"})

    assert client.post("/api/vault/trash/empty", json={"persona": "samantha"}).status_code == 200

    assert changes_for(client, "Garden/Beds.md")["proposals"] == []
    assert changes_for(client, "Garden/Deep/Seeds.md")["proposals"] == []
    assert nc.drafts("samantha") == []


def test_changing_and_deleting_a_comment_report_the_canonical_path(env):
    client, _ = env
    cid = client.post("/api/vault/annotations", json={"path": "Garden plan", "quote": "raised", "persona": "samantha"}).json()["id"]

    patched = client.patch("/api/vault/annotations", json={"path": " ./Garden plan ", "id": cid, "state": "resolved", "persona": "samantha"})
    deleted = client.delete("/api/vault/annotations", params={"path": "Garden plan", "id": cid, "persona": "samantha"})

    assert patched.json()["path"] == "Garden plan.md" and deleted.json()["path"] == "Garden plan.md"


def test_a_comment_can_carry_the_editors_own_context_for_words_not_yet_saved(env):
    client, _ = env

    made = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "newly typed", "before": "I just ", "after": " words", "text": "check", "persona": "samantha"})

    assert made.status_code == 201
    (a,) = changes_for(client, "Garden plan.md")["annotations"]
    assert (a["quote"], a["before"], a["after"], a["status"]) == ("newly typed", "I just ", " words", "detached")


def test_an_answer_names_the_comment_it_is_under_and_takes_its_passage(env):
    client, _ = env
    root = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "text": "why?", "persona": "samantha"}).json()

    answer = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "reply_to": root["id"], "text": "because", "persona": "samantha"})

    assert answer.status_code == 201
    assert (answer.json()["reply_to"], answer.json()["quote"], answer.json()["author"]) == (root["id"], "raised", "user")


def test_an_answer_to_an_unknown_comment_and_a_comment_with_nothing_to_comment_on_are_refused(env):
    client, _ = env
    base = {"path": "Garden plan.md", "persona": "samantha"}

    assert client.post("/api/vault/annotations", json={**base, "reply_to": "nope", "text": "x"}).status_code == 404
    assert client.post("/api/vault/annotations", json={**base, "text": "x"}).status_code == 400
    assert changes_for(client, "Garden plan.md")["annotations"] == []


def test_resolving_a_comment_through_the_route_takes_it_and_its_answers_away_quietly(env):
    client, _ = env
    root = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "text": "why?", "persona": "samantha"}).json()
    client.post("/api/vault/annotations", json={"path": "Garden plan.md", "reply_to": root["id"], "text": "because", "persona": "samantha"})

    client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": root["id"], "state": "resolved", "persona": "samantha"})

    assert changes_for(client, "Garden plan.md")["annotations"] == []
    assert client.get("/api/vault/drafts", params={"persona": "samantha"}).json()["drafts"] == []


def test_half_a_context_is_not_used_the_passage_is_found_in_the_note_instead(env):
    client, _ = env

    made = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "before": "only this half", "text": "c", "persona": "samantha"})

    assert made.status_code == 201
    assert made.json()["before"].endswith("The beds are ") and made.json()["after"].startswith(".")


def test_saving_a_draft_replaces_the_new_note_text_in_her_folder_and_never_touches_the_vault(env):
    client, vault = env
    nc.propose_create("samantha", "Compost.md", "# Compost\n\nfirst\n", say="New.")
    before = vault_files(vault)

    res = client.patch("/api/vault/changes/draft", json={"path": "Compost.md", "persona": "samantha", "text": "# Compost\n\nedited by the user\n"})

    assert res.status_code == 200
    (proposal,) = client.get("/api/vault/changes", params={"path": "Compost.md", "persona": "samantha"}).json()["proposals"]
    assert proposal["text"] == "# Compost\n\nedited by the user\n" and proposal["name"] == "Compost"
    assert vault_files(vault) == before


def test_the_saved_draft_survives_a_new_app_because_it_is_a_file_in_her_folder(env):
    client, _ = env
    nc.propose_create("samantha", "Compost.md", "# Compost\n", say="New.")
    client.patch("/api/vault/changes/draft", json={"path": "Compost.md", "persona": "samantha", "text": "# Compost\n\nkept\n"})

    again = TestClient(create_app())  # as after a restart: nothing is held in memory

    (proposal,) = again.get("/api/vault/changes", params={"path": "Compost.md", "persona": "samantha"}).json()["proposals"]
    assert proposal["text"] == "# Compost\n\nkept\n"


def test_saving_a_draft_changes_only_that_persona_and_that_note(env):
    client, _ = env
    nc.propose_create("samantha", "Compost.md", "# Compost\n", say="")
    nc.propose_create("grace", "Compost.md", "# Grace's\n", say="")
    nc.propose_create("samantha", "Other.md", "# Other\n", say="")

    client.patch("/api/vault/changes/draft", json={"path": "Compost.md", "persona": "samantha", "text": "# Changed\n"})

    text = lambda who, path: client.get("/api/vault/changes", params={"path": path, "persona": who}).json()["proposals"][0]["text"]  # noqa: E731
    assert (text("samantha", "Compost.md"), text("grace", "Compost.md"), text("samantha", "Other.md")) == ("# Changed\n", "# Grace's\n", "# Other\n")


def test_saving_text_for_a_note_with_no_new_note_draft_is_404_and_adds_nothing(env):
    client, _ = env
    nc.propose_edit("samantha", "Garden plan.md", NOTE, find="three times", replace="four times", say="")

    on_edit = client.patch("/api/vault/changes/draft", json={"path": "Garden plan.md", "persona": "samantha", "text": "x"})
    on_nothing = client.patch("/api/vault/changes/draft", json={"path": "Nope.md", "persona": "samantha", "text": "x"})

    assert (on_edit.status_code, on_nothing.status_code) == (404, 404)
    assert client.get("/api/vault/changes", params={"path": "Nope.md", "persona": "samantha"}).json()["proposals"] == []


def test_saving_a_draft_for_an_unknown_persona_is_404(env):
    client, _ = env
    res = client.patch("/api/vault/changes/draft", json={"path": "Compost.md", "persona": "nobody", "text": "x"})
    assert res.status_code == 404


def test_a_draft_saved_under_another_spelling_of_its_path_reaches_the_same_draft(env):
    client, _ = env
    nc.propose_create("samantha", "Sub/Compost.md", "# Compost\n", say="")

    res = client.patch("/api/vault/changes/draft", json={"path": "./Sub/Compost", "persona": "samantha", "text": "# By another spelling\n"})

    assert res.status_code == 200 and res.json()["path"] == "Sub/Compost.md"
    (proposal,) = client.get("/api/vault/changes", params={"path": "Sub/Compost.md", "persona": "samantha"}).json()["proposals"]
    assert proposal["text"] == "# By another spelling\n"


def test_a_draft_is_saved_for_the_persona_who_asked_not_the_default_one(env):
    client, _ = env
    nc.propose_create("samantha", "Compost.md", "# Samantha's\n", say="")
    nc.propose_create("grace", "Compost.md", "# Grace's\n", say="")

    client.patch("/api/vault/changes/draft", json={"path": "Compost.md", "persona": "grace", "text": "# Grace edited\n"})

    text = lambda who: client.get("/api/vault/changes", params={"path": "Compost.md", "persona": who}).json()["proposals"][0]["text"]  # noqa: E731
    assert (text("samantha"), text("grace")) == ("# Samantha's\n", "# Grace edited\n")


def test_a_comment_of_hers_is_declined_through_the_route_with_or_without_a_reply_of_the_users(env):
    client, _ = env
    bare = nc.annotate("samantha", "Garden plan.md", NOTE, quote="raised", text="Are you sure?", author="persona")
    said = nc.annotate("samantha", "Garden plan.md", NOTE, quote="three", text="Really?", author="persona")
    client.post("/api/vault/annotations", json={"path": "Garden plan.md", "persona": "samantha", "reply_to": said["id"], "text": "Yes, I am."})

    results = [client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": c["id"], "persona": "samantha", "verdict": "declined"}) for c in (bare, said)]

    assert [r.status_code for r in results] == [200, 200]
    got = {a["id"]: a for a in client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"]}
    assert (got[bare["id"]]["state"], got[bare["id"]]["verdict"]) == ("resolved", "declined")
    assert (got[said["id"]]["state"], got[said["id"]]["verdict"]) == ("resolved", "declined")


def test_the_route_refuses_a_verdict_on_the_users_own_comment_and_an_unknown_verdict(env):
    client, _ = env
    mine = nc.annotate("samantha", "Garden plan.md", NOTE, quote="raised", text="mine", author="user")
    hers = nc.annotate("samantha", "Garden plan.md", NOTE, quote="three", text="hers", author="persona")

    on_mine = client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": mine["id"], "persona": "samantha", "verdict": "accepted"})
    unknown = client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": hers["id"], "persona": "samantha", "verdict": "maybe"})

    assert (on_mine.status_code, unknown.status_code) == (400, 400)
    assert "Only the persona's comments" in on_mine.json()["detail"]
