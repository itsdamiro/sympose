"""`/attach <path>` (docs/decisions/089, `media`): a PDF, an image, a sound or a video from this computer goes with the
next message. The terminal has no drop or paste, so the file is named by its path (a path dragged from the file manager
into the terminal works, with its quotes and escapes). The file is read here and held in memory until that message goes;
it is not copied anywhere. The message carries a `[attached: name]` marker, as the web app's does."""

import os
import shlex
from pathlib import Path

from sympose.cli import transcript as transcript_mod
from sympose.engine import media

USAGE = "Usage: /attach <path to a PDF, image, sound or video>. It goes with your next message."


def _say(app, line: str) -> None:
    transcript_mod.mount_line(app, line, "system")


def marker(name: str) -> str:
    return f"[attached: {name}]"


def with_markers(value: str, files: list[media.File]) -> str:
    """`value` with a marker for each of `files` that it does not already name (a stopped message comes back with its markers)."""
    missing = [marker(f.name) for f in files if marker(f.name) not in value]
    return " ".join([value, *missing]) if missing else value


def path_words(args: str, windows: bool = os.name == "nt") -> list[str]:
    """The words of a typed or dragged path: quotes and backslash escapes read the way a POSIX shell does, except on
    Windows, where a backslash is the path's own and only the quotes around it are taken off."""
    if windows:
        return [args.strip().strip("\"'")]
    try:
        return shlex.split(args)
    except ValueError:
        return [args.strip()]


def run(app, args: str) -> None:
    if not args.strip():
        _say(app, USAGE if not app.pending_files else f"Waiting for your next message: {', '.join(f.name for f in app.pending_files)}")
        return
    path = Path(" ".join(path_words(args))).expanduser()  # a path typed with spaces and no quotes arrives as several words
    try:
        if not path.is_file():
            _say(app, f"No file at {path}.")
            return
        if path.stat().st_size > media.MAX_BYTES:
            _say(app, f"{path.name} is too large to send (the limit is {media.MAX_BYTES // (1024 * 1024)} MB for one message).")
            return
        made = media.make(path.name, path.read_bytes())
        app.pending_files = list(media.check([*app.pending_files, made]))
    except media.MediaRefused as e:
        _say(app, str(e))
        return
    except OSError as e:
        _say(app, f"Couldn't read {path.name}: {e.strerror or e}.")
        return
    _say(app, f"Attached {app.pending_files[-1].name}. It goes with your next message.")
