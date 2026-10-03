"""Adding the built-in look to a definition note that exists (docs/decisions/064)."""

import os

import pytest

from sympose import folder_looks, folder_looks_write
from sympose.folder_looks_write import Refused, add_look, insert_properties

WHOLE = {"vault_folders": ["*"]}
LINES = ["icon: film-roll", "accent: '#be123c'"]


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    root = tmp_path / "vault"
    root.mkdir()
    return str(root)


def _write(root, rel_path, content):
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def _read(root, rel_path):
    with open(os.path.join(root, rel_path), encoding="utf-8", newline="") as f:
        return f.read()


def test_the_lines_go_at_the_end_of_the_existing_frontmatter():
    text = "---\ntype: folder\ntags: [a]\n---\nFilms I watched.\n"
    assert insert_properties(text, LINES) == "---\ntype: folder\ntags: [a]\nicon: film-roll\naccent: '#be123c'\n---\nFilms I watched.\n"


def test_a_note_with_no_frontmatter_gets_a_block_and_keeps_its_text():
    assert insert_properties("Films.\n", ["icon: x"]) == "---\nicon: x\n---\nFilms.\n"


def test_an_empty_block_is_filled():
    assert insert_properties("---\n---\nFilms.\n", ["icon: x"]) == "---\nicon: x\n---\nFilms.\n"


def test_a_dashed_line_in_the_body_is_not_the_end_of_the_block():
    text = "---\ntype: folder\n---\nA\n\n---\n\nB\n"
    assert insert_properties(text, ["icon: x"]) == "---\ntype: folder\nicon: x\n---\nA\n\n---\n\nB\n"


def test_a_block_that_is_never_closed_is_left_alone():
    assert insert_properties("---\ntype: folder\nFilms.\n", ["icon: x"]) is None


def test_a_crlf_note_gets_its_lines_inside_its_own_block_and_no_second_block():
    text = "---\r\ntype: folder\r\n---\r\nFilms.\r\n"
    assert insert_properties(text, ["icon: x"]) == "---\r\ntype: folder\r\nicon: x\n---\r\nFilms.\r\n"


def test_a_byte_order_mark_is_kept_in_front():
    assert insert_properties("﻿---\na: 1\n---\nx\n", ["icon: x"]) == "﻿---\na: 1\nicon: x\n---\nx\n"


def test_offer_is_the_built_in_icon_and_the_colours_the_note_does_not_set(vault):
    notes = [{"rel_path": "Movies/Movies.md", "meta": {"accent": "#111111"}}]
    assert folder_looks.offer("Movies", notes) == ["icon: film-roll", "accent_dark: '#f2889b'"]


def test_there_is_no_offer_for_a_note_that_has_an_icon_whatever_it_holds():
    for held in ("star", "", None, "not an icon!"):
        assert folder_looks.offer("Movies", [{"rel_path": "Movies/Movies.md", "meta": {"icon": held}}]) == []


def test_there_is_no_offer_without_a_definition_or_for_a_folder_the_list_does_not_know():
    assert folder_looks.offer("Movies", [{"rel_path": "Movies/Alien.md", "meta": {}}]) == []
    assert folder_looks.offer("Garden", [{"rel_path": "Garden/Garden.md", "meta": {}}]) == []


def test_add_look_writes_only_the_properties_and_the_folder_is_then_drawn_with_them(vault):
    body = "---\ntype: folder\n---\n# Movies\n\nFilms I watched.\n\n## Template\n\n```\ntitle:\n```\n"
    _write(vault, "Movies/Movies.md", body)
    _write(vault, "Movies/Alien.md", "x")

    written = add_look(WHOLE, "Movies")

    assert written[0] == "icon: film-roll"
    assert _read(vault, "Movies/Movies.md") == body.replace("type: folder\n", "type: folder\n" + "".join(f"{line}\n" for line in written))
    from sympose import vault_graph

    tree = {n["name"]: n for n in vault_graph.get_vault_tree(WHOLE)}
    assert tree["Movies"]["icon"] == "film-roll"
    with pytest.raises(Refused):  # a second time there is nothing to add
        add_look(WHOLE, "Movies")


