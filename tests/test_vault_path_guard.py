"""Which folders are too broad to be added as a vault (sympose/vault_path_guard.py). The rules are run
over Windows-style paths (`ntpath`) and Unix-style paths (`posixpath`) so both are checked on any machine;
a real Windows machine is still where the real folders (%SystemRoot% and so on) get their own check."""

import ntpath
import os
import posixpath

import pytest
from fastapi import HTTPException

from sympose import server_vault_handlers as vh
from sympose import settings_store, vault_path_guard as guard, vault_registry

WIN = dict(pathmod=ntpath, casefold=True)
WIN_HOME = r"C:\Users\Sam"
WIN_SYSTEM = [r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)", r"C:\ProgramData"]
WIN_HOLDERS = [r"C:\Users"]
MAC_HOME = "/Users/sam"
MAC_SYSTEM = ["/System", "/Library", "/Applications", "/usr", "/bin", "/sbin", "/etc", "/cores"]
LINUX_HOME = "/home/sam"
LINUX_SYSTEM = ["/usr", "/bin", "/etc", "/boot", "/dev", "/proc", "/sys"]
HOLDERS = ["/Volumes", "/mnt", "/media", "/Users", "/home"]


def win(path):
    return guard.refusal(path, home=WIN_HOME, system=WIN_SYSTEM, holders=WIN_HOLDERS, **WIN)


def mac(path):
    return guard.refusal(path, home=MAC_HOME, system=MAC_SYSTEM, holders=HOLDERS, pathmod=posixpath, casefold=True)


def linux(path):
    return guard.refusal(path, home=LINUX_HOME, system=LINUX_SYSTEM, holders=HOLDERS, pathmod=posixpath)


@pytest.mark.parametrize(
    "path",
    [
        "C:\\", "c:/", r"D:\\", r"\\server\share", r"C:\Users", WIN_HOME, r"c:\users\SAM",  # roots, users, home, any case
        r"C:\Windows", r"C:\Windows\System32", r"C:\Program Files", r"c:\program files\App",
        r"C:\Users\Sam\..",  # `..` climbs out to C:\Users
    ],
)
def test_windows_refuses_the_broad_folders(path):
    assert win(path) == guard.REASON


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\Sam\Documents\Notes", r"C:\Users\Sam\Documents", r"D:\Notes", r"E:\Vaults\Work",
        r"C:\Notes", r"\\server\share\notes", r"C:\Users\Sam\OneDrive\Vault",
    ],
)
def test_windows_allows_a_folder_where_notes_are_kept(path):
    assert win(path) is None


@pytest.mark.parametrize(
    "path",
    ["/", "/Users", "/Users/sam", "/Volumes", "/System", "/System/Library/Fonts", "/Library", "/Applications/Obsidian.app", "/usr/local", "/etc"],
)
def test_macos_refuses_the_broad_folders(path):
    assert mac(path) == guard.REASON


@pytest.mark.parametrize(
    "path",
    [
        "/Users/sam/Documents/Notes", "/Users/sam/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vault",
        "/Volumes/Backup/Notes", "/private/var/folders/x/notes", "/Users/sam/Obsidian",
    ],
)
def test_macos_allows_a_folder_where_notes_are_kept(path):
    assert mac(path) is None


def test_macos_ignores_the_case_of_a_folder_name():
    assert mac("/users/SAM") == guard.REASON and mac("/SYSTEM") == guard.REASON


@pytest.mark.parametrize("path", ["/", "/home", "/home/sam", "/mnt", "/media", "/usr/share", "/etc", "/boot", "/proc/1"])
def test_linux_refuses_the_broad_folders(path):
    assert linux(path) == guard.REASON


@pytest.mark.parametrize(
    "path", ["/home/sam/notes", "/home/sam/Documents/Vault", "/mnt/data/notes", "/media/sam/usb/notes", "/tmp/pytest-of-sam/vault", "/opt/notes", "/srv/notes"]
)
def test_linux_allows_a_folder_where_notes_are_kept(path):
    assert linux(path) is None


def test_linux_case_matters():
    assert linux("/Home/sam") is None  # a different folder on a case-sensitive filesystem


def test_a_folder_that_only_starts_with_a_broad_name_is_not_that_folder():
    assert linux("/usrlocal/notes") is None and linux("/home2/notes") is None
    assert win(r"C:\Windows2\notes") is None and win(r"C:\Users2\Sam") is None


def test_a_missing_home_only_drops_the_home_rule():
    assert guard.refusal("/notes", home=None, system=LINUX_SYSTEM, pathmod=posixpath) is None
    assert guard.refusal("/", home=None, system=LINUX_SYSTEM, pathmod=posixpath) == guard.REASON


# -- on this machine's real paths, and at both ways in ----------------------------------------------


def test_check_refuses_this_machines_root_and_home_and_allows_a_notes_folder(tmp_path):
    root = os.path.abspath(os.sep)
    assert guard.check(root) == guard.REASON
    assert guard.check(os.path.expanduser("~")) == guard.REASON
    assert guard.check(os.path.dirname(os.path.expanduser("~"))) == guard.REASON
    assert guard.check(str(tmp_path)) is None


def test_check_sees_through_a_symlink_to_a_broad_folder(tmp_path):
    link = tmp_path / "notes"
    try:
        link.symlink_to(os.path.expanduser("~"), target_is_directory=True)
    except OSError:
        pytest.skip("this system does not allow creating symlinks")
    assert guard.check(str(link)) == guard.REASON


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return tmp_path


def test_the_web_route_says_why_a_broad_folder_is_refused(settings):
    with pytest.raises(HTTPException) as exc_info:
        vh.add_vault(os.path.expanduser("~"))
    assert exc_info.value.status_code == 400 and exc_info.value.detail == guard.REASON
    assert settings_store.get("added_vaults") is None


def test_the_registry_itself_refuses_a_broad_folder(settings):
    assert vault_registry.add_vault(os.path.abspath(os.sep)) is None
    assert settings_store.get("added_vaults") is None


def test_an_ordinary_folder_is_still_added(settings):
    notes = settings / "Notes"
    notes.mkdir()
    assert vh.add_vault(str(notes))["active"] == str(notes)
