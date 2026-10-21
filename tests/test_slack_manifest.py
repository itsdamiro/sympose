"""The Slack App manifest of a persona (docs/decisions/093) and `sympose slack manifest`."""

import json
from pathlib import Path

import pytest
from helpers import write_persona

from sympose import launcher, slack_connect, slack_manifest


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "ada-lovelace", "name: Ada Lovelace the Analyst of Engines and Numbers Extraordinary\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def test_the_manifest_asks_for_what_the_adapter_uses_and_no_more():
    m = slack_manifest.manifest("samantha", "Samantha")
    assert m["oauth_config"]["scopes"]["bot"] == ["app_mentions:read", "chat:write", "commands", "im:history"]
    assert m["settings"]["event_subscriptions"]["bot_events"] == ["app_mention", "message.im"]
    assert m["settings"]["socket_mode_enabled"] is True
    assert [c["command"] for c in m["features"]["slash_commands"]] == ["/new"]
    assert "url" not in m["features"]["slash_commands"][0]  # Socket Mode needs no address
    assert "request_url" not in m["settings"]["event_subscriptions"]
    assert m["settings"]["interactivity"] == {"is_enabled": False}


def test_a_person_can_message_the_bot_from_its_home():
    home = slack_manifest.manifest("samantha", "Samantha")["features"]["app_home"]
    assert home["messages_tab_enabled"] is True and home["messages_tab_read_only_enabled"] is False


def test_the_scopes_are_the_ones_the_setup_note_lists(home):
    note = (Path(__file__).parent.parent / "docs" / "SLACK_SETUP.md").read_text(encoding="utf-8")
    for scope in slack_manifest.BOT_SCOPES + slack_manifest.BOT_EVENTS:
        assert f"`{scope}`" in note


def test_the_name_is_the_personas_and_is_cut_at_slacks_limit():
    assert slack_manifest.manifest("samantha", "Samantha")["display_information"]["name"] == "Samantha"
    long = slack_manifest.manifest("ada", "x" * 50)["display_information"]["name"]
    assert long == "x" * slack_manifest.NAME_LIMIT


def test_a_blank_name_falls_back_to_the_handle():
    assert slack_manifest.manifest("ada", "  ")["display_information"]["name"] == "ada"


def test_the_bot_name_keeps_to_what_slack_allows():
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-_.")
    for handle in ("samantha", "Ada-Lovelace", "a b", "é"):
        shown = slack_manifest.manifest(handle, "x")["features"]["bot_user"]["display_name"]
        assert shown and set(shown) <= allowed and len(shown) <= slack_manifest.BOT_NAME_LIMIT


def test_a_very_long_handle_is_cut_to_slacks_limit_for_the_bot_name():
    shown = slack_manifest.manifest("a" * 200, "x")["features"]["bot_user"]["display_name"]
    assert shown == "a" * slack_manifest.BOT_NAME_LIMIT == "a" * 80


def test_a_dot_in_a_handle_is_kept_in_the_bot_name():
    assert slack_manifest.manifest("a.b_c-d", "x")["features"]["bot_user"]["display_name"] == "a.b_c-d"


def test_the_bot_shows_as_online():
    assert slack_manifest.manifest("samantha", "S")["features"]["bot_user"]["always_online"] is True


def test_a_handle_is_the_bot_name_as_it_is():
    assert slack_manifest.manifest("ada-lovelace", "x")["features"]["bot_user"]["display_name"] == "ada-lovelace"


def test_render_is_json_of_that_persona(home):
    m = json.loads(slack_manifest.render("samantha"))
    assert m["display_information"]["name"] == "Samantha" and m["features"]["bot_user"]["display_name"] == "samantha"


def test_render_cuts_a_long_persona_name(home):
    m = json.loads(slack_manifest.render("ada-lovelace"))
    assert len(m["display_information"]["name"]) == slack_manifest.NAME_LIMIT


def test_render_is_none_for_a_persona_that_does_not_exist(home):
    assert slack_manifest.render("nobody") is None


def test_the_command_prints_the_manifest(home, capsys):
    assert launcher.main(["slack", "manifest", "samantha"]) == 0
    assert json.loads(capsys.readouterr().out)["display_information"]["name"] == "Samantha"


def test_the_command_names_a_persona_that_is_missing(home, capsys):
    assert slack_connect.manifest("nobody") == 1
    assert "no persona called 'nobody'" in capsys.readouterr().err


def test_the_command_needs_a_handle():
    with pytest.raises(SystemExit) as stop:
        launcher.main(["slack", "manifest"])
    assert stop.value.code == 2


def test_the_connection_listens_for_the_command_the_manifest_declares():
    assert slack_connect.NEW_COMMAND == slack_manifest.NEW_COMMAND["command"] == "/new"
