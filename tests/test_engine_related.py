"""Notes close in meaning (docs/decisions/066), and the field that carries them inside a grounded note's passage
(`for_hits`, beside the mechanical connections of docs/decisions/035 and never mixed into them). The embedding model is replaced by a fake that reads a vector
written in each note ("VEC 1 0 0"), so the mechanics are pinned down without Ollama: the vault's average note is
taken away, the level chooses the bar, the setting turns it off, and an unusable embedding model gives nothing."""

import os
import re
import threading
import time
from array import array

import pytest

from sympose import settings_store
from sympose.engine import embeddings, grounding, related, semantic, semantic_refresh, similarity

WHOLE = {"vault_folders": ["*"]}

# Seen from `a` after the vault's average note is taken away: a2 0.99, a3 0.46, m1 0.35, w 0.28 (just under the
# widest bar), the rest below that.
SPREAD = {
    "a": (1, 0, 0), "a2": (0.9, 0.1, 0), "a3": (0.7, 0.6, 0), "b": (0, 1, 0), "b2": (0.1, 0.95, 0.1),
    "c": (0, 0, 1), "c2": (0, 0.1, 1), "d": (-1, -1, -1),
    "m1": (0.65, 0.6, 0.1), "m2": (0.6, 0.7, 0.1), "m3": (0.55, 0.75, 0.1), "m4": (0.5, 0.8, 0.1), "m5": (0.4, 0.9, 0.1),
    "w": (0.64, 0.625, 0.1),
}
# Every note points mostly the same way (raw cosine above 0.98 for all of them); only the small part differs.
COMMON = {"x": (10, 1, 0), "x2": (10, 1.1, 0), "y": (10, 0, 1), "y2": (10, 0, 1.1), "z": (10, -1, -1)}


def put(vault, vectors):
    for name, vec in vectors.items():
        with open(os.path.join(vault, name + ".md"), "w", encoding="utf-8") as f:
            f.write("VEC " + " ".join(map(str, vec)))


@pytest.fixture(autouse=True, params=["numpy", "plain"])
def _both_paths(request, monkeypatch):
    """Every test here runs with numpy and without it: the two paths must give the same neighbours."""
    if request.param == "plain":
        monkeypatch.setattr(similarity, "numpy", None)


@pytest.fixture
def calls():
    return []


@pytest.fixture
def vault(tmp_path, monkeypatch, calls):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    semantic._forget_for_tests()
    semantic_refresh._forget_for_tests()
    related._forget_for_tests()

    def fake_embed(texts, kind, model_name=None):
        calls.append(len(texts))
        return [[float(x) for x in re.search(r"VEC ([-\d. ]+)", t).group(1).split()] for t in texts]

    monkeypatch.setattr(embeddings, "embed", fake_embed)
    settings_store.set("grounding_search", "auto")
    return str(root)


def paths(found):
    return [n["path"] for n in found]


def test_the_closest_notes_come_first_above_the_balanced_bar(vault):
    put(vault, SPREAD)

    found = related.neighbours(WHOLE, "a.md", 5)

    assert paths(found) == ["a2.md", "a3.md"]
    assert found[0]["title"] == "a2" and found[0]["score"] > found[1]["score"] > 0.40


def test_the_level_chooses_the_bar(vault):
    put(vault, SPREAD)
    seen = {}
    for level in ("close", "balanced", "wide"):
        settings_store.set("connections_relevance", level)
        seen[level] = paths(related.neighbours(WHOLE, "a.md", 5))

    assert seen == {"close": ["a2.md"], "balanced": ["a2.md", "a3.md"], "wide": ["a2.md", "a3.md", "m1.md"]}


def test_a_missing_or_unknown_level_is_balanced(vault):
    assert related.level() == "balanced"
    settings_store.set("connections_relevance", "extreme")
    assert related.level() == "balanced"


def test_the_limit_and_the_skipped_paths(vault):
    put(vault, SPREAD)
    settings_store.set("connections_relevance", "wide")

    assert paths(related.neighbours(WHOLE, "a.md", 1)) == ["a2.md"]
    assert paths(related.neighbours(WHOLE, "a.md", 5, skip=["a2.md"])) == ["a3.md", "m1.md"]


def test_a_note_is_never_its_own_neighbour_and_an_unknown_note_has_none(vault):
    put(vault, SPREAD)

    assert "a.md" not in paths(related.neighbours(WHOLE, "a.md", 20))
    assert related.neighbours(WHOLE, "nothing.md", 5) == []