def test_a_crlf_note_stays_crlf(vault):
    _write(vault, "Movies/Movies.md", "---\r\ntype: folder\r\n---\r\nFilms.\r\n")
    add_look(WHOLE, "Movies")
    assert _read(vault, "Movies/Movies.md") == "---\r\ntype: folder\r\nicon: film-roll\r\naccent: '#be123c'\r\naccent_dark: '#f2889b'\r\n---\r\nFilms.\r\n"


def test_a_note_that_changed_since_it_was_read_is_not_overwritten(vault, monkeypatch):
    _write(vault, "Movies/Movies.md", "---\ntype: folder\n---\nFilms.\n")
    real = folder_looks_write.vault_write.overwrite_note

    def raced(profile, note, content, *, expected_mtime=None):
        _write(vault, "Movies/Movies.md", "changed by someone\n")
        os.utime(os.path.join(vault, "Movies/Movies.md"), (1, 1))
        return real(profile, note, content, expected_mtime=expected_mtime)

    monkeypatch.setattr(folder_looks_write.vault_write, "overwrite_note", raced)
    with pytest.raises(Refused, match="changed"):
        add_look(WHOLE, "Movies")
    assert _read(vault, "Movies/Movies.md") == "changed by someone\n"


def test_a_folder_with_no_definition_or_a_chosen_icon_is_refused_and_unchanged(vault):
    _write(vault, "Movies/Alien.md", "x")
    with pytest.raises(Refused):
        add_look(WHOLE, "Movies")
    _write(vault, "People/People.md", "---\nicon: star\n---\nPeople.\n")
    with pytest.raises(Refused):
        add_look(WHOLE, "People")
    assert _read(vault, "People/People.md") == "---\nicon: star\n---\nPeople.\n"


def test_a_persona_that_cannot_see_the_folder_cannot_have_it_written(vault):
    _write(vault, "Movies/Movies.md", "---\ntype: folder\n---\nFilms.\n")
    with pytest.raises(Refused):
        add_look({"vault_folders": ["Code"]}, "Movies")
    assert "icon" not in _read(vault, "Movies/Movies.md")


def test_a_mixed_note_keeps_its_stray_line_breaks_except_as_a_save_always_does(vault):
    # Mostly LF with one CRLF line in the body: the fix must not rewrite that line.
    _write(vault, "Movies/Movies.md", "---\ntype: folder\n---\nFilms.\r\nMore.\nEnd.\n")
    add_look(WHOLE, "Movies")
    assert _read(vault, "Movies/Movies.md").endswith("Films.\r\nMore.\nEnd.\n")


def test_a_note_that_is_not_utf8_is_refused_and_unchanged(vault):
    path = os.path.join(vault, "Movies", "Movies.md")
    os.makedirs(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(b"---\ntype: folder\n---\nFilms \xe9.\n")
    with pytest.raises(Refused, match="UTF-8"):
        add_look(WHOLE, "Movies")
    with open(path, "rb") as f:
        assert f.read() == b"---\ntype: folder\n---\nFilms \xe9.\n"


@pytest.mark.parametrize("answer", ["Error: Failed to write note: [Errno 28] No space left on device", "something unexpected"])
def test_a_write_that_failed_is_refused_and_never_reported_as_added(vault, monkeypatch, answer):
    _write(vault, "Movies/Movies.md", "---\ntype: folder\n---\nFilms.\n")
    monkeypatch.setattr(folder_looks_write.vault_write, "overwrite_note", lambda *a, **k: answer)
    with pytest.raises(Refused, match="could not be written"):
        add_look(WHOLE, "Movies")


def test_a_note_that_cannot_be_read_is_refused_with_the_reason_and_unchanged(vault, monkeypatch):
    _write(vault, "Movies/Movies.md", "---\ntype: folder\n---\nFilms.\n")
    real_open = open

    def denied(path, *args, **kwargs):
        if str(path).endswith("Movies.md") and "r" in (args[0] if args else kwargs.get("mode", "r")):
            raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(folder_looks_write.folder_looks, "offer", lambda folder, notes: ["icon: film-roll"])  # past the snapshot's own read
    monkeypatch.setattr("builtins.open", denied)
    with pytest.raises(Refused, match="could not be read"):
        add_look(WHOLE, "Movies")
    monkeypatch.undo()
    assert _read(vault, "Movies/Movies.md") == "---\ntype: folder\n---\nFilms.\n"
