"""Where the code is in a note's text: a `[[link]]` inside a fenced block or an inline code span is a sample, not a link
(Obsidian does not follow it), so a repair that rewrites links leaves it alone (docs/decisions/084)."""

import re
from bisect import bisect_right
from typing import Callable

_OPEN = re.compile(r"([ \t>]*)(`{3,}|~{3,})(.*)")  # a fence's opening line: what is before it, its characters, the info string
_INLINE = re.compile(r"(?<!`)(`+)(?!`)(?:(?!\n[ \t]*\r?\n).)+?(?<!`)\1(?!`)", re.DOTALL)  # a run of backticks to the next run of as many
_LINES = re.compile(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+")  # not `splitlines`: it also breaks at U+2028, a form feed and others, which Markdown does not


def _fences(text: str) -> list[tuple[int, int]]:
    """The fenced blocks of `text` as (start, end) offsets. A fence opens with three or more backticks or tildes (a
    backtick fence's info string holds no backtick) and closes with its own character, at least as many times, or at the
    end of the text. A fence indented four columns or more, outside a quote, is an indented code block, not a fence
    (inside a list it may be one): it counts only when it closes, so a stray one cannot turn the rest of the note into code."""
    spans: list[tuple[int, int]] = []
    opened: tuple[int, str, int, bool] | None = None  # where the open fence starts, its character, how many, whether indented
    at = 0
    for line in _LINES.findall(text):
        body = line.rstrip("\r\n")
        if opened is None:
            found = _OPEN.fullmatch(body)
            if found and not (found[2][0] == "`" and "`" in found[3]):
                indented = len(found[1].rsplit(">", 1)[-1].expandtabs(4)) >= 4
                opened = (at, found[2][0], len(found[2]), indented)
        elif re.fullmatch(rf"[ \t>]*{re.escape(opened[1])}{{{opened[2]},}}[ \t]*", body):
            spans.append((opened[0], at + len(line)))
            opened = None
        at += len(line)
    if opened and not opened[3]:
        spans.append((opened[0], len(text)))
    return spans


def code_spans(text: str) -> list[tuple[int, int]]:
    """The code of `text` as (start, end) offsets, in order and apart: the fenced blocks, and the inline spans, each
    closed by as many backticks as opened it, within a paragraph, found outside the fences."""
    fences = _fences(text)
    parts, at = [], 0  # the text with every fence blanked out, so an inline span is looked for outside them
    for start, end in fences:
        parts += [text[at:start], re.sub(r"[^\r\n]", " ", text[start:end])]
        at = end
    parts.append(text[at:])
    return sorted(fences + [m.span() for m in _INLINE.finditer("".join(parts))])


def in_code(text: str) -> Callable[[int], bool]:
    """A test of whether an offset into `text` falls in code. The spans are found on the first call, so a note with no
    link to test costs nothing, and each test is a search of them, not a walk."""
    spans: list[tuple[int, int]] | None = None

    def inside(position: int) -> bool:
        nonlocal spans
        if spans is None:
            spans = code_spans(text)
        i = bisect_right(spans, (position, float("inf")))
        return i > 0 and position < spans[i - 1][1]

    return inside
