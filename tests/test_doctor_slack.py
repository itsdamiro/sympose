"""What `sympose doctor` says about Slack (docs/decisions/093, 029): problems stop a persona being in Slack; a report says who is."""

import io

import pytest
from helpers import write_persona

from sympose import doctor, doctor_slack, settings_store, slack_approval, slack_credentials, slack_heartbeat

TOKENS = ("BOT", "APP")


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "ada-lovelace", "name: Ada\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    for name in ("SLACK_SAMANTHA_BOT_TOKEN", "SLACK_SAMANTHA_APP_TOKEN", "SLACK_ADA_LOVELACE_BOT_TOKEN", "SLACK_ADA_LOVELACE_APP_TOKEN", slack_credentials.OWNER_VARIABLE):
        monkeypatch.delenv(name, raising=False)
    return base


def _pair(monkeypatch, key, which=TOKENS):
    for kind in which:
        monkeypatch.setenv(f"SLACK_{key}_{kind}_TOKEN", "x")


def _all_set(monkeypatch):
    _pair(monkeypatch, "SAMANTHA")
    monkeypatch.setenv(slack_credentials.OWNER_VARIABLE, "U1")
    settings_store.set(slack_approval.SETTING, True)


def test_an_installation_that_never_touched_slack_has_nothing_to_say(home):
    assert doctor_slack.problems() == [] and doctor_slack.report() == []


def test_a_persona_with_only_one_token_is_named_with_the_one_it_lacks(home, monkeypatch):
    _pair(monkeypatch, "SAMANTHA", ("BOT",))
    assert doctor_slack.problems() == [
        "the persona 'samantha' has its Slack bot token but not its app token (SLACK_SAMANTHA_APP_TOKEN in .env), so it is not in Slack"
    ]
    monkeypatch.delenv("SLACK_SAMANTHA_BOT_TOKEN")
    _pair(monkeypatch, "SAMANTHA", ("APP",))
    assert "has its Slack app token but not its bot token (SLACK_SAMANTHA_BOT_TOKEN" in doctor_slack.problems()[0]


def test_a_blank_token_counts_as_missing(home, monkeypatch):
    monkeypatch.setenv("SLACK_SAMANTHA_BOT_TOKEN", "  ")
    monkeypatch.setenv("SLACK_SAMANTHA_APP_TOKEN", "x")
    assert "bot token" not in doctor_slack.problems()[0].split("but not")[0]


def test_a_dash_in_a_handle_is_an_underscore_in_the_variable(home, monkeypatch):
    _pair(monkeypatch, "ADA_LOVELACE", ("APP",))
    assert "SLACK_ADA_LOVELACE_BOT_TOKEN" in doctor_slack.problems()[0]


def test_a_token_for_nobody_on_the_roster_is_said(home, monkeypatch):
    _pair(monkeypatch, "ARCHIA")
    found = doctor_slack.problems()
    assert len(found) == 1 and "SLACK_ARCHIA_BOT_TOKEN or SLACK_ARCHIA_APP_TOKEN" in found[0] and "no persona has that handle" in found[0]


def test_a_blank_token_for_nobody_on_the_roster_is_not_a_finding(home, monkeypatch):
    monkeypatch.setenv("SLACK_ARCHIA_BOT_TOKEN", "")
    monkeypatch.setenv("SLACK_ARCHIA_APP_TOKEN", "  ")
    assert doctor_slack.problems() == []


def test_a_dashed_persona_is_not_taken_for_a_stranger(home, monkeypatch):
    _pair(monkeypatch, "ADA_LOVELACE")
    assert not any("no persona has that handle" in p for p in doctor_slack.problems())


def test_a_pair_without_the_owner_or_the_approval_says_both(home, monkeypatch):
    _pair(monkeypatch, "SAMANTHA")
    found = doctor_slack.problems()
    assert len(found) == 2
    assert slack_credentials.OWNER_VARIABLE in found[0] and "switched off in Settings" in found[1]


def test_everything_in_place_is_no_problem(home, monkeypatch):
    _all_set(monkeypatch)
    assert doctor_slack.problems() == []


def test_the_owner_and_the_approval_matter_only_when_a_persona_has_a_pair(home, monkeypatch):
    _pair(monkeypatch, "SAMANTHA", ("BOT",))
    assert not any("sympose slack` will not start" in p for p in doctor_slack.problems())


def test_the_report_names_a_persona_with_a_pair_as_not_connected_until_it_beats(home, monkeypatch):
    _all_set(monkeypatch)
    assert doctor_slack.report() == ["Slack:", "- persona samantha: not connected (is `sympose slack` running?)"]
    slack_heartbeat.beat("samantha")
    assert doctor_slack.report() == ["Slack:", "- persona samantha: connected"]


def test_the_report_leaves_out_a_persona_without_a_pair(home, monkeypatch):
    _pair(monkeypatch, "ADA_LOVELACE", ("BOT",))
    assert doctor_slack.report() == []


def test_doctor_counts_a_slack_problem_and_prints_the_report(home, monkeypatch):
    _pair(monkeypatch, "SAMANTHA")
    out = io.StringIO()
    code = doctor.run(out=out)
    text = out.getvalue()
    assert code == 1 and "switched off in Settings" in text and "needs your attention" in text
    assert "Slack:\n- persona samantha: not connected" in text


def test_doctor_is_healthy_with_slack_set_up(home, monkeypatch):
    _all_set(monkeypatch)
    out = io.StringIO()
    assert doctor.run(out=out) == 0 and "Everything looks healthy." in out.getvalue()
