"""The look (colours and icon) of folders below a top-level folder, kept in that folder's definition note (docs/decisions/090): what is
read from the note, the nearest coloured folder, the text edit that keeps every other line, the save the Folder look
dialog makes (an existing definition edited in place, a missing one created with only this property), and a renamed or
moved folder taking its entries with it. Everything runs in a temporary vault."""

import os

import pytest
from helpers import write_persona

from sympose import subfolder_colors as sc
from sympose.folder_looks_write import Changed, Refused

ALL = {"vault_folders": ["*"]}
PROJECTS = (
    "---\ntype: folder\nicon: folder-library\naccent: '#0284c7'\nsubfolders:\n  sympose:\n    accent: '#7c3aed'\n"
    "    accent_dark: '#b98cff'\n---\n# Projects\n\nWhat I build.\n\n## Template\n\n```yaml\nstatus:\n```\n\nMy closing remarks.\n"
)
VIOLET = {"accent": "#7c3aed", "accent_dark": "#b98cff"}
ROSE = {"accent": "#be123c", "accent_dark": "#f2889b"}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    for folder in ("Projects/sympose/decisions", "Projects/stylo", "Notes/old"):
        (root / folder).mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def put(vault, rel, text, newline=""):
    with open(os.path.join(vault, rel), "w", encoding="utf-8", newline=newline) as f:
        f.write(text)


def get(vault, rel="Projects/Projects.md"):
    with open(os.path.join(vault, rel), encoding="utf-8", newline="") as f:
        return f.read()


# --- reading ---------------------------------------------------------------------------------


def meta(text):
    from sympose.vault_snapshot import parse_frontmatter

    return parse_frontmatter(text)[0]


def test_reads_the_entries_of_a_note():
    assert sc.of_note(meta(PROJECTS)) == {"sympose": VIOLET}


@pytest.mark.parametrize(
    "front",
    [
        "subfolders: nope",
        "subfolders: [a, b]",
        "subfolders:\n  sympose: red",
        "subfolders:\n  sympose:\n    accent: red",
        "subfolders:\n  sympose:\n    accent: '#12345'",
        "subfolders:\n  ../x:\n    accent: '#123456'",
        "subfolders:\n  .git/x:\n    accent: '#123456'",
        "subfolders:\n  a//b:\n    accent: '#123456'",
        "subfolders:\n  '':\n    accent: '#123456'",
    ],
)
def test_a_value_of_the_wrong_shape_is_the_same_as_none(front):
    assert sc.of_note(meta(f"---\n{front}\n---\n")) == {}


def test_a_colour_that_is_half_set_keeps_the_half():
    assert sc.of_note(meta("---\nsubfolders:\n  a:\n    accent: '#123456'\n    accent_dark: nope\n---\n")) == {"a": {"accent": "#123456"}}


def test_a_key_is_read_whatever_slashes_it_is_written_with():
    found = sc.of_note(meta("---\nsubfolders:\n  /a/b/:\n    accent: '#123456'\n---\n"))
    assert list(found) == ["a/b"]


def test_colors_are_keyed_by_vault_path_and_only_from_the_definition_note():
    notes = [
        {"rel_path": "Projects/Projects.md", "meta": meta(PROJECTS)},
        {"rel_path": "Projects/other.md", "meta": meta(PROJECTS)},  # not the definition
        {"rel_path": "Notes/Notes.md", "meta": {"subfolders": {"old": {"accent": "#111111"}}}},
        {"rel_path": "Templates/Templates.md", "meta": {"subfolders": {"x": {"accent": "#222222"}}}},  # cannot have one
    ]
    assert sc.colors(notes) == {"Projects/sympose": VIOLET, "Notes/old": {"accent": "#111111"}}


