"""Keeps the reference library true as the code changes (docs/decisions/019, issue #8). A note that
names a setting, an environment variable, a file, a slash command, a `sympose` command or a flag that
no longer exists is a wrong answer from the persona about her own product, so it fails here.

The checks are structural, not about wording: a name a note puts in backticks must exist in the code
(as a quoted string in the package source, as a line of `.env.example`, or, for a slash command, in
the command registry), so a renamed or removed name makes the note fail. Two limits: a quoted name
that survives only in a comment or docstring still passes, and a note that describes a setting's
behaviour wrongly is not seen at all; that still needs the note edited in the same commit as the change."""

import glob
import os
import re

from reference_cases import REFERENCE_DIR

from sympose.cli import commands

ROOT = os.path.join(REFERENCE_DIR, "..", "..")
_SETTING = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)+")  # grounding_search, cloud_share
_ENV = re.compile(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*")  # VAULT_PATHS, PORT
_FILE = re.compile(r"([\w.-]+\.(json|yaml|md|sqlite|example)|\.[a-z]+)")  # settings.json, .env
_SLASH = re.compile(r"/[a-z]+")  # /model
_SYMPOSE = re.compile(r"sympose (\w+)")  # sympose web
_FLAG = re.compile(r"--[a-z][a-z-]*")  # --port
# Read by the model libraries, not by Sympose (the notes tell the user to set them for a cloud model).
_PROVIDER_ENV = re.compile(r"[A-Z]+_API_KEY")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _package_source() -> str:
    return "\n".join(_read(p) for p in sorted(glob.glob(os.path.join(ROOT, "sympose", "**", "*.py"), recursive=True)))


def _library() -> dict[str, str]:
    return {n: _read(os.path.join(REFERENCE_DIR, n)) for n in sorted(os.listdir(REFERENCE_DIR)) if n.endswith(".md")}


def stale_names(notes: dict[str, str], source: str, launcher: str, env_example: str, registry: set[str]) -> list[str]:
    """`"note: name"` for every backticked name in `notes` that the code does not have."""

    def in_code(name: str) -> bool:
        return f'"{name}"' in source or f"'{name}'" in source or name in env_example.split()

    stale = []
    for note, text in notes.items():
        for token in re.findall(r"`([^`\n]+)`", text):
            names: list[str] = []
            if _SETTING.fullmatch(token) and not in_code(token):
                names.append(token)
            if _ENV.fullmatch(token) and len(token) > 3 and not _PROVIDER_ENV.fullmatch(token) and not in_code(token):
                names.append(token)
            if _FILE.fullmatch(token) and not in_code(token) and not os.path.exists(os.path.join(ROOT, token)):
                names.append(token)
            if _SLASH.fullmatch(token) and token not in registry:
                names.append(token)
            if token.startswith("sympose "):
                sub = _SYMPOSE.match(token)
                if sub and f'"{sub.group(1)}"' not in launcher:
                    names.append(f"sympose {sub.group(1)}")
            if token.startswith(("sympose ", "--")):
                names += [flag for flag in _FLAG.findall(token) if f'"{flag}"' not in launcher]
            stale += [f"{note}: {name}" for name in names]
    return stale


def _stale_in_library(notes: dict[str, str]) -> list[str]:
    return stale_names(
        notes,
        _package_source(),
        _read(os.path.join(ROOT, "sympose", "launcher.py")),
        _read(os.path.join(ROOT, ".env.example")),
        {c.name for c in commands.COMMANDS},
    )


def test_every_name_the_library_gives_exists_in_the_code():
    notes = _library()

    assert len(notes) >= 10  # an unread library would pass for nothing
    assert _stale_in_library(notes) == []


def test_a_note_naming_something_that_does_not_exist_is_caught():
    notes = {
        "Fake.md": "Set `no_such_setting` in `nothing.json`, use `/nothing`, run `sympose nothing --nowhere`, "
        "or set `NO_SUCH_VARIABLE`.\n"
        "Real ones pass: `grounding_search`, `settings.json`, `/model`, `sympose web --port`, `VAULT_PATHS`, "
        "`GEMINI_API_KEY`, `.env.example`."
    }

    assert sorted(_stale_in_library(notes)) == sorted(
        [
            "Fake.md: no_such_setting",
            "Fake.md: NO_SUCH_VARIABLE",
            "Fake.md: nothing.json",
            "Fake.md: /nothing",
            "Fake.md: sympose nothing",
            "Fake.md: --nowhere",
        ]
    )
