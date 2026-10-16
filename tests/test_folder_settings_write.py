"""Reading and changing a folder's definition note from the Folder settings dialog (docs/decisions/087): only the
fields that differ are rewritten, everything else in the note stays, and a note that changed meanwhile is refused.
Creating the first definition is `test_root_folder_setup.py`. Everything runs in a temporary vault."""

import os
import time

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import folder_settings_write as sw
from sympose.folder_looks_write import Changed, Failed, Refused
from sympose.server import create_app
from sympose.vault_write_status import NOTE_DENIED

ALL = {"vault_folders": ["*"]}
NOTE = (
    "---\ntype: folder\nicon: old\naccent: '#be123c'\n---\n# Movies\n\nFilms I watched.\n\n"
    "## Template\n\n```yaml\nrole:\ntags: []\n```\n\nMy own closing remarks.\n"
)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    (root / "Movies").mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: false\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


def put_note(vault, text, rel="Movies/Movies.md", newline=""):
    with open(os.path.join(vault, rel), "w", encoding="utf-8", newline=newline) as f:
        f.write(text)


def read(vault, rel="Movies/Movies.md"):
    with open(os.path.join(vault, rel), encoding="utf-8", newline="") as f:
        return f.read()


def dialog(vault, **changes):
    """What the dialog sends when it opens on `vault`'s Movies definition and the user changes `changes`."""
    start = sw.read(ALL, "Movies")
    fields = {"purpose": start["purpose"], "template": start["template"]}
    fields.update({key: start[key] for key in ("icon", "accent", "accent_dark")})
    return sw.Settings(**{**fields, **changes})


def save(vault, **changes):
    return sw.save(ALL, "Movies", dialog(vault, **changes))


# --- read -----------------------------------------------------------------------------------


def test_read_gives_the_notes_own_values(vault):
    put_note(vault, NOTE)
    assert sw.read(ALL, "Movies") == {
        "editable": True, "defined": True, "purpose": "Films I watched.", "template": ["role:", "tags: []"],
        "template_source": "note", "icon": "old", "accent": "#be123c", "accent_dark": None,
    }


def test_read_gives_no_purpose_template_or_look_for_what_the_note_does_not_have(vault):
    put_note(vault, "# Movies\n")
    answer = sw.read(ALL, "Movies")
    assert (answer["purpose"], answer["template"], answer["icon"], answer["accent"]) == ("", [], None, None)


def test_read_ignores_a_look_value_of_the_wrong_shape(vault):
    put_note(vault, "---\nicon: Not A Name\naccent: red\naccent_dark: '#f2889b'\n---\n# Movies\n")
    answer = sw.read(ALL, "Movies")
    assert (answer["icon"], answer["accent"], answer["accent_dark"]) == (None, None, "#f2889b")


def test_read_of_a_note_that_is_not_text_is_a_refusal_not_a_crash(vault):
    with open(os.path.join(vault, "Movies", "Movies.md"), "wb") as f:
        f.write(b"\xff\xfe\x00bad")
    with pytest.raises(Refused, match="could not be read as text"):
        sw.read(ALL, "Movies")


def test_read_of_a_definition_the_persona_cannot_open_is_not_editable(vault):
    put_note(vault, NOTE)
    assert sw.read({"vault_folders": ["Movies/Sub"]}, "Movies") == {"editable": False}


# --- save, a definition that exists ---------------------------------------------------------


def test_saving_what_was_read_changes_nothing_and_does_not_touch_the_file(vault):
    put_note(vault, NOTE)
    before = os.stat(os.path.join(vault, "Movies", "Movies.md")).st_mtime_ns
    assert save(vault) is False
    assert read(vault) == NOTE and os.stat(os.path.join(vault, "Movies", "Movies.md")).st_mtime_ns == before


def test_a_new_icon_changes_only_the_icon_line(vault):
    put_note(vault, NOTE)
    save(vault, icon="film-roll")
    assert read(vault) == NOTE.replace("icon: old", "icon: film-roll")


def test_a_cleared_icon_removes_only_its_line(vault):
    put_note(vault, NOTE)
    save(vault, icon=None)
    assert read(vault) == NOTE.replace("icon: old\n", "")


def test_a_new_colour_pair_is_added_after_the_users_own_properties(vault):
    put_note(vault, NOTE.replace("accent: '#be123c'\n", ""))
    save(vault, accent="#be123c", accent_dark="#f2889b")
    assert read(vault) == NOTE.replace("accent: '#be123c'\n", "accent: '#be123c'\naccent_dark: '#f2889b'\n")


def test_a_new_purpose_changes_only_the_purpose_paragraph(vault):
    put_note(vault, NOTE)
    save(vault, purpose="Films and series.")
    assert read(vault) == NOTE.replace("Films I watched.", "Films and series.")


