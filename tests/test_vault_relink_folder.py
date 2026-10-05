"""Rewriting the links that name a renamed folder (docs/decisions/073): a wikilink or embed whose path qualifier names the
folder and resolves, against the folder's files as they were, to one of them. A link by name alone is never touched."""

import os

from sympose.vault_write_relink_folder import relink_folder, rewrite_folder_links

INSIDE = {
    "people/anna.md", "people/anna", "people/sub/ben.md", "people/sub/ben", "people/photos/anna.png",
    "people/people.md", "people/people",
}


def rewrite(text, old="People", new="Team", inside=INSIDE):
    return rewrite_folder_links(text, old, new, inside)


def test_a_link_that_names_the_folder_is_retargeted_keeping_its_heading_and_alias():
    text = "See [[People/Anna]], [[People/Anna#Work]], [[People/Anna|her]] and [[People/Anna#Work|work]]."

    new, hits = rewrite(text)

    assert new == "See [[Team/Anna]], [[Team/Anna#Work]], [[Team/Anna|her]] and [[Team/Anna#Work|work]]."
    assert hits == 4


def test_an_embed_and_a_file_with_an_extension_are_retargeted_too():
    new, hits = rewrite("![[People/Photos/anna.png|200]] and ![[People/Anna]]")

    assert new == "![[Team/Photos/anna.png|200]] and ![[Team/Anna]]" and hits == 2


def test_a_link_by_name_alone_is_never_touched_nor_is_a_link_to_a_note_that_is_not_in_the_folder():
    text = "[[Anna]] [[Ben]] [[Other/Anna]] [[People/Nobody]] [[People]]"

    assert rewrite(text) == (text, 0)


def test_a_subfolder_path_and_the_definition_note_are_retargeted():
    new, hits = rewrite("[[People/Sub/Ben]] and [[People/People]]")

    assert new == "[[Team/Sub/Ben]] and [[Team/People]]" and hits == 2


def test_the_shortest_path_form_that_does_not_name_the_folder_is_left_alone():
    assert rewrite("[[Sub/Ben]] [[Photos/anna.png]]") == ("[[Sub/Ben]] [[Photos/anna.png]]", 0)


def test_a_folder_of_the_same_name_somewhere_else_is_not_the_renamed_one():
    text = "[[Other/People/Anna]] [[Archive/People/Ben]]"

    assert rewrite(text) == (text, 0)


def test_a_nested_folder_is_matched_by_its_whole_path_or_by_its_name_alone():
    inside = {"a/people/anna.md", "a/people/anna"}

    new, hits = rewrite("[[A/People/Anna]] [[People/Anna]] [[B/People/Anna]]", old="A/People", inside=inside)

    assert new == "[[A/Team/Anna]] [[Team/Anna]] [[B/People/Anna]]" and hits == 2


def test_the_comparison_ignores_case_and_keeps_the_links_own_spelling_elsewhere():
    new, hits = rewrite("[[people/anna]] [[PEOPLE/Anna|Her]]")

    assert new == "[[Team/anna]] [[Team/Anna|Her]]" and hits == 2


def test_plain_text_and_markdown_links_are_left_as_they_were():
    text = "People/Anna in plain text, and [a link](People/Anna.md)."

    assert rewrite(text) == (text, 0)


# -- over the vault ---------------------------------------------------------------------------------------------------


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


def test_every_note_that_links_into_the_folder_is_rewritten_and_only_those(tmp_path):
    root = str(tmp_path)
    write(root, "Team/Anna.md", "I know [[People/Ben]]\n")  # inside the renamed folder, now at its new path
    write(root, "Team/Ben.md", "x\n")
    write(root, "Journal/Day.md", "Met [[People/Anna|Anna]].\r\nAnd [[Ben]].\r\n")
    write(root, "Journal/Other.md", "no links here about People\n")
    write(root, ".obsidian/workspace.md", "[[People/Anna]]\n")
    inside = {"people/anna.md", "people/anna", "people/ben.md", "people/ben"}

    updated, failed = relink_folder(root, [root], "People", "Team", inside)

    assert (updated, failed) == (2, 0)
    assert open(os.path.join(root, "Team/Anna.md"), newline="").read() == "I know [[Team/Ben]]\n"
    assert open(os.path.join(root, "Journal/Day.md"), newline="").read() == "Met [[Team/Anna|Anna]].\r\nAnd [[Ben]].\r\n"  # line endings kept
    assert open(os.path.join(root, "Journal/Other.md")).read() == "no links here about People\n"
    assert open(os.path.join(root, ".obsidian/workspace.md")).read() == "[[People/Anna]]\n"  # a dot folder is not the vault's notes


def test_a_note_outside_the_sandbox_is_not_rewritten(tmp_path):
    root = str(tmp_path)
    write(root, "Team/Anna.md", "[[People/Ben]]\n")
    write(root, "Private/Secret.md", "[[People/Ben]]\n")

    updated, failed = relink_folder(root, [os.path.join(root, "Team")], "People", "Team", {"people/ben.md", "people/ben"})

    assert (updated, failed) == (1, 0)
    assert open(os.path.join(root, "Private/Secret.md")).read() == "[[People/Ben]]\n"


def test_a_note_that_cannot_be_rewritten_is_counted_not_hidden(tmp_path, monkeypatch):
    root = str(tmp_path)
    write(root, "A.md", "[[People/Anna]]\n")
    write(root, "B.md", "[[People/Anna]]\n")
    from sympose import vault_write_relink_folder as mod

    real = mod.write_atomic_text
    monkeypatch.setattr(mod, "write_atomic_text", lambda path, *a, **k: (_ for _ in ()).throw(OSError("read-only")) if path.endswith("A.md") else real(path, *a, **k))

    updated, failed = relink_folder(root, [root], "People", "Team", {"people/anna.md", "people/anna"})

    assert (updated, failed) == (1, 1)
