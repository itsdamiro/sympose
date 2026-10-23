"""A Slack message reaching a persona (docs/decisions/093): who may talk, the `slack` approval, the conversation a message
belongs to, one turn at a time, and what is said when the turn fails. The turn and the model are fakes."""

import json
import threading
import time

import pytest
from helpers import write_persona
from slack_shapes import BOT, OWNER, dm, mention, shared

from sympose import draft_limit, note_changes, settings_store, slack_approval, slack_channel, slack_credentials, slack_drafts, slack_files, slack_sessions
from sympose.engine import media, turn
from sympose.engine.turn_result import TurnResult
from sympose.slack_events import parse

LOCAL = "ollama_chat/gemma4:e4b"


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", f"name: Samantha\nmodel: {LOCAL}\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv(slack_credentials.OWNER_VARIABLE, OWNER)
    settings_store.set(slack_approval.SETTING, True)
    return base


@pytest.fixture
def turns(monkeypatch):
    """Every `run_turn` call as `(handle, message, session_id, kwargs)`; set `.fail` to raise, `.reply` and `.withheld` to shape the result."""
    class Turns(list):
        fail = None
        reply = "A **short** answer."
        withheld: list[str] = []
        proposes: list[tuple] = []  # (title, text) or (title, text, folder) of each new note the fake turn proposes
        elsewhere: list[tuple[str, str]] = []  # the same, proposed on another thread while the turn runs

    seen = Turns()

    def fake(handle, message, session_id=None, **kwargs):
        seen.append((handle, message, session_id, kwargs))
        for title, text, *folder in seen.proposes:
            note_changes.propose_create(handle, note_changes.new_note_path(), text, say="", title=title, folder=folder[0] if folder else None)
        for title, text in seen.elsewhere:
            other = threading.Thread(target=note_changes.propose_create, args=(handle, note_changes.new_note_path(), text), kwargs={"say": "", "title": title})
            other.start()
            other.join()
        if seen.fail:
            raise seen.fail
        return TurnResult(reply=seen.reply, session_id=session_id, withheld=list(seen.withheld))

    monkeypatch.setattr(turn, "run_turn", fake)
    return seen


def _answer(body, seen=None, token=""):
    return slack_channel.answer("samantha", parse(body, BOT), seen or slack_sessions.Seen(), token)


# --- who may talk -------------------------------------------------------------------------------
def test_the_owner_is_answered_in_slacks_own_format(home, turns):
    reply = _answer(dm("hi"))
    assert reply.text == "A *short* answer."
    assert turns[0][:2] == ("samantha", "hi")


def test_anyone_else_is_dropped_before_the_engine(home, turns):
    assert _answer(dm("hi", user="U0STRANGER")) is None
    assert _answer(mention(user="U0STRANGER")) is None
    assert turns == []


def test_without_an_owner_nobody_is_answered(home, turns, monkeypatch):
    monkeypatch.delenv(slack_credentials.OWNER_VARIABLE)
    assert _answer(dm("hi")) is None
    assert turns == []


def test_a_strangers_message_is_not_logged(home, turns, caplog):
    with caplog.at_level("DEBUG"):
        _answer(dm("a secret about the vault", user="U0STRANGER"))
    assert "secret" not in caplog.text


# --- the approval -------------------------------------------------------------------------------
def test_switched_off_says_so_and_runs_nothing(home, turns):
    settings_store.set(slack_approval.SETTING, False)
    reply = _answer(dm("hi"))
    assert reply.text == slack_channel.SWITCHED_OFF
    assert turns == []


def test_it_is_off_until_the_user_switches_it_on(home, turns, tmp_path):
    (tmp_path / "settings.json").unlink()
    assert slack_channel.approved() is False
    assert _answer(dm("hi")).text == slack_channel.SWITCHED_OFF


def test_a_setting_of_the_wrong_kind_leaves_it_off(home, turns):
    settings_store.set(slack_approval.SETTING, "yes")
    assert slack_channel.approved() is False


