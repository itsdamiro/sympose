"""The start-up notice for a persona folder the roster misses (docs/decisions/029, issue #72). This machine's
file system ignores case, so a file system that keeps case is simulated by making the lower-case lookup fail."""

import asyncio

import pytest
from helpers import write_persona

from sympose import launcher, persona_files
from sympose.cli.app import SymposeCLI


@pytest.fixture
def base(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return profiles


@pytest.fixture
def keeps_case(monkeypatch):
    monkeypatch.setattr(persona_files, "_found_as_lower", lambda folder, name: False)


def test_a_file_system_that_ignores_case_misses_nothing(base):
    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "Grace", "name: Grace\n")
    (base / "Notes").mkdir()

    assert persona_files.missed_folders() == [] and persona_files.missed_notice() is None


def test_a_mixed_case_persona_folder_is_missed_on_a_file_system_that_keeps_case(base, keeps_case):
    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "Grace", "name: Grace\n")
    write_persona(base, "Anais", "name: Anais\n")
    (base / "Notes").mkdir()  # not a persona: no persona.yaml

    assert persona_files.missed_folders() == ["Anais", "Grace"]
    notice = persona_files.missed_notice()
    assert "'Anais', 'Grace'" in notice and "not lower case" in notice and "sympose doctor --fix" in notice


def test_a_folder_the_roster_finds_under_its_lower_case_name_is_not_missed(base, monkeypatch):
    write_persona(base, "Grace", "name: Grace\n")
    monkeypatch.setattr(persona_files, "_found_as_lower", lambda folder, name: True)  # a `grace` folder of its own

    assert persona_files.missed_folders() == []  # the roster lists that one; the doctor reports the clash


def test_no_profiles_folder_misses_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "none"))

    assert persona_files.missed_folders() == [] and persona_files.missed_notice() is None


def test_the_terminal_chat_says_it_at_start_up(base, keeps_case):
    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "Grace", "name: Grace\n")

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            return [child.visual.plain for child in app.transcript.children]

    lines = asyncio.run(scenario())

    assert any("'Grace'" in line and "sympose doctor --fix" in line for line in lines)


def test_the_terminal_chat_says_nothing_when_no_persona_is_missed(base):
    write_persona(base, "samantha", "name: Samantha\n")

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            return [child.visual.plain for child in app.transcript.children]

    assert not any("doctor" in line for line in asyncio.run(scenario()))


def test_the_web_app_prints_it_before_the_address(base, keeps_case, monkeypatch, capsys):
    import uvicorn

    write_persona(base, "samantha", "name: Samantha\n")
    write_persona(base, "Grace", "name: Grace\n")
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    monkeypatch.delenv("PORT", raising=False)

    assert launcher.main(["web"]) == 0

    err = capsys.readouterr().err
    assert "'Grace'" in err and "sympose doctor --fix" in err
