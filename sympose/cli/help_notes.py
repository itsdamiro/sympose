"""`/help` and the Sympose reference notes (docs/decisions/019, "`/help` lists the notes"): the notes the
persona answers from, listed by title and shown in the transcript when one is chosen. Read from the
package's own `sympose/reference/`, the same files the persona searches, so there is no second copy."""

import os

from rich.style import Style
from rich.text import Text

from sympose.cli import picker, transcript as transcript_mod
from sympose.cli.selection import SelectionOption
from sympose.engine import reference

PICKER_KIND = "help"


def note_titles() -> list[str]:
    """The titles of the reference notes (their file names without `.md`), in file order; none if the folder is missing."""
    if not os.path.isdir(reference.REFERENCE_DIR):
        return []
    return sorted(n.removesuffix(".md") for n in os.listdir(reference.REFERENCE_DIR) if n.endswith(".md"))


async def open_picker(app) -> None:
    titles = note_titles()
    if titles:
        await picker.open_picker(
            app, PICKER_KIND, "Sympose guide: choose a note to read (Esc to close)", [SelectionOption(t, t) for t in titles]
        )


def show(app, title: str) -> None:
    """Print the note called `title` as system lines: plain text, since a note can hold `[[` and `[`.
    A title that is not one of the notes is ignored, never used as a path."""
    if title not in note_titles():
        return
    with open(os.path.join(reference.REFERENCE_DIR, f"{title}.md"), encoding="utf-8") as f:
        text = f.read().strip()
    heading = f"# {title}"
    body = text.removeprefix(heading).strip() if text.startswith(heading) else text
    transcript_mod.mount_line(app, transcript_mod.styled_line("", Style(bold=True), title), "system")
    transcript_mod.mount_line(app, Text(body), "system")
