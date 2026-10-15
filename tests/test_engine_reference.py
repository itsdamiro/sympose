"""Tests for sympose.engine.reference (docs/decisions/022): the Sympose reference
library in a persona's turns. What the notes answer is measured in
test_reference_eval.py; these pin down who gets them and how they are labelled."""

import os

import pytest

from sympose.engine import reference

HAS = {"sympose_reference": True}


def test_a_persona_without_the_library_gets_nothing():
    assert reference.ground({}, "how do I add a second vault?") == []
    assert reference.ground({"sympose_reference": False}, "how do I add a second vault?") == []


def test_a_persona_with_it_gets_labelled_passages_marked_as_sympose():
    hits = reference.ground(HAS, "how do I add a second vault?")

    assert hits and all(h["source"] == "sympose" for h in hits)
    assert all(h["rel_path"].startswith("Sympose reference/") for h in hits)
    assert hits[0]["rel_path"] == "Sympose reference/Add or switch vaults.md"
    assert "workspace switcher" in hits[0]["text"]


def test_at_most_three_passages_are_returned():
    assert len(reference.ground(HAS, "what does the context_window setting do?")) <= 3


def test_a_follow_up_is_found_by_its_rewritten_query_which_comes_first():
    message = "and how do I undo that?"  # on its own words it finds nothing about /default
    assert not any("/default" in h["text"] for h in reference.ground(HAS, message))

    hits = reference.ground(HAS, message, "undo the /default command")

    assert "/default" in hits[0]["text"] and len(hits) <= reference.MAX_WITH_REWRITE
    assert all(h["source"] == "sympose" and h["rel_path"].startswith("Sympose reference/") for h in hits)


def test_the_rewritten_query_never_brings_the_passages_past_the_cap(monkeypatch):
    def hit(name):
        return {"rel_path": f"{name}.md", "text": name, "title": name, "index": 0}

    found = {"message": [hit("m1"), hit("m2"), hit("m3")], "rewritten": [hit("r1"), hit("r2"), hit("r3"), hit("m1")]}
    monkeypatch.setattr(reference, "_search", lambda index, query: list(found[query]))

    hits = reference.ground(HAS, "message", "rewritten")

    assert [h["text"] for h in hits] == ["r1", "m1", "r2", "m2", "r3"]  # they take turns, the rewrite's first, nothing twice, five at most


def test_a_message_alone_brings_at_most_three_library_passages():
    hits = reference.ground(HAS, "what are the settings of Sympose and what do the chat commands do?")

    assert 0 < len(hits) <= reference.MAX_PASSAGES


def test_the_meaning_search_refines_the_message_and_the_rewrite(monkeypatch):
    refined = []
    monkeypatch.setattr(reference.semantic, "refine", lambda index, query, hits, **kw: refined.append(query) or hits)

    reference.ground(HAS, "and how do I undo that?", "undo the /default command")

    assert refined == ["and how do I undo that?", "undo the /default command"]


def test_the_rewritten_query_adds_nothing_twice_and_nothing_for_a_persona_without_the_library():
    question = "how do I make a different persona the default?"
    alone = reference.ground(HAS, question)
    both = reference.ground(HAS, question, question)
    assert [(h["rel_path"], h["text"]) for h in both] == [(h["rel_path"], h["text"]) for h in alone]
    assert reference.ground({}, "x", "undo the /default command") == []


def test_ordinary_chat_finds_nothing_in_the_library():
    assert reference.ground(HAS, "hey, how are you today?") == []
    assert reference.ground(HAS, "thanks, that helps!") == []


def test_missing_notes_are_no_hits_and_not_a_failed_turn(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(reference, "REFERENCE_DIR", str(tmp_path / "nowhere"))

    assert reference.ground(HAS, "how do I add a second vault?") == []
    assert "missing from this install" in caplog.text


def test_the_index_is_reused_until_a_note_changes(monkeypatch, tmp_path):
    (tmp_path / "Personas.md").write_text("# Personas\n\n## What is a persona\n\nA persona is a character you chat with.")
    monkeypatch.setattr(reference, "REFERENCE_DIR", str(tmp_path))
    monkeypatch.setattr(reference, "_CACHE", None)
    built = []
    real = reference.build_index
    monkeypatch.setattr(reference, "build_index", lambda snap, **kwargs: built.append(1) or real(snap, **kwargs))

    reference.ground(HAS, "what is a persona")
    reference.ground(HAS, "what is a persona")
    assert len(built) == 1
    (tmp_path / "Extra.md").write_text("# Extra\n\nAnother note.")
    os.utime(tmp_path, (1, 1_000_000_000))  # the directory's own mtime is what the cache watches
    reference.ground(HAS, "what is a persona")
    assert len(built) == 2


def test_the_shipped_notes_are_in_the_package_data_glob():
    import tomllib

    with open(os.path.join(reference.REFERENCE_DIR, "..", "..", "pyproject.toml"), "rb") as f:
        config = tomllib.load(f)
    assert "reference/*.md" in config["tool"]["setuptools"]["package-data"]["sympose"]  # the web app is there too (ADR 028)
    assert all(n.endswith(".md") for n in os.listdir(reference.REFERENCE_DIR))


def test_the_shipped_samantha_has_the_library_and_says_so_explicitly():
    import yaml

    with open(os.path.join(reference.REFERENCE_DIR, "..", "..", "profiles", "samantha", "persona.yaml")) as f:
        assert yaml.safe_load(f)["sympose_reference"] is True


@pytest.mark.parametrize("message", ["who made Sympose?", "does Sympose work in Slack?", "can Samantha write my notes?"])
def test_the_questions_the_library_is_for_find_something(message):
    assert reference.ground(HAS, message)


def test_a_broad_question_still_returns_at_most_three_passages():
    # Uncapped, this question matches nine.
    assert len(reference.ground(HAS, "which settings go in settings.json and which in .env")) == 3