def test_new_template_lines_change_only_the_block_and_keep_what_follows_it(vault):
    put_note(vault, NOTE)
    save(vault, template=["role:", "year:"])
    assert read(vault) == NOTE.replace("tags: []", "year:")
    assert read(vault).endswith("My own closing remarks.\n")


def test_everything_at_once_is_one_write_with_each_part_changed(vault):
    put_note(vault, NOTE)
    save(vault, purpose="P.", template=["a:"], icon="book", accent=None, accent_dark="#7aa7e0")
    assert read(vault) == (
        "---\ntype: folder\nicon: book\naccent_dark: '#7aa7e0'\n---\n# Movies\n\nP.\n\n## Template\n\n```yaml\na:\n```\n\n"
        "My own closing remarks.\n"
    )


def test_a_definition_of_only_a_look_gets_a_purpose_and_a_template_later(vault):
    sw.save(ALL, "Movies", sw.Settings(icon="film-roll"))
    save(vault, purpose="Films.", template=["role:"])
    text = read(vault)
    assert text.startswith("---\nicon: film-roll\n---\n# Movies\n\nFilms.\n\n## Template") and defs.read_template(text) == "role:"


def test_a_purpose_over_the_limit_that_the_user_wrote_by_hand_does_not_block_an_icon_change(vault):
    long = "x" * (write_defs.MAX_PURPOSE + 100)
    put_note(vault, f"---\nicon: old\n---\n# Movies\n\n{long}\n\n## Template\n\n```yaml\n```\n")
    save(vault, icon="book")
    assert long in read(vault) and "icon: book" in read(vault)


def test_a_purpose_over_the_limit_is_refused_when_it_is_the_thing_changed(vault):
    put_note(vault, NOTE)
    with pytest.raises(Refused, match="at most"):
        save(vault, purpose="x" * (write_defs.MAX_PURPOSE + 1))
    assert read(vault) == NOTE


@pytest.mark.parametrize("lines", [["```"], ["a:"] * (write_defs.MAX_LINES + 1), ["---"]])
def test_template_lines_the_readers_could_not_read_back_are_refused_and_nothing_is_written(vault, lines):
    put_note(vault, NOTE)
    with pytest.raises(Refused):
        save(vault, template=lines)
    assert read(vault) == NOTE


def test_a_look_the_page_could_not_draw_is_refused_for_an_edit_too(vault):
    put_note(vault, NOTE)
    with pytest.raises(Refused, match="not an icon Sympose has"):
        save(vault, icon="nope")
    assert read(vault) == NOTE


def test_an_unusable_value_already_in_the_note_is_replaced_by_a_chosen_one_and_left_when_untouched(vault):
    put_note(vault, "---\nicon: Not A Name\n---\n# Movies\n")
    save(vault)  # the dialog saw no icon and the user chose none: nothing to do
    assert read(vault) == "---\nicon: Not A Name\n---\n# Movies\n"
    save(vault, icon="book")
    assert read(vault) == "---\nicon: book\n---\n# Movies\n"


def test_a_note_that_opens_a_properties_block_it_never_closes_is_not_repaired(vault):
    put_note(vault, "---\nicon: old\n# Movies\n\nFilms.\n")
    with pytest.raises(Refused, match="does not close"):
        save(vault, icon="book")


def test_an_unclosed_properties_block_is_not_edited_for_a_purpose_or_a_template_either(vault):
    unclosed = "---\nicon: old\ntype: x\n# Movies\n\nFilms.\n"
    put_note(vault, unclosed)
    with pytest.raises(Refused, match="does not close"):
        sw.save(ALL, "Movies", sw.Settings(purpose="Other.", template=["a:"], icon="old"))
    assert read(vault) == unclosed


def test_a_note_that_is_not_utf8_is_refused_and_not_changed(vault):
    with open(os.path.join(vault, "Movies", "Movies.md"), "wb") as f:
        f.write(b"---\nicon: a\n---\n\xff\xfe")
    with pytest.raises(Refused, match="not plain UTF-8"):
        sw.save(ALL, "Movies", sw.Settings(icon="book"))
    with open(os.path.join(vault, "Movies", "Movies.md"), "rb") as f:
        assert f.read() == b"---\nicon: a\n---\n\xff\xfe"


