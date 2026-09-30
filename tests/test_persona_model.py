"""Saving a persona's model into its persona.yaml (docs/decisions/044): only the `model:` line is touched,
the hand-written rest of the file stays as it was, and anything that cannot be verified is not written."""

import os

import pytest
import yaml

from sympose import persona_model, profile

FILE = """name: 'Samantha'
handle: 'samantha'
aliases: ['Sam']
title: 'Polymath'

# "*" = full vault access.
vault_folders: '*'
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    (tmp_path / "samantha").mkdir()
    return tmp_path / "samantha" / "persona.yaml"


def write(home, text):
    home.write_text(text, encoding="utf-8", newline="")


def test_a_model_is_appended_and_the_rest_of_the_file_is_untouched(home):
    write(home, FILE)
    assert persona_model.set_model("samantha", "gemini/gemini-flash-latest") is True
    text = home.read_text(encoding="utf-8")
    assert text == FILE + "model: 'gemini/gemini-flash-latest'\n"  # comments, quotes and order kept
    assert profile.get_profile("samantha")["model"] == "gemini/gemini-flash-latest"


def test_an_existing_model_line_is_replaced_in_place(home):
    write(home, FILE.replace("title:", "model: 'ollama_chat/gemma2:9b'   # my local one\ntitle:"))
    assert persona_model.set_model("samantha", "openai/gpt-4o-mini") is True
    lines = home.read_text(encoding="utf-8").splitlines()
    assert lines[3] == "model: 'openai/gpt-4o-mini'" and lines[4].startswith("title:")
    assert lines.count("# \"*\" = full vault access.") == 1


def test_clearing_removes_only_the_model_line(home):
    write(home, FILE + "model: 'openai/gpt-4o-mini'\n")
    assert persona_model.set_model("samantha", None) is True
    assert home.read_text(encoding="utf-8") == FILE
    assert profile.get_profile("samantha")["model"] is None


def test_clearing_when_there_is_no_model_changes_nothing(home, monkeypatch):
    write(home, FILE)
    monkeypatch.setattr(persona_model, "write_atomic_text", lambda *a, **k: pytest.fail("rewrote an unchanged file"))
    assert persona_model.set_model("samantha", None) is True
    assert home.read_text(encoding="utf-8") == FILE


def test_a_file_without_a_final_newline_still_gets_the_line_on_its_own_row(home):
    write(home, "name: 'S'\nvault_folders: '*'")
    assert persona_model.set_model("samantha", "m/x") is True
    assert home.read_text(encoding="utf-8") == "name: 'S'\nvault_folders: '*'\nmodel: 'm/x'\n"


def test_windows_line_endings_are_kept(home):
    write(home, "name: 'S'\r\nvault_folders: '*'\r\n")
    persona_model.set_model("samantha", "m/x")
    assert home.read_bytes() == b"name: 'S'\r\nvault_folders: '*'\r\nmodel: 'm/x'\r\n"


def test_a_byte_order_mark_is_kept(home):
    home.write_bytes(b"\xef\xbb\xbfname: 'S'\n")
    assert persona_model.set_model("samantha", "m/x") is True
    assert home.read_bytes().startswith(b"\xef\xbb\xbfname: 'S'\n")


def test_a_quote_in_the_id_is_escaped_so_it_reads_back_the_same(home):
    write(home, FILE)
    assert persona_model.set_model("samantha", "o'brien/model") is True
    assert yaml.safe_load(home.read_text(encoding="utf-8"))["model"] == "o'brien/model"


def test_a_model_written_as_a_block_is_not_half_replaced(home):
    original = "name: 'S'\nmodel: >\n  ollama_chat/\n  gemma2:9b\nvault_folders: '*'\n"
    write(home, original)
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_text(encoding="utf-8") == original


def test_a_line_that_only_looks_like_the_model_key_inside_another_value_is_not_edited(home):
    original = 'title: "long\nmodel: not this"\nname: s\n'  # parses fine, and the line starts at column 0
    write(home, original)
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_text(encoding="utf-8") == original


def test_a_duplicated_model_key_is_not_edited_because_the_later_one_would_still_win(home):
    original = "name: s\nmodel: 'a/one'\nmodel: 'b/two'\n"
    write(home, original)
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_text(encoding="utf-8") == original


def test_a_key_written_with_a_space_before_the_colon_is_replaced_not_duplicated(home):
    write(home, "name: s\nmodel : 'old/one'\n")
    assert persona_model.set_model("samantha", "m/x") is True
    assert home.read_text(encoding="utf-8") == "name: s\nmodel: 'm/x'\n"


def test_a_file_that_is_not_valid_yaml_is_not_written(home):
    write(home, "name: [unclosed\n")
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_text(encoding="utf-8") == "name: [unclosed\n"


def test_a_file_that_is_not_utf8_is_not_written(home):
    home.write_bytes(b"name: '\xff\xfe'\n")
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_bytes() == b"name: '\xff\xfe'\n"


def test_a_missing_file_or_an_unsafe_handle_is_not_written(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path))
    assert persona_model.set_model("nobody", "m/x") is False
    assert persona_model.set_model("../evil", "m/x") is False
    assert list(tmp_path.iterdir()) == []


def test_a_failed_write_leaves_the_file_as_it_was(home, monkeypatch):
    write(home, FILE)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(persona_model, "write_atomic_text", boom)
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_text(encoding="utf-8") == FILE
    assert not any(n.endswith(".tmp") for n in os.listdir(home.parent))


def test_a_yaml_file_that_is_not_a_mapping_is_not_written(home):
    write(home, "- just\n- a list\n")
    assert persona_model.set_model("samantha", "m/x") is False
    assert home.read_text(encoding="utf-8") == "- just\n- a list\n"


def test_clearing_a_file_that_is_not_a_mapping_is_not_treated_as_done(home):
    write(home, "- just\n- a list\n")
    assert persona_model.set_model("samantha", None) is False
