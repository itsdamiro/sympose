"""The purpose paragraph of a folder's definition (docs/decisions/033, stage 2): what the model is given (titles and
names, never text, properties or values), what comes back, and the four states of a proposal. The model is a fake."""

import os

import pytest

from sympose import settings_store
from sympose.engine import folder_purpose as fp
from sympose.engine import model as model_mod
from sympose.engine.prompt_text import PURPOSE_INSTRUCTIONS

ALL = {"vault_folders": ["*"]}
CLOUD = "gemini/gemini-2.5-flash"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(root)


class FakeModel:
    """Stands in for `call_model`: records every call, answers with `text` or raises `error`."""

    def __init__(self, text="These notes are about people.", truncated=False, error=None):
        self.text, self.truncated, self.error, self.calls = text, truncated, error, []

    def __call__(self, messages, model=None, num_ctx=None, max_tokens=None):
        self.calls.append({"messages": messages, "model": model, "num_ctx": num_ctx, "max_tokens": max_tokens})
        if self.error:
            raise self.error
        return model_mod.ModelReply(self.text, 10, self.truncated)


@pytest.fixture
def fake(monkeypatch):
    def install(**kwargs):
        made = FakeModel(**kwargs)
        monkeypatch.setattr(model_mod, "call_model", made)
        return made

    return install


def put(vault, rel, text="x"):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def people(vault, count=5, body="Private words in the body."):
    for n in range(count):
        put(vault, f"People/Person {n}.md", f"---\nrole: worker\nemail: p{n}@x.example\n---\n{body}")


def user_text(made):
    return made.calls[0]["messages"][1]["content"]


# --- what the model is given -----------------------------------------------------------------


def note(rel, title=None, name=None):
    meta = {k: v for k, v in (("title", title), ("name", name)) if v}
    return {"rel_path": rel, "file_name": os.path.basename(rel), "meta": meta, "body": ""}


def test_a_title_is_the_title_property_else_the_name_property_else_the_file_name():
    notes = [note("P/a.md", title="Real Title"), note("P/b.md", name="A Name"), note("P/File Name.md")]

    assert fp.titles_in(notes, "P") == ["Real Title", "A Name", "File Name"]


def test_a_title_that_is_not_text_is_not_sent_as_a_python_repr():
    notes = [note("P/a.md"), note("P/b.md"), note("P/c.md"), note("P/d.md"), note("P/e.md")]
    for n, bad in zip(notes, (["Dana", "Lee"], {"en": "X"}, 5, "   ", None)):
        n["meta"] = {"title": bad, "name": bad} if bad is not None else {}

    assert fp.titles_in(notes, "P") == ["a", "b", "c", "d", "e"]
    assert fp.titles_in([{**note("P/x.md"), "meta": {"title": ["no"], "name": " Real "}}], "P") == ["Real"]


def test_titles_are_sorted_by_path_and_the_definition_is_left_out():
    notes = [note("P/b.md"), note("P/a.md"), note("P/Sub/c.md"), note("P/P.md"), note("Q/z.md")]

    assert fp.titles_in(notes, "P") == ["a", "b", "c"]


def test_a_big_folder_shows_its_range_and_the_same_folder_gives_the_same_list():
    notes = [note(f"P/n{n:03d}.md") for n in range(100)]

    titles = fp.titles_in(notes, "P")

    assert len(titles) == 40 and titles[0] == "n000" and titles[-1] == "n099"
    assert titles == sorted(titles) and len(set(titles)) == 40 and titles == fp.titles_in(list(reversed(notes)), "P")
    assert fp.titles_in(notes, "P", 1) == ["n000"] and fp.titles_in(notes[:3], "P") == ["n000", "n001", "n002"]


