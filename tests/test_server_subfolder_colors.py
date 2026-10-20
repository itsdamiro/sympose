"""Folder looks below a top-level folder (docs/decisions/090) through the real app on a scratch vault: the routes the
Folder look dialog calls, the colour a note's node and the icon and colour a tree folder carry, and the entries following a renamed or
moved folder. The module's own cases are `test_subfolder_colors.py`."""

import pytest
import yaml
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose.server import create_app

PROJECTS = "---\nicon: folder-library\naccent: '#0284c7'\naccent_dark: '#56c9e0'\n---\n# Projects\n"
VIOLET = {"accent": "#7c3aed", "accent_dark": "#b98cff"}
ROSE = {"accent": "#be123c", "accent_dark": "#f2889b"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for rel, text in {
        "Projects/Projects.md": PROJECTS,
        "Projects/sympose/Plan.md": "plan\n",
        "Projects/sympose/decisions/One.md": "one\n",
        "Projects/stylo/Plan.md": "plan\n",
        "Projects/Loose.md": "loose\n",
        "Notes/Idea.md": "idea\n",
    }.items():
        (vault / rel).parent.mkdir(parents=True, exist_ok=True)
        (vault / rel).write_text(text)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return TestClient(create_app()), vault


def paint(client, path, look=VIOLET, **extra):
    return client.put("/api/vault/folder/color", json={"path": path, **look, "persona": "samantha", **extra})


def frontmatter(vault, rel="Projects/Projects.md"):
    text = (vault / rel).read_text()
    return yaml.safe_load(text.split("---\n")[1])


def nodes(client):
    return {n["id"]: n for n in client.get("/api/vault/graph", params={"persona": "samantha"}).json()["nodes"]}


def folder(tree, path):
    for node in tree:
        if node["path"] == path:
            return node
        if node["type"] == "folder" and (found := folder(node.get("children", []), path)):
            return found
    return None


def test_the_get_route_gives_the_folders_own_colours(env):
    client, _ = env
    assert client.get("/api/vault/folder/color", params={"path": "Projects/sympose", "persona": "samantha"}).json() == {
        "editable": True, "accent": None, "accent_dark": None, "icon": None,
    }
    paint(client, "Projects/sympose")
    assert client.get("/api/vault/folder/color", params={"path": "Projects/sympose", "persona": "samantha"}).json() == {"editable": True, **VIOLET, "icon": None}
    assert client.get("/api/vault/folder/color", params={"path": "Projects", "persona": "samantha"}).json() == {"editable": False}


def test_the_put_route_writes_the_entry_into_the_top_level_note_and_keeps_its_own_look(env):
    client, vault = env
    assert paint(client, "Projects/sympose").json() == {"path": "Projects/sympose", "created": False}
    front = frontmatter(vault)
    assert front["subfolders"] == {"sympose": VIOLET} and front["accent"] == "#0284c7" and front["icon"] == "folder-library"


def test_the_put_route_clears_a_colour_when_both_are_left_out(env):
    client, vault = env
    paint(client, "Projects/sympose")
    assert client.put("/api/vault/folder/color", json={"path": "Projects/sympose", "persona": "samantha"}).status_code == 200
    assert "subfolders" not in frontmatter(vault)


def test_the_put_route_creates_the_note_of_a_folder_that_has_none(env):
    client, vault = env
    (vault / "Notes" / "sub").mkdir()
    assert paint(client, "Notes/sub", ROSE).json()["created"] is True
    assert frontmatter(vault, "Notes/Notes.md") == {"subfolders": {"sub": ROSE}}


@pytest.mark.parametrize(
    ("path", "body", "status"),
    [
        ("Projects", VIOLET, 400),
        ("Projects/nope", VIOLET, 404),
        ("Projects/sympose", {"accent": "red"}, 400),
        ("Projects/sympose", {"accent": "#123456", "accent_dark": "javascript:alert(1)"}, 400),
        ("../x", VIOLET, 400),
    ],
)
def test_the_put_route_refuses_what_it_cannot_write(env, path, body, status):
    client, vault = env
    before = (vault / "Projects/Projects.md").read_text()
    assert paint(client, path, body).status_code == status
    assert (vault / "Projects/Projects.md").read_text() == before


def test_a_note_s_node_carries_the_colour_of_its_nearest_coloured_folder(env):
    client, _ = env
    paint(client, "Projects/sympose", VIOLET)
    paint(client, "Projects/sympose/decisions", ROSE)
    graph = nodes(client)
    assert graph["Projects/sympose/Plan.md"]["accent"] == VIOLET["accent"]
    assert graph["Projects/sympose/Plan.md"]["colored_by"] == "Projects/sympose"
    assert graph["Projects/sympose/decisions/One.md"]["accent_dark"] == ROSE["accent_dark"]
    assert graph["Projects/sympose/decisions/One.md"]["colored_by"] == "Projects/sympose/decisions"


def test_a_note_with_no_coloured_folder_above_it_keeps_the_top_level_folder_s_colour(env):
    client, _ = env
    paint(client, "Projects/sympose")
    for note in ("Projects/stylo/Plan.md", "Projects/Loose.md"):
        assert nodes(client)[note]["accent"] == "#0284c7" and "colored_by" not in nodes(client)[note]
    assert "accent" not in nodes(client)["Notes/Idea.md"]


def test_a_tree_folder_carries_its_own_colour_and_a_neighbour_does_not(env):
    client, _ = env
    paint(client, "Projects/sympose", VIOLET)
    tree = client.get("/api/vault/tree", params={"persona": "samantha"}).json()["tree"]
    assert folder(tree, "Projects/sympose")["accent_dark"] == VIOLET["accent_dark"]
    assert "accent" not in folder(tree, "Projects/stylo")
    assert "accent" not in folder(tree, "Projects/sympose/decisions")
    assert folder(tree, "Projects")["accent"] == "#0284c7"


def test_renaming_a_folder_carries_its_colour_and_says_so(env):
    client, vault = env
    paint(client, "Projects/sympose", VIOLET)
    paint(client, "Projects/sympose/decisions", ROSE)
    res = client.patch("/api/vault/folder", json={"path": "Projects/sympose", "new_name": "sympose2", "persona": "samantha"})
    assert res.status_code == 200 and "2 folder colours carried along" in res.json()["detail"]
    assert frontmatter(vault)["subfolders"] == {"sympose2": VIOLET, "sympose2/decisions": ROSE}
    assert nodes(client)["Projects/sympose2/Plan.md"]["colored_by"] == "Projects/sympose2"


def test_moving_a_folder_carries_its_colour(env):
    client, vault = env
    paint(client, "Projects/sympose", VIOLET)
    res = client.patch("/api/vault/folder/move", json={"path": "Projects/sympose", "destination": "Projects/stylo", "persona": "samantha"})
    assert res.status_code == 200 and "folder colour carried along" in res.json()["detail"]
    assert frontmatter(vault)["subfolders"] == {"stylo/sympose": VIOLET}


def test_moving_a_folder_to_another_top_level_folder_takes_its_colour_to_that_note(env):
    client, vault = env
    paint(client, "Projects/sympose", VIOLET)
    res = client.patch("/api/vault/folder/move", json={"path": "Projects/sympose", "destination": "Notes", "persona": "samantha"})
    assert res.status_code == 200
    assert "subfolders" not in frontmatter(vault)
    assert frontmatter(vault, "Notes/Notes.md") == {"subfolders": {"sympose": VIOLET}}


def test_renaming_a_top_level_folder_keeps_its_entries_because_the_note_goes_with_it(env):
    client, vault = env
    paint(client, "Projects/sympose", VIOLET)
    res = client.patch("/api/vault/folder", json={"path": "Projects", "new_name": "Work", "persona": "samantha"})
    assert res.status_code == 200
    assert frontmatter(vault, "Work/Work.md")["subfolders"] == {"sympose": VIOLET}
    assert nodes(client)["Work/sympose/Plan.md"]["colored_by"] == "Work/sympose"


ROCKET = {"icon": "rocket"}


def test_the_put_route_writes_and_the_get_route_reads_an_icon_with_the_colours(env):
    client, vault = env
    assert paint(client, "Projects/sympose", {**VIOLET, **ROCKET}).status_code == 200
    assert frontmatter(vault)["subfolders"] == {"sympose": {**VIOLET, **ROCKET}}
    got = client.get("/api/vault/folder/color", params={"path": "Projects/sympose", "persona": "samantha"}).json()
    assert got == {"editable": True, **VIOLET, **ROCKET}


def test_the_put_route_refuses_an_icon_the_app_does_not_have(env):
    client, vault = env
    before = (vault / "Projects/Projects.md").read_text()
    assert paint(client, "Projects/sympose", {"icon": "no-such-icon-here"}).status_code == 400
    assert (vault / "Projects/Projects.md").read_text() == before


def test_a_tree_folder_carries_its_own_icon_and_a_neighbour_does_not(env):
    client, _ = env
    paint(client, "Projects/sympose", ROCKET)
    tree = client.get("/api/vault/tree", params={"persona": "samantha"}).json()["tree"]
    assert folder(tree, "Projects/sympose")["icon"] == "rocket"
    assert "icon" not in folder(tree, "Projects/stylo")
    assert "icon" not in folder(tree, "Projects/sympose/decisions")
    assert folder(tree, "Projects")["icon"] == "folder-library"


def test_an_icon_does_not_colour_the_nebula_nor_reach_a_note_s_node(env):
    client, _ = env
    paint(client, "Projects/sympose", ROCKET)
    node = nodes(client)["Projects/sympose/Plan.md"]
    assert node["accent"] == "#0284c7" and "colored_by" not in node and "icon" not in node
    paint(client, "Projects/sympose", {**VIOLET, **ROCKET})
    node = nodes(client)["Projects/sympose/Plan.md"]
    assert node["accent"] == VIOLET["accent"] and node["colored_by"] == "Projects/sympose" and "icon" not in node
