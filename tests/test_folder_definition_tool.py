"""The persona offering a folder's definition while she talks (docs/decisions/033, 087): `propose_folder_definition` files
the definition note as a new-note draft whose template is counted from the folder's real notes, never written by the model.
Nothing here writes the vault: the file exists only when the user accepts the draft."""

import json
import os

import pytest

from sympose import note_changes as nc
from sympose import note_changes_store as store
from sympose.engine import edit_tools as et
from sympose.engine import edit_turn, persona_tools, skills, unfiled

H = "samantha"
PROFILE = {"handle": H, "vault_folders": ["*"]}
PURPOSE = "People the user knows, one note each."


@pytest.fixture(autouse=True)
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    for n in range(6):
        put(str(root), f"People/Person {n}.md", "---\nrole: friend\nemail: a@b.c\n---\nText.\n")
    put(str(root), "Empty/.keep", "")
    return str(root)


def put(vault, rel, text):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def files(vault):
    return sorted(os.path.join(d, f) for d, _, names in os.walk(vault) for f in names)


def text_of(draft):
    return next(p for p in store.read(H, draft["path"])["proposals"] if p["kind"] == "create")["text"]


def call(**args):
    return et.run(H, None, None, "propose_folder_definition", {"folder": "People", "purpose": PURPOSE, "say": "Defined People.", **args}, PROFILE)


def test_a_definition_is_filed_as_a_draft_at_the_folders_own_name(vault):
    before = files(vault)

    result = call()

    assert result.lookup == {"tool": "propose_folder_definition", "saved": True}
    (draft,) = nc.drafts(H)
    assert (draft["name"], draft["folder"]) == ("People", "People")
    assert text_of(draft).startswith("# People\n\n" + PURPOSE) and "role: friend" in text_of(draft)
    assert files(vault) == before  # nothing is written before the user's Accept


def test_the_template_is_counted_from_the_notes_and_no_argument_can_set_it(vault):
    call(template="invented: yes", text="invented: yes")

    (draft,) = nc.drafts(H)
    assert "invented" not in text_of(draft) and "email: a@b.c" in text_of(draft)


def test_a_purpose_left_empty_gives_a_definition_with_the_template_only():
    result = call(purpose="")

    (draft,) = nc.drafts(H)
    assert result.lookup["saved"] and text_of(draft).startswith("# People\n\n## Template")
    assert "no purpose sentence" in result.text


def test_what_is_told_back_holds_counts_and_none_of_the_notes_content():
    result = call()

    assert "6 of its notes" in result.text and "2 property lines" in result.text
    assert "friend" not in result.text and "email" not in result.text


def test_the_folders_case_is_forgiven():
    assert call(folder="people").lookup["saved"] and nc.drafts(H)[0]["folder"] == "People"


@pytest.mark.parametrize("folder", ["Nowhere", "Templates", "Empty", "../etc", ""])
def test_a_folder_that_cannot_have_one_is_refused_and_nothing_is_filed(folder):
    result = call(folder=folder)

    assert result.lookup["saved"] is False and nc.drafts(H) == []


def test_a_folder_that_has_a_definition_is_left_alone(vault):
    put(vault, "People/People.md", "# People\n")

    result = call()

    assert result.lookup["saved"] is False and "already has a definition" in result.text and nc.drafts(H) == []


def test_a_purpose_that_would_read_as_a_heading_is_refused():
    result = call(purpose="First line\n# Not a heading")

    assert result.lookup["saved"] is False and nc.drafts(H) == []


def test_a_second_proposal_for_the_same_folder_is_refused_while_the_first_waits():
    call()

    again = call()

    assert again.lookup["saved"] is False and len(nc.drafts(H)) == 1


def test_a_persona_with_no_vault_files_nothing(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")

    result = et.run(H, None, None, "propose_folder_definition", {"folder": "People", "purpose": "", "say": "s"}, PROFILE)

    assert result.lookup["saved"] is False and nc.drafts(H) == []


def test_unreadable_arguments_are_said():
    result = et.run(H, None, None, "propose_folder_definition", {"purpose": "x"}, PROFILE)

    assert result.lookup["saved"] is False and "folder, say" in result.text


def test_it_is_a_tool_only_and_never_read_from_a_marker():
    reply = '<!-- propose_folder_definition: {"folder": "People", "say": "s"} -->'

    assert et.apply_marker(H, None, None, reply, PROFILE) == (reply, [])
    assert "<!--" not in json.dumps(et.TOOLS)


def test_it_is_offered_with_no_note_open_and_a_skill_can_name_it():
    names = [t["function"]["name"] for t in persona_tools._edit_tools(edit_turn.Edit("manual", True))]

    assert "propose_folder_definition" in names and "propose_folder_definition" in skills.tools_of(False, True, True)


def test_a_reply_claiming_it_after_the_call_is_not_corrected():
    lookups = call().lookup

    assert unfiled.filed([lookups]) and not unfiled.said_but_not_filed("I've proposed the People definition.", [lookups])


def test_a_folder_outside_the_personas_scope_is_answered_like_one_that_is_not_there(vault):
    put(vault, "Work/W.md", "x")
    scoped = {"handle": H, "vault_folders": ["Work"]}
    args = {"purpose": PURPOSE, "say": "s"}

    hidden = et.run(H, None, None, "propose_folder_definition", {"folder": "People", **args}, scoped)
    missing = et.run(H, None, None, "propose_folder_definition", {"folder": "Nowhere", **args}, scoped)

    assert hidden.lookup["saved"] is False and nc.drafts(H) == []
    assert hidden.text.replace("People", "X") == missing.text.replace("Nowhere", "X")


def test_the_accepted_draft_is_a_definition_the_app_reads_back(vault):
    from sympose import folder_definitions as defs

    call()
    (draft,) = nc.drafts(H)
    put(vault, "People/People.md", text_of(draft))  # what the Accept does: the file at the folder's own name

    with open(os.path.join(vault, "People/People.md"), encoding="utf-8") as f:
        body = f.read()
    assert defs.read_purpose(body) == PURPOSE and "role: friend" in defs.read_template(body)


def test_a_hidden_folders_definition_is_not_given_away(vault):
    put(vault, "Work/W.md", "x")
    put(vault, "People/People.md", "# People\n")
    scoped = {"handle": H, "vault_folders": ["Work"]}
    args = {"purpose": PURPOSE, "say": "s"}

    hidden = et.run(H, None, None, "propose_folder_definition", {"folder": "People", **args}, scoped)
    missing = et.run(H, None, None, "propose_folder_definition", {"folder": "Nowhere", **args}, scoped)

    assert hidden.text.replace("People", "X") == missing.text.replace("Nowhere", "X") and "already has" not in hidden.text
