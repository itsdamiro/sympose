"""Where the code is in a note's text: a `[[link]]` inside a fenced block or an inline code span is a sample, not a link
(Obsidian does not follow it), so a repair that rewrites links leaves it alone (docs/decisions/084)."""

import re

_OPEN = re.compile(r"[ \t>]*(`{3,}|~{3,})(.*)")  # a fence's opening line: its characters, then the info string
_INLINE = re.compile(r"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\r?\n).)+?(?<!`)\1(?!`)", re.DOTALL)  # a run of backticks to the next run of as many


def code_spans(text: str) -> list[tuple[int, int]]:
    """The code of `text` as (start, end) offsets. A fence opens with three or more backticks or tildes (a backtick
    fence's info string holds no backtick) and closes with its own character, at least as many times, or at the end of
    the text; an inline span is closed by as many backticks as opened it, within a paragraph."""
    spans: list[tuple[int, int]] = []
    opened: tuple[int, str, int] | None = None  # where the open fence starts, its character, how many
    masked, at = [], 0  # the text with every fence blanked out, so an inline span is looked for outside them
    for line in re.findall(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+", text):  # not `splitlines`: it also breaks at U+2028, a form feed and others, which Markdown does not
        body, was_open = line.rstrip("\r\n"), opened is not None
        if opened is None:
            found = _OPEN.fullmatch(body)
            if found and not (found[1][0] == "`" and "`" in found[2]):
                opened = (at, found[1][0], len(found[1]))
        elif re.fullmatch(rf"[ \t>]*{re.escape(opened[1])}{{{opened[2]},}}[ \t]*", body):
            spans.append((opened[0], at + len(line)))
            opened = None
        masked.append(re.sub(r"[^\r\n]", " ", line) if was_open or opened else line)
        at += len(line)
    if opened:
        spans.append((opened[0], len(text)))
    spans += [m.span() for m in _INLINE.finditer("".join(masked))]
    return spans


def inside(spans: list[tuple[int, int]], position: int) -> bool:
    """Whether `position` (an offset into the text `spans` were found in) falls in code."""
    return any(start <= position < end for start, end in spans)
