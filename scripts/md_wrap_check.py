#!/usr/bin/env python3
"""Fail on hard-wrapped Markdown prose: a paragraph, list item or quote is one line, and the editor wraps it.

Usage: python3 scripts/md_wrap_check.py [path ...]
A path is a Markdown file or a folder searched for *.md (default: the current folder). Hidden folders,
node_modules and symbolic links are skipped. Reports `file:line: ...` for each line that continues the line above it.
Exits 1 if any, 2 if a path does not exist.

Not flagged: code fences, frontmatter, tables, headings, rules, HTML lines, blank lines, a new list item, and a line
after one that ends in a hard break (two trailing spaces or a backslash).
"""

import os
import re
import sys
from collections.abc import Iterator

LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
SKIPPED_DIRS = {"node_modules"}


def continuation_lines(lines: list[str]) -> Iterator[int]:
    """Yield the index of every line that continues the prose line directly above it."""
    fence = ""  # the opening fence while inside a code block
    frontmatter = bool(lines) and lines[0].rstrip() == "---"
    prose = False  # the line above is prose that a following plain line would continue
    quoted = 0  # blockquote depth of the line above
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if frontmatter:
            if i > 0 and line.rstrip() in ("---", "..."):
                frontmatter, prose = False, False
            continue
        opened = FENCE.match(line)
        if fence:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence) and not line.strip(" `~"):
                fence = ""
            continue
        if opened:
            fence, prose = opened.group(1), False
            continue
        depth = 0
        while (stripped := line.lstrip()).startswith(">"):
            depth, line = depth + 1, stripped[1:]
        text = line.strip()
        if not text or text.startswith(("#", "|", "<")) or RULE.match(line):
            prose = False
            continue
        if LIST_ITEM.match(line):
            prose, quoted = not line.endswith(("  ", "\\")), depth
            continue
        if prose and quoted == depth:
            yield i
        prose, quoted = not line.endswith(("  ", "\\")), depth


def markdown_files(paths: list[str]) -> Iterator[str]:
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRS)
            yield from (p for f in sorted(files) if f.endswith(".md") and not os.path.islink(p := os.path.join(root, f)))


def main(paths: list[str]) -> int:
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:  # a typo in the gate's command must not read as a pass
        print(f"no such file or folder: {', '.join(missing)}")
        return 2
    found = 0
    for path in markdown_files(paths or ["."]):
        with open(path, encoding="utf-8") as f:
            for i in continuation_lines(f.readlines()):
                print(f"{path}:{i + 1}: continues the line above; keep one paragraph or list item on one line")
                found += 1
    if found:
        print(f"{found} wrapped line(s). Join each onto the line above it.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
