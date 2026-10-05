"""What a folder move would do and what it needs the user's word for (docs/decisions/074, slice 1): read only, on a
scratch vault and scratch personas. Nothing here moves a file."""

from pathlib import Path

import pytest
from helpers import write_persona

from sympose.persona_files import profiles_dir
from sympose.profile import get_profile
from sympose.vault_move_folder_plan import OK, plan_move
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_INVALID_NAME, NOTE_NOT_FOUND

FILES = {
    "People/Anna.md": "Anna\n",
    "People/People.md": "# People\n",
    "People/Sub/Ben.md": "Ben\n",
    "People/photo.png": "x",
    "Archive/Old.md": "old\n",
    "Other/Note.md": "Other\n",
    "Other/Deep/Deeper.md": "Deeper\n",
    "Other/Deep/More.md": "More\n",
    "Garden/Garden.md": "# Garden\n",
    "Garden/Plants/Plants.md": "# Plants\n",
    "Garden/Plants/Rose.md": "Rose\n",
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for rel, text in FILES.items():
        (vault / rel).parent.mkdir(parents=True, exist_ok=True)
        (vault / rel).write_text(text)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "ada", "name: Ada\nvault_folders: ['People', 'Other']\n")
    write_persona(profiles, "grace", "name: Grace\nvault_folders: ['Other']\n")
    write_persona(profiles, "sam", "name: Sam\nvault_folders: ['Archive']\n")
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return vault


def profiles_dir_path():
    return Path(profiles_dir())


def plan(path, destination, persona="samantha"):
    return plan_move(get_profile(persona), path, destination)


def reach(path, destination):
    status, got = plan(path, destination)
    assert status == OK
    return {r.handle: (r.gains, r.loses) for r in got.reach}


def test_a_plain_move_is_planned_with_nothing_to_ask(env):
    (env / "Other/Box").mkdir()

    status, got = plan("Other/Deep", "Other/Box")

    assert status == OK
    assert (got.path, got.destination, got.new_path) == ("Other/Deep", "Other/Box", "Other/Box/Deep")
    assert got.clash is False and got.note_clashes == () and got.reach == () and got.definition is None


def test_the_plan_says_what_it_found_when_there_is_something_to_ask(env):
    status, got = plan("People", "Archive")

    assert status == OK and got.new_path == "Archive/People"
    assert [(r.handle, r.gains) for r in got.reach] == [("sam", 3)] and got.definition == "stops"


def test_a_folder_can_go_to_the_vault_root(env):
    status, got = plan("People/Sub", "")

    assert status == OK and got.new_path == "Sub"


def test_a_missing_folder_or_destination_is_not_found(env):
    assert plan("Nope", "Archive")[0] == NOTE_NOT_FOUND
    assert plan("People", "Nope")[0] == NOTE_NOT_FOUND
    assert plan("People/Anna.md", "Archive")[0] == NOTE_NOT_FOUND  # a note is not a folder
    assert plan("People", "Archive/Old.md")[0] == NOTE_NOT_FOUND  # nor a destination


@pytest.mark.parametrize("path", ["", ".", ".obsidian", "People/../..", "../outside"])
def test_the_vault_root_and_what_is_outside_it_cannot_be_moved(env, path):
    assert plan(path, "Archive")[0] == NOTE_DENIED


def test_a_dot_folder_is_neither_moved_nor_a_destination(env):
    (env / ".hidden").mkdir()
    assert plan(".hidden", "Archive")[0] == NOTE_DENIED
    assert plan("People", ".hidden")[0] == NOTE_DENIED


def test_a_folder_stays_inside_the_asking_personas_sandbox(env):
    assert plan("Archive", "Other", "grace")[0] == NOTE_DENIED  # the folder is not hers
    assert plan("Other/Deep", "Archive", "grace")[0] == NOTE_DENIED  # the destination is not hers
    assert plan("Other/Deep", "", "grace")[0] == NOTE_DENIED  # nor is the vault root
    assert plan("Other/Deep", "Other", "grace")[0] == NOTE_INVALID_NAME  # her own folder is (and it is where it already is)


@pytest.mark.parametrize("path, destination", [("People", "People"), ("People", "People/Sub"), ("People/Sub", "People"), ("Other/Deep", "Other")])
def test_a_folder_cannot_go_into_itself_into_its_own_subfolder_or_where_it_already_is(env, path, destination):
    assert plan(path, destination)[0] == NOTE_INVALID_NAME


def test_a_file_with_the_folders_name_at_the_destination_is_refused(env):
    (env / "Archive" / "People").write_text("not a folder")
    assert plan("People", "Archive")[0] == NOTE_EXISTS


def test_a_folder_of_that_name_at_the_destination_is_a_clash(env):
    (env / "Archive" / "People").mkdir()
    status, got = plan("People", "Archive")

    assert status == OK and got.clash is True and got.new_path == "Archive/People"
    assert got.note_clashes == ()  # nothing in it yet


