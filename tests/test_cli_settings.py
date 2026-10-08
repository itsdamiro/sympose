"""`/settings` in the terminal chat (docs/decisions/036): the list, flipping a toggle or a choice,
typing a number, and the module — not the screen — deciding what is valid."""

import asyncio

import pytest
from helpers import write_persona

from sympose import engine, settings_store
from sympose.cli import commands, settings_list, settings_registry as registry
from sympose.cli.app import SymposeCLI
from sympose.cli.composer import DEFAULT_PLACEHOLDER
from sympose.engine import settings_apply as apply, budget, edit_turn, embeddings, followup, memory, memory_refresh, recap

# The rows, in the order the list shows them, and the digit that chooses each (1 to 9).
KEYS = [
    "show_grounding", "show_trim_notice", "show_context_meter", "show_background_status", "status_typing", "reply_reveal",
    "context_window", "reply_limit", "history_tokens", "model_timeout", "grounding_followups", "session_recaps", "recap_count", "recap_chars", "past_chats", "connections_by_meaning", "connections_relevance", "auto_compact", "compact_at", "compact_to",
    "grounding_search", "embedding_min_similarity", "embedding_margin", "library_sync_limit", "vault_lookup", "vault_lookup_rounds",
    "memory_remember", "memory_rewrite", "memory_auto_refresh", "parallel_replies", "edit_mode", "show_note_marker", "open_note_cap", "annotations_cap", "skill_lookup", "skill_cap",
]


def run_async(coro):
    return asyncio.run(coro)


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


def _lines(app):
    return [plain_text(c) for c in app.transcript.children]