def test_the_approval_applies_to_a_local_model_too(home, turns):
    settings_store.set(slack_approval.SETTING, False)
    assert _answer(dm("hi")).text == slack_channel.SWITCHED_OFF  # the persona's model is local


# --- the conversation a message belongs to ------------------------------------------------------
def test_a_direct_message_continues_the_same_conversation(home, turns):
    _answer(dm("one", ts="1.1", event_id="E1"))
    _answer(dm("two", ts="2.2", event_id="E2", thread_ts="1.1"))
    assert turns[0][2] == turns[1][2]


def test_a_channel_thread_is_its_own_conversation_and_answered_in_the_thread(home, turns):
    first = _answer(mention(ts="5.5", event_id="E1"))
    second = _answer(mention(ts="6.6", thread_ts="5.5", event_id="E2"))
    third = _answer(mention(ts="7.7", event_id="E3"))
    assert turns[0][2] == turns[1][2] != turns[2][2]
    assert (first.thread_ts, second.thread_ts, third.thread_ts) == ("5.5", "5.5", "7.7")


def test_a_direct_message_is_answered_in_the_channel_not_a_thread(home, turns):
    assert _answer(dm("hi")).thread_ts is None


def test_a_channel_and_a_direct_message_are_not_one_conversation(home, turns):
    _answer(dm("one", event_id="E1"))
    _answer(mention(event_id="E2"))
    assert turns[0][2] != turns[1][2]


def test_a_redelivered_event_is_answered_once(home, turns):
    seen = slack_sessions.Seen()
    assert _answer(dm("hi"), seen) is not None
    assert _answer(dm("hi"), seen) is None
    assert len(turns) == 1


def test_slash_new_starts_another_conversation(home, turns):
    _answer(dm("one", event_id="E1"))
    reply = slack_channel.new_conversation("samantha", parse(dm("/new"), BOT))
    _answer(dm("two", event_id="E2"))
    assert reply.text == "New conversation."
    assert turns[0][2] != turns[1][2]


def test_slash_new_from_anyone_else_does_nothing(home, turns):
    _answer(dm("one", event_id="E1"))
    assert slack_channel.new_conversation("samantha", parse(dm("/new", user="U0STRANGER"), BOT)) is None
    _answer(dm("two", event_id="E2"))
    assert turns[0][2] == turns[1][2]


def test_slash_new_in_a_channel_says_to_use_a_thread(home, turns):
    reply = slack_channel.new_conversation("samantha", parse(mention(ts="9.9"), BOT))
    assert "thread" in reply.text and reply.thread_ts == "9.9"


# --- the turn -----------------------------------------------------------------------------------
def test_the_turn_may_propose_notes_and_is_told_it_is_in_slack(home, turns):
    _answer(dm("hi"))
    assert turns[0][3] == {"edits": True, "in_slack": True, "files": ()}


def test_a_note_the_turn_proposed_is_shown_under_the_reply_as_it_waits(home, turns):
    turns.proposes = [("Seeds", "# Seeds\n\nSow in March.\n")]

    text = _answer(dm("write it")).text

    assert text.startswith("A *short* answer.\n\n*New note: Seeds*\n```\n# Seeds\n\nSow in March.\n```")
    assert text.endswith(slack_drafts.FOOTER)
    assert len(note_changes.drafts("samantha")) == 1  # shown, and still waiting for Accept in the web app


def test_a_note_proposed_from_slack_counts_against_slacks_limit_and_the_web_chats_does_not(home, turns):
    turns.proposes = [("Mine", "# Mine\n\nAsked for here.\n")]
    turns.elsewhere = [("Theirs", "# Theirs\n\nAsked for in the web app.\n")]

    _answer(dm("write it"))

    assert draft_limit.waiting("samantha", draft_limit.SLACK) == 1 and len(note_changes.drafts("samantha")) == 2


