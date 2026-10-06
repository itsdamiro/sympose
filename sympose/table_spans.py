"""Where a Markdown table is in a note's text, and whether a change fits inside one of its cells (docs/decisions/069).

The editor draws a change of hers inside a table cell only when the quoted words sit within one cell's own text and the
replacement stays in that cell; anything else cannot be drawn there, and a change nobody can see must not exist. A table
is found by its shape (a header row, a delimiter row of dashes with as many cells, the rows below until a blank line),
outside fenced code."""

import re

_DELIMITER = re.compile(r"^\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
_OPEN = re.compile(r"(`{3,}|~{3,})(.*)$")  # a code fence's opening line: its characters, then the info string
_LIST = re.compile(r"(?:[-*+]|\d{1,9}[.)])[ \t]+")  # a list marker, which a table's header row may follow
_MARGIN = re.compile(r"[ \t]*(?:>[ \t]?)*")  # what a line starts with before its own text: indent, blockquote markers
_PIPE = re.compile(r"(?<!\\)\|")
_REFUSAL = "Quote words that sit inside one cell of the table, with a replacement that stays in that cell: a table change across cells, rows or lines cannot be shown to the user, so say it in a comment instead."


def _cells(line: str) -> list[tuple[int, int]]:
    """The cells of one row as (start, end) offsets into `line`, outer pipes dropped."""
    cuts = [m.start() for m in _PIPE.finditer(line)]
    first = line[: cuts[0]].strip() == "" if cuts else False
    last = line[cuts[-1] + 1 :].strip() == "" if cuts else False
    edges = ([-1] if not first else []) + cuts + ([len(line)] if not last else [])
    return [(a + 1, b) for a, b in zip(edges, edges[1:])]


def _fence_after(fence: tuple[str, int] | None, line: str) -> tuple[str, int] | None:
    """The code fence still open after `line`: a fence opens with three or more backticks or tildes (a backtick
    fence's info string holds no backtick, or the line is inline code) and closes with its own character, at least as
    many times, and nothing else on the line."""
    if fence is None:
        found = _OPEN.match(line)
        return (found[1][0], len(found[1])) if found and not (found[1][0] == "`" and "`" in found[2]) else None
    return None if re.fullmatch(rf"{re.escape(fence[0])}{{{fence[1]},}}[ \t]*", line) else fence


def _tables(text: str) -> list[list[tuple[int, str, bool]]]:
    """Each table as its rows: (offset of the row's own text, that text, whether it is the delimiter row). A line's own
    text leaves out its end (`\\r` of a Windows note) and its margin, so a table in a blockquote or under a list item is
    read like any other."""
    lines, at = [], 0
    for raw in text.split("\n"):
        margin = _MARGIN.match(raw).end()
        lines.append((at + margin, raw[margin:].rstrip("\r")))
        at += len(raw) + 1
    found, fence, i = [], None, 0
    while i < len(lines):
        offset, line = lines[i]
        fence = _fence_after(fence, line)
        listed = _LIST.match(line)
        lead = listed.end() if listed else 0
        head = line[lead:]
        header = "|" in head and i + 1 < len(lines) and fence is None
        if header and _DELIMITER.match(lines[i + 1][1]) and "|" in lines[i + 1][1] and len(_cells(head)) == len(_cells(lines[i + 1][1])):
            rows = [(offset + lead, head, False), (*lines[i + 1], True)]
            i += 2
            while i < len(lines) and lines[i][1].strip() and _fence_after(None, lines[i][1]) is None:
                rows.append((*lines[i], False))
                i += 1
            found.append(rows)
            continue
        i += 1
    return found


def has_table(text: str) -> bool:
    """Whether `text` holds a table (so the persona is told how far her changes may go in it)."""
    return bool(_tables(text))


def problem(text: str, start: int, end: int, replace: str) -> str | None:
    """Why a change to `text[start:end]` cannot be drawn, or `None` when it can (outside a table, or inside one cell)."""
    for rows in _tables(text):
        top = rows[0][0]
        bottom = rows[-1][0] + len(rows[-1][1])
        if end <= top or start >= bottom:
            continue
        for offset, line, delimiter in rows:
            if offset <= start and end <= offset + len(line) and not delimiter:
                for a, b in _cells(line):
                    content = line[a:b]
                    lead = a + len(content) - len(content.lstrip())
                    stop = a + len(content.rstrip())
                    if offset + lead <= start and end <= offset + stop and start < end:
                        return _REFUSAL if _PIPE.search(replace) or "\n" in replace or replace.endswith("\\") else None
        return _REFUSAL
    return None
