"""Giving a folder its first definition from the Folder settings dialog (docs/decisions/038, 087): a definition
written from what the user typed, what is refused so the note stays readable, who may do it, and the two routes.
Changing a definition that exists is `test_folder_settings_write.py`. Everything runs in a temporary vault, profile
directory and settings file."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import folder_settings_write as settings_write
from sympose import generic_template, settings_store
from sympose.folder_looks_write import Changed, Failed, Missing, Refused
from sympose.server import create_app
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

SETTINGS = "/api/vault/folder/settings"
ALL = {"vault_folders": ["*"]}
LINES = ['title: "{{title}}"', "created: {{date}}", "tags: []"]


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "Books").mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    write_persona(profiles, "scoped", "name: Scoped\nvault_folders: ['Other']\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


@pytest.fixture
def client(vault):
    return TestClient(create_app())


def read(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8") as f:
        return f.read()


def save(profile, folder, purpose="", template=(), **look):
    return settings_write.save(profile, folder, settings_write.Settings(purpose, list(template), **look))


# --- save, for a folder without a definition ------------------------------------------------


def test_the_typed_purpose_and_lines_become_the_definition(vault):
    assert save(ALL, "Books", "What I read.", LINES) is True
    text = read(vault, "Books/Books.md")
    assert text == '# Books\n\nWhat I read.\n\n## Template\n\n```yaml\ntitle: "{{title}}"\ncreated: {{date}}\ntags: []\n```\n'


def test_what_is_written_reads_back_through_the_readers_the_rest_of_sympose_uses(vault):
    save(ALL, "Books", "What I read.", LINES)
    text = read(vault, "Books/Books.md")
    assert defs.read_purpose(text) == "What I read."
    assert defs.read_template(text) == "\n".join(LINES)


def test_a_definition_without_a_purpose_has_only_the_template(vault):
    save(ALL, "Books", "  ", LINES)
    assert read(vault, "Books/Books.md").startswith("# Books\n\n## Template")


def test_a_definition_without_lines_has_an_empty_block(vault):
    save(ALL, "Books", "What I read.", ["", "  "])
    assert read(vault, "Books/Books.md").endswith("```yaml\n```\n")


def test_lines_are_split_and_stripped_of_blank_ones_and_trailing_space(vault):
    save(ALL, "Books", "", ["title: a  \n\nrole:", "  ", "tags: []"])
    assert defs.read_template(read(vault, "Books/Books.md")) == "title: a\nrole:\ntags: []"


def test_a_definition_made_while_the_dialog_was_open_is_not_replaced_by_a_create(vault, monkeypatch):
    save(ALL, "Books", "First.", LINES)
    monkeypatch.setattr(write_defs, "defined", lambda vault, folder: False)  # the dialog saw no definition
    with pytest.raises(Changed, match="got a description while this was open"):
        save(ALL, "Books", "Second.", LINES)
    assert "First." in read(vault, "Books/Books.md")


def test_the_folder_must_exist_and_nothing_is_created_for_one_that_does_not(vault):
    with pytest.raises(Missing):
        save(ALL, "Nope", "x", LINES)
    assert not os.path.exists(os.path.join(vault, "Nope"))


@pytest.mark.parametrize("folder", ["", "Templates", ".obsidian", "Books/Sub", "Books\\Sub", ".hidden"])
def test_only_a_top_level_folder_of_the_users_content_can_have_one(vault, folder):
    os.makedirs(os.path.join(vault, "Templates"), exist_ok=True)
    os.makedirs(os.path.join(vault, ".obsidian"), exist_ok=True)
    with pytest.raises(Refused, match="not a folder that can have a definition"):
        save(ALL, folder, "x", LINES)


def test_a_persona_scoped_away_from_the_folder_is_told_what_a_missing_folder_is_told(vault):
    scoped = {"vault_folders": ["Other"]}
    os.makedirs(os.path.join(vault, "Other"))
    with pytest.raises(Missing):  # exists, but not for this persona
        save(scoped, "Books", "x", LINES)
    with pytest.raises(Missing):  # does not exist
        save(scoped, "Nope", "x", LINES)
    assert not os.path.exists(os.path.join(vault, "Books", "Books.md"))


def test_a_persona_may_write_in_a_folder_of_its_own_scope(vault):
    os.makedirs(os.path.join(vault, "Other"))
    assert save({"vault_folders": ["Other"]}, "Other", "x", LINES) is True
    assert os.path.exists(os.path.join(vault, "Other", "Other.md"))


def test_a_folder_that_is_a_file_is_not_a_folder(vault):
    open(os.path.join(vault, "Plain"), "w").close()
    with pytest.raises(Missing):
        save(ALL, "Plain", "x", LINES)


# --- what is refused ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "purpose, template",
    [
        ("x", ["```"]),
        ("x", ["  ~~~yaml"]),
        ("x", ["a: b\n```\nmore"]),
        ("# A heading", []),
        ("Fine.\n## Template", []),
        ("Fine.\n  # indented heading", []),
        ("x" * (write_defs.MAX_PURPOSE + 1), []),
        ("x", ["a: b"] * (write_defs.MAX_LINES + 1)),
        ("x", ["a: " + "b" * write_defs.MAX_LINE]),
        ("", []),
        ("  ", ["", "  "]),
        ("x", ["---", "title:", "---"]),
        ("x", ["title:", "  ---  "]),
    ],
)
def test_a_definition_that_the_readers_could_not_read_back_is_refused_and_writes_nothing(vault, purpose, template):
    with pytest.raises(Refused):
        save(ALL, "Books", purpose, template)
    assert not os.path.exists(os.path.join(vault, "Books", "Books.md"))


@pytest.mark.parametrize(
    "purpose, template",
    [
        ("x" * write_defs.MAX_PURPOSE, []),
        ("Uses a # inside a line.", ["a: #tag"]),
        ("x", ["a: b"] * write_defs.MAX_LINES),
        ("x", ["a: " + "b" * (write_defs.MAX_LINE - 3)]),
        ("x", ["` one backtick", "``two"]),
        ("", ["title:"]),
        ("Only a purpose.", []),
        ("x", ["a: ---", "b: x---"]),
    ],
)
def test_the_limits_are_inclusive_and_a_hash_or_backticks_inside_a_line_are_fine(vault, purpose, template):
    assert write_defs.refusal(purpose, template) is None


# --- the routes -----------------------------------------------------------------------------


def put(client, **body):
    return client.put(SETTINGS, json=body)


def test_the_settings_route_starts_an_undefined_folder_from_the_generic_template_and_says_so(client):
    answer = client.get(SETTINGS, params={"folder": "Books"}).json()
    assert answer == {"editable": True, "defined": False, "purpose": "", "template": LINES, "template_source": "settings"}


def test_the_settings_route_starts_from_the_vaults_own_template_file_when_it_has_one(client, vault):
    os.makedirs(os.path.join(vault, "Templates"))
    with open(os.path.join(vault, "Templates", "Note template.md"), "w", encoding="utf-8") as f:
        f.write("---\ntitle: {{title}}\nstatus: new\n---")
    answer = client.get(SETTINGS, params={"folder": "Books"}).json()
    assert (answer["template"], answer["template_source"]) == (["title: {{title}}", "status: new"], "vault")


def test_the_settings_route_follows_the_users_keys(client):
    settings_store.set(generic_template.KEYS_SETTING, ["title", "aliases"])
    assert client.get(SETTINGS, params={"folder": "Books"}).json()["template"] == ['title: "{{title}}"', "aliases:"]


def test_the_settings_route_writes_the_note_and_says_it_was_created(client, vault):
    response = put(client, path="Books", purpose="What I read.", template=LINES, icon="book", accent="#1d4ed8")
    assert response.status_code == 200 and response.json() == {"path": "Books", "created": True}
    text = read(vault, "Books/Books.md")
    assert defs.read_purpose(text) == "What I read." and text.startswith("---\nicon: book\naccent: '#1d4ed8'\n---\n# Books")


def test_the_settings_route_edits_a_definition_that_exists_and_says_so(client, vault):
    put(client, path="Books", purpose="First.", template=LINES)
    response = put(client, path="Books", purpose="Second.", template=LINES)
    assert response.json() == {"path": "Books", "created": False} and "Second." in read(vault, "Books/Books.md")


def test_the_settings_route_answers_404_for_a_folder_that_is_not_there(client):
    assert put(client, path="Nope", template=LINES).status_code == 404


def test_the_settings_route_answers_a_folder_outside_the_personas_scope_like_one_that_is_missing(client):
    scoped = put(client, path="Books", template=LINES, persona="scoped")
    missing = put(client, path="Nope", template=LINES, persona="scoped")
    assert (scoped.status_code, missing.status_code) == (404, 404)


def test_the_settings_route_answers_400_for_a_folder_that_cannot_have_one(client, vault):
    os.makedirs(os.path.join(vault, "Templates"))
    for path in ("Templates", "Books/Sub"):
        response = put(client, path=path, purpose="x")
        assert response.status_code == 400 and "not a folder that can have a definition" in response.json()["detail"]


def test_a_failed_write_is_not_reported_as_a_success(client, monkeypatch):
    monkeypatch.setattr(write_defs, "write", lambda profile, made: "Error: Failed to create note: disk full")
    response = put(client, path="Books", purpose="x")
    assert response.status_code == 500 and "disk full" in response.json()["detail"]


def test_a_value_error_that_is_not_a_refusal_is_not_shown_as_a_400(client, monkeypatch):
    def boom(profile, made):
        raise ValueError("internal detail")

    monkeypatch.setattr(write_defs, "write", boom)
    with pytest.raises(ValueError, match="internal detail") as caught:
        put(client, path="Books", purpose="x")
    assert not isinstance(caught.value, Refused)


def test_the_settings_route_answers_400_with_the_reason_for_a_refusal(client):
    response = put(client, path="Books", template=["```"])
    assert response.status_code == 400 and "code fence" in response.json()["detail"]


def test_the_settings_route_answers_404_for_an_unknown_persona(client):
    assert put(client, path="Books", purpose="x", persona="ghost").status_code == 404
    assert client.get(SETTINGS, params={"folder": "Books", "persona": "ghost"}).status_code == 404


def test_the_settings_route_needs_a_path_and_a_folder(client):
    assert put(client, path="", template=[]).status_code == 422
    assert client.get(SETTINGS).status_code == 422


def test_a_denial_from_the_writer_is_a_400_not_a_created_note(client, monkeypatch):
    monkeypatch.setattr(write_defs, "write", lambda profile, made: NOTE_DENIED)
    assert put(client, path="Books", purpose="x").status_code == 400


def test_a_create_that_lost_the_race_is_a_409(client, monkeypatch):
    monkeypatch.setattr(write_defs, "write", lambda profile, made: NOTE_EXISTS)
    response = put(client, path="Books", purpose="x")
    assert response.status_code == 409 and "got a description" in response.json()["detail"]


def test_a_folder_with_a_typed_definition_is_not_offered_as_due(vault):
    for n in range(6):
        with open(os.path.join(vault, "Books", f"B{n}.md"), "w") as f:
            f.write("x")
    assert [f for f, _ in write_defs.due(ALL)] == ["Books"]
    save(ALL, "Books", "What I read.", LINES)
    assert write_defs.due(ALL) == []


def test_a_note_created_in_the_folder_starts_from_the_typed_template(vault):
    from sympose import vault_write_create

    save(ALL, "Books", "", ['title: "{{title}}"', "author:", "rating:"])
    vault_write_create.create_note(ALL, "Books/Dune")
    text = read(vault, "Books/Dune.md")
    assert text.startswith('---\ntitle: "Dune"\nauthor:\nrating:\n---')


# --- which folders have settings ------------------------------------------------------------


def editable(profile, folder):
    return settings_write.read(profile, folder)["editable"]


def test_a_root_folder_of_the_users_content_is_editable_with_or_without_a_definition(vault):
    assert editable(ALL, "Books") is True
    save(ALL, "Books", "x", LINES)
    assert editable(ALL, "Books") is True


@pytest.mark.parametrize("folder", ["", "Nope", "Templates", ".obsidian", "Books/Sub", "Books\\Sub", "Plain"])
def test_anything_else_is_not_editable(vault, folder):
    os.makedirs(os.path.join(vault, "Templates"), exist_ok=True)
    os.makedirs(os.path.join(vault, ".obsidian"), exist_ok=True)
    os.makedirs(os.path.join(vault, "Books", "Sub"), exist_ok=True)
    open(os.path.join(vault, "Plain"), "w").close()
    assert settings_write.read(ALL, folder) == {"editable": False}


def test_a_folder_outside_the_personas_scope_is_not_editable(vault):
    assert editable({"vault_folders": ["Other"]}, "Books") is False


def test_a_folder_the_persona_created_below_its_own_primary_folder_is_not_a_root_folder(vault):
    os.makedirs(os.path.join(vault, "Personas", "X", "Foo"))
    assert editable({"vault_folders": ["Personas/X"]}, "Foo") is False  # `Foo` is not at the vault's root


def test_the_settings_route_says_whether_a_folder_is_editable(client, vault):
    assert client.get(SETTINGS, params={"folder": "Books"}).json()["editable"] is True
    assert client.get(SETTINGS, params={"folder": "Nope"}).json() == {"editable": False}
    assert client.get(SETTINGS, params={"folder": "Books", "persona": "scoped"}).json() == {"editable": False}


def test_no_vault_means_not_editable_and_not_found(vault, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")
    assert editable(ALL, "Books") is False
    with pytest.raises(Missing):
        save(ALL, "Books", "x", LINES)


def test_the_settings_route_answers_409_when_there_is_no_vault(client, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")
    assert client.get(SETTINGS, params={"folder": "Books"}).status_code == 409


def test_a_look_alone_is_enough_for_a_first_definition(vault):
    assert save(ALL, "Books", icon="book") is True
    text = read(vault, "Books/Books.md")
    assert text.startswith("---\nicon: book\n---\n# Books") and defs.read_purpose(text) is None


@pytest.mark.parametrize(
    "look, reason",
    [
        ({"icon": "not-in-the-set"}, "not an icon Sympose has"),
        ({"icon": "Book"}, "not an icon Sympose has"),
        ({"accent": "red"}, "six hexadecimal digits"),
        ({"accent_dark": "#12345"}, "six hexadecimal digits"),
        ({"accent": "rgb(1,2,3)"}, "six hexadecimal digits"),
        ({"accent": "#fff\n---"}, "six hexadecimal digits"),
        ({"accent": "#1234567"}, "six hexadecimal digits"),
        ({"accent_dark": "#be123c\n"}, "six hexadecimal digits"),
    ],
)
def test_a_look_the_page_could_not_draw_is_refused_and_writes_nothing(vault, look, reason):
    with pytest.raises(Refused, match=reason):
        save(ALL, "Books", "x", LINES, **look)
    assert not os.path.exists(os.path.join(vault, "Books", "Books.md"))


def test_a_failed_create_is_a_failure_not_a_refusal(vault, monkeypatch):
    monkeypatch.setattr(write_defs, "write", lambda profile, made: "Error: disk full")
    with pytest.raises(Failed, match="disk full"):
        save(ALL, "Books", "x", LINES)
