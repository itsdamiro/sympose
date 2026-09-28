"""The generic note template (docs/decisions/038): the setting's keys, the vault's own `Note template.md` winning,
the note a user gets when nothing else applies, and a quoted title placeholder that cannot break the frontmatter.
Everything runs in a temporary vault and settings file."""

import datetime
import os

import pytest
import yaml

from sympose import generic_template as generic
from sympose import settings_store, vault_write_create
from sympose.vault_snapshot import parse_frontmatter

ALL = {"vault_folders": ["*"]}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def put(vault, rel, text):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8") as f:
        return f.read()


# --- the setting ----------------------------------------------------------------------------


def test_the_keys_default_to_title_created_and_tags():
    assert generic.keys() == ["title", "created", "tags"]  # a literal: a test that reads the constant cannot fail


def test_a_users_keys_are_used_in_their_order_without_repeats():
    settings_store.set(generic.KEYS_SETTING, ["title", "aliases", "date created", "title"])
    assert generic.keys() == ["title", "aliases", "date created"]


@pytest.mark.parametrize(
    "bad",
    ["title", None, 3, [], ["created", "tags"], ["title", 3], ["title", ""], ["title", "a: b"], ["title", "x\ny"], ["title", "tags "], [" title"], ["title", " "], {"title": 1}],
)
def test_anything_but_a_list_of_property_names_with_a_title_leaves_the_default(bad):
    settings_store.set(generic.KEYS_SETTING, bad)
    assert generic.keys() == ["title", "created", "tags"]


def test_each_key_starts_as_its_placeholder_and_an_unknown_key_starts_empty():
    settings_store.set(generic.KEYS_SETTING, ["title", "created", "tags", "status"])
    assert generic.key_lines() == ['title: "{{title}}"', "created: {{date}}", "tags: []", "status:"]


def test_text_wraps_the_lines_as_frontmatter():
    assert generic.text() == '---\ntitle: "{{title}}"\ncreated: {{date}}\ntags: []\n---'


# --- where the lines come from --------------------------------------------------------------


def test_without_a_note_template_file_the_lines_come_from_the_setting(scratch):
    assert generic.lines_for(scratch) == (['title: "{{title}}"', "created: {{date}}", "tags: []"], "settings")


def test_a_note_template_file_wins_over_the_setting(scratch):
    put(scratch, "Templates/Note template.md", "---\ntitle: {{title}}\nstatus: new\n---\n\nbody")
    settings_store.set(generic.KEYS_SETTING, ["title", "aliases"])
    assert generic.lines_for(scratch) == (["title: {{title}}", "status: new"], "vault")


def test_a_note_template_file_without_frontmatter_is_not_used_for_the_lines(scratch):
    put(scratch, "Templates/Note template.md", "just a checklist")
    assert generic.lines_for(scratch)[1] == "settings"


def test_a_note_template_file_that_cannot_be_read_falls_back_to_the_setting(scratch):
    put(scratch, "Templates/Note template.md", "x")
    with open(os.path.join(scratch, "Templates", "Note template.md"), "wb") as f:
        f.write(b"---\ntitle: \xff\xfe\n---")  # not UTF-8
    assert generic.lines_for(scratch)[1] == "settings"


def test_a_vault_that_is_not_there_falls_back_to_the_setting(tmp_path):
    assert generic.lines_for(str(tmp_path / "nowhere"))[1] == "settings"


# --- the note a user gets -------------------------------------------------------------------


def test_a_note_with_no_template_starts_from_the_users_keys(scratch):
    settings_store.set(generic.KEYS_SETTING, ["title", "aliases", "tags"])
    vault_write_create.create_note(ALL, "Idea")
    meta, body = parse_frontmatter(read(scratch, "Idea.md"))
    assert list(meta) == ["title", "aliases", "tags"]
    assert meta["title"] == "Idea" and meta["tags"] == [] and meta["aliases"] is None
    assert body == "\n# Idea\n\n"


def test_the_created_key_is_todays_date(scratch):
    vault_write_create.create_note(ALL, "Idea")
    assert str(parse_frontmatter(read(scratch, "Idea.md"))[0]["created"]) == datetime.date.today().isoformat()


def test_the_vaults_note_template_still_wins_over_the_keys(scratch):
    put(scratch, "Templates/Note template.md", "---\ntitle: {{title}}\nstatus: new\n---")
    settings_store.set(generic.KEYS_SETTING, ["title", "aliases"])
    vault_write_create.create_note(ALL, "Idea")
    assert parse_frontmatter(read(scratch, "Idea.md"))[0] == {"title": "Idea", "status": "new"}


@pytest.mark.parametrize("title", ["A: B", 'Say "Hi" Now', "Café 日本", "Meeting #3"])
def test_a_quoted_title_placeholder_in_a_users_template_reads_back_as_the_title(scratch, title):
    put(scratch, "Templates/Note template.md", '---\ntitle: "{{title}}"\n---')
    vault_write_create.create_note(ALL, title)
    block = read(scratch, f"{title}.md").split("---")[1]
    assert yaml.safe_load(block)["title"] == title  # strict YAML: `parse_frontmatter` falls back to a line scan and would hide a break


def test_an_unquoted_title_placeholder_is_filled_as_it_always_was(scratch):
    put(scratch, "Templates/Note template.md", "---\ntitle: {{title}}\n---")
    vault_write_create.create_note(ALL, "Plain")
    assert "title: Plain\n" in read(scratch, "Plain.md")


# --- frontmatter_lines ----------------------------------------------------------------------


def test_frontmatter_lines_drops_blank_lines_and_trailing_space_and_stops_at_the_closing_rule():
    text = "---\ntitle: a  \n\n  \nrole:\t\n---\n\nbody\n---\nnot a property"
    assert generic.frontmatter_lines(text) == ["title: a", "role:"]


def test_frontmatter_lines_is_empty_without_an_opening_rule():
    assert generic.frontmatter_lines("title: a\n---") == []
    assert generic.frontmatter_lines("") == []


def test_frontmatter_lines_reads_a_block_that_is_never_closed_to_the_end():
    assert generic.frontmatter_lines("---\ntitle: a\ntags: []") == ["title: a", "tags: []"]
