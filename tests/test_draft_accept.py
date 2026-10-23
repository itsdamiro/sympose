"""Accepting or declining a new-note draft without the web app (docs/decisions/093, "Accept and Decline in Slack"): the note
made, where and under what name, what is refused, and that nothing is written until it is asked for."""

import os
import threading

import pytest
from helpers import write_persona

from sympose import draft_accept, note_changes

H = "samantha"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    base = tmp_path / "profiles"
    write_persona(base, H, "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return root


def draft(title="Seeds", text="# Seeds\n\nSow in March.\n", folder="Inbox") -> tuple[str, str]:
    proposal = note_changes.propose_create(H, note_changes.new_note_path(), text, say="", title=title, folder=folder)
    (path,) = [e["path"] for e in note_changes.store.entries(H) if any(p["id"] == proposal["id"] for p in e["proposals"])]
    return path, proposal["id"]


def waiting() -> int:
    return len(note_changes.drafts(H))


# --- the name -------------------------------------------------------------------------------------
@pytest.mark.parametrize("title, name", [
    ("Seeds", "Seeds"),
    ("  Sowing   in\tMarch ", "Sowing in March"),
    ('a/b\\c:d*e?f"g<h>i|j#k^l[m]n', "a b c d e f g h i j k l m n"),
    ("", "Untitled"),
    (None, "Untitled"),
    ("///", "Untitled"),
    ("x" * 200, "x" * 80),
])
def test_a_title_becomes_a_file_name(title, name):
    assert draft_accept.file_name(title) == name


# --- accept ---------------------------------------------------------------------------------------
def test_accepting_makes_the_note_in_its_folder_with_the_text_it_holds_now_and_forgets_the_draft(vault):
    path, proposal_id = draft()
    note_changes.edit_draft(H, path, "# Seeds\n\nEdited since.\n")

    done = draft_accept.accept(H, path, proposal_id)

    assert done == draft_accept.Decided("Seeds", "Inbox/Seeds.md")
    assert (vault / "Inbox" / "Seeds.md").read_text() == "# Seeds\n\nEdited since.\n"
    assert waiting() == 0


def test_a_name_that_is_taken_is_numbered_and_the_note_there_is_not_touched(vault):
    (vault / "Inbox").mkdir()
    (vault / "Inbox" / "Seeds.md").write_text("mine")
    (vault / "Inbox" / "Seeds (2).md").write_text("mine too")
    path, proposal_id = draft()

    done = draft_accept.accept(H, path, proposal_id)

    assert done.path == "Inbox/Seeds (3).md"
    assert (vault / "Inbox" / "Seeds.md").read_text() == "mine" and (vault / "Inbox" / "Seeds (2).md").read_text() == "mine too"


def test_the_twentieth_name_is_still_tried(vault):
    (vault / "Inbox").mkdir()
    for n in range(1, 20):
        (vault / "Inbox" / (f"Seeds ({n}).md" if n > 1 else "Seeds.md")).write_text("x")
    path, proposal_id = draft()

    assert draft_accept.accept(H, path, proposal_id).path == "Inbox/Seeds (20).md"


def test_when_twenty_names_are_taken_nothing_is_made_and_the_draft_waits(vault):
    (vault / "Inbox").mkdir()
    for n in range(1, 21):
        (vault / "Inbox" / (f"Seeds ({n}).md" if n > 1 else "Seeds.md")).write_text("x")
    path, proposal_id = draft()

    with pytest.raises(draft_accept.Refused, match="Seeds could not be saved"):
        draft_accept.accept(H, path, proposal_id)

    assert not (vault / "Inbox" / "Seeds (21).md").exists() and waiting() == 1


def test_a_draft_with_no_folder_is_made_in_the_personas_main_folder(vault):
    path, proposal_id = draft(folder=None)

    done = draft_accept.accept(H, path, proposal_id)

    assert os.path.exists(vault / done.path)


def test_a_folder_outside_what_the_persona_may_write_to_is_refused_and_the_draft_waits(vault, tmp_path):
    write_persona(tmp_path / "profiles", "narrow", "name: Narrow\nvault_folders: Garden\n")
    proposal = note_changes.propose_create("narrow", note_changes.new_note_path(), "# Seeds\n", say="", title="Seeds", folder="Elsewhere")
    (path,) = [e["path"] for e in note_changes.store.entries("narrow")]

    with pytest.raises(draft_accept.Refused, match="outside what this persona may write to"):
        draft_accept.accept("narrow", path, proposal["id"])

    assert not (vault / "Elsewhere").exists() and len(note_changes.drafts("narrow")) == 1


def test_a_vault_that_cannot_be_written_is_refused_and_the_draft_waits(vault, monkeypatch):
    monkeypatch.setattr(draft_accept.vault_write_create, "create_note", lambda *a, **k: "Error: Failed to create note: disk full")
    path, proposal_id = draft()

    with pytest.raises(draft_accept.Refused, match="the vault could not be written"):
        draft_accept.accept(H, path, proposal_id)

    assert waiting() == 1


def test_a_draft_that_is_gone_is_said_to_be_gone_and_nothing_is_made(vault):
    path, proposal_id = draft()
    note_changes.forget(H, path)

    with pytest.raises(draft_accept.Gone):
        draft_accept.accept(H, path, proposal_id)

    assert not (vault / "Inbox").exists()


def test_a_wrong_proposal_id_is_gone_not_another_drafts_note(vault):
    path, _ = draft()
    other_path, other_id = draft("Other", "# Other\n")

    with pytest.raises(draft_accept.Gone):
        draft_accept.accept(H, path, other_id)

    assert waiting() == 2 and other_path != path


def test_a_draft_that_already_has_a_real_path_is_made_there_and_never_numbered(vault):
    (vault / "Garden").mkdir()
    proposal = note_changes.propose_create(H, "Garden/Real.md", "# Real\n", say="", title="Real", folder="Inbox")

    done = draft_accept.accept(H, "Garden/Real.md", proposal["id"])

    assert done.path == "Garden/Real.md" and (vault / "Garden" / "Real.md").read_text() == "# Real\n"
    assert not (vault / "Inbox").exists()


def test_a_draft_with_a_real_path_that_is_taken_is_refused_and_waits(vault):
    (vault / "Garden").mkdir()
    (vault / "Garden" / "Real.md").write_text("mine")
    proposal = note_changes.propose_create(H, "Garden/Real.md", "# Real\n", say="", title="Real")

    with pytest.raises(draft_accept.Refused, match="a note already exists at Garden/Real"):
        draft_accept.accept(H, "Garden/Real.md", proposal["id"])

    assert (vault / "Garden" / "Real.md").read_text() == "mine" and waiting() == 1


def test_a_persona_that_is_gone_is_refused_and_the_draft_waits(vault, monkeypatch):
    path, proposal_id = draft()
    monkeypatch.setattr(draft_accept.profile_mod, "resolve_profile", lambda handle: None)

    with pytest.raises(draft_accept.Refused, match="this persona was not found"):
        draft_accept.accept(H, path, proposal_id)

    assert waiting() == 1


def test_a_draft_forgotten_in_the_same_moment_elsewhere_still_gives_the_note(vault, monkeypatch):
    path, proposal_id = draft()
    real = note_changes.discard_proposal
    monkeypatch.setattr(draft_accept.note_changes, "discard_proposal", lambda *a: (real(*a), real(*a)))

    assert draft_accept.accept(H, path, proposal_id).path == "Inbox/Seeds.md"


def test_two_presses_at_once_make_one_note(vault):
    path, proposal_id = draft()
    results = []

    def press():
        try:
            results.append(draft_accept.accept(H, path, proposal_id).path)
        except draft_accept.Gone:
            results.append("gone")

    threads = [threading.Thread(target=press) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert sorted(results) == ["Inbox/Seeds.md"] + ["gone"] * 5
    assert sorted(os.listdir(vault / "Inbox")) == ["Seeds.md"]


# --- decline --------------------------------------------------------------------------------------
def test_declining_forgets_the_draft_and_writes_nothing(vault):
    path, proposal_id = draft()

    assert draft_accept.decline(H, path, proposal_id) == draft_accept.Decided("Seeds", None)

    assert waiting() == 0 and not (vault / "Inbox").exists()


def test_declining_a_draft_that_is_gone_says_so(vault):
    path, proposal_id = draft()
    note_changes.forget(H, path)

    with pytest.raises(draft_accept.Gone):
        draft_accept.decline(H, path, proposal_id)


def test_declining_a_draft_forgotten_between_the_look_and_the_forgetting_says_so(vault, monkeypatch):
    path, proposal_id = draft()

    def gone(*args):
        raise KeyError(proposal_id)

    monkeypatch.setattr(draft_accept.note_changes, "discard_proposal", gone)

    with pytest.raises(draft_accept.Gone):
        draft_accept.decline(H, path, proposal_id)


# --- one at a time, between programs -----------------------------------------------------------------
def test_an_accept_waits_for_another_program_that_is_accepting(vault):
    """The web app and `sympose slack` are two programs: a lock on a file in the persona's folder makes a press that reaches both
    wait for the first, which has then forgotten the draft, so the second finds it gone and no numbered copy is made."""
    import fcntl

    from sympose import persona_files

    path, proposal_id = draft()
    outcome = []
    os.makedirs(os.path.dirname(persona_files.slack_path(H, draft_accept.LOCK)), exist_ok=True)
    other = open(persona_files.slack_path(H, draft_accept.LOCK), "a")  # what the other program holds while it works
    fcntl.flock(other, fcntl.LOCK_EX)
    worker = threading.Thread(target=lambda: outcome.append(draft_accept.accept(H, path, proposal_id)))
    worker.start()
    worker.join(0.5)
    assert worker.is_alive() and not (vault / "Inbox" / "Seeds.md").exists()

    other.close()
    worker.join(5)

    assert outcome == [draft_accept.Decided("Seeds", "Inbox/Seeds.md")]
