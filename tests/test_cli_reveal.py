"""The speed of the word-by-word reveal of a reply (docs/decisions/032)."""

import pytest

from sympose import settings_store
from sympose.cli import reveal


def test_the_reveal_defaults_to_50_words_per_second():
    assert reveal.words_per_second() == 50


@pytest.mark.parametrize("value, expected", [(20, 20), (7.5, 7.5), (0, 0), (300, 300)])
def test_a_number_is_read_as_written(value, expected):
    settings_store.set("reply_reveal", value)
    assert reveal.words_per_second() == expected


@pytest.mark.parametrize("value", ["fast", "20", None, True, False, -1, [20], {"wps": 20}, float("nan"), float("inf")])
def test_anything_else_leaves_the_default(value):
    settings_store.set("reply_reveal", value)
    assert reveal.words_per_second() == 50


def test_at_50_words_per_second_a_frame_of_a_twentieth_of_a_second_adds_two_or_three_words():
    shown = [reveal.words_shown(1000, frame, 50) for frame in range(1, 5)]

    assert shown == [3, 5, 8, 10]


def test_at_20_words_per_second_it_is_one_word_a_frame_as_it_always_was():
    assert [reveal.words_shown(1000, frame, 20) for frame in range(1, 5)] == [1, 2, 3, 4]


def test_a_speed_below_one_word_a_frame_still_shows_the_first_word_at_once_then_waits():
    assert reveal.words_shown(1000, 1, 5) == 1
    assert reveal.words_shown(1000, 4, 5) == 1
    assert reveal.words_shown(1000, 5, 5) == 2


def test_zero_shows_everything_in_the_first_frame():
    assert reveal.words_shown(600, 1, 0) == 600


def test_it_never_shows_more_words_than_there_are():
    assert reveal.words_shown(4, 10, 50) == 4