def test_sub_folders_are_the_folders_directly_under_it_that_hold_notes():
    notes = [note("P/a.md"), note("P/Beta/x.md"), note("P/alpha/y.md"), note("P/alpha/deep/z.md"), note("P/P.md"), note("Q/Other/w.md")]

    assert fp.subfolders_of(notes, "P") == ["alpha", "Beta"]
    assert fp.subfolders_of([note(f"P/S{n:02d}/x.md") for n in range(20)], "P") == [f"S{n:02d}" for n in range(10)]


def test_the_request_holds_the_folder_its_titles_and_its_sub_folders_and_the_instruction():
    system, user = fp.request("People", ["Ann", "Bo"], ["Old"])

    assert system == {"role": "system", "content": PURPOSE_INSTRUCTIONS}
    assert user["content"] == "Folder: People\nTitles of some of the notes in it:\n- Ann\n- Bo\nNames of its sub-folders: Old\n\nDescription:"
    assert "sub-folders" not in fp.request("People", ["Ann"], [])[1]["content"]


def test_what_is_sent_never_holds_a_note_text_a_property_or_a_value(scratch, fake):
    people(scratch, body="Body words nobody may see.")
    put(scratch, "Templates/People template.md", "---\nsecretkey: secretvalue\ntags:\n  - mine\nup: '[[Someone]]'\n---\n")
    made = fake()

    fp.propose(ALL, "People")

    sent = user_text(made).lower()  # the instruction itself tells the model not to mention properties
    for private in ("body words", "secretkey", "secretvalue", "mine", "someone", "worker", "@x.example", "role", "email", "propert"):
        assert private not in sent


# --- what comes back -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("These notes are about people.", "These notes are about people."),
        ("  These notes\nare about   people.  ", "These notes are about people."),
        ('"These notes are about people."', "These notes are about people."),
        ("Description: These notes are about people.", "These notes are about people."),
        ("Purpose: Movies I watched. And more! Third sentence. Fourth.", "Movies I watched. And more!"),
        ("UNCLEAR", ""), ("unclear.", ""), ("UN CLEAR", ""), (" Unclear! ", ""),
        ("", None), ("   ", None), ("- one\n- two", None), ("# People\nAbout people.", None), ("1. one\n2. two", None), ("> quoted", None),
    ],
)
def test_a_reply_is_cleaned_into_the_purpose_or_an_unclear_or_nothing(reply, expected):
    assert fp.clean(reply) == expected


def test_a_reply_cut_by_the_limit_ends_at_its_last_whole_sentence():
    assert fp.clean("First sentence. Second sen", truncated=True) == "First sentence."
    assert fp.clean("First sentence. Second sentence.", truncated=True) == "First sentence. Second sentence."
    assert fp.clean("Cut before any end", truncated=True) is None
    assert fp.clean("First sentence. Second sen", truncated=False) == "First sentence. Second sen"


# --- the proposal ------------------------------------------------------------------------------------


def test_a_purpose_is_written_into_the_draft_beside_the_counted_template(scratch, fake):
    people(scratch)
    made = fake(text="These notes are about the people I know.")

    result = fp.propose(ALL, "People")

    assert result.state == fp.WRITTEN and len(made.calls) == 1
    assert result.draft.text.startswith("# People\n\nThese notes are about the people I know.\n\n## Template\n")
    assert result.draft.template == ["role: worker", "email:"] and "role: worker" in result.draft.text


def test_an_unclear_folder_has_the_template_and_no_purpose_and_no_invention(scratch, fake):
    people(scratch)
    fake(text="UNCLEAR")

    result = fp.propose(ALL, "People")

    assert result.state == fp.UNCLEAR and result.draft.text.startswith("# People\n\n## Template")


def test_a_model_that_fails_or_writes_nothing_gives_the_template_and_says_why(scratch, fake):
    people(scratch)
    fake(error=model_mod.EngineModelError("Couldn't reach model"))
    down = fp.propose(ALL, "People")
    fake(text="")
    empty = fp.propose(ALL, "People")

    assert (down.state, down.reason) == (fp.FAILED, "Couldn't reach model") and down.draft.text.startswith("# People\n\n## Template")
    assert empty.state == fp.FAILED and empty.reason and empty.draft.text.startswith("# People\n\n## Template")
    fake(error=model_mod.ReplyLimitError("spent it thinking"))
    assert fp.propose(ALL, "People").state == fp.FAILED  # a reasoning model that used its whole limit