def test_a_note_that_changed_while_the_dialog_was_open_is_refused_and_not_overwritten(vault, monkeypatch):
    put_note(vault, NOTE)
    real = sw._edited

    def edited_by_someone_else(text, folder, settings):
        path = os.path.join(vault, "Movies", "Movies.md")
        os.utime(path, (time.time() + 60, time.time() + 60))  # another editor saved it after this read it
        return real(text, folder, settings)

    monkeypatch.setattr(sw, "_edited", edited_by_someone_else)
    with pytest.raises(Changed, match="changed while it was being read"):
        save(vault, icon="book")
    assert read(vault) == NOTE


def test_a_failed_write_is_a_failure_not_a_refusal(vault, monkeypatch):
    put_note(vault, NOTE)
    monkeypatch.setattr("sympose.vault_write.overwrite_note", lambda *a, **k: "Error: disk full")
    with pytest.raises(Failed, match="disk full"):
        save(vault, icon="book")


def test_a_write_the_persona_may_not_make_is_a_refusal_with_its_own_words_and_changes_nothing(vault, monkeypatch):
    put_note(vault, NOTE)
    monkeypatch.setattr("sympose.vault_write.overwrite_note", lambda *a, **k: NOTE_DENIED)
    with pytest.raises(Refused, match="may not write there") as caught:
        save(vault, icon="book")
    assert not isinstance(caught.value, Failed) and read(vault) == NOTE


def test_a_note_that_is_mostly_crlf_stays_crlf_on_every_line(vault):
    put_note(vault, NOTE.replace("\n", "\r\n"))
    save(vault, icon="book", purpose="New.", template=["a:"])
    text = read(vault)
    assert "\n" not in text.replace("\r\n", "") and "icon: book\r\n" in text and "New.\r\n" in text


def test_a_note_that_is_mostly_lf_keeps_its_lone_crlf_lines(vault):
    odd = NOTE.replace("Films I watched.\n", "Films I watched.\r\n")
    put_note(vault, odd)
    save(vault, icon="book")
    assert read(vault) == odd.replace("icon: old", "icon: book")


def test_saved_values_read_back_through_every_reader_sympose_uses(vault):
    put_note(vault, NOTE)
    save(vault, purpose="Films and series.", template=["role:", "year:"], icon="book", accent="#1d4ed8", accent_dark="#7aa7e0")
    answer = sw.read(ALL, "Movies")
    assert (answer["purpose"], answer["template"], answer["icon"], answer["accent"], answer["accent_dark"]) == (
        "Films and series.", ["role:", "year:"], "book", "#1d4ed8", "#7aa7e0",
    )
    assert defs.template_for_folder(vault, "Movies") == "---\nrole:\nyear:\n---"


def test_a_folder_scoped_below_the_definition_cannot_edit_it(vault):
    put_note(vault, NOTE)
    with pytest.raises(Exception):  # noqa: B017 - Missing: the folder is not there for this persona
        sw.save({"vault_folders": ["Other"]}, "Movies", sw.Settings(icon="book"))
    assert read(vault) == NOTE


# --- the routes, for a definition that exists -----------------------------------------------


@pytest.fixture
def client(vault):
    return TestClient(create_app())


def test_the_get_route_gives_the_notes_values_and_the_put_route_changes_one(client, vault):
    put_note(vault, NOTE)
    got = client.get("/api/vault/folder/settings", params={"folder": "Movies"}).json()
    assert got["icon"] == "old" and got["purpose"] == "Films I watched."
    body = {"path": "Movies", "purpose": got["purpose"], "template": got["template"], "icon": "film-roll", "accent": "#be123c"}
    assert client.put("/api/vault/folder/settings", json=body).json() == {"path": "Movies", "created": False}
    assert read(vault) == NOTE.replace("icon: old", "icon: film-roll")


def test_the_put_route_answers_409_when_the_note_changed_meanwhile(client, vault, monkeypatch):
    put_note(vault, NOTE)
    real = sw._edited

    def late(text, folder, settings):
        path = os.path.join(vault, "Movies", "Movies.md")
        os.utime(path, (time.time() + 60, time.time() + 60))
        return real(text, folder, settings)

    monkeypatch.setattr(sw, "_edited", late)
    response = client.put("/api/vault/folder/settings", json={"path": "Movies", "icon": "book"})
    assert response.status_code == 409 and read(vault) == NOTE


def test_the_put_route_answers_400_for_an_icon_outside_the_set(client, vault):
    put_note(vault, NOTE)
    response = client.put("/api/vault/folder/settings", json={"path": "Movies", "icon": "nope"})
    assert response.status_code == 400 and "not an icon Sympose has" in response.json()["detail"]


def test_the_get_route_answers_409_for_a_note_that_is_not_text(client, vault):
    with open(os.path.join(vault, "Movies", "Movies.md"), "wb") as f:
        f.write(b"\xff\xfe")
    assert client.get("/api/vault/folder/settings", params={"folder": "Movies"}).status_code == 409
