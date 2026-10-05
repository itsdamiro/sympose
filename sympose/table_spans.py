"""Where a Markdown table is in a note's text, and whether a change fits inside one of its cells (docs/decisions/069).

The editor draws a change of hers inside a table cell only when the quoted words sit within one cell's own text and the
replacement stays in that cell; anything else cannot be drawn there, and a change nobody can see must not exist. A table
is found by its shape (a header row, a delimiter row of dashes with as many cells, the rows below until a blank line),
outside fenced code."""

import re

_DELIMITER = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_PIPE = re.compile(r"(?<!\\)\|")
_REFUSAL = "Quote words that sit inside one cell of the table, with a replacement that stays in that cell: a table change across cells, rows or lines cannot be shown to the user, so say it in a comment instead."


def _cells(line: str) -> list[tuple[int, int]]:
    """The cells of one row as (start, end) offsets into `line`, outer pipes dropped."""
    cuts = [m.start() for m in _PIPE.finditer(line)]
    first = line[: cuts[0]].strip() == "" if cuts else False
    last = line[cuts[-1] + 1 :].strip() == "" if cuts else False
    edges = ([-1] if not first else []) + cuts + ([len(line)] if not last else [])
    return [(a + 1, b) for a, b in zip(edges, edges[1:])]


def _tables(text: str) -> list[list[tuple[int, str, bool]]]:
    """Each table as its rows: (offset of the line, the line, whether it is the delimiter row)."""
    lines, at = [], 0
    for line in text.split("\n"):
        lines.append((at, line))
        at += len(line) + 1
    found, fenced, i = [], False, 0
    while i < len(lines):
        offset, line = lines[i]
        if _FENCE.match(line):
            fenced = not fenced
        header = "|" in line and i + 1 < len(lines) and not fenced
        if header and _DELIMITER.match(lines[i + 1][1]) and "|" in lines[i + 1][1] and len(_cells(line)) == len(_cells(lines[i + 1][1])):
            rows = [(offset, line, False), (*lines[i + 1], True)]
            i += 2
            while i < len(lines) and lines[i][1].strip() and not _FENCE.match(lines[i][1]):
                rows.append((*lines[i], False))
                i += 1
            found.append(rows)
            continue
        i += 1
    return found


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
                        return _REFUSAL if _PIPE.search(replace) or "\n" in replace else None
        return _REFUSAL
    return None