def test_a_cloud_model_without_the_notes_approval_is_sent_nothing(scratch, fake):
    people(scratch)
    made = fake()

    result = fp.propose(ALL, "People", model=CLOUD)

    assert result.state == fp.WITHHELD and made.calls == [] and result.draft.text.startswith("# People\n\n## Template")
    for other in (["properties"], ["recaps"], "notes", None, [], ["bogus"]):
        settings_store.set("cloud_share", other)
        assert fp.propose(ALL, "People", model=CLOUD).state == fp.WITHHELD
    assert made.calls == []


def test_a_cloud_model_with_the_notes_approval_is_asked_and_a_local_one_always_is(scratch, fake):
    people(scratch)
    made = fake()
    settings_store.set("cloud_share", ["notes"])

    assert fp.propose(ALL, "People", model=CLOUD).state == fp.WRITTEN
    settings_store.set("cloud_share", [])
    assert fp.propose(ALL, "People", model="ollama_chat/gemma2:9b").state == fp.WRITTEN
    assert [c["model"] for c in made.calls] == [CLOUD, "ollama_chat/gemma2:9b"]


def test_the_model_is_the_personas_own_else_the_chat_model_setting(scratch, fake):
    people(scratch)
    made = fake()

    fp.propose({**ALL, "model": "ollama_chat/persona-model"}, "People")
    settings_store.set("chat_model", "ollama_chat/chosen")
    fp.propose(ALL, "People")

    assert [c["model"] for c in made.calls] == ["ollama_chat/persona-model", "ollama_chat/chosen"]


def test_a_local_model_gets_the_small_limit_and_a_cloud_model_room(scratch, fake):
    people(scratch)
    made = fake()
    settings_store.set("cloud_share", ["notes"])

    fp.propose(ALL, "People", model="ollama_chat/gemma2:9b")
    fp.propose(ALL, "People", model=CLOUD)

    assert made.calls[0]["max_tokens"] == 120 and made.calls[1]["max_tokens"] >= 1000 and made.calls[0]["num_ctx"]


def test_a_folder_that_cannot_have_a_definition_is_not_asked_about(scratch, fake):
    people(scratch)
    put(scratch, "Templates/Note template.md", "---\n---")
    made = fake()

    assert fp.propose(ALL, "Templates") is None and fp.propose(ALL, "Nothing") is None
    put(scratch, "People/People.md", "# People")
    assert fp.propose(ALL, "People") is None and made.calls == []


def test_proposing_writes_nothing(scratch, fake):
    people(scratch)
    fake()
    before = sorted(os.path.join(d, f) for d, _, files in os.walk(scratch) for f in files)

    fp.propose(ALL, "People")

    assert sorted(os.path.join(d, f) for d, _, files in os.walk(scratch) for f in files) == before


def test_a_cut_reply_is_ended_at_a_whole_sentence_in_the_draft(scratch, fake):
    people(scratch)
    fake(text="These notes are about people. They also hold conta", truncated=True)

    assert fp.propose(ALL, "People").draft.text.startswith("# People\n\nThese notes are about people.\n\n## Template")


def test_the_template_counted_and_the_titles_sent_are_of_the_same_read_of_the_vault(scratch, fake, monkeypatch):
    people(scratch)
    made = fake()
    reads = []
    real = fp.get_vault_snapshot
    monkeypatch.setattr(fp, "get_vault_snapshot", lambda *a: reads.append(a) or real(*a))
    from sympose import folder_definitions_write as write_defs

    monkeypatch.setattr(write_defs, "get_vault_snapshot", lambda *a: reads.append(a) or real(*a))
    fp.propose(ALL, "People")

    assert len(reads) == 1 and len(made.calls) == 1
