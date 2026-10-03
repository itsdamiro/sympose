"""A top-level folder's look is read from its definition note's properties (docs/decisions/064)."""

import os
import pathlib
import re

import pytest

from sympose import folder_looks, vault_graph

WHOLE = {"vault_folders": ["*"]}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    root = tmp_path / "vault"
    root.mkdir()
    return str(root)


def _write(root, rel_path, content):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _note(rel_path, **meta):
    return {"rel_path": rel_path, "meta": meta}


def test_a_definition_notes_icon_and_colours_are_its_folders_look():
    notes = [_note("Movies/Movies.md", icon="film-roll", accent="#f2889b", accent_dark="#aa6677")]
    assert folder_looks.looks(notes) == {"Movies": {"icon": "film-roll", "accent": "#f2889b", "accent_dark": "#aa6677"}}


def test_only_the_keys_that_are_set_are_returned():
    assert folder_looks.looks([_note("Movies/Movies.md", icon="film-roll")]) == {"Movies": {"icon": "film-roll"}}


def test_a_value_of_an_unsafe_shape_is_the_same_as_none():
    notes = [_note("Movies/Movies.md", icon="x; y", accent="red; background:url(//evil)", accent_dark=3)]
    assert folder_looks.looks(notes) == {}


def test_a_note_that_is_not_the_folders_definition_has_no_say():
    notes = [
        _note("Movies/Alien.md", icon="film-roll"),  # an ordinary note
        _note("Movies/Sub/Sub.md", icon="film-roll"),  # a nested folder: definitions are top-level only
        _note("Movies.md", icon="film-roll"),  # at the root
    ]
    assert folder_looks.looks(notes) == {}


def test_the_case_of_the_definitions_name_is_ignored():
    assert folder_looks.looks([_note("Movies/movies.md", icon="film-roll")]) == {"Movies": {"icon": "film-roll"}}


def test_a_folder_that_cannot_have_a_definition_gets_no_look():
    assert folder_looks.looks([_note("Templates/Templates.md", icon="star")]) == {}


def test_the_tree_carries_the_look_on_the_top_level_folder_only(vault):
    _write(vault, "Movies/Movies.md", "---\nicon: film-roll\naccent: '#f2889b'\n---\nFilms.\n")
    _write(vault, "Movies/Sub/Alien.md", "x")
    _write(vault, "Books/Dune.md", "x")

    tree = {n["name"]: n for n in vault_graph.get_vault_tree(WHOLE)}

    assert (tree["Movies"]["icon"], tree["Movies"]["accent"]) == ("film-roll", "#f2889b")
    assert "icon" not in tree["Books"]
    sub = next(c for c in tree["Movies"]["children"] if c["name"] == "Sub")
    assert "icon" not in sub


def test_the_graph_carries_the_folders_colour_on_its_notes_and_not_the_icon(vault):
    _write(vault, "Movies/Movies.md", "---\nicon: film-roll\naccent: '#f2889b'\naccent_dark: '#aa6677'\n---\nFilms.\n")
    _write(vault, "Movies/Alien.md", "x")
    _write(vault, "Books/Dune.md", "x")

    nodes = {n["id"]: n for n in vault_graph.get_vault_graph(WHOLE)["nodes"]}

    assert (nodes["Movies/Alien.md"]["accent"], nodes["Movies/Alien.md"]["accent_dark"]) == ("#f2889b", "#aa6677")
    assert "icon" not in nodes["Movies/Alien.md"]
    assert "accent" not in nodes["Books/Dune.md"]


def _ts_table(path, start):
    """The text of the object or list in the web app's source file `path` that begins at `start`."""
    text = (pathlib.Path(__file__).resolve().parent.parent / "ui" / "src" / "lib" / path).read_text()
    block = text[text.index(start) :].split("\n}", 1)[0].split("\n]", 1)[0]
    return block


def test_the_built_in_looks_equal_the_web_apps_fallback_tables():
    """The vault health writes `BUILT_IN` into definitions, and the web app draws the same folders from its own
    tables until then: they must say the same thing, or the fix would change how a folder looks."""
    icons = dict(re.findall(r'name: "(\w+)", icon: "([\w-]+)"', _ts_table("vault-folders.ts", "export const VAULT_FOLDERS")))
    dark = dict(re.findall(r'(\w+): "(#[0-9a-f]{6})"', _ts_table("nebula-graph.ts", "export const FOLDER_COLORS:")))
    light = dict(re.findall(r'(\w+): "(#[0-9a-f]{6})"', _ts_table("nebula-graph.ts", "export const FOLDER_COLORS_LIGHT")))
    for folder, (icon, accent, accent_dark) in folder_looks.BUILT_IN.items():
        assert (icons.get(folder), light.get(folder), dark.get(folder)) == (icon, accent, accent_dark), folder
    assert set(icons) == set(folder_looks.BUILT_IN)


def test_a_colour_the_note_already_sets_is_not_offered_again():
    meta = {"accent": "#111111", "accent_dark": "#222222"}
    assert folder_looks.offer("Movies", [{"rel_path": "Movies/Movies.md", "meta": meta}]) == ["icon: film-roll"]


def test_a_note_below_a_folder_called_like_the_definition_is_not_the_definition():
    notes = [_note("Movies/Movies.md/Alien.md", icon="film-roll")]
    assert folder_looks.looks(notes) == {}
    assert folder_looks.offer("Movies", notes) == []
