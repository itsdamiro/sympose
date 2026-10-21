"""A reply as Slack shows it (docs/decisions/093): Markdown turned into Slack's own `mrkdwn`. Code is left exactly as it is,
a table or a `[[wiki link]]` is passed through as text (how Slack shows them is still to be measured against a real workspace)."""

import re

LIMIT = 40_000  # Slack cuts a message here
MAX_CHARS = 39_000  # a reply is cut here, which leaves room for the line that says so and for what was proposed (`slack_drafts`)
CUT = "\n\n_The rest is cut: Slack takes no more in one message. Open the conversation in the web app to read it._"
_CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.MULTILINE)
_BULLET = re.compile(r"^(\s*)[-*+]\s+", re.MULTILINE)
_BOLD_MARK = "\x00"  # stands for a Slack bold star until the single stars have become italics


def _outside_code(text: str, convert) -> str:
    parts, last = [], 0
    for code in _CODE.finditer(text):
        parts.append(convert(text[last:code.start()]))
        parts.append(code.group(0).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        last = code.end()
    parts.append(convert(text[last:]))
    return "".join(parts)


def _convert(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = _HEADING.sub(lambda m: f"**{m.group(1)}**", text)
    text = _BOLD.sub(lambda m: f"{_BOLD_MARK}{m.group(1) or m.group(2)}{_BOLD_MARK}", text)
    text = _ITALIC.sub(r"_\1_", text)
    text = text.replace(_BOLD_MARK, "*")
    text = _LINK.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", text)
    return _BULLET.sub(r"\1• ", text)


def to_mrkdwn(markdown: str) -> str:
    text = _outside_code(markdown.strip(), _convert)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS].rstrip() + CUT