@pytest.fixture(autouse=True)
def no_background_builds(monkeypatch):
    monkeypatch.setattr(engine, "refresh_recaps", lambda handle, model=None: None)
    monkeypatch.setattr(engine, "refresh_embeddings", lambda handle: None)
    monkeypatch.setattr(engine, "refresh_status_phrases", lambda handle, model=None: None)


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    write_persona(base, "samantha", "name: Samantha\nhandle: samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def _setting(key):
    return registry.find(key)


# -- the registry ----------------------------------------------------------


def test_the_list_holds_the_agreed_settings_in_order():
    assert [s.key for s in registry.SETTINGS] == KEYS
    assert len(set(KEYS)) == len(KEYS)


def test_a_setting_that_has_a_home_of_its_own_is_not_listed():
    listed = {s.key for s in registry.SETTINGS}
    assert not listed & {"chat_model", "default_persona", "cloud_share", "active_vault", "added_vaults"}


def test_settings_is_a_real_command_now():
    command = commands.find_command("/settings")
    assert "not available" not in command.summary and "mock" not in command.summary


@pytest.mark.shipped_defaults
def test_every_toggle_is_on_when_nothing_is_set_except_the_off_by_default_ones():
    """`memory_remember` ships off (docs/decisions/041: trusting a model with even a safe,
    append-only write is the user's own call, never a default). `memory_auto_refresh` ships off
    too, and `show_note_marker` (docs/decisions/072: the line costs a model without tools about half its edits);
    unlike recaps, a context.md/profile.md check shares the same model a real chat turn
    needs, and is not worth running on its own every launch (measured live, 2026-09-29)."""
    off_by_default = {memory.REMEMBER_SETTING, memory_refresh.AUTO_REFRESH_SETTING, edit_turn.SHOW_MARKER_SETTING}
    for s in registry.SETTINGS:
        if s.kind != registry.TOGGLE:
            continue
        assert s.current() is (s.key not in off_by_default), s.key


def test_every_row_fits_an_80_column_terminal_on_one_line():
    """The picker's border, margin and row number take about 6 of the 80 columns."""
    assert max(len(o.label) for o in settings_list.options()) + 6 <= 76


# -- how a value reads ------------------------------------------------------


def test_a_value_reads_as_on_off_a_word_or_a_number_and_says_when_it_is_the_default():
    assert apply.value_text(_setting("show_grounding")) == "on"
    settings_store.set("show_grounding", False)
    assert apply.value_text(_setting("show_grounding")) == "off"
    assert apply.value_text(_setting("grounding_followups")) == "on"
    assert apply.value_text(_setting("context_window")) == "automatic"
    assert apply.value_text(_setting("reply_reveal")) == "50 (default)"
    settings_store.set("reply_reveal", 35)
    settings_store.set("context_window", 8192)
    assert apply.value_text(_setting("reply_reveal")) == "35"
    assert apply.value_text(_setting("context_window")) == "8192"
    assert apply.value_text(_setting("embedding_min_similarity")) == "0.72 (default)"


def test_large_and_long_numbers_read_exactly_as_saved():
    settings_store.set("context_window", 1048576)
    settings_store.set("embedding_min_similarity", 0.123456789)
    assert apply.value_text(_setting("context_window")) == "1048576"  # not 1.04858e+06
    assert apply.value_text(_setting("embedding_min_similarity")) == "0.123456789"


# -- toggles and choices -----------------------------------------------------


def test_a_toggle_turns_off_by_writing_false_and_back_on_by_removing_the_key():
    setting = _setting("show_trim_notice")
    assert apply.flip(setting) == "The notice that older messages were left out (show_trim_notice) is now off."
    assert settings_store.get("show_trim_notice") is False
    assert apply.flip(setting) == "The notice that older messages were left out (show_trim_notice) is now on."
    assert settings_store.get("show_trim_notice") is None  # the default applies again, not a copy of it


@pytest.mark.shipped_defaults
def test_every_toggle_really_changes_what_its_module_reads():
    for setting in registry.SETTINGS:
        if setting.kind != registry.TOGGLE:
            continue
        start = setting.current()
        apply.flip(setting)
        assert setting.current() is not start, setting.key
        apply.flip(setting)
        assert setting.current() is start, setting.key


def test_the_followup_choice_steps_off_and_back():
    setting = _setting("grounding_followups")
    apply.flip(setting)
    assert settings_store.get("grounding_followups") == "off" and followup.enabled() is False
    apply.flip(setting)
    assert settings_store.get("grounding_followups") is None and followup.enabled() is True


def test_the_search_choice_steps_through_all_four_and_the_default_removes_the_key(monkeypatch):
    monkeypatch.setattr(embeddings, "DEFAULT_MODE", embeddings.AUTO)  # what ships (the tests default to keywords)
    setting = _setting("grounding_search")
    seen = []
    for _ in range(4):
        apply.flip(setting)
        seen.append((embeddings.mode(), settings_store.get("grounding_search")))
    assert seen == [
        ("keywords", "keywords"), ("embeddings", "embeddings"), ("hybrid", "hybrid"), ("auto", None),
    ]


def test_memory_remember_ships_off_and_turns_on_by_writing_true():
    setting = _setting("memory_remember")
    assert apply.value_text(setting) == "off"
    assert apply.flip(setting) == "Adding to decisions.md when asked to remember (memory_remember) is now on."
    assert settings_store.get("memory_remember") is True
    assert apply.flip(setting) == "Adding to decisions.md when asked to remember (memory_remember) is now off."
    assert settings_store.get("memory_remember") is None


def test_memory_rewrite_steps_between_ask_and_auto_and_the_default_removes_the_key():
    setting = _setting("memory_rewrite")
    assert apply.value_text(setting) == "ask"
    apply.flip(setting)
    assert settings_store.get("memory_rewrite") == "auto"
    apply.flip(setting)
    assert settings_store.get("memory_rewrite") is None  # ask is the default, so it removes the key


def test_a_toggle_that_ships_off_would_be_written_on_and_removed_when_off():
    """`_flip` does not assume every toggle ships on: the default's value is what removes the key."""
    shipped_off = registry.Setting(
        "some_knob", registry.TOGGLE, "a knob", lambda: settings_store.get("some_knob", False), lambda: False
    )
    apply.flip(shipped_off)
    assert settings_store.get("some_knob") is True
    apply.flip(shipped_off)
    assert settings_store.get("some_knob") is None


def test_a_choice_whose_write_is_not_read_back_says_it_could_not_save(monkeypatch):
    monkeypatch.setattr(settings_store, "set", lambda key, value: False)
    assert apply.flip(_setting("show_grounding")) == "Couldn't save The notes used for a reply, in its header (show_grounding)."


def test_a_change_the_module_does_not_read_back_is_reported_not_claimed():
    stuck = registry.Setting("show_grounding", registry.TOGGLE, "a knob that ignores its setting", lambda: True)
    assert apply.flip(stuck) == "Couldn't save A knob that ignores its setting (show_grounding)."


# -- numbers ------------------------------------------------------------------


def _type(key, text):
    return apply.set_number(_setting(key), text)


def test_a_valid_number_is_saved_and_ends_the_prompt():
    assert _type("context_window", "8192") == ("How much text a local model takes (context_window) is now 8192.", True)
    assert settings_store.get("context_window") == 8192 and budget.context_setting() == 8192


def test_a_number_the_module_raises_is_kept_and_the_line_says_what_is_in_force():
    message, done = _type("context_window", "1000")
    assert done is True
    assert message.startswith("How much text a local model takes (context_window) is now 2048 (1000 was adjusted:")
    assert budget.context_setting() == 2048


def test_a_number_the_module_ignores_is_refused_and_leaves_things_as_they_were():
    message, done = _type("reply_limit", "10")
    assert done is False and message.startswith("10 is not valid for Space kept for the reply (reply_limit):") and "left as it was" in message
    assert settings_store.get("reply_limit") is None  # nothing was there, so nothing is left behind
    _type("reply_limit", "100")
    _type("reply_limit", "10")
    assert settings_store.get("reply_limit") == 100  # what was there before comes back


@pytest.mark.parametrize(
    "key, text",
    [("embedding_min_similarity", "7"), ("embedding_min_similarity", "1"), ("embedding_min_similarity", "0"),
     ("embedding_margin", "7"), ("embedding_margin", "-0.1"), ("reply_reveal", "-1")],
)
def test_out_of_range_values_are_refused(key, text):
    message, done = _type(key, text)
    assert done is False and "is not valid for" in message
    assert settings_store.get(key) is None


@pytest.mark.parametrize(
    "key, text, stored",
    [("embedding_min_similarity", "0.74", 0.74), ("embedding_margin", "0", 0), ("embedding_margin", "1", 1),
     ("reply_reveal", "0", 0), ("reply_reveal", "35", 35), ("reply_reveal", "35.0", 35), ("reply_reveal", "2.5", 2.5),
     ("reply_reveal", "  20  ", 20)],
)
def test_in_range_values_are_saved_as_typed(key, text, stored):
    message, done = _type(key, text)
    assert done is True and message.startswith(f"{apply.label(_setting(key))} is now")
    assert settings_store.get(key) == stored
    assert type(settings_store.get(key)) is type(stored)  # 35 stays a whole number, not 35.0


@pytest.mark.parametrize("key, text", [("context_window", "abc"), ("context_window", "8192.5"), ("context_window", "8k"),
                                       ("reply_reveal", "fast"), ("reply_reveal", "nan"), ("reply_reveal", "inf")])
def test_something_that_is_not_a_number_keeps_the_prompt_open_and_saves_nothing(key, text):
    message, done = _type(key, text)
    assert done is False and message.startswith(f"'{text}' is not a")
    assert settings_store.get(key) is None


def test_an_enormous_whole_number_is_taken_or_refused_but_never_crashes():
    message, done = _type("context_window", "9" * 400)
    assert isinstance(message, str) and done in (True, False)


def test_whole_number_settings_say_whole_number():
    assert "is not a whole number" in _type("reply_limit", "1.5")[0]
    assert "is not a number" in _type("reply_reveal", "x")[0]


def test_an_empty_entry_puts_the_default_back():
    settings_store.set("context_window", 4096)
    assert _type("context_window", "") == ("How much text a local model takes (context_window) is back to automatic.", True)
    assert settings_store.get("context_window") is None
    settings_store.set("reply_reveal", 10)
    assert _type("reply_reveal", "   ") == ("How fast a reply is written out (reply_reveal) is back to 50 (default).", True)


def test_when_the_old_value_cannot_be_put_back_it_says_so(monkeypatch):
    real_set = settings_store.set
    calls = []

    def flaky_set(key, value):
        calls.append(value)
        return real_set(key, value) if len(calls) == 1 else False  # the write works, the put-back does not

    apply.set_number(_setting("reply_limit"), "100")
    monkeypatch.setattr(settings_store, "set", flaky_set)
    message, done = _type("reply_limit", "10")
    assert done is False and "Couldn't put it back" in message and "left as it was" not in message


def test_a_save_that_fails_says_so_and_keeps_the_prompt_open(monkeypatch):
    monkeypatch.setattr(settings_store, "set", lambda key, value: False)
    assert _type("context_window", "8192") == ("Couldn't save How much text a local model takes (context_window).", False)


# -- through the chat, with real key presses -----------------------------------


async def _open(pilot, app):
    await pilot.pause()
    app.composer.focus()
    await pilot.press(*"/settings", "enter")
    await pilot.pause()


def test_slash_settings_lists_every_setting_with_its_value(profiles):
    settings_store.set("show_grounding", False)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            assert app.panel_kind == settings_list.PICKER_KIND
            labels = [str(app.panel.get_option_at_index(i).prompt) for i in range(app.panel.option_count)]
            assert len(labels) == 36
            assert "(show_grounding) — off" in labels[0]
            assert "(status_typing) — 40 (default)" in labels[4]
            assert "(reply_reveal) — 50 (default)" in labels[5]
            assert "(context_window) — automatic" in labels[6]

    run_async(scenario())


def test_choosing_a_toggle_flips_it_and_the_list_opens_again_on_that_row(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("2")
            await pilot.pause()
            assert settings_store.get("show_trim_notice") is False
            assert app.panel_kind == settings_list.PICKER_KIND and app.panel.highlighted == 1
            assert "(show_trim_notice) — off" in str(app.panel.get_option_at_index(1).prompt)
            assert "The notice that older messages were left out (show_trim_notice) is now off." in _lines(app)
            await pilot.press("2")
            await pilot.pause()
            assert settings_store.get("show_trim_notice") is None
            assert "The notice that older messages were left out (show_trim_notice) is now on." in _lines(app)

    run_async(scenario())


def test_choosing_a_number_asks_for_it_in_the_chat_box_and_saves_it_on_enter(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("7")  # context_window
            await pilot.pause()
            assert app.pending_setting == "context_window" and app.panel is None
            assert "context_window" in app.composer.placeholder and "Esc cancels" in app.composer.placeholder
            await pilot.press(*"8192", "enter")
            await pilot.pause()
            assert settings_store.get("context_window") == 8192
            assert app.pending_setting is None and app.composer.placeholder == DEFAULT_PLACEHOLDER
            assert app.composer.value == ""
            assert "How much text a local model takes (context_window) is now 8192." in _lines(app)
            assert app.panel_kind == settings_list.PICKER_KIND and app.panel.highlighted == 6
            assert "(context_window) — 8192" in str(app.panel.get_option_at_index(6).prompt)

    run_async(scenario())


def test_what_is_typed_at_the_prompt_is_a_value_not_a_command_and_a_bad_one_keeps_it_open(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("8")  # reply_limit
            await pilot.pause()
            await pilot.press("/", "m")  # would list /model
            await pilot.pause()
            assert app.panel is None  # no command list while a value is being asked for
            await pilot.press("enter")
            await pilot.pause()
            assert any("'/m' is not a whole number" in line for line in _lines(app))
            assert app.pending_setting == "reply_limit"
            await pilot.press(*"10", "enter")
            await pilot.pause()
            assert any("10 is not valid for Space kept for the reply (reply_limit)" in line for line in _lines(app))
            assert app.pending_setting == "reply_limit" and settings_store.get("reply_limit") is None
            await pilot.press(*"512", "enter")
            await pilot.pause()
            assert settings_store.get("reply_limit") == 512 and app.pending_setting is None

    run_async(scenario())


def test_an_empty_entry_at_the_prompt_resets_the_setting(profiles):
    settings_store.set("context_window", 4096)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("7", "enter")
            await pilot.pause()
            assert settings_store.get("context_window") is None
            assert app.pending_setting is None
            assert "How much text a local model takes (context_window) is back to automatic." in _lines(app)

    run_async(scenario())


def test_escape_at_the_prompt_leaves_the_setting_as_it_was(profiles):
    settings_store.set("context_window", 4096)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("7")
            await pilot.pause()
            await pilot.press(*"9999", "escape")
            await pilot.pause()
            assert settings_store.get("context_window") == 4096
            assert app.pending_setting is None and app.composer.placeholder == DEFAULT_PLACEHOLDER
            assert "Left as it was." in _lines(app)
            assert app.panel is None

    run_async(scenario())


def test_escape_closes_the_list_and_a_line_typed_after_it_is_a_normal_message(profiles, monkeypatch):
    sent = []
    from sympose.cli import turns

    monkeypatch.setattr(turns.engine, "run_turn", lambda handle, message, *a, **k: sent.append(message) or engine.TurnResult(reply="ok", session_id="s"))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("escape")
            await pilot.pause()
            assert app.panel is None
            await pilot.press(*"hi", "enter")
            for _ in range(50):
                await pilot.pause(0.1)
                if sent:
                    break
            assert sent == ["hi"]

    run_async(scenario())


def test_a_setting_changed_here_applies_to_the_module_that_reads_it(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press(*["down"] * 12, "enter")  # session_recaps, the twelfth row
            await pilot.pause()
            assert recap.enabled() is False

    run_async(scenario())


def test_rows_past_the_ninth_are_reached_with_the_arrow_keys(profiles):
    """Digits choose rows 1 to 9; the list is twenty-nine long and the picker shows about ten."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press(*["down"] * 23, "enter")  # the first press lands on the first row
            await pilot.pause()
            assert app.pending_setting == "embedding_margin"

    run_async(scenario())


def test_escape_at_the_prompt_also_clears_what_was_half_typed(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("7", *"30", "escape")
            await pilot.pause()
            assert app.composer.value == ""  # Enter next must not send "30" as a message

    run_async(scenario())


def test_tab_and_the_arrows_do_not_fill_in_a_command_while_a_number_is_asked_for(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await _open(pilot, app)
            await pilot.press("7", "/", "m", "tab", "down", "up")
            await pilot.pause()
            assert app.composer.value == "/m" and app.panel is None and app.filling_tab_count == 0

    run_async(scenario())
