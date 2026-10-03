"""A grounded note's links (docs/decisions/067) and its connections to other notes (docs/decisions/035): shared
tags or aliases and the same top-level folder, ranked in that order and capped, riding inside the note's own
passage; its links, both ways, are stated on their own. Everything runs in a temporary vault and settings file."""

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


NO_LINKS = {"to": [], "from": [], "more_to": 0, "more_from": 0}


def test_a_note_with_no_connection_of_any_kind_still_says_it_has_no_links(scratch):
    put(scratch, "Anna.md")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert "connections" not in result[0]
    assert result[0]["links"] == NO_LINKS  # "none" is a fact she can quote, not a silence


def test_a_link_out_is_stated_as_a_link_and_not_as_a_connection(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["links"] == {**NO_LINKS, "to": ["Ben"]}
    assert "connections" not in result[0]


def test_a_link_in_is_stated_as_a_link_from(scratch):
    put(scratch, "Anna.md")
    put(scratch, "Ben.md", "links to [[Anna]]")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["links"] == {**NO_LINKS, "from": ["Ben"]}
    assert "connections" not in result[0]


def test_a_link_to_itself_is_not_a_link(scratch):
    put(scratch, "Anna.md", "links to [[Anna]]")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["links"] == NO_LINKS


def test_a_link_to_nothing_is_not_a_link(scratch):
    put(scratch, "Anna.md", "links to [[Nobody]]")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["links"] == NO_LINKS


def test_similar_titles_with_no_link_between_them_are_not_linked(scratch):
    # The measured failure (docs/decisions/067): "Workspaces" and "Workspace" read as linked from their titles.
    put(scratch, "Workspaces.md", "links to [[Core plugins]]")
    put(scratch, "Core plugins.md")
    put(scratch, "Workspace.md", "the main container")

    result = connections.for_hits(ALL, [hit("Workspaces.md")])

    assert result[0]["links"]["to"] == ["Core plugins"] and "Workspace" not in result[0]["links"]["to"] + result[0]["links"]["from"]


def test_the_names_of_a_hubs_links_are_capped_and_the_rest_counted(scratch):
    put(scratch, "Hub.md", " ".join(f"[[N{n}]]" for n in range(8)))
    for n in range(8):
        put(scratch, f"N{n}.md")

    links = connections.for_hits(ALL, [hit("Hub.md")])[0]["links"]

    assert links["to"] == ["N0", "N1", "N2", "N3", "N4"] and links["more_to"] == 3 and links["more_from"] == 0


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


def test_a_linked_note_is_not_repeated_among_the_tag_and_folder_connections(scratch):
    put(scratch, "People/Anna.md", "---\ntags: [friend]\n---\nlinks to [[Cara]]")
    put(scratch, "People/Ben.md", "---\ntags: [friend]\n---\n")
    put(scratch, "People/Cara.md", "---\ntags: [friend]\n---\n")
    put(scratch, "People/Dee.md")

    result = connections.for_hits(ALL, [hit("People/Anna.md")])

    assert result[0]["links"]["to"] == ["Cara"]
    assert result[0]["connections"] == ["Ben", "Dee"]  # the tag, then the folder; never Cara again


def test_connections_are_capped_at_three(scratch):
    put(scratch, "People/Anna.md")
    for name in ("Ben", "Cara", "Dee", "Eve"):
        put(scratch, f"People/{name}.md")

    result = connections.for_hits(ALL, [hit("People/Anna.md")])

    assert len(result[0]["connections"]) == 3


def test_a_link_is_named_by_its_declared_title(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md", "---\ntitle: Benjamin\n---\n")

    result = connections.for_hits(ALL, [hit("Anna.md")])

    assert result[0]["links"]["to"] == ["Benjamin"]


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


def test_a_note_found_through_two_passages_states_its_links_once_on_the_first(scratch):
    put(scratch, "Anna.md", "links to [[Ben]]")
    put(scratch, "Ben.md")
    two_passages = [hit("Anna.md", heading="One"), hit("Anna.md", heading="Two")]

    result = connections.for_hits(ALL, two_passages)

    assert result[0]["links"]["to"] == ["Ben"]
    assert "links" not in result[1] and "connections" not in result[1]  # not repeated under every passage


def test_a_scoped_persona_never_connects_to_a_note_it_cannot_see(scratch):
    put(scratch, "People/Anna.md", "links to [[Secret]]")
    put(scratch, "Hidden/Secret.md")
    scoped = {"vault_folders": ["People"]}

    result = connections.for_hits(scoped, [hit("People/Anna.md")])

    assert result[0]["links"] == NO_LINKS and "connections" not in result[0]