def test_a_turn_at_slacks_limit_is_refused_the_note_but_not_the_turn(home, turns):
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    turns.proposes = [("One", "# One\n\nFirst.\n")]
    _answer(dm("write it"))
    turns.proposes = [("Two", "# Two\n\nSecond.\n")]

    with pytest.raises(note_changes.CannotAnchor, match="1 draft from Slack is waiting"):  # the fake turn does not catch what the real tool does
        _answer(dm("write another"))

    assert draft_limit.waiting("samantha", draft_limit.SLACK) == 1


def test_a_note_another_conversation_proposed_meanwhile_is_not_shown(home, turns):
    turns.proposes = [("Mine", "# Mine\n\nAsked for here.\n")]
    turns.elsewhere = [("Theirs", "# Theirs\n\nAsked for in the web app.\n")]

    text = _answer(dm("write it")).text

    assert "Mine" in text and "Theirs" not in text and "Asked for in the web app" not in text
    assert len(note_changes.drafts("samantha")) == 2


def test_a_reply_that_proposed_nothing_has_no_block(home, turns):
    assert _answer(dm("hi")).text == "A *short* answer."


def test_a_turn_that_failed_after_it_proposed_a_note_says_so_and_still_shows_the_note(home, turns):
    turns.proposes = [("Seeds", "# Seeds\n\nSow in March.\n")]
    turns.fail = turn.EngineModelError("down")

    text = _answer(dm("hi")).text

    assert text.startswith(slack_channel.NO_MODEL + "\n\n*New note: Seeds*") and "Sow in March." in text
    assert text.endswith(slack_drafts.FOOTER)
    assert len(note_changes.drafts("samantha")) == 1


def test_a_turn_that_failed_before_it_proposed_anything_says_only_its_one_line(home, turns):
    turns.fail = turn.EngineModelError("down")

    assert _answer(dm("hi")).text == slack_channel.NO_MODEL


def test_a_stopped_turn_says_nothing_even_if_it_had_proposed_a_note(home, turns):
    turns.proposes = [("Seeds", "# Seeds\n")]
    turns.fail = turn.TurnCancelled()

    assert _answer(dm("hi")) is None
    assert len(note_changes.drafts("samantha")) == 1  # whoever stopped it is at the web app, where it waits


def test_the_next_message_does_not_show_the_note_of_the_one_before(home, turns):
    turns.proposes = [("Seeds", "# Seeds\n")]
    _answer(dm("one", event_id="E1"))
    turns.proposes = []

    assert "Seeds" not in _answer(dm("two", event_id="E2")).text


def test_what_was_held_back_from_a_cloud_model_is_not_added_to_the_reply(home, turns):
    turns.withheld = ["notes", "memory"]
    assert _answer(dm("hi")).text == "A *short* answer."


@pytest.mark.parametrize("error, said", [
    (turn.EngineModelError("down"), slack_channel.NO_MODEL),
    (turn.PersonaNotFoundError("gone"), slack_channel.NO_PERSONA),
])
def test_a_failed_turn_says_one_plain_line(home, turns, error, said):
    turns.fail = error
    assert _answer(dm("hi")).text == said


def test_a_stopped_turn_says_nothing(home, turns):
    turns.fail = turn.TurnCancelled()
    assert _answer(dm("hi")) is None


def test_a_persona_that_is_gone_says_so(home, turns):
    assert slack_channel.answer("ghost", parse(dm("hi"), BOT), slack_sessions.Seen()).text == slack_channel.NO_PERSONA
    assert turns == []


def test_the_lock_is_let_go_after_a_failure(home, turns):
    turns.fail = turn.EngineModelError("down")
    _answer(dm("one", event_id="E1"))
    turns.fail = None
    assert _answer(dm("two", event_id="E2")).text == "A *short* answer."