def test_the_nearest_coloured_folder_wins():
    own = {"Projects/sympose": VIOLET, "Projects/sympose/decisions": ROSE}
    assert sc.nearest("Projects/sympose/decisions/a.md", own) == ("Projects/sympose/decisions", ROSE)
    assert sc.nearest("Projects/sympose/decisions/deep/a.md", own) == ("Projects/sympose/decisions", ROSE)
    assert sc.nearest("Projects/sympose/a.md", own) == ("Projects/sympose", VIOLET)
    assert sc.nearest("Projects/sympose/other/a.md", own) == ("Projects/sympose", VIOLET)


def test_a_note_with_no_coloured_folder_above_it_has_none():
    own = {"Projects/sympose": VIOLET}
    assert sc.nearest("Projects/stylo/a.md", own) is None
    assert sc.nearest("Projects/a.md", own) is None  # the top-level folder's own colour is not an entry
    assert sc.nearest("a.md", own) is None


# --- the text edit -----------------------------------------------------------------------------


def test_an_entry_is_added_and_every_other_line_stays():
    out = sc.with_entries(PROJECTS, {"stylo": ROSE})
    assert out is not None
    assert sc.of_note(meta(out)) == {"sympose": VIOLET, "stylo": ROSE}
    assert out.replace("  stylo:\n    accent: '#be123c'\n    accent_dark: '#f2889b'\n", "") == PROJECTS


def test_an_entry_is_changed_in_place_and_the_others_stay():
    out = sc.with_entries(PROJECTS, {"sympose": ROSE})
    assert sc.of_note(meta(out)) == {"sympose": ROSE}
    assert out.endswith(PROJECTS[PROJECTS.index("---\n# Projects") :])


def test_removing_the_last_entry_removes_the_property():
    out = sc.with_entries(PROJECTS, {"sympose": None})
    assert "subfolders" not in out
    assert out == PROJECTS.replace(
        "subfolders:\n  sympose:\n    accent: '#7c3aed'\n    accent_dark: '#b98cff'\n", ""
    )


def test_removing_what_is_not_there_changes_nothing():
    assert sc.with_entries(PROJECTS, {"nope": None}) == PROJECTS
    assert sc.with_entries("# Plain\n", {"nope": None}) == "# Plain\n"


def test_a_note_without_properties_gets_a_block():
    out = sc.with_entries("# Projects\n", {"sympose": VIOLET})
    assert out == "---\nsubfolders:\n  sympose:\n    accent: '#7c3aed'\n    accent_dark: '#b98cff'\n---\n# Projects\n"


def test_a_note_with_other_properties_gets_the_property_at_the_end_of_them():
    out = sc.with_entries("---\nicon: x\n---\nbody\n", {"a": {"accent": "#123456"}})
    assert out == "---\nicon: x\nsubfolders:\n  a:\n    accent: '#123456'\n---\nbody\n"


def test_an_entry_this_module_cannot_read_is_kept():
    text = "---\nsubfolders:\n  odd:\n    note: mine\n    accent: '#123456'\n---\n"
    out = sc.with_entries(text, {"sympose": VIOLET})
    assert "note: mine" in out
    assert sc.of_note(meta(out))["sympose"] == VIOLET


def test_a_hand_written_key_with_slashes_is_changed_not_duplicated():
    text = "---\nsubfolders:\n  /a/b/:\n    accent: '#123456'\n---\n"
    out = sc.with_entries(text, {"a/b": ROSE})
    assert out.count("accent:") == 1
    assert sc.of_note(meta(out)) == {"a/b": ROSE}


@pytest.mark.parametrize("text", ["---\nsubfolders: nope\n---\n", "---\nsubfolders:\n  - a\n---\n", "---\nicon: x\n# never closed\n"])
def test_a_note_it_cannot_edit_safely_is_refused(text):
    assert sc.with_entries(text, {"a": ROSE}) is None


def test_line_endings_stay():
    text = PROJECTS.replace("\n", "\r\n")
    out = sc.with_entries(text, {"sympose": ROSE})
    assert "\r\n" in out and "\n" not in out.replace("\r\n", "")


def test_the_colour_is_quoted_so_a_hash_is_not_a_comment():
    out = sc.with_entries("---\nicon: x\n---\n", {"a": {"accent": "#123456"}})
    assert "accent: '#123456'" in out


