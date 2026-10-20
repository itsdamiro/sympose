"""The operating system's part of scheduled runs (docs/decisions/091, slice 4): one launchd entry that calls
`sympose run --due` every five minutes, so a job runs while the web app is closed. macOS only (Windows is #117).

The entry belongs to the user (`~/Library/LaunchAgents`, loaded for their login), names the Python and the folder Sympose
was installed from (that folder's `.env` is read, as for every command), and keeps only the environment settings that
point Sympose at its folders. It changes nothing in the vault."""

import contextlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from sympose.atomic_write import write_atomic_text

LABEL = "com.sympose.jobs"
EVERY_SECONDS = 300
_ENV_KEPT = ("VAULT_PATHS", "SYMPOSE_PROFILES_DIR", "SYMPOSE_SETTINGS_PATH")


class ScheduleRefused(Exception):
    """Said to the user as it stands: why the entry could not be added or taken away."""


def supported() -> bool:
    return sys.platform == "darwin"


def _folder() -> Path:
    return Path(os.environ.get("SYMPOSE_LAUNCH_AGENTS_DIR") or Path.home() / "Library" / "LaunchAgents")


def plist_path() -> Path:
    return _folder() / f"{LABEL}.plist"


def installed() -> bool:
    return supported() and plist_path().is_file()


def _log_path() -> Path:
    return Path(os.environ.get("SYMPOSE_LOG_DIR") or Path.home() / "Library" / "Logs" / "Sympose") / "jobs.log"


def entry() -> dict:
    """What launchd is told: this Python, `sympose run --due`, from the folder Sympose runs from."""
    log = str(_log_path())
    values = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "sympose.launcher", "run", "--due"],
        "WorkingDirectory": str(Path.cwd()),
        "StartInterval": EVERY_SECONDS,
        "RunAtLoad": False,
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }
    kept = {k: os.environ[k] for k in _ENV_KEPT if os.environ.get(k)}
    if kept:
        values["EnvironmentVariables"] = kept
    return values


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, timeout=30)


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _unload() -> None:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        _launchctl("bootout", f"{_domain()}/{LABEL}")  # not loaded is fine: the aim is that it is not


def install() -> None:
    """Write the entry and load it. Running it again replaces the entry, so a moved Sympose is pointed right."""
    if not supported():
        raise ScheduleRefused("Running jobs while Sympose is closed is only set up for macOS so far.")
    path = plist_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _log_path().parent.mkdir(parents=True, exist_ok=True)
        write_atomic_text(str(path), plistlib.dumps(entry()).decode("utf-8"), newline="")
    except OSError as e:
        raise ScheduleRefused(f"Couldn't write {path}: {e}") from None
    _unload()
    try:
        done = _launchctl("bootstrap", _domain(), str(path))
    except (OSError, subprocess.SubprocessError) as e:
        raise ScheduleRefused(f"Couldn't start the schedule: {e}") from None
    if done.returncode != 0:
        with contextlib.suppress(OSError):
            path.unlink()
        raise ScheduleRefused(f"Couldn't start the schedule: {(done.stderr or done.stdout).strip() or 'launchctl refused.'}")


def remove() -> None:
    """Unload the entry and delete it. Nothing installed is not an error."""
    if not supported():
        return
    _unload()
    try:
        plist_path().unlink(missing_ok=True)
    except OSError as e:
        raise ScheduleRefused(f"Couldn't remove {plist_path()}: {e}") from None