def test_two_messages_to_one_persona_run_one_after_the_other(home, turns, monkeypatch):
    running, most, guard = 0, 0, threading.Lock()

    def measured(handle, message, session_id=None, **kwargs):
        nonlocal running, most
        with guard:
            running += 1
            most = max(most, running)
        time.sleep(0.1)
        with guard:
            running -= 1
        return TurnResult(reply="ok", session_id=session_id)

    monkeypatch.setattr(turn, "run_turn", measured)
    threads = [threading.Thread(target=_answer, args=(dm(f"m{i}", event_id=f"E{i}"),)) for i in range(3)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert most == 1


# --- the tokens ---------------------------------------------------------------------------------
def test_a_persona_has_tokens_only_with_both(monkeypatch):
    monkeypatch.setenv("SLACK_SAMANTHA_BOT_TOKEN", "xoxb-1")
    assert slack_credentials.tokens("samantha") is None
    monkeypatch.setenv("SLACK_SAMANTHA_APP_TOKEN", " xapp-1 ")
    assert slack_credentials.tokens("samantha") == ("xoxb-1", "xapp-1")


def test_tokens_are_read_by_the_personas_handle_alone(monkeypatch):
    monkeypatch.setenv("SLACK_ARCHIA_BOT_TOKEN", "xoxb-a")
    monkeypatch.setenv("SLACK_ARCHIA_APP_TOKEN", "xapp-a")
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    assert slack_credentials.tokens("samantha") is None
    assert slack_credentials.tokens("archia") == ("xoxb-a", "xapp-a")


def test_a_shared_token_pair_is_not_a_fallback(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-shared")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-shared")
    assert slack_credentials.tokens("samantha") is None


# --- the line in the terminal for each message (slack_trace) ---------------------------------------
@pytest.mark.parametrize("arrange, line", [
    (lambda turns, home: None, None),
    (lambda turns, home: setattr(turns, "fail", turn.EngineModelError("down")), "the model failed, said so"),
    (lambda turns, home: setattr(turns, "fail", turn.PersonaNotFoundError("gone")), "the persona was not found, said so"),
    (lambda turns, home: setattr(turns, "fail", turn.TurnCancelled()), "stopped while answering, no reply"),
    (lambda turns, home: settings_store.set(slack_approval.SETTING, False), "Slack is switched off in settings, said so"),
])
def test_what_happened_to_a_message_is_one_line_with_no_words_of_it(home, turns, capsys, arrange, line):
    arrange(turns, home)
    turns.reply = "the private reply"
    _answer(dm("a secret about the vault"))
    out = capsys.readouterr().out
    assert (line in out) if line else out == ""
    assert "secret" not in out and "private" not in out
    assert out.count("\n") == (1 if line else 0)
    assert out == "" or out.split(" ", 1)[1].startswith("samantha: ")


def test_a_message_from_anyone_else_is_a_line_that_says_so(home, turns, capsys):
    _answer(dm("a secret", user="U0STRANGER"))
    assert "samantha: ignored, not from the owner\n" in capsys.readouterr().out


def test_a_redelivery_is_a_line_that_says_so(home, turns, capsys):
    seen = slack_sessions.Seen()
    _answer(dm("hi", event_id="E1"), seen)
    capsys.readouterr()
    _answer(dm("hi", event_id="E1"), seen)
    assert "samantha: ignored, Slack delivered it again\n" in capsys.readouterr().out


def test_a_persona_that_is_gone_is_a_line_that_says_so(home, turns, capsys):
    slack_channel.answer("ghost", parse(dm("hi"), BOT), slack_sessions.Seen())
    assert "ghost: the persona was not found, said so\n" in capsys.readouterr().out


def test_a_message_stopped_before_it_ran_is_a_line_that_says_so(home, turns, capsys, monkeypatch):
    monkeypatch.setattr(slack_channel, "acquire", lambda *_: False)
    assert _answer(dm("hi")) is None
    assert turns == []
    assert "samantha: stopped before it ran, no reply\n" in capsys.readouterr().out


# --- files shared with the message (docs/decisions/093, "files attached in Slack") -------------------
@pytest.fixture
def fetched(monkeypatch):
    """Every `slack_files.fetch` call as `(files, token)`; set `.refuse` to a message to refuse them."""
    class Fetched(list):
        refuse = None

    calls = Fetched()

    def fake(files, token):
        calls.append((files, token))
        if calls.refuse:
            raise media.MediaRefused(calls.refuse)
        return tuple(media.make(f.name, b"%PDF bytes") for f in files)

    monkeypatch.setattr(slack_files, "fetch", fake)
    return calls


def _shared(text="read this", **more):
    return dm(text, subtype="file_share", files=[shared("notes.pdf")], **more)


def test_a_file_is_fetched_with_the_personas_token_and_given_to_the_turn_with_its_marker(home, turns, fetched):
    _answer(_shared(), token="xoxb-samantha")

    (files, token), = fetched
    assert token == "xoxb-samantha" and [f.name for f in files] == ["notes.pdf"]
    handle, message, _, kwargs = turns[0]
    assert message == "read this\n[attached: notes.pdf]"
    assert [f.name for f in kwargs["files"]] == ["notes.pdf"] and kwargs["files"][0].data == b"%PDF bytes"


def test_a_message_with_no_words_is_only_the_markers(home, turns, fetched):
    body = _shared()
    body["event"]["text"] = ""
    _answer(body)
    assert turns[0][1] == "[attached: notes.pdf]"


def test_a_message_without_files_fetches_nothing(home, turns, fetched):
    _answer(dm("hi"))
    assert fetched == [] and turns[0][1] == "hi"


def test_a_strangers_file_is_never_fetched(home, turns, fetched):
    assert _answer(_shared(user="U0STRANGER")) is None
    assert fetched == [] and turns == []


def test_a_file_is_not_fetched_when_slack_is_switched_off(home, turns, fetched):
    settings_store.set(slack_approval.SETTING, False)
    assert _answer(_shared()).text == slack_channel.SWITCHED_OFF
    assert fetched == []


def test_a_redelivered_event_fetches_the_file_once(home, turns, fetched):
    seen = slack_sessions.Seen()
    _answer(_shared(), seen)
    assert _answer(_shared(), seen) is None
    assert len(fetched) == 1 and len(turns) == 1


def test_files_that_cannot_be_taken_are_said_and_no_turn_runs(home, turns, fetched):
    fetched.refuse = "notes.pdf is empty."
    reply = _answer(_shared())
    assert reply.text == "notes.pdf is empty." and reply.thread_ts is None
    assert turns == []


def test_a_refusal_in_a_channel_is_answered_in_the_thread(home, turns, fetched):
    fetched.refuse = "At most 3 files can go with one message."
    body = mention(ts="5.5")
    body["event"]["files"] = [shared()]
    assert _answer(body).thread_ts == "5.5"


def test_the_refusal_has_a_line_in_the_terminal_without_the_files(home, turns, fetched, capsys):
    fetched.refuse = "secret-name.pdf is empty."
    _answer(_shared())
    out = capsys.readouterr().out
    assert "the files could not be taken, said so" in out and "secret-name" not in out


def test_the_files_are_fetched_with_the_conversations_lock_held(home, turns, monkeypatch):
    """A slow download must not let a later message of the same conversation run first."""
    inside = []

    def fake(files, token):
        inside.append(slack_channel.lock_for("samantha", None, LOCAL).locked())
        return ()

    monkeypatch.setattr(slack_files, "fetch", fake)
    _answer(_shared())
    assert inside == [True]


# --- buttons under a draft, and what a press does (ADR 093, amendment of 2026-10-23) -----------------
@pytest.fixture
def vault(home, tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    write_persona(home, "samantha", f"name: Samantha\nmodel: {LOCAL}\nvault_folders: '*'\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    return root


def _filed(turns, title="Seeds", text="# Seeds\n\nSow in March.\n"):
    """A reply that proposed one note, and the value its buttons carry."""
    turns.proposes = [(title, text, "Inbox")]
    reply = _answer(dm("write it", event_id=f"E-{title}"))
    return reply, reply.prompts[0]["blocks"][1]["elements"][0]["value"]


def _press(action, value, user=OWNER):
    return slack_channel.decide("samantha", user, action, value)


def test_a_note_shown_whole_is_offered_one_message_of_buttons_in_the_same_place(home, turns):
    turns.proposes = [("Seeds", "# Seeds\n\nSow in March.\n", "Inbox"), ("Roots", "# Roots\n", "Inbox")]

    reply = _answer(mention(ts="5.5"))

    assert [p["text"] for p in reply.prompts] == ["Save *Seeds* to Inbox?", "Save *Roots* to Inbox?"] and reply.thread_ts == "5.5"


def test_a_reply_that_proposed_nothing_is_offered_no_buttons(home, turns):
    assert _answer(dm("hi")).prompts == ()


def test_a_note_that_was_cut_is_offered_no_buttons(home, turns):
    turns.proposes = [("Long", "word " * 20000)]

    reply = _answer(dm("write it"))

    assert "Cut here" in reply.text and reply.prompts == ()


def test_a_turn_that_failed_after_it_proposed_a_note_still_offers_its_buttons(home, turns):
    turns.proposes = [("Seeds", "# Seeds\n\nSow in March.\n", "Inbox")]
    turns.fail = turn.EngineModelError("down")

    assert [p["text"] for p in _answer(dm("hi")).prompts] == ["Save *Seeds* to Inbox?"]


def test_pressing_accept_makes_the_note_replaces_the_buttons_and_frees_the_room(vault, turns):
    settings_store.set(draft_limit.SLACK_SETTING, 1)
    _, value = _filed(turns)

    decision = _press(slack_drafts.ACCEPT, value)

    assert decision == slack_channel.Decision("Saved *Seeds* as `Inbox/Seeds.md`.", True)
    assert (vault / "Inbox" / "Seeds.md").read_text() == "# Seeds\n\nSow in March.\n"
    assert note_changes.drafts("samantha") == [] and draft_limit.waiting("samantha", draft_limit.SLACK) == 0


def test_pressing_decline_forgets_the_draft_and_writes_nothing(vault, turns):
    _, value = _filed(turns)

    decision = _press(slack_drafts.DECLINE, value)

    assert decision == slack_channel.Decision("Declined *Seeds*; nothing was saved.", True)
    assert not (vault / "Inbox").exists() and note_changes.drafts("samantha") == []


def test_a_second_press_says_the_draft_is_not_waiting_and_writes_nothing_more(vault, turns):
    _, value = _filed(turns)
    _press(slack_drafts.ACCEPT, value)

    again = _press(slack_drafts.ACCEPT, value)

    assert again == slack_channel.Decision(slack_channel.NOT_WAITING, True)
    assert sorted(p.name for p in (vault / "Inbox").iterdir()) == ["Seeds.md"]


def test_a_press_after_the_draft_was_declined_in_the_web_app_says_it_is_not_waiting(vault, turns):
    _, value = _filed(turns)
    note_changes.forget("samantha", json.loads(value)[0])

    assert _press(slack_drafts.ACCEPT, value) == slack_channel.Decision(slack_channel.NOT_WAITING, True)


def test_a_press_from_anyone_else_changes_nothing_and_says_nothing(vault, turns):
    _, value = _filed(turns)

    assert _press(slack_drafts.ACCEPT, value, user="U0STRANGER") is None
    assert _press(slack_drafts.DECLINE, value, user="U0STRANGER") is None

    assert not (vault / "Inbox").exists() and len(note_changes.drafts("samantha")) == 1


def test_without_an_owner_nobody_may_press(vault, turns, monkeypatch):
    _, value = _filed(turns)
    monkeypatch.delenv(slack_credentials.OWNER_VARIABLE)

    assert _press(slack_drafts.ACCEPT, value) is None and len(note_changes.drafts("samantha")) == 1


def test_a_press_with_slack_switched_off_is_answered_to_the_owner_alone_and_writes_nothing(vault, turns):
    _, value = _filed(turns)
    settings_store.set(slack_approval.SETTING, False)

    assert _press(slack_drafts.ACCEPT, value) == slack_channel.Decision(slack_channel.SWITCHED_OFF, False)
    assert not (vault / "Inbox").exists() and len(note_changes.drafts("samantha")) == 1


def test_a_press_for_a_persona_that_is_gone_is_answered_to_the_owner_alone(vault, turns, monkeypatch):
    _, value = _filed(turns)
    monkeypatch.setattr(slack_channel.profile_mod, "resolve_profile", lambda handle: None)

    assert _press(slack_drafts.ACCEPT, value) == slack_channel.Decision(slack_channel.NO_PERSONA, False)


def test_a_refused_note_keeps_its_buttons_and_the_reason_goes_to_the_owner_alone(vault, turns):
    _, value = _filed(turns)
    (vault / "Inbox").mkdir()
    for n in range(1, 21):
        (vault / "Inbox" / (f"Seeds ({n}).md" if n > 1 else "Seeds.md")).write_text("x")

    decision = _press(slack_drafts.ACCEPT, value)

    assert decision.final is False and decision.text.startswith("Seeds could not be saved") and len(note_changes.drafts("samantha")) == 1


@pytest.mark.parametrize("value", ["", "not json", "{}", "[]", '["only one"]', '["a", "b", "c"]', "[1, 2]", '[null, "x"]', "7"])
def test_a_value_that_is_not_ours_is_ignored(vault, turns, value):
    _filed(turns)

    assert _press(slack_drafts.ACCEPT, value) is None and len(note_changes.drafts("samantha")) == 1


def test_a_value_naming_another_drafts_id_does_not_save_the_draft_it_names_a_path_for(vault, turns):
    _, value = _filed(turns)
    path, _ = json.loads(value)

    assert _press(slack_drafts.ACCEPT, json.dumps([path, "not-its-id"])) == slack_channel.Decision(slack_channel.NOT_WAITING, True)


@pytest.mark.parametrize("action, line", [
    (slack_drafts.ACCEPT, "samantha: button pressed (accept)\n"),
    (slack_drafts.DECLINE, "samantha: button pressed (decline)\n"),
])
def test_a_press_is_a_line_in_the_terminal(vault, turns, capsys, action, line):
    _, value = _filed(turns)
    capsys.readouterr()

    _press(action, value)

    assert line in capsys.readouterr().out


@pytest.mark.parametrize("action, line", [
    (slack_drafts.ACCEPT, "saved"), (slack_drafts.DECLINE, "declined"),
])
def test_what_became_of_a_press_is_a_line_with_no_name_or_path_in_it(vault, turns, capsys, action, line):
    _, value = _filed(turns)
    capsys.readouterr()

    _press(action, value)

    out = capsys.readouterr().out
    assert f"samantha: {line}\n" in out and "Seeds" not in out and "Inbox" not in out


def test_the_other_ways_a_press_ends_are_lines_too(vault, turns, capsys, monkeypatch):
    _, value = _filed(turns)
    capsys.readouterr()
    _press(slack_drafts.ACCEPT, value, user="U0STRANGER")
    _press(slack_drafts.ACCEPT, "nonsense")
    settings_store.set(slack_approval.SETTING, False)
    _press(slack_drafts.ACCEPT, value)
    settings_store.set(slack_approval.SETTING, True)
    _press(slack_drafts.ACCEPT, json.dumps(["new/none", "x"]))
    monkeypatch.setattr(slack_channel.profile_mod, "resolve_profile", lambda handle: None)
    _press(slack_drafts.ACCEPT, value)

    out = capsys.readouterr().out
    for line in ("ignored, not from the owner", "ignored, not a button of ours", "Slack is switched off in settings, said so",
                 "no longer waiting, said so", "the persona was not found, said so"):
        assert f"samantha: {line}\n" in out


def test_a_refusal_is_a_line_that_says_so(vault, turns, capsys):
    _, value = _filed(turns)
    (vault / "Inbox").mkdir()
    for n in range(1, 21):
        (vault / "Inbox" / (f"Seeds ({n}).md" if n > 1 else "Seeds.md")).write_text("x")
    capsys.readouterr()

    _press(slack_drafts.ACCEPT, value)

    assert "samantha: could not be saved, said so\n" in capsys.readouterr().out
