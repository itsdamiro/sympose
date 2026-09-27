"""A grounded note's connections to other notes (docs/decisions/035): links, backlinks, shared tags or
aliases, and the same top-level folder, ranked in that order and capped, riding inside the note's own
passage. Everything runs in a temporary vault and settings file."""

import os

import pytest

from sympose.engine import connections

ALL = {"vault_folders": ["*"]}


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def put(vault, rel, text=""):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def hit(rel_path, title=None, **extra):
    return {"rel_path": rel_path, "title": title or rel_path, "heading": "", "text": "x", "kind": "text", **extra}


def test_no_vault_returns_the_hits_unchanged():
    hits = [hit("Anna.md")]

    assert connections.for_hits({"vault_folders": ["*"]}, hits) == hits


def test_a_note_with_no_connection_of_any_kind_is_unchanged(scratch):
    put(scratch, "Anna.md")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert "connections" not in result[0]


def test_a_link_out_is_a_connection(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["connections"] == ["Ben"]


def test_a_link_in_is_a_connection(scratch):
    put(scratch, "Anna.md")
    put(scratch, "Ben.md", "links to [[Anna]]")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["connections"] == ["Ben"]


def test_a_link_to_itself_is_not_a_connection(scratch):
    put(scratch, "Anna.md", "links to [[Anna]]")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert "connections" not in result[0]


def test_a_link_to_nothing_is_not_a_connection(scratch):
    put(scratch, "Anna.md", "links to [[Nobody]]")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert "connections" not in result[0]


def test_a_shared_tag_is_a_connection(scratch):
    put(scratch, "Anna.md", "---\ntags: [friend]\n---\n")
    put(scratch, "Ben.md", "---\ntags: [friend]\n---\n")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["connections"] == ["Ben"]


def test_a_shared_alias_is_a_connection(scratch):
    put(scratch, "Anna.md", "---\naliases: [Annie]\n---\n")
    put(scratch, "Ben.md", "---\naliases: [Annie]\n---\n")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["connections"] == ["Ben"]


def test_the_same_top_level_folder_is_the_weakest_connection(scratch):
    put(scratch, "People/Anna.md")
    put(scratch, "People/Ben.md")

    result = connections.for_hits(ALL, [hit("People/Anna.md")])

    assert result[0]["connections"] == ["Ben"]


def test_links_outrank_tags_which_outrank_the_shared_folder(scratch):
    put(scratch, "People/Anna.md", "---\ntags: [friend]\n---\nlinks to [[Cara]]")
    put(scratch, "People/Ben.md", "---\ntags: [friend]\n---\n")
    put(scratch, "People/Cara.md")
    put(scratch, "People/Dee.md")

    result = connections.for_hits(ALL, [hit("People/Anna.md")])

    assert result[0]["connections"][0] == "Cara"  # the link
    assert set(result[0]["connections"][1:]) == {"Ben", "Dee"}  # the tag, then the folder


def test_connections_are_capped_at_three(scratch):
    put(scratch, "People/Anna.md")
    for name in ("Ben", "Cara", "Dee", "Eve"):
        put(scratch, f"People/{name}.md")

    result = connections.for_hits(ALL, [hit("People/Anna.md")])

    assert len(result[0]["connections"]) == 3


def test_a_connection_is_named_by_its_declared_title(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md", "---\ntitle: Benjamin\n---\n")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["connections"] == ["Benjamin"]


def test_the_sympose_reference_is_left_untouched(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md")
    reference_hit = hit("Sympose reference/Search.md", source="sympose")

    result = connections.for_hits(ALL, [reference_hit])

    assert result == [reference_hit]


def test_a_properties_passage_is_left_untouched(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md")
    properties_hit = hit("Anna.md", kind="properties")

    result = connections.for_hits(ALL, [properties_hit])

    assert result == [properties_hit]


def test_a_note_found_through_two_passages_gets_its_connections_computed_once(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md")
    two_passages = [hit("Anna.md", heading="One"), hit("Anna.md", heading="Two")]

    result = connections.for_hits(ALL, two_passages)

    assert result[0]["connections"] == ["Ben"]
    assert result[1]["connections"] is result[0]["connections"]  # the very same list, not recomputed


def test_a_scoped_persona_never_connects_to_a_note_it_cannot_see(scratch):
    put(scratch, "People/Anna.md", "links to [[Secret]]")
    put(scratch, "Hidden/Secret.md")
    scoped = {"vault_folders": ["People"]}

    result = connections.for_hits(scoped, [hit("People/Anna.md")])

    assert "connections" not in result[0]
