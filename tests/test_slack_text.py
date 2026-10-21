"""Markdown as Slack's mrkdwn (docs/decisions/093)."""

from sympose import slack_text
from sympose.slack_text import to_mrkdwn


def test_bold_italic_and_headings():
    assert to_mrkdwn("**bold** and *italic* and __also bold__") == "*bold* and _italic_ and *also bold*"
    assert to_mrkdwn("## A heading\ntext") == "*A heading*\ntext"


def test_a_link_and_a_bullet():
    assert to_mrkdwn("see [Rust](https://rust-lang.org)") == "see <https://rust-lang.org|Rust>"
    assert to_mrkdwn("- one\n  - two\n* three") == "• one\n  • two\n• three"


def test_code_is_left_as_written_apart_from_the_characters_slack_reads():
    assert to_mrkdwn("`**not bold**` and ```\n- a < b\n```") == "`**not bold**` and ```\n- a &lt; b\n```"


def test_characters_slack_reads_are_escaped_outside_code():
    assert to_mrkdwn("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_a_wiki_link_is_plain_text():
    assert to_mrkdwn("see [[My Note]]") == "see [[My Note]]"


def test_a_multiplication_star_is_not_italic():
    assert to_mrkdwn("2 * 3 * 4") == "2 * 3 * 4"


def test_a_long_reply_is_cut_and_says_so():
    out = to_mrkdwn("x" * 50_000)
    assert len(out) <= slack_text.MAX_CHARS + len(slack_text.CUT)
    assert out.endswith(slack_text.CUT)


def test_a_reply_at_the_limit_is_not_cut():
    assert to_mrkdwn("x" * slack_text.MAX_CHARS) == "x" * slack_text.MAX_CHARS
