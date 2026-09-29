"""A note's properties ride along with the note when it is found (docs/decisions/030, "Stage 2")."""

from datetime import date

import pytest
from helpers import write_persona

from sympose.engine import followup, grounding, grounding_properties as gp, prompt, sharing, turn
from sympose.engine import grounding_index as gi
from sympose.engine.model import ModelReply


def test_every_property_with_a_value_is_a_key_value_line():
    meta = {"status": "in progress", "role": "designer", "empty": "", "nothing": None, "none": [], "done": False}

    assert gp.properties_text(meta) == "status: in progress\nrole: designer\ndone: false"


def test_a_list_is_joined_with_commas_and_a_date_is_a_date():
    meta = {"tags": ["a", "b"], "due": date(2026, 10, 1), "scores": [1, 2]}

    assert gp.properties_text(meta) == "tags: a, b\ndue: 2026-10-01\nscores: 1, 2"


@pytest.mark.parametrize(
    "value",
    ["[[Anna Ruiz]]", "[[Anna Ruiz|Anna]]", "[[Anna Ruiz#Bio]]", [["Anna Ruiz"]], ["[[Anna Ruiz]]"]],
)
def test_a_link_is_the_name_of_the_note_it_points_to(value):
    """An unquoted `[[Anna Ruiz]]` is read by the YAML parser as a list inside a list."""
    assert gp.properties_text({"author": value}) == "author: Anna Ruiz"


def test_a_note_with_no_properties_has_no_text():
    assert gp.properties_text({}) == ""
    assert gp.properties_text({"a": "", "b": None}) == ""


def test_the_text_is_cut_at_a_line_not_in_the_middle_of_one():
    meta = {f"key{i}": "x" * 60 for i in range(20)}

    text = gp.properties_text(meta)

    assert len(text) <= gi.MAX_PASSAGE_CHARS
    assert all(line == f"key{n}: " + "x" * 60 for n, line in enumerate(text.splitlines()))
    assert len(text.splitlines()) == 5


def test_one_value_longer_than_a_passage_is_cut_and_not_dropped():
    text = gp.properties_text({"summary": "word " * 300})

    assert text.startswith("summary: word") and len(text) <= gi.MAX_PASSAGE_CHARS


def test_a_long_value_does_not_cost_the_short_properties_after_it():
    """A long `description` early in the block must not push out `status` or `email` behind it."""
    meta = {"description": "long " * 90, "status": "done", "email": "a@b.c"}

    text = gp.properties_text(meta)

    assert len(text) <= gi.MAX_PASSAGE_CHARS
    assert text.splitlines()[-2:] == ["status: done", "email: a@b.c"]


def test_a_line_that_no_longer_fits_is_left_out_and_a_shorter_one_after_it_still_goes_in():
    meta = {"a": "x" * 100, "b": "x" * 100, "c": "x" * 100, "wide": "y" * 100, "status": "done"}

    text = gp.properties_text(meta)

    assert [line.split(":")[0] for line in text.splitlines()] == ["a", "b", "c", "status"]


def test_a_value_on_several_lines_stays_one_value_and_never_reads_as_a_key():
    """A block scalar can hold text that looks like `key: value`; it must not turn into a key of its own."""
    text = gp.properties_text({"notes": "call Bob\n  status: done\n", "role": "chef"})

    assert text == "notes: call Bob status: done\nrole: chef"


def _hit(path, heading="", text="body"):
    return {"rel_path": path, "title": path[:-3], "heading": heading, "text": text, "tags": ["t"], "kind": "text"}


def test_one_properties_passage_per_note_however_many_of_its_passages_were_found():
    hits = [_hit("A.md", "One"), _hit("B.md"), _hit("A.md", "Two")]

    found = gp.for_hits({"A.md": "status: done", "B.md": "role: chef"}, hits)

    assert [(h["rel_path"], h["text"], h["kind"], h["heading"]) for h in found] == [
        ("A.md", "status: done", "properties", "Properties"),
        ("B.md", "role: chef", "properties", "Properties"),
    ]
    assert found[0]["title"] == "A" and found[0]["tags"] == ["t"]


