"""Setting up a new root folder (docs/decisions/038): a definition written from what the user typed, what is
refused so the note stays readable, that nothing existing is replaced, and the two routes. Everything runs in a
temporary vault, profile directory and settings file."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import generic_template, server_definition_handlers, settings_store
from sympose.server import create_app
from sympose.server_models import FolderDefinition
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS, NOTE_NOT_FOUND

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


# --- write_own ------------------------------------------------------------------------------


def test_the_typed_purpose_and_lines_become_the_definition(vault):
    result = write_defs.write_own(ALL, "Books", "What I read.", LINES)
    assert result == f"Created note: `{os.path.join('Books', 'Books.md')}`"
    text = read(vault, "Books/Books.md")
    assert text == '# Books\n\nWhat I read.\n\n## Template\n\n```yaml\ntitle: "{{title}}"\ncreated: {{date}}\ntags: []\n```\n'


def test_what_is_written_reads_back_through_the_readers_the_rest_of_sympose_uses(vault):
    write_defs.write_own(ALL, "Books", "What I read.", LINES)
    text = read(vault, "Books/Books.md")
    assert defs.read_purpose(text) == "What I read."
    assert defs.read_template(text) == "\n".join(LINES)


def test_a_definition_without_a_purpose_has_only_the_template(vault):
    write_defs.write_own(ALL, "Books", "  ", LINES)
    assert read(vault, "Books/Books.md").startswith("# Books\n\n## Template")


def test_a_definition_without_lines_has_an_empty_block(vault):
    write_defs.write_own(ALL, "Books", "What I read.", ["", "  "])
    assert read(vault, "Books/Books.md").endswith("```yaml\n```\n")


def test_lines_are_split_and_stripped_of_blank_ones_and_trailing_space(vault):
    write_defs.write_own(ALL, "Books", "", ["title: a  \n\nrole:", "  ", "tags: []"])
    assert defs.read_template(read(vault, "Books/Books.md")) == "title: a\nrole:\ntags: []"


def test_an_existing_definition_is_never_replaced(vault):
    write_defs.write_own(ALL, "Books", "First.", LINES)
    assert write_defs.write_own(ALL, "Books", "Second.", LINES) == NOTE_EXISTS
    assert "First." in read(vault, "Books/Books.md")


def test_the_folder_must_exist_and_nothing_is_created_for_one_that_does_not(vault):
    assert write_defs.write_own(ALL, "Nope", "x", LINES) == NOTE_NOT_FOUND
    assert not os.path.exists(os.path.join(vault, "Nope"))


@pytest.mark.parametrize("folder", ["", "Templates", ".obsidian", "Books/Sub", "Books\\Sub", ".hidden"])
def test_only_a_top_level_folder_of_the_users_content_can_have_one(vault, folder):
    os.makedirs(os.path.join(vault, "Templates"), exist_ok=True)
    os.makedirs(os.path.join(vault, ".obsidian"), exist_ok=True)
    with pytest.raises(write_defs.Refused, match="not a folder that can have a definition"):
        write_defs.write_own(ALL, folder, "x", LINES)


def test_a_persona_scoped_away_from_the_folder_is_told_what_a_missing_folder_is_told(vault):
    scoped = {"vault_folders": ["Other"]}
    os.makedirs(os.path.join(vault, "Other"))
    assert write_defs.write_own(scoped, "Books", "x", LINES) == NOTE_NOT_FOUND  # exists, but not for this persona
    assert write_defs.write_own(scoped, "Nope", "x", LINES) == NOTE_NOT_FOUND  # does not exist
    assert not os.path.exists(os.path.join(vault, "Books", "Books.md"))


def test_a_persona_may_write_in_a_folder_of_its_own_scope(vault):
    os.makedirs(os.path.join(vault, "Other"))
    result = write_defs.write_own({"vault_folders": ["Other"]}, "Other", "x", LINES)
    assert result.startswith("Created note:")


def test_a_folder_that_is_a_file_is_not_a_folder(vault):
    open(os.path.join(vault, "Plain"), "w").close()
    assert write_defs.write_own(ALL, "Plain", "x", LINES) == NOTE_NOT_FOUND


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
    with pytest.raises(ValueError):
        write_defs.write_own(ALL, "Books", purpose, template)
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


def test_the_generic_template_route_answers_the_setting_and_says_so(client):
    response = client.get("/api/vault/note-template")
    assert response.status_code == 200
    assert response.json() == {"lines": LINES, "source": "settings"}


def test_the_generic_template_route_answers_the_vaults_own_file_when_it_has_one(client, vault):
    os.makedirs(os.path.join(vault, "Templates"))
    with open(os.path.join(vault, "Templates", "Note template.md"), "w", encoding="utf-8") as f:
        f.write("---\ntitle: {{title}}\nstatus: new\n---")
    assert client.get("/api/vault/note-template").json() == {"lines": ["title: {{title}}", "status: new"], "source": "vault"}


def test_the_generic_template_route_follows_the_users_keys(client):
    settings_store.set(generic_template.KEYS_SETTING, ["title", "aliases"])
    assert client.get("/api/vault/note-template").json()["lines"] == ['title: "{{title}}"', "aliases:"]


def test_the_definition_route_writes_the_note_and_answers_201(client, vault):
    response = client.post("/api/vault/folder/definition", json={"path": "Books", "purpose": "What I read.", "template": LINES})
    assert response.status_code == 201
    assert response.json()["path"] == "Books"
    assert defs.read_purpose(read(vault, "Books/Books.md")) == "What I read."


def test_the_definition_route_answers_409_when_one_exists(client):
    body = {"path": "Books", "purpose": "x", "template": LINES}
    assert client.post("/api/vault/folder/definition", json=body).status_code == 201
    response = client.post("/api/vault/folder/definition", json=body)
    assert response.status_code == 409 and "already has a definition" in response.json()["detail"]


def test_the_definition_route_answers_404_for_a_folder_that_is_not_there(client):
    assert client.post("/api/vault/folder/definition", json={"path": "Nope", "template": LINES}).status_code == 404


def test_the_definition_route_answers_a_folder_outside_the_personas_scope_like_one_that_is_missing(client):
    scoped = client.post("/api/vault/folder/definition", json={"path": "Books", "template": LINES, "persona": "scoped"})
    missing = client.post("/api/vault/folder/definition", json={"path": "Nope", "template": LINES, "persona": "scoped"})
    assert (scoped.status_code, missing.status_code) == (404, 404)


def test_the_definition_route_answers_400_for_a_folder_that_cannot_have_one(client, vault):
    os.makedirs(os.path.join(vault, "Templates"))
    for path in ("Templates", "Books/Sub"):
        response = client.post("/api/vault/folder/definition", json={"path": path, "purpose": "x"})
        assert response.status_code == 400 and "not a folder that can have a definition" in response.json()["detail"]


def test_a_failed_write_is_not_reported_as_a_success(client, monkeypatch):
    monkeypatch.setattr(write_defs, "write", lambda profile, made: "Error: Failed to create note: disk full")
    response = client.post("/api/vault/folder/definition", json={"path": "Books", "purpose": "x"})
    assert response.status_code == 500 and "disk full" in response.json()["detail"]


def test_a_value_error_that_is_not_a_refusal_is_not_shown_as_a_400(vault, monkeypatch):
    def boom(profile, made):
        raise ValueError("internal detail")

    monkeypatch.setattr(write_defs, "write", boom)
    with pytest.raises(ValueError, match="internal detail") as caught:
        server_definition_handlers.write_definition(FolderDefinition(path="Books", purpose="x"))
    assert not isinstance(caught.value, write_defs.Refused)


def test_the_definition_route_answers_400_with_the_reason_for_a_refusal(client):
    response = client.post("/api/vault/folder/definition", json={"path": "Books", "template": ["```"]})
    assert response.status_code == 400 and "code fence" in response.json()["detail"]


def test_the_definition_route_answers_404_for_an_unknown_persona(client):
    assert client.post("/api/vault/folder/definition", json={"path": "Books", "persona": "ghost"}).status_code == 404


def test_the_definition_route_needs_a_path(client):
    assert client.post("/api/vault/folder/definition", json={"path": "", "template": []}).status_code == 422


def test_a_folder_with_a_typed_definition_is_not_offered_as_due(vault):
    for n in range(6):
        with open(os.path.join(vault, "Books", f"B{n}.md"), "w") as f:
            f.write("x")
    assert [f for f, _ in write_defs.due(ALL)] == ["Books"]
    write_defs.write_own(ALL, "Books", "What I read.", LINES)
    assert write_defs.due(ALL) == []


def test_a_note_created_in_the_folder_starts_from_the_typed_template(vault):
    from sympose import vault_write_create

    write_defs.write_own(ALL, "Books", "", ['title: "{{title}}"', "author:", "rating:"])
    vault_write_create.create_note(ALL, "Books/Dune")
    text = read(vault, "Books/Dune.md")
    assert text.startswith('---\ntitle: "Dune"\nauthor:\nrating:\n---')


# --- definable ------------------------------------------------------------------------------


def test_a_root_folder_of_the_users_content_without_a_definition_is_definable(vault):
    assert write_defs.definable(ALL, "Books") is True


@pytest.mark.parametrize("folder", ["", "Nope", "Templates", ".obsidian", "Books/Sub", "Books\\Sub", "Plain"])
def test_anything_else_is_not_definable(vault, folder):
    os.makedirs(os.path.join(vault, "Templates"), exist_ok=True)
    os.makedirs(os.path.join(vault, ".obsidian"), exist_ok=True)
    os.makedirs(os.path.join(vault, "Books", "Sub"), exist_ok=True)
    open(os.path.join(vault, "Plain"), "w").close()
    assert write_defs.definable(ALL, folder) is False


def test_a_folder_with_a_definition_is_not_definable(vault):
    write_defs.write_own(ALL, "Books", "x", LINES)
    assert write_defs.definable(ALL, "Books") is False


def test_a_folder_outside_the_personas_scope_is_not_definable(vault):
    assert write_defs.definable({"vault_folders": ["Other"]}, "Books") is False


def test_a_folder_the_persona_created_below_its_own_primary_folder_is_not_a_root_folder(vault):
    os.makedirs(os.path.join(vault, "Personas", "X", "Foo"))
    profile = {"vault_folders": ["Personas/X"]}
    assert write_defs.definable(profile, "Foo") is False  # `Foo` is not at the vault's root


def test_the_template_route_says_whether_a_folder_is_definable_only_when_asked(client, vault):
    assert "definable" not in client.get("/api/vault/note-template").json()
    assert client.get("/api/vault/note-template", params={"folder": "Books"}).json()["definable"] is True
    assert client.get("/api/vault/note-template", params={"folder": "Nope"}).json()["definable"] is False
    assert client.get("/api/vault/note-template", params={"folder": "Books", "persona": "scoped"}).json()["definable"] is False


def test_the_template_route_404s_an_unknown_persona_when_asked_about_a_folder(client):
    assert client.get("/api/vault/note-template", params={"folder": "Books", "persona": "ghost"}).status_code == 404


def test_no_vault_means_not_definable_and_not_found(vault, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")
    assert write_defs.definable(ALL, "Books") is False
    assert write_defs.write_own(ALL, "Books", "x", LINES) == NOTE_NOT_FOUND


def test_a_denial_from_the_writer_is_a_403_not_a_created_note(client, monkeypatch):
    monkeypatch.setattr(write_defs, "write", lambda profile, made: NOTE_DENIED)
    response = client.post("/api/vault/folder/definition", json={"path": "Books", "purpose": "x"})
    assert response.status_code == 403
