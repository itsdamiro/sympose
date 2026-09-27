"""`sympose vault` (docs/decisions/034): the two options, the exit codes, and that a draft is written only on a yes.
Runs in a temporary vault and settings file; the model is a fake."""

import io
import os

import pytest

from sympose import launcher, vault_command
from sympose.engine import model as model_mod


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "none"))
    monkeypatch.setattr(model_mod, "call_model", lambda *a, **k: model_mod.ModelReply("Notes about the people I work with.", 8, False))
    return str(root)


def put(vault, rel, text="Some words."):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def people(vault, count=5):
    for n in range(count):
        put(vault, f"People/P{n}.md", f"---\nrole: worker\n---\nText {n}.")


def run(fn, *args, **kwargs):
    out = io.StringIO()
    return fn(*args, out=out, **kwargs), out.getvalue()


# --- --health -------------------------------------------------------------------------------
def test_health_exits_zero_when_nothing_is_wrong_and_one_when_something_is(scratch):
    put(scratch, "A/Fine.md")
    assert run(vault_command.health)[0] == 0

    put(scratch, "A/Empty.md", "")
    code, out = run(vault_command.health)

    assert code == 1 and "Empty notes (1)" in out


def test_a_folder_offered_a_definition_does_not_make_health_exit_one(scratch):
    people(scratch)

    code, out = run(vault_command.health)

    assert code == 0 and "Folders due a definition (1)" in out


def test_health_says_so_when_there_is_no_vault_or_no_such_persona(scratch, monkeypatch, tmp_path):
    (tmp_path / "none").mkdir()  # a profiles folder that exists is what makes an unknown persona fail closed
    code, out = run(vault_command.health, "nobody")
    assert code == 1 and "no persona named 'nobody'" in out

    monkeypatch.setenv("VAULT_PATHS", "")
    code, out = run(vault_command.health)
    assert code == 1 and "no vault is set up" in out


# --- --draft --------------------------------------------------------------------------------
def test_a_draft_is_shown_and_not_written_when_the_answer_is_no(scratch):
    people(scratch)

    code, out = run(vault_command.draft, "People", ask=lambda prompt: "n")

    assert code == 0 and "Draft of People/People.md:" in out and "Notes about the people I work with." in out
    assert "role:" in out and "counted from 5 notes" in out and "Not written." in out
    assert not os.path.exists(os.path.join(scratch, "People/People.md"))


@pytest.mark.parametrize("answer", ["", "maybe", "yep"])
def test_anything_but_a_yes_writes_nothing(scratch, answer):
    people(scratch)

    run(vault_command.draft, "People", ask=lambda prompt: answer)

    assert not os.path.exists(os.path.join(scratch, "People/People.md"))


def test_no_answer_at_all_writes_nothing(scratch):
    people(scratch)

    def closed(prompt):
        raise EOFError

    code, out = run(vault_command.draft, "People", ask=closed)

    assert code == 0 and "Not written." in out and not os.path.exists(os.path.join(scratch, "People/People.md"))


@pytest.mark.parametrize("answer", ["y", "YES", " yes "])
def test_a_yes_writes_the_note_shown(scratch, answer):
    people(scratch)

    code, out = run(vault_command.draft, "People", ask=lambda prompt: answer)

    written = open(os.path.join(scratch, "People/People.md"), encoding="utf-8").read()
    assert code == 0 and "Created note" in out
    assert "Notes about the people I work with." in written and "role:" in written


def test_a_folder_that_cannot_have_a_definition_says_so_and_asks_nothing(scratch):
    people(scratch)
    put(scratch, "People/People.md", "mine")

    def never(prompt):
        raise AssertionError("asked")

    code, out = run(vault_command.draft, "People", ask=never)
    assert code == 1 and "cannot be given a definition" in out
    assert run(vault_command.draft, "Nowhere", ask=never)[0] == 1


def test_a_model_that_cannot_help_gives_a_draft_that_says_why_and_still_asks(scratch, monkeypatch):
    people(scratch)

    def down(*a, **k):
        raise model_mod.EngineModelError("connection refused")

    monkeypatch.setattr(model_mod, "call_model", down)

    code, out = run(vault_command.draft, "People", ask=lambda prompt: "n")

    assert code == 0 and "could not write a purpose (connection refused)" in out and "role:" in out


# --- the command line -----------------------------------------------------------------------
def test_the_command_has_health_and_draft_and_they_exclude_each_other(scratch, capsys):
    with pytest.raises(SystemExit) as stop:
        launcher.main(["vault", "--health", "--draft", "People"])

    assert stop.value.code == 2 and "not allowed with" in capsys.readouterr().err


def test_vault_with_no_option_prints_its_help(scratch, capsys):
    assert launcher.main(["vault"]) == 0

    out = capsys.readouterr().out
    assert "--health" in out and "--draft" in out and "--persona" in out


def test_vault_health_runs_through_the_launcher(scratch, capsys):
    put(scratch, "A/Empty.md", "")

    assert launcher.main(["vault", "--health"]) == 1

    assert "Empty notes (1)" in capsys.readouterr().out


def test_a_note_that_appeared_after_the_draft_was_shown_is_not_overwritten_and_says_so(scratch):
    people(scratch)

    def answer_after_it_appears(prompt):
        put(scratch, "People/People.md", "written meanwhile")
        return "y"

    code, out = run(vault_command.draft, "People", ask=answer_after_it_appears)

    assert code == 1 and "exists already, so nothing was changed" in out and "__note" not in out
    assert open(os.path.join(scratch, "People/People.md"), encoding="utf-8").read() == "written meanwhile"


def test_draft_reads_as_the_persona_it_is_given(scratch, tmp_path, capsys):
    (tmp_path / "none").mkdir()

    assert launcher.main(["vault", "--draft", "People", "--persona", "nobody"]) == 1

    assert "no persona named 'nobody'" in capsys.readouterr().out
