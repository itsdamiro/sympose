"""Changing one part of a folder's definition note and leaving the rest of it as it is (docs/decisions/087): text in,
text out, nothing read or written here.

A definition note has three parts the Folder settings dialog owns: the look in its frontmatter (`icon`, `accent`,
`accent_dark`), the purpose (everything before the `## Template` heading except `# ` title lines, the span
`read_purpose` reads) and the template's code block (the span `read_template` reads). Each function below changes
its own part. Everything else stays byte for byte: the user's other properties, any text after the template block,
and the note's line endings (lines are cut with their breaks kept and put back as they were)."""

import re

from sympose import folder_definitions as defs
from sympose import folder_looks


def key_span(lines: list[str], key: str) -> tuple[int, int] | None:
    """`(first, after)` indexes of `key`'s property in frontmatter `lines`: its line and the indented lines that
    continue it. `None` when the note does not set it."""
    first = next((i for i, line in enumerate(lines) if re.match(rf"{re.escape(key)}[ \t]*:", line)), None)
    if first is None:
        return None
    after = first + 1
    while after < len(lines) and lines[after][:1] in (" ", "\t"):
        after += 1
    return first, after


def with_look(text: str, look: dict[str, str | None]) -> str | None:
    """`text` with each key of `look` set to its value in the frontmatter, or removed when the value is `None`.
    A key the note already sets keeps its place; a new one goes at the end of the frontmatter (a block is made when
    there is none); a key not in `look` is not touched. `None` when the note opens a frontmatter block it never
    closes."""
    parts = defs.split_frontmatter(text)
    if parts is None:
        return None
    front, rest = parts
    lines = front.splitlines(keepends=True)
    inner = lines[1:-1] if front else []  # the lines between the two `---` rules
    added: list[str] = []
    for key, value in look.items():
        span = key_span(inner, key)
        if span is None:
            if value is not None:
                added.append(folder_looks.line(key, value) + "\n")
        elif value is None:
            del inner[span[0] : span[1]]
        else:
            ending = "\r\n" if inner[span[0]].endswith("\r\n") else "\n"
            inner[span[0] : span[1]] = [folder_looks.line(key, value) + ending]
    if front:
        return lines[0] + "".join(inner) + "".join(added) + lines[-1] + rest
    return f"---\n{''.join(added)}---\n{rest}" if added else text


def with_purpose(text: str, purpose: str) -> str:
    """`text` with its purpose replaced by `purpose` (removed when blank). The `# ` title lines stay where they
    are, the purpose follows them, and the `## Template` heading and everything after it is not touched. A note with
    no Template heading has its whole body (after the frontmatter) read as the purpose, so it is replaced whole."""
    front, rest = defs.split_frontmatter(text) or ("", text)
    lines = rest.splitlines(keepends=True)
    end = next((i for i, line in enumerate(lines) if defs.TEMPLATE_HEADING.match(line.strip())), len(lines))
    kept = [line for line in lines[:end] if line.strip().startswith("# ")]
    if kept and (purpose.strip() or end < len(lines)) and not kept[-1].endswith("\n"):
        kept[-1] += "\n"
    new = ([*(["\n"] if kept else []), purpose.strip() + "\n"]) if purpose.strip() else []
    blank = ["\n"] if (kept or new) and end < len(lines) else []
    return front + "".join(kept + new + blank + lines[end:])


def with_template(text: str, template: list[str]) -> str:
    """`text` with the property lines inside its `## Template` code block replaced by `template`, the fences and
    everything around them as they were; a note without the section gets one at its end (nothing is added when
    `template` is empty)."""
    front, rest = defs.split_frontmatter(text) or ("", text)
    lines = rest.splitlines(keepends=True)
    block = [f"{line}\n" for line in template]
    span = defs.template_span(lines)
    if span is None:
        if not template:
            return text
        gap = "" if not rest.strip() else ("\n" if rest.endswith("\n") else "\n\n")
        return f"{front}{rest}{gap}## Template\n\n```yaml\n{''.join(block)}```\n"
    _, fence, end = span
    opening = lines[fence] if lines[fence].endswith("\n") else lines[fence] + "\n"
    marker = lines[fence].strip()[:3]
    closing = lines[end:] if end < len(lines) else [f"{marker}\n"]
    return front + "".join(lines[:fence] + [opening] + block + closing)