def test_what_every_note_shares_does_not_make_them_neighbours(vault):
    put(vault, COMMON)

    assert paths(related.neighbours(WHOLE, "x.md", 5)) == ["x2.md"]  # y is 0.98 away before the average is taken away


def test_the_meter_runs_from_the_bar_to_the_top(vault):
    assert related.percent(0.40, 0.40) == 0
    assert related.percent(0.55, 0.40) == 50
    assert related.percent(0.70, 0.40) == 100
    assert related.percent(0.95, 0.40) == 100 and related.percent(0.20, 0.40) == 0
    assert related.percent(0.50, 0.30) == 50  # a wider level moves the bottom of the meter down with its bar
    put(vault, SPREAD)
    found = related.neighbours(WHOLE, "a.md", 5)
    assert [n["percent"] for n in found] == [100, related.percent(found[1]["score"], 0.40)]


def test_off_gives_nothing_and_asks_nothing_of_the_model(vault, calls):
    put(vault, SPREAD)
    settings_store.set("connections_by_meaning", "off")

    assert related.neighbours(WHOLE, "a.md", 5) == [] and calls == []


def test_a_missing_or_unknown_setting_is_auto(vault):
    assert related.mode() == "auto"
    settings_store.set("connections_by_meaning", "sometimes")
    assert related.mode() == "auto"


def test_keywords_mode_never_uses_the_embedding_model(vault, calls):
    put(vault, SPREAD)
    settings_store.set("grounding_search", "keywords")

    assert related.neighbours(WHOLE, "a.md", 5) == [] and calls == []


def test_a_cloud_embedding_model_is_not_sent_the_notes(vault, calls):
    put(vault, SPREAD)
    settings_store.set("embedding_model", "gemini/text-embedding-004")

    assert related.neighbours(WHOLE, "a.md", 5) == [] and calls == []


def test_a_model_that_does_not_answer_gives_nothing_not_an_error(vault, monkeypatch):
    put(vault, SPREAD)

    def broken(texts, kind, model_name=None):
        raise embeddings.EmbeddingUnavailable("down")

    monkeypatch.setattr(embeddings, "embed", broken)

    assert related.neighbours(WHOLE, "a.md", 5) == []


def test_the_notes_are_made_once_for_as_long_as_the_vectors_are_the_same(vault, monkeypatch):
    put(vault, SPREAD)
    made = []
    original = related._Notes
    monkeypatch.setattr(related, "_Notes", lambda *args: made.append(1) or original(*args))

    related.neighbours(WHOLE, "a.md", 5)
    related.neighbours(WHOLE, "b.md", 5)

    assert len(made) == 1


def test_a_note_is_the_average_of_all_its_passages(vault):
    put(vault, SPREAD)
    with open(os.path.join(vault, "mix.md"), "w", encoding="utf-8") as f:
        f.write("## One\nVEC 1 0 0\n\n## Two\nVEC 0 0 1\n")  # half of it points at `a`, half at `c`
    settings_store.set("connections_relevance", "wide")

    found = related.neighbours(WHOLE, "mix.md", 20)

    assert {"a.md", "c.md"} <= set(paths(found))
    assert {n["path"]: n["score"] for n in found}["c.md"] == pytest.approx(0.76, abs=0.01)  # the average, not the sum


