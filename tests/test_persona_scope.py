"""A renamed folder in the personas' own folder scopes (docs/decisions/073): each persona whose `vault_folders` names the
folder, or one inside it, has the entry rewritten in her own `persona.yaml` -- only that entry, comments and layout kept
-- and the user is told who changed and who could not be."""

import yaml
from helpers import write_persona

from sympose import persona_scope


def setup(tmp_path, monkeypatch, personas):
    base = tmp_path / "profiles"
    for handle, body in personas.items():
        write_persona(base, handle, body)
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def text_of(base, handle):
    return (base / handle / "persona.yaml").read_text()


def scope_of(base, handle):
    return yaml.safe_load(text_of(base, handle))["vault_folders"]


def test_a_scalar_entry_a_flow_list_and_a_block_list_are_each_rewritten(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {
        "one": "name: One\nvault_folders: 'People'\n",
        "two": "name: Two\nvault_folders: ['People', \"Code\"]\n",
        "three": "name: Three\nvault_folders:\n  - Code\n  - People\n",
    })

    changed, stuck = persona_scope.rename_folder("People", "Team")

    assert sorted(changed) == ["One", "Three", "Two"] and stuck == []
    assert scope_of(base, "one") == "Team"
    assert scope_of(base, "two") == ["Team", "Code"]
    assert scope_of(base, "three") == ["Code", "Team"]


def test_only_the_entry_changes_comments_quotes_and_the_rest_of_the_file_stay(tmp_path, monkeypatch):
    body = "# my persona\nname: Ada   # her name\nvault_folders: [\"People\", 'Code']   # where she may look\nmodel: x\n"
    base = setup(tmp_path, monkeypatch, {"ada": body})

    persona_scope.rename_folder("People", "Team")

    assert text_of(base, "ada") == body.replace('"People"', '"Team"')


def test_a_folder_inside_the_renamed_one_follows_and_a_neighbour_with_the_same_start_does_not(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {"ada": "name: Ada\nvault_folders: ['People/Sub', 'People and Pets', 'Other/People']\n"})

    changed, _ = persona_scope.rename_folder("People", "Team")

    assert changed == ["Ada"]
    assert scope_of(base, "ada") == ["Team/Sub", "People and Pets", "Other/People"]


def test_the_whole_vault_scope_and_unrelated_scopes_are_untouched_and_not_reported(tmp_path, monkeypatch):
    body_all, body_other = "name: All\nvault_folders: '*'\n", "name: Other\nvault_folders: ['Code']\n"
    base = setup(tmp_path, monkeypatch, {"all": body_all, "other": body_other})

    assert persona_scope.rename_folder("People", "Team") == ([], [])
    assert (text_of(base, "all"), text_of(base, "other")) == (body_all, body_other)


def test_the_older_singular_key_is_followed_too(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {"old": "name: Old\nvault_folder: People\n"})

    changed, _ = persona_scope.rename_folder("People", "Team")

    assert changed == ["Old"] and yaml.safe_load(text_of(base, "old"))["vault_folder"] == "Team"


def test_a_bare_entry_is_matched_whole_not_inside_a_longer_name(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {"ada": "name: Ada\nvault_folders: [People, PeopleX, XPeople]\n"})

    persona_scope.rename_folder("People", "Team")

    assert scope_of(base, "ada") == ["Team", "PeopleX", "XPeople"]


def test_an_entry_that_would_not_read_back_as_written_leaves_the_file_as_it_was_and_is_reported(tmp_path, monkeypatch):
    body = "name: Ada\nvault_folders: People\n"
    base = setup(tmp_path, monkeypatch, {"ada": body})

    changed, stuck = persona_scope.rename_folder("People", "Team: Two")  # `vault_folders: Team: Two` is not valid YAML

    assert (changed, stuck) == ([], ["Ada"]) and text_of(base, "ada") == body


def test_a_file_that_cannot_be_written_is_reported_and_the_others_still_change(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {"ada": "name: Ada\nvault_folders: People\n", "bo": "name: Bo\nvault_folders: People\n"})
    real = persona_scope.write_atomic_text

    def write(path, text, *a, **k):
        if "/ada/" in str(path):
            raise OSError("read-only")
        return real(path, text, *a, **k)

    monkeypatch.setattr(persona_scope, "write_atomic_text", write)

    changed, stuck = persona_scope.rename_folder("People", "Team")

    assert (changed, stuck) == (["Bo"], ["Ada"]) and scope_of(base, "bo") == "Team" and scope_of(base, "ada") == "People"


def test_a_persona_file_that_is_not_yaml_is_skipped_without_a_word(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {"bad": "name: [unclosed\n", "ok": "name: Ok\nvault_folders: People\n"})

    changed, stuck = persona_scope.rename_folder("People", "Team")

    assert (changed, stuck) == (["Ok"], []) and text_of(base, "bad") == "name: [unclosed\n"


def test_a_persona_without_a_name_is_reported_by_her_handle(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, {"grace": "vault_folders: People\n"})

    assert persona_scope.rename_folder("People", "Team")[0] == ["grace"]


def test_a_nested_folder_is_matched_by_its_whole_path(tmp_path, monkeypatch):
    base = setup(tmp_path, monkeypatch, {"ada": "name: Ada\nvault_folders: ['A/People', 'People']\n"})

    persona_scope.rename_folder("A/People", "A/Team")

    assert scope_of(base, "ada") == ["A/Team", "People"]


def test_the_same_word_under_another_key_or_in_a_comment_is_not_a_scope_and_is_left_alone(tmp_path, monkeypatch):
    body = "# People is the folder she may read\nname: Ada\nvault_folders:\n  - People   # this one\nnickname: People\ngoal: People\n"
    base = setup(tmp_path, monkeypatch, {"ada": body})

    persona_scope.rename_folder("People", "Team")

    assert text_of(base, "ada") == body.replace("  - People   # this one", "  - Team   # this one")