def test_a_note_without_properties_adds_nothing():
    assert gp.for_hits({"A.md": "status: done"}, [_hit("B.md")]) == []
    assert gp.for_hits({}, [_hit("B.md")]) == []


def _note(path, meta, body="Some text about the launch of the new site."):
    return {"rel_path": path, "file_name": path, "meta": meta, "body": body}


def test_the_index_keeps_properties_but_does_not_search_them():
    """Layer 1 must not change which notes are found: a word that is only in a property finds nothing."""
    notes = [_note("Atlas.md", {"status": "shipped", "owner": "Zorblax"}), _note("Other.md", {})]

    index = gi.build_index(notes)

    assert index.properties == {"Atlas.md": "status: shipped\nowner: Zorblax"}
    assert "zorblax" not in index.note_df and all("zorblax" not in p.tf for p in index.passages)
    assert grounding.retrieve(index, "who is Zorblax?") == []


def test_a_note_found_by_its_text_is_shown_with_its_properties_after_the_text():
    index = gi.build_index([_note("Atlas.md", {"status": "in progress", "owner": "Ana"})])
    hits = grounding.retrieve(index, "launch of the new site")

    shown = prompt.build_user_turn("is it done?", hits + gp.for_hits(index.properties, hits))

    assert shown.index("Some text about the launch") < shown.index("its properties, one per key: status: in progress; owner: Ana")
    assert "Atlas (Atlas.md › Properties)" in shown


def test_a_cloud_model_gets_no_properties_until_the_user_approves_them(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    cloud, local = "gemini/gemini-2.5-flash", "ollama_chat/gemma2:9b"
    hits = [_hit("A.md")]
    found = hits + gp.for_hits({"A.md": "email: a@b.c"}, hits)

    assert sharing.gate(cloud, found, []).withheld == {"notes": 1, "properties": 1}
    assert [h["kind"] for h in sharing.gate(local, found, []).grounding] == ["text", "properties"]
    sharing.set_approved("notes", True)
    gated = sharing.gate(cloud, found, [])
    assert [h["kind"] for h in gated.grounding] == ["text"] and gated.withheld == {"properties": 1}
    sharing.set_approved("properties", True)
    assert [h["kind"] for h in sharing.gate(cloud, found, []).grounding] == ["text", "properties"]


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(followup, "enabled", lambda: False)
    calls = []
    monkeypatch.setattr(turn.model_mod, "call_model", lambda messages, model=None, **_: calls.append(messages) or ModelReply("ok", 5))
    return calls


def test_a_turn_sends_the_properties_of_the_notes_it_found_and_no_others(scratch, monkeypatch):
    index = gi.build_index([_note("Atlas.md", {"status": "in progress"}), _note("Unfound.md", {"status": "secret"})])
    hit = {**_hit("Atlas.md", text="The launch"), "index": 1}
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [hit])
    monkeypatch.setattr(grounding, "scope_index", lambda profile: index)

    result = turn.run_turn("samantha", "is the launch done?")

    sent = scratch[0][-1]["content"]
    assert "status: in progress" in sent and "secret" not in sent
    assert [h["kind"] for h in result.grounding] == ["text", "properties"]


def test_a_turn_that_found_nothing_sends_no_properties(scratch, monkeypatch):
    index = gi.build_index([_note("Atlas.md", {"status": "in progress"})])
    monkeypatch.setattr(grounding, "ground", lambda profile, msg, max_results=5: [])
    monkeypatch.setattr(grounding, "scope_index", lambda profile: index)

    result = turn.run_turn("samantha", "good morning")

    assert result.grounding == [] and "status: in progress" not in scratch[0][-1]["content"]


def test_when_the_prompt_is_too_small_the_properties_go_before_the_text():
    hits = [{**_hit("Atlas.md", text="filler words for the passage " * 30), "index": 1}]
    found = hits + gp.for_hits({"Atlas.md": "status: " + "value words " * 25}, hits)

    def build(history, grounding, recaps, decisions):
        return [{"role": "user", "content": " ".join(h["text"] for h in grounding)}]

    room = turn.budget.count_tokens(build([], hits, [], []), "ollama_chat/gemma2:9b")
    fitted = turn.budget.fit(build, [], found, "ollama_chat/gemma2:9b", room)

    assert fitted.grounding == hits
