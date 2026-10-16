"""What a note's file name may be (docs/decisions/084): the one copy of the rules, read by the health check that says a
title cannot be a file name and by the repair that renames a note to its title, so the two cannot disagree."""

import re

from sympose.wikilinks import WIKILINK_UNSAFE_CHARS

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"com{n}" for n in range(1, 10)), *(f"lpt{n}" for n in range(1, 10))})  # Windows
LONGEST = 250  # bytes a file name may have, less its `.md`


def why_not_a_file_name(title: str) -> str | None:
    """Why a note cannot be renamed to `title`, as the end of a sentence, or `None` when it can. Not only what a disk
    refuses: a rename drops a quote mark at the edge of a name and a link cannot hold `[`, `]`, `|` or `#`."""
    unsafe = _UNSAFE.search(title)
    if unsafe:
        return f"a file name cannot hold {unsafe.group()!r}"
    if len(title.encode("utf-8")) > LONGEST:
        return "it is too long for a file name"
    for char in title:
        if char in WIKILINK_UNSAFE_CHARS:
            return f"a link to it could not hold {char!r}"
    if title != title.strip() or title.endswith("."):
        return "a file name cannot start or end with a space or end with a dot"
    if title.startswith("."):
        return "a note whose name starts with a dot is hidden"
    if title.startswith("'") or title.endswith("'"):
        return "a rename drops an apostrophe at the start or end of a name"
    if title.split(".")[0].strip().lower() in _RESERVED:
        return "Windows does not allow that name for a file"
    return None
