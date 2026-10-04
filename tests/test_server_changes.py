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


def test_a_comment_is_added_resolved_edited_and_deleted_through_the_routes(env):
    client, _ = env

    made = client.post("/api/vault/annotations", json={"path": "Garden plan.md", "quote": "raised", "text": "why?", "persona": "samantha"})
    cid = made.json()["id"]
    assert made.status_code == 201 and made.json()["author"] == "user" and made.json()["state"] == "open"

    assert client.patch("/api/vault/annotations", json={"path": "Garden plan.md", "id": cid, "state": "resolved", "text": "why raised?", "persona": "samantha"}).status_code == 200
    (c,) = client.get("/api/vault/changes", params={"path": "Garden plan.md", "persona": "samantha"}).json()["annotations"]
    assert (c["state"], c["text"]) == ("resolved", "why raised?")

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


def test_a_comment_whose_passage_was_rewritten_is_reported_detached(env):
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
