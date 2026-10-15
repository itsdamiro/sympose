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


def movies(vault, extra=""):
    put(vault, "Movies/Movies.md", f"---\ntype: folder\n{extra}---\nFilms.\n")


def answers(*replies):
    given = iter(replies)
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return next(given)

    ask.prompts = prompts
    return ask


def read(vault, rel):
    return open(os.path.join(vault, rel), encoding="utf-8").read()


def titled(vault, rel="Notes/old name.md", title="Better name"):
    put(vault, rel, f"---\ntitle: {title}\n---\nWords.")


# --- --fix (ADR 084) ------------------------------------------------------------------------
def test_health_never_asks_and_never_writes_and_says_where_the_fixes_are(scratch, monkeypatch):
    movies(scratch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked"))
    before = read(scratch, "Movies/Movies.md")

    code, text = run(vault_command.health)

    assert code == 0 and "Movies/Movies.md: has no icon" in text and "`sympose vault --fix`" in text
    assert read(scratch, "Movies/Movies.md") == before


def test_fix_adds_an_icon_only_on_a_yes(scratch):
    movies(scratch)
    before = read(scratch, "Movies/Movies.md")
    code, text = run(vault_command.fix, ask=answers("n"))
    assert code == 0 and "icon: film-roll" in text and "Left as it is." in text and "0 changed, 1 left as they are." in text
    assert read(scratch, "Movies/Movies.md") == before

    code, text = run(vault_command.fix, ask=answers("y"))
    now = read(scratch, "Movies/Movies.md")
    assert "Added to Movies/Movies.md." in text and "1 changed, 0 left" in text
    assert "icon: film-roll\n" in now and now.endswith("Films.\n") and "type: folder" in now
    assert "Folder definitions with no icon" not in run(vault_command.health)[1]


def test_fix_asks_about_each_repair_on_its_own_and_never_in_bulk(scratch):
    movies(scratch)
    put(scratch, "People/People.md", "---\ntype: folder\n---\nPeople.\n")
    ask = answers("y", "n")

    run(vault_command.fix, ask=ask)

    assert len(ask.prompts) == 2
    assert "icon:" in read(scratch, "Movies/Movies.md") and "icon:" not in read(scratch, "People/People.md")


def test_q_stops_the_walk_and_an_end_of_input_stops_it_too(scratch):
    movies(scratch)
    put(scratch, "People/People.md", "---\ntype: folder\n---\nPeople.\n")
    ask = answers("q")
    run(vault_command.fix, ask=ask)
    assert len(ask.prompts) == 1 and "icon:" not in read(scratch, "Movies/Movies.md") + read(scratch, "People/People.md")

    def eof(prompt):
        raise EOFError

    code, _ = run(vault_command.fix, ask=eof)
    assert code == 0 and "icon:" not in read(scratch, "Movies/Movies.md")


def test_fix_without_a_terminal_asks_nothing_and_changes_nothing(scratch):
    movies(scratch)
    code, text = run(vault_command.fix)  # stdin is not a terminal under pytest
    assert code == 1 and "needs a terminal" in text and "icon:" not in read(scratch, "Movies/Movies.md")


def test_fix_does_not_prompt_when_its_output_is_not_a_terminal(scratch, monkeypatch):
    movies(scratch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("asked"))
    assert run(vault_command.fix)[0] == 1  # `out` is a StringIO, so not a terminal


def test_a_title_rename_is_shown_and_made_only_on_a_yes_and_the_links_follow(scratch):
    titled(scratch)
    put(scratch, "Other/Linker.md", "See [[old name]] and [[Notes/old name|the note]].")
    code, text = run(vault_command.fix, ask=answers("n"))
    assert "Rename Notes/old name.md to Better name.md" in text and os.path.exists(os.path.join(scratch, "Notes/old name.md"))

    code, text = run(vault_command.fix, ask=answers("y"))

    assert code == 0 and "1 changed" in text
    assert not os.path.exists(os.path.join(scratch, "Notes/old name.md")) and os.path.exists(os.path.join(scratch, "Notes/Better name.md"))
    assert read(scratch, "Other/Linker.md") == "See [[Better name]] and [[Notes/Better name|the note]]."
    assert "Titles that are not the file name" not in run(vault_command.health)[1]


def test_a_title_that_cannot_be_a_name_or_is_taken_gets_no_offer_and_is_counted(scratch):
    titled(scratch, "A/colon.md", '"Why: this"')
    titled(scratch, "A/hash.md", '"Part #2"')
    put(scratch, "A/Taken.md", "Words.")
    titled(scratch, "A/third.md", "taken")  # differs from `Taken` only in case, and `Taken.md` is another note
    ask = answers()

    code, text = run(vault_command.fix, ask=ask)

    assert code == 0 and ask.prompts == [] and "3 more findings have no repair here." in text


def test_a_stale_folder_link_is_pointed_at_the_folder_its_note_moved_to(scratch):
    put(scratch, "Ideas/Idea.md", "The idea.")
    put(scratch, "Log/Day.md", "Read [[Projects/Idea#Start|it]], then [[Projects/Idea]] and ![[Projects/Idea]] again.\n")
    code, text = run(vault_command.health)
    assert code == 1 and "Links with a folder that no longer matches (1)" in text

    code, text = run(vault_command.fix, ask=answers("y"))

    assert "[[Projects/Idea]] becomes [[Ideas/Idea]]" in text and "Changed 3 links in Log/Day.md." in text
    assert read(scratch, "Log/Day.md") == "Read [[Ideas/Idea#Start|it]], then [[Ideas/Idea]] and ![[Ideas/Idea]] again.\n"
    assert run(vault_command.health)[0] == 0


def test_a_link_whose_name_several_notes_have_is_never_guessed(scratch):
    put(scratch, "A/Idea.md", "one")
    put(scratch, "B/Idea.md", "two")
    put(scratch, "Log/Day.md", "[[Projects/Idea]]")
    ask = answers()

    code, text = run(vault_command.fix, ask=ask)

    assert ask.prompts == [] and "1 more findings have no repair here." in text
    assert "2 notes have that name" in run(vault_command.health)[1]
    assert read(scratch, "Log/Day.md") == "[[Projects/Idea]]"


def test_a_repair_whose_note_changed_after_the_scan_is_refused_and_not_offered_again(scratch):
    put(scratch, "Ideas/Idea.md", "The idea.")
    put(scratch, "Log/Day.md", "[[Projects/Idea]]")

    def edit_then_yes(prompt):
        put(scratch, "Log/Day.md", "no link here now")
        return "y"

    code, text = run(vault_command.fix, ask=edit_then_yes)

    assert code == 1 and "not in the note any more" in text and "0 changed" in text


def test_a_rename_onto_a_name_taken_meanwhile_is_refused(scratch):
    titled(scratch)

    def take_the_name_then_yes(prompt):
        put(scratch, "Notes/Better name.md", "someone else's")
        return "y"

    code, text = run(vault_command.fix, ask=take_the_name_then_yes)

    assert code == 1 and "exists already, so nothing was changed" in text and "__note" not in text
    assert read(scratch, "Notes/old name.md").endswith("Words.") and read(scratch, "Notes/Better name.md") == "someone else's"


def test_fix_runs_through_the_launcher_and_excludes_the_other_options(scratch, capsys):
    assert launcher.main(["vault", "--fix"]) == 1  # no terminal under pytest
    assert "needs a terminal" in capsys.readouterr().out
    with pytest.raises(SystemExit) as stop:
        launcher.main(["vault", "--fix", "--health"])
    assert stop.value.code == 2


@pytest.mark.parametrize("answer", ["", "maybe", "nope"])
def test_anything_but_a_yes_leaves_a_repair_alone(scratch, answer):
    titled(scratch)

    run(vault_command.fix, ask=answers(answer))

    assert os.path.exists(os.path.join(scratch, "Notes/old name.md"))


@pytest.mark.parametrize("title", ["Ends with a dot.", "x" * 300, ".NET notes", "AUX", "Com3", "\"'90s music\"", "\"Her notes'\""])
def test_a_title_a_file_cannot_have_gets_no_repair(scratch, title):
    titled(scratch, "A/note.md", title)
    ask = answers()

    run(vault_command.fix, ask=ask)

    assert ask.prompts == []


def test_a_rename_made_by_fix_moves_the_personas_pending_changes_with_it(scratch):
    from sympose import note_changes, note_changes_store

    titled(scratch)
    note_changes.propose_edit("samantha", "Notes/old name.md", "Words.", find="Words", replace="Better words", say="Reworded.")
    assert note_changes_store.read("samantha", "Notes/old name.md")["proposals"]

    run(vault_command.fix, ask=answers("y"))

    assert not note_changes_store.read("samantha", "Notes/old name.md").get("proposals")
    (moved,) = note_changes_store.read("samantha", "Notes/Better name.md")["proposals"]
    assert (moved["find"], moved["replace"]) == ("Words", "Better words")


def test_the_summary_counts_a_repair_that_failed_apart_from_one_left_as_it_is(scratch, monkeypatch):
    from sympose import vault_fixes

    movies(scratch)
    titled(scratch, "Notes/one.md", "First")
    titled(scratch, "Notes/two.md", "Second")
    results = iter([(False, "It could not be done."), (True, "Done.")])
    monkeypatch.setattr(vault_fixes, "apply", lambda profile, repair: next(results))

    code, text = run(vault_command.fix, ask=answers("n", "y", "y"))

    assert code == 1 and "1 changed, 1 left as they are, 1 could not be made." in text


def test_ctrl_c_at_the_prompt_stops_like_q_and_still_gives_the_summary(scratch):
    movies(scratch)

    def interrupted(prompt):
        raise KeyboardInterrupt

    code, text = run(vault_command.fix, ask=interrupted)

    assert code == 0 and "0 changed, 0 left as they are." in text and "icon:" not in read(scratch, "Movies/Movies.md")


def test_ctrl_c_while_the_vault_is_scanned_between_two_prompts_stops_too(scratch, monkeypatch):
    from sympose import vault_health

    movies(scratch)
    put(scratch, "People/People.md", "---\ntype: folder\n---\nPeople.\n")
    real_scan, scans = vault_health.scan, []

    def interrupted_second_scan(profile):
        scans.append(1)
        if len(scans) == 2:
            raise KeyboardInterrupt
        return real_scan(profile)

    monkeypatch.setattr(vault_health, "scan", interrupted_second_scan)

    code, text = run(vault_command.fix, ask=answers("y"))

    assert code == 0 and "Stopped." in text and "1 changed, 0 left as they are." in text


def test_ctrl_c_during_the_first_scan_gives_the_summary_too(scratch, monkeypatch):
    from sympose import vault_health

    def interrupted(profile):
        raise KeyboardInterrupt

    monkeypatch.setattr(vault_health, "scan", interrupted)

    code, text = run(vault_command.fix, ask=answers())

    assert code == 0 and "Stopped." in text and "0 changed, 0 left as they are." in text


def test_ctrl_c_while_a_repair_is_being_made_says_which_note_to_look_at_and_counts_it_as_failed(scratch, monkeypatch):
    from sympose import vault_fixes

    titled(scratch)

    def interrupted(profile, repair):
        raise KeyboardInterrupt

    monkeypatch.setattr(vault_fixes, "apply", interrupted)

    code, text = run(vault_command.fix, ask=answers("y"))

    assert code == 1 and "Stopped while changing Notes/old name.md: it may be half made" in text
    assert "Stopped." in text and "0 changed, 0 left as they are, 1 could not be made." in text


def test_a_link_in_a_note_the_persona_may_not_write_says_so_like_a_rename_does(scratch):
    from sympose import vault_fixes

    put(scratch, "B/L.md", "[[Old/Idea]]")
    repair = vault_fixes.Repair(vault_fixes.RELINK, (), "B/L.md", "Old/Idea", "New/Idea")
    only_a = {"handle": "x", "vault_folders": ["A"]}

    assert vault_fixes.apply(only_a, repair) == (False, "This persona may not write there, so nothing was changed.")
    assert read(scratch, "B/L.md") == "[[Old/Idea]]"


def test_a_note_whose_name_another_note_shares_is_not_renamed(scratch):
    titled(scratch, "A/Dup.md", "Better name")
    put(scratch, "B/Dup.md", "The other one.")
    put(scratch, "L.md", "[[Dup]]")
    ask = answers()

    code, text = run(vault_command.fix, ask=ask)

    assert ask.prompts == [] and "1 more findings have no repair here." in text and os.path.exists(os.path.join(scratch, "A/Dup.md"))


def test_a_title_another_note_already_has_as_its_name_is_not_taken_by_a_rename(scratch):
    titled(scratch, "A/one.md", "Better name")
    put(scratch, "B/Better name.md", "Mine.")
    ask = answers()

    run(vault_command.fix, ask=ask)

    assert ask.prompts == []
