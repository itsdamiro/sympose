"""Folders and notes hidden from the web app's view (docs/decisions/037): the list in the settings
file, the marks on the tree, the filtered graph, the flagged search hits and the routes — and that
none of it reaches what the persona reads."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import settings_store, vault_graph, vault_hidden, vault_paths
from sympose.engine import grounding
from sympose.profile import resolve_profile
from sympose.server import create_app

VAULT_KEY = "the-vault"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    files = {
        "Projects/Alpha.md": "Alpha links to [[Secret]] and [[Beta]] and [[Missing]].",
        "Projects/Beta.md": "Beta is plain.",
        "Journal/Secret.md": "The secret plan mentions a zebra. See [[Nowhere]] and [[Beta]].",
        "Journal/Journal.md": "# Journal\n\nWhat this folder is for.",
        "Drafts/One.md": "Draft one zebra.",
        "Drafts/Two.md": "Draft two.",
        "Loose.md": "Loose links to [[Missing]].",
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    return str(root)


@pytest.fixture
def client(vault):
    return TestClient(create_app())


def _paths(nodes):
    for node in nodes:
        yield node
        yield from _paths(node.get("children") or [])


def _by_path(tree):
    return {n["path"]: n for n in _paths(tree)}


# -- the rules ---------------------------------------------------------------


@pytest.mark.parametrize("raw, want", [
    ("a/b", "a/b"), ("a\\b\\", "a/b"), ("/a/", "a"), ("  Note.md  ", "Note.md"), ("a b/c d.md", "a b/c d.md"),
])
def test_a_path_is_normalised(raw, want):
    assert vault_hidden.normalize(raw) == want


@pytest.mark.parametrize("raw", ["", "  ", "/", "..", "a/../b", "./a", "a//b", "a\x00b", "x" * 1025, None, 3])
def test_anything_that_is_not_a_plain_relative_path_is_refused(raw):
    assert vault_hidden.normalize(raw) is None


def test_a_folder_hides_what_is_under_it_but_not_a_folder_with_a_longer_name():
    assert vault_hidden.is_hidden("Draft/a.md", ["Draft"]) and vault_hidden.is_hidden("Draft", ["Draft"])
    assert not vault_hidden.is_hidden("Drafts/a.md", ["Draft"])
    assert not vault_hidden.is_hidden("Other/Draft/a.md", ["Draft"])


def test_the_list_is_read_back_in_a_case_blind_order():
    for path in ("b", "C", "a"):
        vault_hidden.hide("/v1", path)
    assert vault_hidden.hidden_paths("/v1") == ["a", "b", "C"]  # not "C" first, as a plain sort would


def test_the_list_is_kept_per_vault_idempotent_and_sorted():
    assert vault_hidden.hide("/v1", "b") and vault_hidden.hide("/v1", "A") and vault_hidden.hide("/v1", "b")
    assert vault_hidden.hide("/v2", "x")
    assert vault_hidden.hidden_paths("/v1") == ["A", "b"]
    assert vault_hidden.hidden_paths("/v2") == ["x"]
    assert vault_hidden.unhide("/v1", "b") and vault_hidden.unhide("/v1", "b")
    assert vault_hidden.hidden_paths("/v1") == ["A"]
    assert settings_store.get("hidden_paths") == {"/v1": ["A"], "/v2": ["x"]}


def test_emptying_the_last_list_leaves_no_key_behind():
    vault_hidden.hide("/v1", "a")
    vault_hidden.unhide("/v1", "a")
    assert settings_store.get("hidden_paths") is None


def test_a_malformed_setting_reads_as_nothing_hidden():
    for junk in ("x", ["a"], {"/v": "a"}, {"/v": [1, None]}, 5):
        settings_store.set("hidden_paths", junk)
        assert vault_hidden.hidden_paths("/v") == []


def test_a_damaged_setting_is_left_alone_not_overwritten_with_what_is_left_of_it():
    for junk in ("hand edited", ["a", "b"], 5):
        settings_store.set("hidden_paths", junk)
        assert vault_hidden.hide("/v", "a") is False
        assert vault_hidden.unhide("/v", "a") is False
        assert settings_store.get("hidden_paths") == junk


def test_changing_one_vaults_list_leaves_every_other_entry_exactly_as_it_was():
    settings_store.set("hidden_paths", {"/other": ["z", 3], "/odd": "hand edited"})
    assert vault_hidden.hide("/v", "a")
    assert settings_store.get("hidden_paths") == {"/other": ["z", 3], "/odd": "hand edited", "/v": ["a"]}
    assert vault_hidden.unhide("/v", "a")
    assert settings_store.get("hidden_paths") == {"/other": ["z", 3], "/odd": "hand edited"}


def test_two_hides_at_the_same_moment_both_land(monkeypatch):
    import threading
    import time

    real_set = settings_store.set

    def slow_set(key, value):
        time.sleep(0.02)  # a wide window between reading the list and writing it back
        return real_set(key, value)

    monkeypatch.setattr(vault_hidden.settings_store, "set", slow_set)
    threads = [threading.Thread(target=vault_hidden.hide, args=("/v", f"n{i}")) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert vault_hidden.hidden_paths("/v") == [f"n{i}" for i in range(8)]


def test_a_write_that_fails_says_so(monkeypatch):
    monkeypatch.setattr(vault_hidden.settings_store, "set", lambda key, value: False)
    assert vault_hidden.hide("/v", "a") is False


def test_definition_notes_are_shown_only_when_asked_for():
    assert vault_hidden.definitions_shown() is False
    assert vault_hidden.set_definitions_shown(True) and vault_hidden.definitions_shown() is True
    assert vault_hidden.set_definitions_shown(False) and vault_hidden.definitions_shown() is False
    assert settings_store.get("show_definition_notes") is None


# -- the tree ------------------------------------------------------------------


def test_the_tree_marks_what_is_hidden_and_what_is_under_it(client):
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    nodes = _by_path(client.get("/api/vault/tree").json()["tree"])
    assert nodes["Drafts"]["hidden"] == "user"
    assert nodes["Drafts/One.md"]["hidden"] == "user" and nodes["Drafts/Two.md"]["hidden"] == "user"
    assert nodes["Journal/Secret.md"]["hidden"] == "user"
    assert "hidden" not in nodes["Journal"] and "hidden" not in nodes["Projects/Alpha.md"]


def test_nothing_is_removed_from_the_tree_so_a_link_can_still_be_resolved(client):
    before = set(_by_path(client.get("/api/vault/tree").json()["tree"]))
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    assert set(_by_path(client.get("/api/vault/tree").json()["tree"])) == before


def test_a_hidden_note_is_not_listed_as_anyones_neighbour(client):
    before = _by_path(client.get("/api/vault/tree").json()["tree"])
    assert "Journal/Secret.md" in before["Projects/Alpha.md"]["links"]
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    after = _by_path(client.get("/api/vault/tree").json()["tree"])
    assert "Journal/Secret.md" not in after["Projects/Alpha.md"]["links"]
    assert "Projects/Beta.md" in after["Projects/Alpha.md"]["links"]  # the others stay
    assert after["Journal/Secret.md"]["links"] == before["Journal/Secret.md"]["links"]  # its own list is untouched


def test_a_ghost_id_is_never_taken_for_a_hidden_folder(client):
    """A broken link `[[Ideas]]` has the id `Ideas` (no note is called that); hiding the folder `Ideas`
    must not drop that neighbour, which is not a note the user hid."""
    from pathlib import Path

    root = Path(vault_paths.get_master_vault())
    (root / "Ideas").mkdir()
    (root / "Ideas" / "Foo.md").write_text("an idea")
    (root / "Linker.md").write_text("[[Ideas]]")
    client.post("/api/vault/hidden", json={"path": "Ideas"})
    assert _by_path(client.get("/api/vault/tree").json()["tree"])["Linker.md"]["links"] == ["Ideas"]


def test_a_folder_definition_note_is_marked_until_the_switch_is_on(client):
    nodes = _by_path(client.get("/api/vault/tree").json()["tree"])
    assert nodes["Journal/Journal.md"]["hidden"] == "definition"
    assert "hidden" not in nodes["Projects/Beta.md"]
    client.put("/api/vault/hidden/definitions", json={"show": True})
    nodes = _by_path(client.get("/api/vault/tree").json()["tree"])
    assert "hidden" not in nodes["Journal/Journal.md"]


def test_only_the_definition_note_of_a_top_level_folder_counts_as_one(client):
    from pathlib import Path

    root = Path(vault_paths.get_master_vault())
    (root / "Journal" / "Sub").mkdir()
    (root / "Journal" / "Sub" / "Sub.md").write_text("not a definition")
    (root / "Other.md").write_text("root note")
    nodes = _by_path(client.get("/api/vault/tree").json()["tree"])
    assert "hidden" not in nodes["Journal/Sub/Sub.md"] and "hidden" not in nodes["Other.md"]


def test_a_folder_that_cannot_have_a_definition_has_no_definition_note(client):
    """`Templates/Templates.md` is a note like any other: `Templates` is not a folder of the user's content."""
    from pathlib import Path

    root = Path(vault_paths.get_master_vault())
    (root / "Templates").mkdir()
    (root / "Templates" / "Templates.md").write_text("a template")
    assert "hidden" not in _by_path(client.get("/api/vault/tree").json()["tree"])["Templates/Templates.md"]


