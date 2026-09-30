"""Tests for sympose.engine.memory_tools (docs/decisions/041): the `remember` tool, its
inline-marker equivalent for a model that can't call tools, and applying either to a reply."""

from helpers import write_persona

from sympose.engine import memory, memory_tools


def _persona(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return directory


# -- run: the tool ---------------------------------------------------------------------------


def test_an_unrelated_tool_name_is_not_this_modules_and_returns_none(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    assert memory_tools.run("samantha", "search_notes", '{"query": "x"}') is None


def test_remember_appends_the_text_and_says_so(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    result = memory_tools.run("samantha", "remember", '{"text": "Chose SQLite"}')
    assert result.text == memory_tools._SAVED
    assert result.lookup == {"tool": "remember", "saved": True}
    [entry] = memory.decisions("samantha")
    assert entry.endswith("Chose SQLite")


def test_remember_with_no_text_argument_answers_plainly_instead_of_writing(tmp_path, monkeypatch):
    directory = _persona(tmp_path, monkeypatch)
    result = memory_tools.run("samantha", "remember", "{}")
    assert result.text == memory_tools._BAD_ARGUMENTS
    assert result.lookup == {"tool": "remember", "saved": False}
    assert not (directory / "decisions.md").exists()


def test_remember_accepts_a_dict_argument_too(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    result = memory_tools.run("samantha", "remember", {"text": "Kept it simple"})
    assert result.lookup["saved"] is True
    [entry] = memory.decisions("samantha")
    assert entry.endswith("Kept it simple")


# -- extract: the marker fallback for a model that can't call tools -------------------------


def test_extract_pulls_the_marker_out_and_strips_it():
    text = "Sure, I'll keep that in mind.\n\n<!-- remember: the user prefers dark mode -->"
    cleaned, remembered = memory_tools.extract(text)
    assert cleaned == "Sure, I'll keep that in mind."
    assert remembered == ["the user prefers dark mode"]


def test_extract_with_no_marker_leaves_the_text_untouched():
    cleaned, remembered = memory_tools.extract("Just a normal reply.")
    assert cleaned == "Just a normal reply." and remembered == []


def test_extract_with_no_marker_does_not_reformat_unrelated_spacing():
    # A reply that never had a marker must come back byte-identical: `memory_remember` being on
    # must not visibly change replies that have nothing to do with it.
    text = "Line one.\n\n\n\nLine two.  \n"
    cleaned, remembered = memory_tools.extract(text)
    assert cleaned == text and remembered == []


def test_extract_handles_more_than_one_marker():
    text = "<!-- remember: a -->\nSome reply.\n<!-- remember: b -->"
    cleaned, remembered = memory_tools.extract(text)
    assert cleaned == "Some reply."
    assert remembered == ["a", "b"]


def test_extract_drops_a_blank_marker():
    cleaned, remembered = memory_tools.extract("Reply.\n<!-- remember:    -->")
    assert cleaned == "Reply." and remembered == []


def test_extract_is_case_insensitive_and_tolerant_of_spacing():
    cleaned, remembered = memory_tools.extract("Reply.\n<!--REMEMBER:   x   -->")
    assert cleaned == "Reply." and remembered == ["x"]


# -- apply_marker: extract + actually write, recorded like a tool call ----------------------


def test_apply_marker_writes_each_remembered_line_and_records_it(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    text = "Got it.\n<!-- remember: likes dark mode -->"

    cleaned, lookups = memory_tools.apply_marker("samantha", text)

    assert cleaned == "Got it."
    assert lookups == [{"tool": "remember", "saved": True}]
    [entry] = memory.decisions("samantha")
    assert entry.endswith("likes dark mode")


def test_apply_marker_with_nothing_to_remember_writes_nothing(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    cleaned, lookups = memory_tools.apply_marker("samantha", "Just chatting.")
    assert cleaned == "Just chatting." and lookups == []
    assert memory.decisions("samantha") == []


def test_apply_marker_on_a_reply_that_is_only_the_marker_still_says_something(tmp_path, monkeypatch):
    _persona(tmp_path, monkeypatch)
    cleaned, lookups = memory_tools.apply_marker("samantha", "<!-- remember: likes dark mode -->")
    assert cleaned == memory_tools.MARKER_ONLY_REPLY
    assert lookups == [{"tool": "remember", "saved": True}]
