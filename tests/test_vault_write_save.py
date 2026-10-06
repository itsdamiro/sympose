"""Saving a note from the editor (docs/decisions/048, #98): the file's line endings are kept, and a file that is
not valid text is never saved over."""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import vault_write
from sympose.server import create_app
from sympose.vault_write_status import NOTE_NOT_TEXT

PROFILE = {"vault_folders": ["*"]}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return tmp_path


def put(vault, name, raw: bytes):
    path = vault / name
    path.write_bytes(raw)
    return path


def test_a_crlf_note_stays_crlf_after_a_save(vault):
    path = put(vault, "Win.md", b"one\r\ntwo\r\n")
    vault_write.overwrite_note(PROFILE, "Win.md", "one\ntwo\nthree")  # what the editor sends: LF
    assert path.read_bytes() == b"one\r\ntwo\r\nthree\r\n"


def test_an_lf_note_stays_lf(vault):
    path = put(vault, "Unix.md", b"one\ntwo\n")
    vault_write.overwrite_note(PROFILE, "Unix.md", "one\ntwo\nthree")
    assert path.read_bytes() == b"one\ntwo\nthree\n"


def test_a_note_saved_without_changes_is_byte_for_byte_the_same(vault):
    path = put(vault, "Same.md", b"---\r\ntitle: x\r\n---\r\n\r\nbody\r\n")
    content = path.read_bytes().decode().replace("\r\n", "\n").rstrip("\n")  # what read_note hands the editor
    vault_write.overwrite_note(PROFILE, "Same.md", content)
    assert path.read_bytes() == b"---\r\ntitle: x\r\n---\r\n\r\nbody\r\n"


def test_a_mixed_note_takes_the_style_most_of_its_lines_had(vault):
    crlf_mostly = put(vault, "A.md", b"a\r\nb\r\nc\n")
    lf_mostly = put(vault, "B.md", b"a\nb\nc\r\n")
    vault_write.overwrite_note(PROFILE, "A.md", "a\nb\nc")
    vault_write.overwrite_note(PROFILE, "B.md", "a\nb\nc")
    assert crlf_mostly.read_bytes() == b"a\r\nb\r\nc\r\n" and lf_mostly.read_bytes() == b"a\nb\nc\n"


def test_a_note_with_bytes_that_are_not_text_is_left_exactly_as_it_is(vault):
    raw = b"caf\xe9 au lait\n"  # Latin-1, not UTF-8
    path = put(vault, "Old.md", raw)
    assert vault_write.overwrite_note(PROFILE, "Old.md", "café au lait edited") == NOTE_NOT_TEXT
    assert path.read_bytes() == raw


def test_the_save_route_answers_422_for_such_a_note_and_saves_a_crlf_one_whole(vault, tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    client = TestClient(create_app())
    old = put(vault, "Old.md", b"caf\xe9\n")
    r = client.put("/api/vault/note", json={"path": "Old.md", "content": "x", "persona": "samantha"})
    assert r.status_code == 422 and "Old.md" in r.json()["detail"] and "isn't plain text" in r.json()["detail"]
    assert old.read_bytes() == b"caf\xe9\n"
    win = put(vault, "Win.md", b"a\r\n")
    r = client.put("/api/vault/note", json={"path": "Win.md", "content": "a\nb", "persona": "samantha"})
    assert r.status_code == 200 and win.read_bytes() == b"a\r\nb\r\n"
    assert not [f for f in os.listdir(vault) if f.endswith(".tmp")]