def test_a_definition_note_the_user_hid_is_hidden_as_theirs(client):
    client.put("/api/vault/hidden/definitions", json={"show": True})
    client.post("/api/vault/hidden", json={"path": "Journal/Journal.md"})
    assert _by_path(client.get("/api/vault/tree").json()["tree"])["Journal/Journal.md"]["hidden"] == "user"


# -- the graph -----------------------------------------------------------------


def _graph(client):
    return client.get("/api/vault/graph").json()


def test_the_graph_loses_a_hidden_note_and_every_line_to_it(client):
    before = _graph(client)
    ids = {n["id"] for n in before["nodes"]}
    assert "Journal/Secret.md" in ids
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    after = _graph(client)
    assert "Journal/Secret.md" not in {n["id"] for n in after["nodes"]}
    assert all("Journal/Secret.md" not in (ln["source"], ln["target"]) for ln in after["links"])
    assert {n["id"] for n in after["nodes"]} == ids - {"Journal/Secret.md", "Nowhere"}


def test_a_ghost_reached_only_from_a_hidden_note_goes_with_it_and_one_reached_from_others_stays(client):
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    ids = {n["id"] for n in _graph(client)["nodes"]}
    assert "Nowhere" not in ids  # only the hidden note linked to it
    assert "Missing" in ids  # a visible note does


