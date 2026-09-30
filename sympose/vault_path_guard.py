"""Refuses a folder that is far too broad to be a vault when it is added from the web app (a mistake,
not an attack: picking the home folder or the drive root instead of the notes folder would put every
file under it within reach of the editor, the trash and the persona). The rules are about paths only, so
they hold on Windows, macOS and Linux alike:

- a filesystem root: `/`, `C:\\`, or a network share's root;
- the home folder, or any folder that contains it (`/Users`, `/home`, `C:\\Users`);
- an operating system folder or anything inside one (`/System`, `/usr`, `C:\\Windows`, `C:\\Program Files`);
- a folder that only holds other volumes or users (`/Volumes`, `/mnt`, `/media`), but not what is inside them.

Everything else is allowed, Documents and Desktop included: a vault may live anywhere a person keeps their
notes. `check` is the one call; `refusal` is the same rules over plain values, so a test can run them with
Windows paths on any machine."""

import ntpath
import os
import sys
from types import ModuleType
from typing import Iterable

REASON = (
    "That folder is too broad to be a vault (it is your whole computer, your home folder, or part of the "
    "operating system). Pick the folder your notes are in."
)

_POSIX_SYSTEM = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/etc", "/boot", "/dev", "/proc", "/sys")
_MAC_SYSTEM = ("/System", "/Library", "/Applications", "/usr", "/bin", "/sbin", "/etc", "/cores")
_POSIX_HOLDERS = ("/Volumes", "/mnt", "/media", "/Users", "/home")


def _key(path: str, pathmod: ModuleType, casefold: bool) -> str:
    key = pathmod.normcase(pathmod.normpath(path))
    return key.casefold() if casefold else key


def _inside(child: str, parent: str, sep: str) -> bool:
    """`child` is `parent` or in it. Both are already normalized keys."""
    return child == parent or child.startswith(parent.rstrip(sep) + sep)


def refusal(
    path: str,
    *,
    home: str | None,
    system: Iterable[str],
    holders: Iterable[str] = (),
    pathmod: ModuleType = os.path,
    casefold: bool = False,
) -> str | None:
    """`REASON` when `path` (absolute, symlinks resolved) is too broad to be a vault, else `None`."""
    sep = pathmod.sep

    def key(p: str) -> str:
        return _key(p, pathmod, casefold)

    target = key(path)
    if pathmod.splitdrive(target)[1].strip("\\/") == "":  # `/`, `c:\`, or a share's root
        return REASON
    if home and _inside(key(home), target, sep):  # the home folder, or a folder that contains it
        return REASON
    if any(_inside(target, key(folder), sep) for folder in system):
        return REASON
    if any(target == key(folder) for folder in holders):
        return REASON
    return None


def _windows_system() -> list[str]:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    drive = os.environ.get("SystemDrive") or "C:"
    folders = [root, os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramData")]
    return [f for f in folders if f] + [drive + "\\Windows"]


def check(path: str) -> str | None:
    """`REASON` when the folder at `path` is too broad to be a vault, judged on this machine's real paths."""
    real = os.path.realpath(path)
    home = os.path.realpath(os.path.expanduser("~"))
    if sys.platform == "win32":
        holders = [(os.environ.get("SystemDrive") or "C:") + "\\Users"]
        return refusal(real, home=home, system=_windows_system(), holders=holders, pathmod=ntpath, casefold=True)
    system = _MAC_SYSTEM if sys.platform == "darwin" else _POSIX_SYSTEM
    return refusal(
        real,
        home=home,
        system=[os.path.realpath(f) for f in system],
        holders=_POSIX_HOLDERS,
        casefold=sys.platform == "darwin",
    )