def test_a_merge_lists_the_files_that_are_in_both_at_any_depth_and_only_those(env):
    for rel in ("Archive/People/Anna.md", "Archive/People/Sub/Ben.md", "Archive/People/Sub/Other.md", "Archive/People/photo.png"):
        (env / rel).parent.mkdir(parents=True, exist_ok=True)
        (env / rel).write_text("there")

    status, got = plan("People", "Archive")

    assert status == OK and got.clash is True
    assert got.note_clashes == ("Anna.md", "Sub/Ben.md", "photo.png")  # People.md is not there; a folder in both is merged, not a clash


def test_a_file_where_the_other_side_has_a_folder_is_a_clash(env):
    (env / "Archive/People/Sub").mkdir(parents=True)
    (env / "Archive/People/Anna.md").mkdir()  # a folder where the incoming Anna.md would go

    assert plan("People", "Archive")[1].note_clashes == ("Anna.md",)


def test_a_hidden_folder_is_not_walked_for_clashes(env):
    for rel in ("People/.obsidian/app.json", "Archive/People/.obsidian/app.json"):
        (env / rel).parent.mkdir(parents=True, exist_ok=True)
        (env / rel).write_text("{}")

    assert plan("People", "Archive")[1].note_clashes == ()


def test_hidden_files_are_not_clashes_and_there_are_none_without_a_folder_clash(env):
    (env / "Archive/People").mkdir()
    (env / "Archive/People/.DS_Store").write_text("a")
    (env / "People/.DS_Store").write_text("b")

    assert plan("People", "Archive")[1].note_clashes == ()
    assert plan("Other", "Archive")[1].note_clashes == ()


def test_a_move_that_stays_inside_everyones_scope_changes_nobodys_reach(env):
    (env / "Other/Box").mkdir()
    assert reach("Other/Deep", "Other/Box") == {}


def test_a_persona_gains_the_notes_of_a_folder_moved_into_her_scope(env):
    # People holds three notes (Anna, People, Ben; the photo is not a note); Grace is scoped to Other
    assert reach("People", "Other") == {"grace": (3, 0)}


def test_a_persona_loses_the_notes_of_a_folder_moved_out_of_her_scope(env):
    # Other/Deep holds two notes; Ada and Grace read Other, Sam reads Archive
    assert reach("Other/Deep", "Archive") == {"ada": (0, 2), "grace": (0, 2), "sam": (2, 0)}


def test_a_scope_that_names_the_moved_folder_follows_it_so_that_persona_is_not_listed(env):
    # Ada names People: her scope becomes Archive/People, so she reads those notes before and after
    assert reach("People", "Archive") == {"sam": (3, 0)}


def test_a_scope_that_names_a_folder_inside_the_moved_one_follows_it_too(env):
    write_persona(profiles_dir_path(), "ben", "name: Ben\nvault_folders: ['People/Sub']\n")

    assert reach("People", "Archive") == {"sam": (3, 0)}  # Ben's People/Sub became Archive/People/Sub: he keeps Ben.md and gains nothing


def test_the_whole_vault_scope_is_never_listed(env):
    assert "samantha" not in reach("Other/Deep", "Archive")
    assert "samantha" not in reach("People", "Other")


def test_reach_lists_personas_in_name_order_not_handle_order(env):
    write_persona(profiles_dir_path(), "zz", "name: Aaron\nvault_folders: ['Archive']\n")

    got = plan("Other/Deep", "Archive")[1].reach

    assert [r.name for r in got] == ["Aaron", "Ada", "Grace", "Sam"]


def test_notes_in_a_hidden_folder_inside_the_moved_one_are_not_counted(env):
    (env / "People/.obsidian").mkdir()
    (env / "People/.obsidian/Hidden.md").write_text("h")

    assert reach("People", "Other") == {"grace": (3, 0)}


def test_a_folder_that_cannot_have_a_definition_never_reports_one(env):
    for rel in ("Templates/Templates.md", "Templates/Note template.md"):
        (env / rel).parent.mkdir(exist_ok=True)
        (env / rel).write_text("t")

    assert plan("Templates", "Archive")[1].definition is None


def test_a_definition_that_stops_applying_is_reported_for_a_top_level_folder_going_below_the_top(env):
    assert plan("Garden", "Archive")[1].definition == "stops"


def test_the_stops_definition_message_is_for_a_top_level_folder_with_one_that_goes_below_the_top(env):
    assert plan("People", "Archive")[1].definition == "stops"
    assert plan("Archive", "Other")[1].definition is None  # nothing named Archive.md in it
    assert plan("Other", "Archive")[1].definition is None


def test_a_definition_starts_counting_when_a_folder_with_one_reaches_the_top(env):
    assert plan("Garden/Plants", "")[1].definition == "starts"
    assert plan("People/Sub", "")[1].definition is None  # no Sub/Sub.md


def test_the_plan_moves_nothing(env):
    before = sorted(str(p.relative_to(env)) for p in env.rglob("*"))
    plan("People", "Archive")
    assert sorted(str(p.relative_to(env)) for p in env.rglob("*")) == before