def test_a_hidden_neighbour_is_not_counted_in_a_nodes_size(client):
    def val(g, node_id):
        return next(n["val"] for n in g["nodes"] if n["id"] == node_id)

    before = val(_graph(client), "Projects/Beta.md")  # linked from Alpha and from Secret
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    assert val(_graph(client), "Projects/Beta.md") == before - 1


def test_hiding_a_folder_takes_its_notes_out_of_the_graph(client):
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    ids = {n["id"] for n in _graph(client)["nodes"]}
    assert not {"Drafts/One.md", "Drafts/Two.md"} & ids and "Projects/Alpha.md" in ids


def test_definition_notes_stay_in_the_graph(client):
    assert "Journal/Journal.md" in {n["id"] for n in _graph(client)["nodes"]}


def test_a_graph_with_nothing_hidden_is_left_exactly_as_it_was(vault):
    graph = {"nodes": [{"id": "a.md", "val": 1, "exists": True}], "links": []}
    assert vault_hidden.for_graph(graph) is graph


# -- search ----------------------------------------------------------------------


def test_search_still_finds_hidden_notes_and_flags_them(client):
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    hits = {h["rel_path"]: h for h in client.get("/api/vault/search", params={"q": "zebra"}).json()["results"]}
    assert set(hits) == {"Drafts/One.md", "Journal/Secret.md"}
    assert hits["Drafts/One.md"]["hidden"] is True
    assert hits["Drafts/One.md"]["hidden_by"] == ["Drafts"]
    assert "hidden" not in hits["Journal/Secret.md"] and "hidden_by" not in hits["Journal/Secret.md"]


