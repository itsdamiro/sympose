"""Folder definitions (docs/decisions/033), stage 1: which folders are due, the template counted from a folder's
notes, the `## Template` block, drafting (writes nothing), writing (only on a call, never over a note), and the
template a new note starts from. Everything runs in a temporary vault and settings file."""

import os

import pytest

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import settings_store, vault_write_create
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

ALL = {"vault_folders": ["*"]}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def note(rel, **meta):
    return {"rel_path": rel, "file_name": os.path.basename(rel), "meta": meta, "body": ""}


def people(count, **meta):
    return [note(f"People/P{n}.md", **meta) for n in range(count)]


def put(vault, rel, text="x"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(vault, rel):
    with open(os.path.join(vault, rel), encoding="utf-8") as f:
        return f.read()


def tree(vault):
    return sorted(os.path.join(d, f) for d, _, files in os.walk(vault) for f in files)


# --- which folders are due ------------------------------------------------------------------


def test_a_top_level_folder_and_its_definition_path():
    assert defs.top_folder("People/Anna.md") == "People" and defs.top_folder("People/Deep/Anna.md") == "People"
    assert defs.top_folder("Loose.md") == "" and defs.top_folder("People\\Anna.md") == "People"
    assert defs.definition_path("People") == "People/People.md"


def test_a_folder_is_due_at_the_minimum_and_not_below_it():
    assert defs.due_folders(people(4), 5) == []
    assert defs.due_folders(people(5), 5) == [("People", 5)]


def test_notes_at_any_depth_count_once_and_the_definition_is_not_counted():
    notes = people(3) + [note("People/Old/A.md"), note("People/Old/Older/B.md")]
    assert defs.due_folders(notes, 5) == [("People", 5)]
    assert defs.due_folders(people(4) + [note("People/People.md")], 5) == []  # the definition is not a fifth note


def test_a_folder_with_a_definition_is_not_due():
    assert defs.due_folders(people(9) + [note("People/People.md")], 5) == []


def test_a_definition_in_another_folder_or_with_another_name_does_not_count():
    assert defs.due_folders(people(5) + [note("Other/People.md"), note("People/Sub/People.md")], 5) == [("People", 6)]


def test_only_the_users_own_folders_are_due():
    notes = [note(f"{f}/N{n}.md") for f in ("Templates", "templates", ".hidden", "Attachments") for n in range(6)]
    notes += [note(f"Loose{n}.md") for n in range(6)]

    assert defs.due_folders(notes, 5) == []


def test_the_fullest_folder_comes_first():
    notes = people(5) + [note(f"Books/B{n}.md") for n in range(7)] + [note(f"Art/A{n}.md") for n in range(5)]

    assert defs.due_folders(notes, 5) == [("Books", 7), ("Art", 5), ("People", 5)]


def test_the_minimum_is_a_setting_and_a_malformed_one_leaves_the_default():
    assert defs.min_notes() == 5
    settings_store.set(defs.MIN_NOTES_SETTING, 2)
    assert defs.min_notes() == 2 and defs.due_folders(people(2)) == [("People", 2)]
    for bad in (True, 0, -1, 2.5, "3", None, [3]):
        settings_store.set(defs.MIN_NOTES_SETTING, bad)
        assert defs.min_notes() == 5


# --- the template, counted --------------------------------------------------------------------


def test_a_property_is_in_the_template_at_the_share_and_not_below_it():
    notes = [note(f"P/N{n}.md", role="x" if n % 2 else "y", email="e" if n < 2 else None) for n in range(4)]
    notes = [note(f"P/N{n}.md", **({"role": n} | ({"email": f"e{n}"} if n < 2 else {}))) for n in range(4)]

    assert defs.template_lines(notes, "P", 0.5) == ["role:", "email:"]  # email is in 2 of 4
    assert defs.template_lines(notes, "P", 0.51) == ["role:"]
    assert defs.template_lines(notes, "P", 1.0) == ["role:"]


def test_the_most_common_first_and_the_first_seen_among_equals():
    notes = [note("P/A.md", b=1, a=1), note("P/B.md", a=2, c=1), note("P/C.md", a=3, c=2, b=2), note("P/D.md", c=3, b=3)]

    assert defs.template_lines(notes, "P", 0.5) == ["b:", "a:", "c:"]  # b in 3 (seen first), a in 3, c in 3
    assert defs.template_lines([note("P/A.md", z=1, y=1), note("P/B.md", y=2, x=1, z=2)], "P", 0.5) == ["z:", "y:", "x:"]


def test_a_value_every_note_holds_is_kept_and_a_value_that_differs_is_left_empty():
    notes = [note("P/A.md", type="person", role="a"), note("P/B.md", type="person", role="b")]

    assert defs.template_lines(notes, "P") == ["type: person", "role:"]


def test_a_value_only_some_notes_carry_is_theirs_and_not_the_folders():
    notes = [note("P/A.md", type="person", email="a@x"), note("P/B.md", type="person"), note("P/C.md", type="person", email="a@x")]

    assert defs.template_lines(notes, "P") == ["type: person", "email:"]  # both carriers agree, the folder does not


def test_a_constant_is_only_a_short_plain_value_of_one_kind():
    same = lambda **meta: [note("P/A.md", **meta), note("P/B.md", **meta)]  # noqa: E731
    assert defs.template_lines(same(n=3), "P") == ["n: 3"]
    assert defs.template_lines(same(tags=["a"]), "P") == ["tags:"]  # a list is not a constant
    assert defs.template_lines(same(long="x" * 61), "P") == ["long:"]
    assert defs.template_lines(same(short="x" * 60), "P") == ["short: " + "x" * 60]
    assert defs.template_lines([note("P/A.md", n=1), note("P/B.md", n=True)], "P") == ["n:"]  # 1 and true differ


def test_a_value_that_needs_quoting_is_written_as_valid_yaml():
    lines = defs.template_lines([note("P/A.md", note="a: b"), note("P/B.md", note="a: b")], "P")

    assert lines == ["note: 'a: b'"]


def test_notes_without_properties_count_toward_the_share():
    notes = [note("P/A.md", role="a"), note("P/B.md"), note("P/C.md"), note("P/D.md")]

    assert defs.template_lines(notes, "P", 0.5) == []  # 1 of 4


def test_a_property_name_that_is_not_a_plain_name_is_left_out():
    notes = [note(f"P/N{n}.md", **{"role": 1, "a:b": 1, "": 1, "x\ny": 1}) for n in range(2)]

    assert defs.template_lines(notes, "P") == ["role: 1"]


def test_the_definition_and_other_folders_are_not_counted():
    notes = [note("P/A.md", role="a"), note("P/B.md", role="b"), note("P/P.md", junk="j"), note("Q/A.md", other="o")]

    assert defs.template_lines(notes, "P") == ["role:"]
    assert defs.template_lines([], "P") == [] and defs.template_lines(notes, "Nothing") == []


def test_the_share_is_a_setting_and_a_malformed_one_leaves_the_default():
    assert defs.template_share() == 0.5
    settings_store.set(defs.SHARE_SETTING, 0.8)
    assert defs.template_share() == 0.8
    for bad in (True, 0, -0.5, 1.5, "0.8", None, float("inf")):
        settings_store.set(defs.SHARE_SETTING, bad)
        assert defs.template_share() == 0.5


# --- the Template block ---------------------------------------------------------------------


@pytest.mark.parametrize("heading", ["## Template", "# template", "###### TEMPLATE", "## Template ##"])
def test_the_template_is_the_first_block_under_a_heading_called_template(heading):
    assert defs.read_template(f"Purpose.\n\n{heading}\n\n```yaml\nrole:\nemail:\n```\n\nMore.") == "role:\nemail:"


def test_only_the_first_block_is_read_and_a_tilde_fence_works():
    assert defs.read_template("## Template\n\n~~~\na:\n~~~\n\n```\nb:\n```") == "a:"


def test_text_between_the_heading_and_the_block_is_allowed():
    assert defs.read_template("## Template\n\nEvery note starts with:\n\n```\na:\n```") == "a:"


@pytest.mark.parametrize(
    "body",
    ["", "no section", "## Template\n\n```\n```", "## Template\n\nnothing here", "## Template\n\n## Other\n\n```\na:\n```",
     "## Templates\n\n```\na:\n```", "## My Template\n\n```\na:\n```", "##Template\n\n```\na:\n```", "#template\n\n```\na:\n```"],
)
def test_no_section_an_empty_block_or_a_block_under_another_heading_is_no_template(body):
    assert defs.read_template(body) is None


def test_an_unclosed_block_reads_to_the_end_of_the_note():
    assert defs.read_template("## Template\n\n```\na:\nb:") == "a:\nb:"


def test_a_block_is_frontmatter_and_one_that_already_has_its_rules_is_left_as_it_is():
    assert defs.as_template("a:\nb:") == "---\na:\nb:\n---"
    assert defs.as_template("---\na:\n---") == "---\na:\n---"


def test_a_definition_reads_back_what_was_rendered():
    text = defs.render("People", ["role:", "type: person"], "People I know.")

    assert text.startswith("# People\n\nPeople I know.\n\n## Template") and defs.read_template(text) == "role:\ntype: person"


def test_no_purpose_means_none_is_written_and_no_lines_means_an_empty_block():
    assert defs.render("People", ["role:"]) == "# People\n\n## Template\n\n```yaml\nrole:\n```\n"
    assert defs.render("People", [], "  ") == "# People\n\n## Template\n\n```yaml\n```\n"
    assert defs.read_template(defs.render("People", [])) is None


# --- reading a definition from the vault -------------------------------------------------------


def test_the_template_of_a_folder_is_read_from_its_definition_only(scratch):
    put(scratch, "People/People.md", "# People\n\nWho.\n\n## Template\n\n```\nrole:\n```\n")
    put(scratch, "People/Other.md", "## Template\n\n```\nnope:\n```")

    assert defs.template_for_folder(scratch, "People") == "---\nrole:\n---"
    assert defs.template_for_folder(scratch, "Other") is None and defs.template_for_folder("", "People") is None


def test_a_definition_that_cannot_be_read_gives_no_template(scratch):
    with open(os.path.join(scratch, "Bad.md"), "wb"):
        pass
    put(scratch, "Bad/Bad.md")
    with open(os.path.join(scratch, "Bad/Bad.md"), "wb") as f:
        f.write(b"\xff\xfe## Template\n\n```\na:\n```")

    assert defs.template_for_folder(scratch, "Bad") is None


@pytest.mark.parametrize("folder", ["..", ".", "a/b", "../x", "", "Templates", ".hidden"])
def test_a_folder_name_that_is_not_one_top_level_folder_gives_no_template(scratch, folder):
    put(scratch, "x/x.md", "## Template\n\n```\na:\n```")
    put(scratch, "x.md", "## Template\n\n```\na:\n```")

    assert defs.template_for_folder(scratch, folder) is None


# --- drafting writes nothing; writing creates and never replaces ---------------------------------


def _people_vault(vault, count=5):
    for n in range(count):
        put(vault, f"People/Person{n}.md", f"---\nrole: worker\nemail: p{n}@x.example\n---\nBody {n}.")


def test_a_draft_holds_the_text_and_writes_nothing(scratch):
    _people_vault(scratch)
    before = tree(scratch)

    made = write_defs.draft(ALL, "People", "People I know.")

    assert made.rel_path == "People/People.md" and made.template == ["role: worker", "email:"] and made.notes == 5
    assert made.text == defs.render("People", ["role: worker", "email:"], "People I know.") and not made.from_templates_file
    assert tree(scratch) == before


def test_a_draft_needs_a_folder_with_notes_that_is_the_users_and_has_no_definition(scratch):
    _people_vault(scratch)
    put(scratch, "Templates/Note template.md", "---\n---")
    put(scratch, "Empty/.keep", "")

    assert write_defs.draft(ALL, "Templates") is None and write_defs.draft(ALL, "Empty") is None
    assert write_defs.draft(ALL, "Nothing") is None and write_defs.draft(ALL, "..") is None and write_defs.draft(ALL, "") is None
    put(scratch, "People/People.md", "# People")
    assert write_defs.draft(ALL, "People") is None


def test_a_draft_is_none_for_a_definition_the_persona_cannot_see(scratch):
    _people_vault(scratch)
    put(scratch, "Other/x.md")

    assert write_defs.draft({"vault_folders": ["Other"]}, "People") is None  # not in its scope


def test_a_draft_takes_the_users_own_templates_file_for_the_folder(scratch):
    _people_vault(scratch)
    put(scratch, "Templates/People template.md", "---\nname:\nphone:\n---\n\n# {{title}}")

    made = write_defs.draft(ALL, "People")

    assert made.template == ["name:", "phone:"] and made.from_templates_file and made.notes == 0
    assert defs.read_template(made.text) == "name:\nphone:"


def test_writing_creates_the_note_once_and_never_over_it(scratch):
    _people_vault(scratch)
    made = write_defs.draft(ALL, "People", "People I know.")

    assert write_defs.write(ALL, made).startswith("Created note")
    assert read(scratch, "People/People.md") == made.text
    put(scratch, "People/People.md", "my own words\n")
    assert write_defs.write(ALL, made) == NOTE_EXISTS and read(scratch, "People/People.md") == "my own words\n"


def test_writing_is_refused_for_a_draft_that_is_not_a_definition_at_its_own_path(scratch):
    _people_vault(scratch)
    made = write_defs.draft(ALL, "People")

    for tampered in (
        made.__class__(**{**made.__dict__, "rel_path": "People/Elsewhere.md"}),
        made.__class__(**{**made.__dict__, "rel_path": "../People/People.md"}),
        made.__class__(**{**made.__dict__, "folder": "Templates", "rel_path": "Templates/Templates.md"}),
        made.__class__(**{**made.__dict__, "folder": "", "rel_path": "/.md"}),
    ):
        assert write_defs.write(ALL, tampered) == NOTE_DENIED
    assert not os.path.exists(os.path.join(scratch, "People/People.md"))


def test_writing_stays_inside_the_personas_folders(scratch):
    _people_vault(scratch)
    made = write_defs.draft(ALL, "People")

    assert write_defs.write({"vault_folders": ["Other"]}, made) == NOTE_DENIED
    assert not os.path.exists(os.path.join(scratch, "People/People.md"))


# --- the template a new note starts from ----------------------------------------------------------


def _definition(vault, lines="role:\nemail:"):
    put(vault, "People/People.md", f"# People\n\nWho.\n\n## Template\n\n```yaml\n{lines}\n```\n")


def test_a_new_note_in_a_folder_with_a_definition_starts_from_its_template(scratch):
    _definition(scratch)

    assert vault_write_create.create_note(ALL, "People/Anna").startswith("Created note")
    assert read(scratch, "People/Anna.md") == "---\nrole:\nemail:\n---\n\n# Anna\n\n"


def test_the_placeholders_of_a_definition_template_are_filled(scratch):
    _definition(scratch, "title: {{title}}\nyear: {{date:YYYY}}")

    vault_write_create.create_note(ALL, "People/Anna")

    assert read(scratch, "People/Anna.md").startswith("---\ntitle: Anna\nyear: 20")


def test_a_templates_file_made_for_the_folder_beats_the_definition_and_the_definition_beats_the_general_one(scratch):
    put(scratch, "Templates/Note template.md", "---\ngeneral:\n---")
    assert vault_write_create.get_template_for_path(scratch, "People/A.md") == "---\ngeneral:\n---"

    _definition(scratch)
    assert vault_write_create.get_template_for_path(scratch, "People/A.md") == "---\nrole:\nemail:\n---"

    put(scratch, "Templates/People template.md", "---\nown:\n---")
    assert vault_write_create.get_template_for_path(scratch, "People/A.md") == "---\nown:\n---"


def test_a_definition_works_with_no_templates_folder_and_only_for_its_own_folder(scratch):
    _definition(scratch)

    assert vault_write_create.get_template_for_path(scratch, "People/Deep/A.md") == "---\nrole:\nemail:\n---"
    assert vault_write_create.get_template_for_path(scratch, "Other/A.md") is None
    assert vault_write_create.get_template_for_path(scratch, "Loose.md") is None


def test_a_definition_without_a_template_block_leaves_the_rest_as_it_was(scratch):
    put(scratch, "People/People.md", "# People\n\nWho.\n")
    put(scratch, "Templates/Note template.md", "---\ngeneral:\n---")

    assert vault_write_create.get_template_for_path(scratch, "People/A.md") == "---\ngeneral:\n---"


def test_a_hand_edited_definition_is_what_is_used(scratch):
    put(scratch, "People/People.md", "Intro I wrote.\n\n## Template\n\n```yaml\nrole: friend\n```\n\nMy own closing words.\n")

    assert vault_write_create.get_template_for_path(scratch, "People/A.md") == "---\nrole: friend\n---"


# --- edges found by mutation ------------------------------------------------------------------------


def test_a_nested_folder_path_is_not_a_top_level_folder(scratch):
    put(scratch, "A/B/B.md", "## Template\n\n```\nx:\n```")
    put(scratch, "A/B/A/B.md", "## Template\n\n```\nx:\n```")
    for n in range(5):
        put(scratch, f"A/B/N{n}.md")

    assert not defs.can_have_definition("A/B") and not defs.can_have_definition("A\\B")
    assert defs.template_for_folder(scratch, "A/B") is None
    assert write_defs.draft(ALL, "A/B") is None
    forged = write_defs.Draft("A/B", "A/B/A/B.md", "x", [], 0, False)
    assert write_defs.write(ALL, forged) == NOTE_DENIED


def test_a_share_of_exactly_one_is_allowed():
    settings_store.set(defs.SHARE_SETTING, 1)
    assert defs.template_share() == 1.0
    settings_store.set(defs.SHARE_SETTING, 1.0)
    assert defs.template_share() == 1.0


def test_a_property_name_that_is_not_text_is_skipped():
    notes = [note("P/A.md", **{"role": 1}) | {"meta": {"role": 1, 2026: "x", None: "y", True: "z"}}] * 2

    assert defs.template_lines(notes, "P") == ["role: 1"]


def test_the_general_template_is_not_a_template_made_for_a_folder(scratch):
    put(scratch, "Templates/Note template.md", "---\ngeneral:\n---")
    put(scratch, "Templates/People template.md", "---\nown:\n---")

    assert vault_write_create.dedicated_template_file(scratch, "Note") is None
    assert vault_write_create.dedicated_template_file(scratch, "People").endswith("People template.md")


def test_a_template_file_with_no_type_in_its_name_is_not_made_for_the_root(scratch):
    put(scratch, "Templates/template.md", "---\nany:\n---")

    assert vault_write_create.dedicated_template_file(scratch, "") is None
    assert vault_write_create.get_template_for_path(scratch, "Loose.md") is None


# --- found in the code review ------------------------------------------------------------------------


def test_a_folder_called_template_still_has_a_readable_definition():
    text = defs.render("Template", ["role:"], "Notes about templates.")

    assert defs.read_template(text) == "role:"  # its own title is a heading called Template too


def test_a_heading_called_template_with_no_block_does_not_hide_a_later_one():
    assert defs.read_template("## Template\n\nTODO\n\n## Template\n\n```\na:\n```") == "a:"
    assert defs.read_template("## Template\n\n## Other\n\n```\na:\n```\n\n## Template\n\n```\nb:\n```") == "b:"


def test_a_line_that_only_starts_with_a_hash_is_not_a_heading():
    assert defs.read_template("## Template\n\n#todo write this\n#### \n\n```\na:\n```") == "a:"
    assert defs.read_template("## Template\n\n### Sub\n\n```\na:\n```") is None


def test_a_folder_is_found_whatever_the_case_it_was_typed_in(scratch):
    put(scratch, "People/People.md", "## Template\n\n```\nrole:\n```")
    put(scratch, "notes.md")

    assert defs.folder_named(scratch, "people") == "People" and defs.folder_named(scratch, "PEOPLE") == "People"
    assert defs.folder_named(scratch, "People") == "People" and defs.folder_named(scratch, "Nothing") == "Nothing"
    assert defs.folder_named(scratch, "NOTES.MD") == "NOTES.MD"  # a file is not a folder
    assert defs.folder_named(os.path.join(scratch, "missing"), "people") == "people"
    assert defs.template_for_folder(scratch, "people") == "---\nrole:\n---"


def test_a_definition_outside_the_personas_folders_is_not_read(scratch):
    _definition(scratch)
    put(scratch, "People/Sub/x.md")
    inside, outside = [os.path.join(scratch, "People")], [os.path.join(scratch, "People", "Sub")]

    assert defs.template_for_folder(scratch, "People", inside) == "---\nrole:\nemail:\n---"
    assert defs.template_for_folder(scratch, "People", outside) is None
    assert defs.template_for_folder(scratch, "People", []) is None and defs.template_for_folder(scratch, "People") is not None


def test_a_note_made_by_a_persona_scoped_below_the_definition_does_not_use_it(scratch):
    _definition(scratch)
    put(scratch, "People/Sub/x.md")

    vault_write_create.create_note({"vault_folders": ["People/Sub"]}, "People/Sub/Anna")

    assert "role:" not in read(scratch, "People/Sub/Anna.md")
    vault_write_create.create_note({"vault_folders": ["People"]}, "People/Sub/Ben")
    assert read(scratch, "People/Sub/Ben.md").startswith("---\nrole:\nemail:\n---")


def test_on_a_filesystem_that_tells_case_apart_the_typed_case_is_corrected_and_an_exact_folder_wins(scratch, monkeypatch):
    put(scratch, "People/People.md", "## Template\n\n```\nrole:\n```")
    real_open = open

    def strict_open(path, *args, **kwargs):  # a case-sensitive filesystem: the folder must be spelled as it is
        if os.path.relpath(path, scratch).split(os.sep)[0] not in os.listdir(scratch):
            raise FileNotFoundError(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(defs, "open", strict_open, raising=False)

    assert defs.template_for_folder(scratch, "people") == "---\nrole:\n---"

    monkeypatch.setattr(defs.os, "listdir", lambda _: ["people", "People"])
    monkeypatch.setattr(defs.os.path, "isdir", lambda _: True)

    assert defs.folder_named(scratch, "People") == "People" and defs.folder_named(scratch, "PEOPLE") == "people"


def test_a_tag_line_called_template_is_not_the_heading_and_does_not_hide_the_real_one():
    assert defs.read_template("# People\n\n#template\n\n```python\nprint(1)\n```") is None
    assert defs.read_template("#template\n\n```\nwrong:\n```\n\n## Template\n\n```\nright:\n```") == "right:"


def test_a_persona_scoped_below_a_folder_is_not_offered_a_definition_it_cannot_be_given(scratch):
    _people_vault(scratch)
    for n in range(5):
        put(scratch, f"People/Friends/F{n}.md", "x")
    put(scratch, "Books/B0.md")
    for n in range(5):
        put(scratch, f"Books/B{n}.md")
    scoped = {"vault_folders": ["People/Friends"]}

    assert write_defs.due(ALL) == [("People", 10), ("Books", 5)]
    assert write_defs.due(scoped) == [("People", 5)]  # it sees only its own notes, and the folder is due
    put(scratch, "People/People.md", "# People")
    assert write_defs.due(scoped) == [] and write_defs.due(ALL) == [("Books", 5)]  # the definition is there although it cannot see it
    assert write_defs.draft(scoped, "People") is None
    assert write_defs.due({"vault_folders": ["Nowhere"]}) == [] and write_defs.due({}) is not None


def test_a_draft_from_notes_the_caller_has_is_the_same_as_a_draft(scratch):
    _people_vault(scratch)
    from sympose import vault_paths
    from sympose.vault_snapshot import get_vault_snapshot

    vault, allowed = vault_paths.resolve_sandbox(ALL)

    assert write_defs.draft_from(vault, get_vault_snapshot(vault, allowed), "People", "Who.") == write_defs.draft(ALL, "People", "Who.")


def test_with_no_vault_nothing_is_due_and_nothing_is_drafted(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")

    assert write_defs.due(ALL) == [] and write_defs.draft(ALL, "People") is None
