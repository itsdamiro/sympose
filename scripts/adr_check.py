#!/usr/bin/env python3
"""Check the shape of a project's decision records (ADR 012). Reads files only; it fixes nothing.

Usage: python3 scripts/adr_check.py [--dir docs/decisions] [--from NNN]

Every docs/decisions/NNN-slug.md numbered NNN or higher must have: frontmatter with type: decision, a status, a date,
projects, concepts (at least one, each in sentence case), amends, supersedes and tags (including type/decision, the
status tag and at least one topic/ tag that is not just a concept's name in kebab-case); a `> **Summary.**` line; a heading `# NNN — Title`; and a row in the directory's README.md. Whether a
concept has a note in the vault is the vault lint's job, not this script's. Exit 1 on any problem, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

RECORD = re.compile(r"^(\d{3})-.+\.md$")
STATUSES = {"proposed", "accepted", "superseded", "removed"}
REQUIRED = ("type", "status", "date", "projects", "concepts", "amends", "supersedes", "tags")
BLOCK_ITEM = re.compile(r"^\s+-(?:\s+(.*))?$")
BAD_NAME = re.compile(r"[\[\]|#/:\\^]|\s{2}")


def kebab(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_value(raw: str):
    """A scalar or a flow list ([a, b]); a trailing # comment is dropped. Raises ValueError on a list left open."""
    s = re.split(r"(?:^|\s+)#", raw.strip(), maxsplit=1)[0].strip()
    if not s.startswith("["):
        return s.strip("\"'")
    if not s.endswith("]"):
        raise ValueError("the list is not closed")
    return split_items(s[1:-1])


def split_items(inner: str) -> list[str]:
    """The items of a flow list: split on commas outside quotes, quotes dropped (an apostrophe inside a word is text)."""
    items, cur, quote = [], "", ""
    for c in inner:
        if quote:
            if c == quote:
                quote = ""
            else:
                cur += c
        elif c in "\"'" and not cur.strip():
            quote = c
        elif c == ",":
            items.append(cur.strip())
            cur = ""
        else:
            cur += c
    return [x for x in items + [cur.strip()] if x]


def frontmatter(text: str) -> tuple[dict, str, str]:
    """(fields, body, problem). A problem means the fields could not be read."""
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return {}, text, "no frontmatter"
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), 0)
    if not end:
        return {}, text, "the frontmatter is not closed"
    fields, open_key = {}, ""
    for number, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = BLOCK_ITEM.match(line)
        if item and open_key:  # "key:" followed by "- value" lines, as Obsidian writes lists
            fields[open_key] = (fields[open_key] or []) + split_items(item.group(1) or "")
            continue
        key, colon, value = line.partition(":")
        if not colon or not re.fullmatch(r"[A-Za-z_][\w-]*", key):
            return fields, "", f"line {number}: not a `key: value` line"
        try:
            fields[key] = parse_value(value)
            open_key = key if fields[key] == "" else ""
        except ValueError as err:
            return fields, "", f"line {number}: {err}"
    return fields, "\n".join(lines[end + 1:]), ""


def problems_of(name: str, text: str, index: str) -> list[str]:
    number = RECORD.match(name).group(1)
    fields, body, problem = frontmatter(text)
    if problem:
        return [problem]
    out = [f"missing field: {key}" for key in REQUIRED if key not in fields]
    for key in ("type", "status", "date"):
        if isinstance(fields.get(key), list):
            out.append(f"{key} must be a single value, not a list")
            del fields[key]
    if fields.get("type", "decision") != "decision":
        out.append(f"type is {fields['type']!r}, not decision")
    status = fields.get("status")
    if status is not None and status not in STATUSES:
        out.append(f"status {status!r} is not one of {', '.join(sorted(STATUSES))}")
    date = fields.get("date")
    if date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        out.append(f"date {date!r} is not YYYY-MM-DD")
    for key in ("projects", "concepts", "amends", "supersedes", "tags"):
        if key in fields and not isinstance(fields[key], list):
            out.append(f"{key} must be a list, like [a, b]")
    if isinstance(fields.get("projects"), list) and not fields["projects"]:
        out.append("projects is empty")
    concepts = fields.get("concepts")
    if isinstance(concepts, list):
        if not concepts:
            out.append("concepts is empty: name at least one")
        for c in concepts:
            if not (c[:1].isdigit() or c[:1].isupper()) or BAD_NAME.search(c):
                out.append(f"concept {c!r} must be in sentence case, written as its note is named (no [ ] | # / : \\ ^)")
    tags = fields.get("tags")
    if isinstance(tags, list) and status in STATUSES:
        for wanted in ("type/decision", f"status/{status}"):
            if wanted not in tags:
                out.append(f"tags lack {wanted}")
        topics = [t[6:] for t in tags if t.startswith("topic/")]
        if not topics:
            out.append("tags have no topic/ tag: a topic is a question to filter by, listed in the vault's Tags.md")
        own = {kebab(c) for c in concepts} if isinstance(concepts, list) else set()
        out += [f"topic/{t} only repeats a concept; a topic must cut across concepts (docs/VAULT_CONVENTIONS.md)"
                for t in topics if t in own]
    if not re.search(r"^>\s*\*\*Summary\.?\*\*[ \t]*\S", body, re.M):
        out.append("no `> **Summary.**` line")
    heading = next((line for line in body.splitlines() if line.startswith("# ")), "")
    if not re.match(rf"# {number}\b", heading):
        out.append(f"the first heading must start with `# {number}`")
    if f"({name})" not in index:
        out.append("no row in README.md (a link to this file)")
    return out


def check(directory: str, start: int) -> list[str]:
    try:
        names = sorted(n for n in os.listdir(directory) if RECORD.match(n) and int(n[:3]) >= start)
    except FileNotFoundError:
        return []
    try:
        with open(os.path.join(directory, "README.md"), encoding="utf-8") as f:
            index = f.read()
    except FileNotFoundError:
        index = ""
    found = []
    for name in names:
        try:
            with open(os.path.join(directory, name), encoding="utf-8-sig") as f:
                text = f.read()
        except UnicodeDecodeError:
            found.append(f"{directory}/{name}: the file is not UTF-8")
            continue
        found += [f"{directory}/{name}: {p}" for p in problems_of(name, text, index)]
    return found


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check the shape of decision records (ADR 012).")
    parser.add_argument("--dir", default="docs/decisions")
    parser.add_argument("--from", dest="start", type=int, default=1, help="skip records numbered below this")
    args = parser.parse_args(argv)
    found = check(args.dir, args.start)
    for line in found:
        print(line)
    print(f"{len(found)} problem(s)" if found else "decision records ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