def test_a_hit_says_every_entry_that_hides_it_so_unhide_can_really_show_it(client):
    """Hidden through its folder and by name: showing it takes both entries away, not just its own path."""
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    client.post("/api/vault/hidden", json={"path": "Drafts/One.md"})
    hit = client.get("/api/vault/search", params={"q": "Draft one"}).json()["results"][0]
    assert hit["hidden_by"] == ["Drafts", "Drafts/One.md"]
    for path in hit["hidden_by"]:
        client.delete("/api/vault/hidden", params={"path": path})
    hit = client.get("/api/vault/search", params={"q": "Draft one"}).json()["results"][0]
    assert "hidden" not in hit


# -- the routes ------------------------------------------------------------------


def test_the_state_is_read_and_changed_through_the_routes_and_each_answers_with_all_of_it(client):
    assert client.get("/api/vault/hidden").json() == {"hidden": [], "showDefinitionNotes": False}
    assert client.post("/api/vault/hidden", json={"path": "Drafts"}).json()["hidden"] == ["Drafts"]
    assert client.post("/api/vault/hidden", json={"path": "Drafts"}).json()["hidden"] == ["Drafts"]  # idempotent
    assert client.post("/api/vault/hidden", json={"path": "Loose.md"}).json()["hidden"] == ["Drafts", "Loose.md"]
    assert client.delete("/api/vault/hidden", params={"path": "Drafts"}).json()["hidden"] == ["Loose.md"]
    assert client.delete("/api/vault/hidden", params={"path": "Drafts"}).status_code == 200  # nothing to unhide is fine
    assert client.put("/api/vault/hidden/definitions", json={"show": True}).json()["showDefinitionNotes"] is True


def test_a_path_that_is_no_longer_there_is_still_listed_so_it_can_be_unhidden(client):
    client.post("/api/vault/hidden", json={"path": "Gone/Away.md"})
    assert client.get("/api/vault/hidden").json()["hidden"] == ["Gone/Away.md"]
    assert client.delete("/api/vault/hidden", params={"path": "Gone/Away.md"}).json()["hidden"] == []


@pytest.mark.parametrize("path", ["..", "a/../b", "  ", "a//b"])
def test_a_bad_path_is_a_400_and_changes_nothing(client, path):
    assert client.post("/api/vault/hidden", json={"path": path}).status_code == 400
    assert client.delete("/api/vault/hidden", params={"path": path}).status_code == 400
    assert client.get("/api/vault/hidden").json()["hidden"] == []


def test_with_no_vault_configured_hiding_is_a_409(monkeypatch, tmp_path):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setattr(vault_paths, "get_master_vault", lambda: None)
    response = TestClient(create_app()).post("/api/vault/hidden", json={"path": "a"})
    assert response.status_code == 409


def test_a_failed_save_is_a_500_not_a_silent_success(client, monkeypatch):
    monkeypatch.setattr(vault_hidden.settings_store, "set", lambda key, value: False)
    assert client.post("/api/vault/hidden", json={"path": "Drafts"}).status_code == 500


def test_a_damaged_setting_is_a_500_and_stays_as_it_was(client):
    settings_store.set("hidden_paths", "hand edited")
    assert client.post("/api/vault/hidden", json={"path": "Drafts"}).status_code == 500
    assert settings_store.get("hidden_paths") == "hand edited"


def test_the_list_is_per_vault(client, vault, tmp_path, monkeypatch):
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(other))
    assert client.get("/api/vault/hidden").json()["hidden"] == []


# -- hiding is for the view only ----------------------------------------------------


def test_the_note_itself_is_still_served(client):
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    assert client.get("/api/vault/note", params={"path": "Journal/Secret.md"}).status_code == 200


def test_what_the_persona_reads_is_not_touched(client):
    """The engine calls `vault_graph` directly; hiding is applied only by the web routes."""
    client.post("/api/vault/hidden", json={"path": "Journal/Secret.md"})
    client.post("/api/vault/hidden", json={"path": "Drafts"})
    profile = resolve_profile("samantha")
    assert "Journal/Secret.md" in {n["id"] for n in vault_graph.get_vault_graph(profile)["nodes"]}
    tree = _by_path(vault_graph.get_vault_tree(profile))
    assert "hidden" not in tree["Journal/Secret.md"] and "Drafts/One.md" in tree
    assert grounding.scope_index(profile) is not None
