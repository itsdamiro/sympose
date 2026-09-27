"""A note named in full is found when the search found nothing (docs/decisions/030, "A note named in full").
The embedding model is replaced by a fake under which every text is unlike every other, so the search by
meaning finds nothing unless a message is a passage word for word; that is the case the rule is for."""

import os
import zlib

import pytest

from sympose import settings_store
from sympose.engine import embeddings, grounding, grounding_named, semantic, semantic_refresh
from sympose.engine.grounding_index import build_index

WHOLE = {"vault_folders": ["*"]}
_DIMS = 4096


def _vector(text: str) -> list[float]:
    """One direction per text, except that every text about flights points the same way (so a message can match)."""
    v = [0.0] * _DIMS
    v[0 if "flights" in text.lower() else 1 + zlib.crc32(text.strip().encode()) % (_DIMS - 1)] = 1.0
    return v


@pytest.fixture(autouse=True)
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    semantic._forget_for_tests()
    semantic_refresh._forget_for_tests()
    monkeypatch.setattr(embeddings, "embed", lambda texts, kind, model_name=None: [_vector(t) for t in texts])
    settings_store.set("grounding_search", "auto")
    return tmp_path


def _write(root, rel_path, content):
    full = os.path.join(root, "vault", rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def _found(message, profile=WHOLE):
    return [h["rel_path"] for h in grounding.ground(profile, message)]


def test_an_alias_said_in_full_finds_a_note_that_has_only_properties(vault):
    _write(vault, "Anna Ruiz.md", "---\naliases: [Annie]\nrole: designer\n---\n")

    [hit] = grounding.ground(WHOLE, "tell me about Annie")

    assert hit["rel_path"] == "Anna Ruiz.md" and hit["via"] == "name" and hit["matched"] == 2 and hit["index"] == 1


def test_a_title_said_inside_a_sentence_finds_a_note_that_has_text(vault):
    _write(vault, "Budget.md", "The spend was over plan by a tenth in March.")
    _write(vault, "Trip.md", "Flights to Lisbon in May.")

    assert _found("how did we go over budget?") == ["Budget.md"]


def test_the_case_of_the_message_does_not_matter(vault):
    _write(vault, "Budget.md", "The spend was over plan by a tenth in March.")

    assert _found("WHAT ABOUT THE BUDGET") == ["Budget.md"]


def test_a_name_said_only_in_part_finds_nothing(vault):
    _write(vault, "Q3 Marketing Budget.md", "The spend was over plan by a tenth in March.")

    assert _found("how did the marketing go?") == []


def test_a_note_the_search_found_is_not_joined_by_a_note_that_is_named(vault):
    _write(vault, "Budget.md", "The spend was over plan by a tenth in March.")
    _write(vault, "Trip.md", "Flights to Lisbon in May.")

    assert _found("book the flights and check the budget") == ["Trip.md"]  # the search chose; the name adds nothing
    assert _found("check the budget") == ["Budget.md"]  # nothing found by meaning: the name does


def test_two_notes_with_one_name_are_both_attached_and_three_are_none(vault):
    _write(vault, "A/Atlas.md", "The first Atlas plan.")
    _write(vault, "B/Atlas.md", "The second Atlas plan.")

    assert sorted(_found("what is atlas")) == ["A/Atlas.md", "B/Atlas.md"]

    _write(vault, "C/Atlas.md", "The third Atlas plan.")

    assert _found("what is atlas") == []  # a name three notes carry is a category


def test_a_word_the_vault_is_full_of_is_not_a_name(vault):
    for n in range(12):
        _write(vault, f"Doc{n}.md", f"Doc {n} tells how a search works in the app, number {n}.")
    _write(vault, "Search.md", "How the search bar behaves.")

    assert _found("explain how a binary search works") == []  # in every note: it is what the vault is about
    _write(vault, "Quokka.md", "An animal.")
    assert _found("tell me about the quokka") == ["Quokka.md"]  # rare in the vault: a name


def test_a_small_vault_does_not_use_the_share_of_notes(vault):
    _write(vault, "Budget.md", "The spend was over plan.")
    _write(vault, "Trip.md", "The budget for flights.")

    assert _found("what about the budget") == ["Budget.md"]  # 2 of 2 notes hold the word, in a vault too small to judge


def test_the_persona_own_name_is_not_a_topic(vault):
    _write(vault, "Samantha.md", "My neighbour Samantha, who keeps bees.")
    persona = {**WHOLE, "name": "Samantha", "handle": "samantha", "aliases": ["Sam"]}

    assert _found("hi Samantha", persona) == []
    assert _found("hi Samantha", WHOLE) == ["Samantha.md"]  # for a persona with another name it is a note like any


def test_the_keywords_setting_is_left_exactly_as_it_was(vault):
    _write(vault, "Budget.md", "The spend was over plan.")
    index = build_index([{"rel_path": "Budget.md", "file_name": "Budget.md", "meta": {}, "body": "The spend was over plan."}])
    settings_store.set("grounding_search", "keywords")

    assert grounding_named.rescue(index, "what about the budget", []) == []
    settings_store.set("grounding_search", "auto")
    assert [h["rel_path"] for h in grounding_named.rescue(index, "what about the budget", [])] == ["Budget.md"]


@pytest.mark.parametrize("title", ["Ab", "The"])
def test_a_name_that_is_too_short_or_only_filler_words_is_not_a_name(vault, title):
    _write(vault, f"{title}.md", "Some text about something else entirely.")

    assert _found(f"tell me about {title.lower()}") == []


def test_the_passages_of_a_turn_stay_within_the_limit(vault):
    for name in ("Alpha", "Bravo", "Charlie", "Delta"):
        _write(vault, f"{name}.md", f"# {name}\n\nFirst paragraph of {name}.\n\n## More\n\nSecond paragraph of {name}.")

    hits = grounding.ground(WHOLE, "compare alpha bravo charlie and delta", max_results=5)

    assert len(hits) == 5 and [h["index"] for h in hits] == [1, 2, 3, 4, 5]


def test_the_longer_name_comes_first(vault):
    _write(vault, "Clipper.md", "A tool for cutting.")
    _write(vault, "Web Clipper.md", "Saves pages from the web.")

    assert _found("tell me about the web clipper")[0] == "Web Clipper.md"


def test_a_note_is_found_by_its_property_title_and_by_its_file_name(vault):
    _write(vault, "q3-plan.md", "---\ntitle: Harvest Moon\n---\nThe autumn festival plan.")

    assert _found("what is harvest moon") == ["q3-plan.md"]  # the title in the properties
    assert _found("what is in q3 plan") == ["q3-plan.md"]  # the file name, when it differs


def test_at_most_two_passages_of_one_note_are_attached(vault):
    def paragraph(word):
        return (f"{word} spend line over plan in the quarter. ") * 6

    _write(vault, "Budget.md", f"# Budget\n\n{paragraph('One')}\n\n## B\n\n{paragraph('Two')}\n\n## C\n\n{paragraph('Three')}")

    assert len(grounding.ground(WHOLE, "what about the budget")) == 2


def test_a_name_is_judged_by_its_rarest_word(vault):
    for n in range(12):
        _write(vault, f"Doc{n}.md", f"Doc {n} holds the plan for the quarter, number {n}.")
    _write(vault, "Quokka Plan.md", "An animal.")

    assert _found("tell me about the quokka plan") == ["Quokka Plan.md"]  # "plan" is everywhere, "quokka" is not


def test_the_share_of_notes_that_makes_a_word_common_is_a_tenth(vault):
    _write(vault, "Gadget.md", "A device.")
    for n in range(12):
        _write(vault, f"Doc{n}.md", "A gadget is mentioned here." if n < 2 else f"Nothing about it, number {n}.")

    assert _found("tell me about the gadget") == []  # 3 of 13 notes hold it: about a quarter

    _write(vault, "Doc0.md", "Nothing about it.")
    _write(vault, "Doc1.md", "Nothing about it either.")

    assert _found("tell me about the gadget") == ["Gadget.md"]  # only its own note: under a tenth