# --- saving ------------------------------------------------------------------------------------


def test_the_dialog_starts_from_the_folder_s_own_entry(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    assert sc.read(ALL, "Projects/sympose") == {"editable": True, **VIOLET, "icon": None}
    assert sc.read(ALL, "Projects/stylo") == {"editable": True, "accent": None, "accent_dark": None, "icon": None}


@pytest.mark.parametrize("path", ["Projects", "Nope/x", "Projects/missing", "Templates/x", "../x", "", ".git/x"])
def test_a_folder_that_cannot_be_coloured_is_not_editable(vault, path):
    os.makedirs(os.path.join(vault, "Templates", "x"), exist_ok=True)
    assert sc.read(ALL, path) == {"editable": False}


def test_saving_edits_the_existing_definition_in_place(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    assert sc.set_color(ALL, "Projects/stylo", ROSE) is False
    saved = get(vault)
    assert sc.of_note(meta(saved)) == {"sympose": VIOLET, "stylo": ROSE}
    assert "What I build." in saved and saved.endswith("My closing remarks.\n")


def test_clearing_removes_only_that_entry(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    sc.set_color(ALL, "Projects/stylo", ROSE)
    sc.set_color(ALL, "Projects/sympose", None)
    assert sc.of_note(meta(get(vault))) == {"stylo": ROSE}


def test_a_deeper_folder_is_coloured_too(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    sc.set_color(ALL, "Projects/sympose/decisions", ROSE)
    assert sc.of_note(meta(get(vault))) == {"sympose": VIOLET, "sympose/decisions": ROSE}


def test_a_folder_with_no_definition_gets_a_note_with_only_the_property(vault):
    assert sc.set_color(ALL, "Notes/old", ROSE) is True
    assert get(vault, "Notes/Notes.md") == "---\nsubfolders:\n  old:\n    accent: '#be123c'\n    accent_dark: '#f2889b'\n---\n# Notes\n"


def test_clearing_where_there_is_no_definition_creates_nothing(vault):
    assert sc.set_color(ALL, "Notes/old", None) is False
    assert not os.path.exists(os.path.join(vault, "Notes", "Notes.md"))


@pytest.mark.parametrize("look", [{"accent": "red"}, {"accent": "#12345"}, {}, {"nope": "#123456"}, {"accent": "#12345g"}])
def test_a_colour_that_is_not_a_hex_is_refused(vault, look):
    put(vault, "Projects/Projects.md", PROJECTS)
    with pytest.raises(Refused):
        sc.set_color(ALL, "Projects/stylo", look)
    assert get(vault) == PROJECTS


@pytest.mark.parametrize("path", ["Projects", "Nope/x", "Projects/missing", "../x", "Projects/.git"])
def test_a_folder_that_is_not_there_is_refused(vault, path):
    with pytest.raises(Refused):
        sc.set_color(ALL, path, ROSE)


def test_a_note_that_cannot_be_edited_safely_is_left_alone(vault):
    text = "---\nsubfolders: nope\n---\n# Projects\n"
    put(vault, "Projects/Projects.md", text)
    with pytest.raises(Refused):
        sc.set_color(ALL, "Projects/stylo", ROSE)
    assert get(vault) == text


def test_a_persona_without_the_folder_cannot_colour_it(vault):
    with pytest.raises(Refused):
        sc.set_color({"vault_folders": ["Notes"]}, "Projects/stylo", ROSE)


def test_a_note_that_changed_meanwhile_is_refused(vault, monkeypatch):
    put(vault, "Projects/Projects.md", PROJECTS)
    from sympose import folder_looks_write as flw

    monkeypatch.setattr(flw.vault_write, "overwrite_note", lambda *a, **k: flw.NOTE_CONFLICT)
    with pytest.raises(Changed):
        sc.set_color(ALL, "Projects/stylo", ROSE)
    assert get(vault) == PROJECTS


# --- following a rename or a move -------------------------------------------------------------


def move(vault, old, new):
    """What the vault has by the time `follow` runs: the directory is already at its new place."""
    os.makedirs(os.path.dirname(os.path.join(vault, new)), exist_ok=True)
    os.rename(os.path.join(vault, old), os.path.join(vault, new))


def two_entries(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    sc.set_color(ALL, "Projects/sympose/decisions", ROSE)


def test_a_rename_carries_the_folder_and_what_is_inside(vault):
    two_entries(vault)
    move(vault, "Projects/sympose", "Projects/sympose2")
    assert sc.follow(ALL, "Projects/sympose", "Projects/sympose2") == 2
    assert sc.of_note(meta(get(vault))) == {"sympose2": VIOLET, "sympose2/decisions": ROSE}


def test_a_folder_without_entries_moves_nothing(vault):
    two_entries(vault)
    before = get(vault)
    move(vault, "Projects/stylo", "Projects/stylo2")
    assert sc.follow(ALL, "Projects/stylo", "Projects/stylo2") == 0
    assert get(vault) == before


def test_a_top_level_rename_needs_nothing_because_the_note_moves_with_it(vault):
    two_entries(vault)
    move(vault, "Projects", "Work")
    assert sc.follow(ALL, "Projects", "Work") == 0


def test_a_move_to_another_top_level_folder_takes_the_entries_to_its_note(vault):
    two_entries(vault)
    put(vault, "Notes/Notes.md", "---\nicon: x\n---\n# Notes\n")
    move(vault, "Projects/sympose", "Notes/sympose")
    assert sc.follow(ALL, "Projects/sympose", "Notes/sympose") == 2
    assert sc.of_note(meta(get(vault))) == {}
    assert sc.of_note(meta(get(vault, "Notes/Notes.md"))) == {"sympose": VIOLET, "sympose/decisions": ROSE}
    assert "icon: x" in get(vault, "Notes/Notes.md")


def test_a_move_to_a_folder_with_no_note_makes_one(vault):
    two_entries(vault)
    move(vault, "Projects/sympose", "Notes/sympose")
    sc.follow(ALL, "Projects/sympose", "Notes/sympose")
    assert sc.of_note(meta(get(vault, "Notes/Notes.md"))) == {"sympose": VIOLET, "sympose/decisions": ROSE}


def test_a_move_into_a_folder_that_is_coloured_already_keeps_its_colour(vault):
    two_entries(vault)
    put(vault, "Notes/Notes.md", "---\nsubfolders:\n  sympose:\n    accent: '#111111'\n---\n# Notes\n")
    move(vault, "Projects/sympose", "Notes/sympose")
    sc.follow(ALL, "Projects/sympose", "Notes/sympose")
    assert sc.of_note(meta(get(vault, "Notes/Notes.md"))) == {"sympose": {"accent": "#111111"}, "sympose/decisions": ROSE}


def test_a_merge_inside_one_note_keeps_the_destination_s_colour(vault):
    two_entries(vault)
    sc.set_color(ALL, "Projects/stylo", {"accent": "#111111"})
    os.rmdir(os.path.join(vault, "Projects", "stylo"))
    move(vault, "Projects/sympose", "Projects/stylo")
    sc.follow(ALL, "Projects/sympose", "Projects/stylo")
    assert sc.of_note(meta(get(vault)))["stylo"] == {"accent": "#111111"}
    assert "sympose" not in sc.of_note(meta(get(vault)))


def test_a_folder_that_becomes_top_level_leaves_its_entries_behind_and_drops_them(vault):
    two_entries(vault)
    move(vault, "Projects/sympose", "sympose")
    sc.follow(ALL, "Projects/sympose", "sympose")
    assert sc.of_note(meta(get(vault))) == {}


# --- the icon ----------------------------------------------------------------------------------

ROCKET = {"icon": "rocket"}


def test_an_entry_may_hold_an_icon_alone_or_with_colours():
    front = "---\nsubfolders:\n  a:\n    icon: rocket\n  b:\n    icon: rocket\n    accent: '#123456'\n---\n"
    assert sc.of_note(meta(front)) == {"a": {"icon": "rocket"}, "b": {"icon": "rocket", "accent": "#123456"}}


@pytest.mark.parametrize("icon", ["Rocket Ship", "../x", "", 3, "a" * 41, "-x"])
def test_an_icon_of_the_wrong_shape_is_the_same_as_none(icon):
    assert sc.of_note(meta(f"---\nsubfolders:\n  a:\n    icon: {icon!r}\n    accent: '#123456'\n---\n")) == {"a": {"accent": "#123456"}}


def test_an_entry_with_only_a_bad_icon_is_left_out():
    assert sc.of_note(meta("---\nsubfolders:\n  a:\n    icon: '../x'\n---\n")) == {}


def test_an_icon_alone_colours_nothing_so_the_search_goes_on_past_it():
    own = {"Projects/sympose": VIOLET, "Projects/sympose/decisions": ROCKET}
    assert sc.nearest("Projects/sympose/decisions/a.md", own) == ("Projects/sympose", VIOLET)
    assert sc.nearest("Projects/stylo/a.md", {"Projects/stylo": ROCKET}) is None


def test_the_colour_of_an_entry_with_both_leaves_the_icon_out():
    own = {"Projects/sympose": {**VIOLET, **ROCKET}}
    assert sc.nearest("Projects/sympose/a.md", own) == ("Projects/sympose", VIOLET)


def test_the_text_edit_writes_the_icon_with_the_colours():
    text = sc.with_entries("# Projects\n", {"sympose": {**VIOLET, **ROCKET}})
    assert sc.of_note(meta(text)) == {"sympose": {**VIOLET, **ROCKET}}


def test_the_dialog_starts_from_the_folder_s_icon(vault):
    put(vault, "Projects/Projects.md", "---\nsubfolders:\n  stylo:\n    icon: rocket\n---\n# Projects\n")
    assert sc.read(ALL, "Projects/stylo") == {"editable": True, "accent": None, "accent_dark": None, "icon": "rocket"}


def test_saving_an_icon_with_colours_keeps_every_other_line(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    sc.set_color(ALL, "Projects/stylo", {**ROSE, **ROCKET})
    saved = get(vault)
    assert sc.of_note(meta(saved)) == {"sympose": VIOLET, "stylo": {**ROSE, **ROCKET}}
    assert "What I build." in saved and saved.endswith("My closing remarks.\n")


def test_an_icon_alone_can_be_saved_and_then_cleared(vault):
    put(vault, "Projects/Projects.md", PROJECTS)
    sc.set_color(ALL, "Projects/stylo", ROCKET)
    assert sc.of_note(meta(get(vault)))["stylo"] == ROCKET
    sc.set_color(ALL, "Projects/stylo", None)
    assert sc.of_note(meta(get(vault))) == {"sympose": VIOLET}


def test_an_icon_for_a_folder_with_no_definition_makes_the_note_too(vault):
    assert sc.set_color(ALL, "Notes/old", ROCKET) is True
    assert get(vault, "Notes/Notes.md") == "---\nsubfolders:\n  old:\n    icon: rocket\n---\n# Notes\n"


@pytest.mark.parametrize("icon", ["not-an-icon-sympose-has", "Rocket", "../x", ""])
def test_an_icon_the_app_does_not_have_is_refused(vault, icon):
    put(vault, "Projects/Projects.md", PROJECTS)
    with pytest.raises(Refused):
        sc.set_color(ALL, "Projects/stylo", {"icon": icon})
    assert get(vault) == PROJECTS


def test_a_renamed_folder_carries_its_icon(vault):
    put(vault, "Projects/Projects.md", "---\nsubfolders:\n  sympose:\n    icon: rocket\n---\n# Projects\n")
    os.rename(os.path.join(vault, "Projects/sympose"), os.path.join(vault, "Projects/symposium"))
    assert sc.follow(ALL, "Projects/sympose", "Projects/symposium") == 1
    assert sc.of_note(meta(get(vault))) == {"symposium": ROCKET}