def test_two_threads_asking_at_once_do_not_break_the_cache(vault, monkeypatch):
    put(vault, SPREAD)

    class SlowPop(dict):
        def pop(self, *args):  # lets the second thread reach its own pop while the first is still inside one
            time.sleep(0.05)
            return super().pop(*args)

    monkeypatch.setattr(related, "_CACHE", SlowPop({1: (object(), None)}))
    monkeypatch.setattr(related, "_KEEP", 1)
    errors = []

    def ask():
        try:
            related.neighbours(WHOLE, "a.md", 5)
        except Exception as e:  # noqa: BLE001 - the point is that nothing is raised
            errors.append(e)

    threads = [threading.Thread(target=ask) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert errors == []


def test_a_group_with_no_row_stays_all_zeros_and_the_rest_are_unit_length():
    rows = similarity.VectorSet([array("f", [1.0, 0.0]), array("f", [0.0, 1.0]), array("f", [1.0, 1.0])])

    notes = rows.note_set([0, 0, 2], 3)  # group 1 has no row

    assert list(notes.row(1)) == [0.0, 0.0]
    for position in (0, 2):
        assert sum(x * x for x in notes.row(position)) == pytest.approx(1.0)


def test_the_rows_of_one_note_need_not_sit_together():
    a, b, c = array("f", [1.0, 0.2, 0.0]), array("f", [0.0, 1.0, 0.3]), array("f", [0.9, 0.0, 0.1])

    mixed = similarity.VectorSet([a, b, c]).note_set([0, 1, 0], 2)
    together = similarity.VectorSet([a, c, b]).note_set([0, 0, 1], 2)

    for position in (0, 1):
        assert list(mixed.row(position)) == pytest.approx(list(together.row(position)), abs=1e-6)


def test_a_note_that_is_the_average_itself_is_zeros_not_nan():
    only = similarity.VectorSet([array("f", [0.6, 0.8])]).note_set([0], 1)

    assert list(only.row(0)) == [0.0, 0.0]


def test_it_says_while_the_vectors_are_being_built(vault):
    put(vault, SPREAD)
    index = grounding.scope_index(WHOLE)
    assert related.indexing(WHOLE) is False

    semantic_refresh._BUILDING.add((embeddings.model(), id(index)))  # a build is running for this index
    try:
        assert related.indexing(WHOLE) is True
        settings_store.set("connections_by_meaning", "off")
        assert related.indexing(WHOLE) is False  # off asks nothing, so there is nothing to wait for
    finally:
        semantic_refresh._BUILDING.clear()


def test_a_vault_with_no_sandbox_has_no_neighbours(vault, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS")

    assert related.neighbours(WHOLE, "a.md", 5) == []


# -- riding inside a grounded note's passage --


def hit(rel_path, **extra):
    return {"rel_path": rel_path, "title": rel_path[:-3], "heading": "", "text": "x", "kind": "text", **extra}


def test_a_grounded_note_gets_its_neighbours_by_title(vault):
    put(vault, SPREAD)

    out = related.for_hits(WHOLE, [hit("a.md")])

    assert out[0]["related"] == ["a2", "a3"]


def test_a_note_already_grounded_this_turn_is_not_repeated(vault):
    put(vault, SPREAD)

    out = related.for_hits(WHOLE, [hit("a.md"), hit("a2.md")])

    assert out[0]["related"] == ["a3"]


def test_a_neighbour_already_named_as_a_connection_is_not_repeated(vault):
    put(vault, SPREAD)

    out = related.for_hits(WHOLE, [hit("a.md", connections=["a2"])])

    assert out[0]["related"] == ["a3"]


def test_it_is_at_most_three_and_the_level_still_applies(vault):
    put(vault, SPREAD)
    settings_store.set("connections_relevance", "wide")
    settings_store.set("connections_by_meaning", "auto")

    out = related.for_hits(WHOLE, [hit("a.md")])

    assert out[0]["related"] == ["a2", "a3", "m1"]


def test_the_persona_is_given_at_most_three(vault, monkeypatch):
    put(vault, SPREAD)
    monkeypatch.setattr(related, "FOR_PERSONA", 1)

    assert related.for_hits(WHOLE, [hit("a.md")])[0]["related"] == ["a2"]


def test_a_note_found_through_two_passages_is_computed_once_and_shared(vault):
    put(vault, SPREAD)

    out = related.for_hits(WHOLE, [hit("a.md", heading="One"), hit("a.md", heading="Two")])

    assert out[0]["related"] == out[1]["related"] == ["a2", "a3"]


def test_a_note_with_no_neighbour_is_returned_unchanged(vault):
    put(vault, SPREAD)
    only = hit("d.md")

    assert related.for_hits(WHOLE, [only]) == [only]


def test_properties_and_library_passages_are_left_alone(vault):
    put(vault, SPREAD)
    properties = hit("a.md", kind="properties")
    library = hit("Sympose reference/Search.md", source="sympose")

    assert related.for_hits(WHOLE, [properties, library]) == [properties, library]


def test_off_changes_nothing(vault, calls):
    put(vault, SPREAD)
    settings_store.set("connections_by_meaning", "off")
    hits = [hit("a.md")]

    assert related.for_hits(WHOLE, hits) == hits and calls == []


def test_no_hits_changes_nothing(vault):
    assert related.for_hits(WHOLE, []) == []
