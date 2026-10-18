"""A note made from a video: the bare timestamps the model writes become links to that moment (docs/decisions/089)."""

from sympose.engine import video_stamps

VIDEO = "https://www.youtube.com/watch?v=8jPQjjsBbIc"


def test_a_minutes_and_an_hours_timestamp_become_links_with_the_seconds_worked_out():
    assert video_stamps.link("- [3:10] Idea", (VIDEO,)) == f"- [3:10]({VIDEO}&t=190s) Idea"
    assert video_stamps.link("[1:02:15]", (VIDEO,)) == f"[1:02:15]({VIDEO}&t=3735s)"


def test_what_is_already_a_link_or_not_a_time_is_left_as_written():
    text = "[2:05](https://x.test) [2:05][ref] [3:75] [1:75:00] [a:10] [3:1] [[3:10]] word[3:10]"

    assert video_stamps.link(text, (VIDEO,)) == text


def test_nothing_is_linked_without_exactly_one_video():
    assert video_stamps.link("[3:10]", ()) == "[3:10]"
    assert video_stamps.link("[3:10]", (VIDEO, VIDEO + "x")) == "[3:10]"
