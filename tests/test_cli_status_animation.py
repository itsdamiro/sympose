"""The busy line's rotation and its letter-by-letter typing (docs/decisions/043, the 2026-09-30 amendment):
every kind of activity rotates its witty phrase, a pick never repeats the one just shown, and a phrase is
typed out at `status_typing` characters per second. The widget's state machine (`_line`) is driven directly
with a scripted clock, so nothing here depends on how fast the machine is."""

import random

import pytest

from sympose import settings_store
from sympose.cli import background_status as bs
from sympose.engine import status_phrases, turn_status

PHRASES = ["Alpha one…", "Beta two…", "Gamma three…"]


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(status_phrases, "phrases", lambda handle: list(PHRASES))
    settings_store.set(bs.TYPING_SETTING, 0)  # whole phrases by default; typing tests set their own speed


def widget():
    return bs.BackgroundStatus()


def text(line: str) -> str:
    """The line without its spinner."""
    return line[2:]


def step(w, kind, now, detail=""):
    return w._line("samantha", kind, detail, now)


# -- rotation ----------------------------------------------------------------


def test_a_background_job_rotates_to_a_new_witty_phrase_every_interval():
    w = widget()
    seen = [text(step(w, "recap", t)) for t in (0.0, 3.0, 6.0, 9.0, 12.0)]
    assert all(p in PHRASES for p in seen)
    assert all(a != b for a, b in zip(seen, seen[1:]))  # each interval shows a different one


def test_a_phrase_stays_put_between_intervals():
    w = widget()
    first = text(step(w, "memory", 0.0))
    assert [text(step(w, "memory", t)) for t in (0.5, 1.5, 2.9)] == [first, first, first]


def test_a_pick_never_repeats_the_phrase_just_shown_over_many_rotations():
    random.seed(7)
    w = widget()
    seen = [text(step(w, "index", i * 3.0, " 10%")).removesuffix(" 10%") for i in range(60)]
    assert all(a != b for a, b in zip(seen, seen[1:]))


def test_a_persona_with_one_phrase_keeps_showing_it():
    bs.status_phrases.phrases = lambda handle: ["Only one…"]
    w = widget()
    assert [text(step(w, "recap", t)) for t in (0.0, 3.0, 6.0)] == ["Only one…"] * 3


def test_a_change_of_activity_starts_a_new_rotation_from_that_moment():
    w = widget()
    step(w, "recap", 0.0)
    step(w, "recap", 3.0)
    began = text(step(w, "memory", 100.0))  # a different job begins
    assert text(step(w, "memory", 100.5)) == began  # no rotation until its own interval has passed
    assert text(step(w, "memory", 101.0)) == began
    assert text(step(w, "memory", 103.0)) != began


def test_a_real_phase_still_alternates_the_literal_text_and_a_witty_line_and_never_repeats_the_witty_one():
    random.seed(11)
    w = widget()
    literal = bs.REAL_STATUS_TEXT[turn_status.READING]
    lines = [text(step(w, turn_status.READING, t)) for t in (0.0, 2.9, 3.0, 5.9, 6.0, 9.0, 12.0, 15.0)]
    assert lines[0] == lines[1] == literal  # nothing changes before the threshold
    assert lines[2] in PHRASES and lines[3] == lines[2]  # witty from 3 s, held for its slot
    assert lines[4] == literal and lines[6] == literal  # the literal one resurfaces every other slot
    assert lines[5] in PHRASES and lines[7] in PHRASES and lines[5] != lines[7]


def test_nothing_running_shows_nothing_and_the_next_activity_starts_afresh():
    w = widget()
    step(w, "recap", 0.0)
    assert step(w, None, 1.0) == ""
    assert text(step(w, "recap", 2.0)) in PHRASES


def test_the_line_is_redrawn_only_when_its_text_changed(monkeypatch):
    from types import SimpleNamespace

    drawn = []
    monkeypatch.setattr(bs.BackgroundStatus, "app", property(lambda self: SimpleNamespace(persona=SimpleNamespace(handle="samantha"))))
    monkeypatch.setattr(bs, "activity", lambda handle: ("recap", ""))
    monkeypatch.setattr(bs, "_monotonic", lambda: 0.0)
    w = widget()
    monkeypatch.setattr(w, "update", lambda text: drawn.append(text.plain))
    for _ in range(6):
        w._tick()
    assert len(drawn) == 2  # the spinner steps every third frame; the ticks between change nothing


# -- typing by letters ---------------------------------------------------------


def typed(w, kind, now):
    return text(step(w, kind, now))


def test_a_phrase_is_typed_out_one_letter_at_a_time_at_the_speed_the_setting_names():
    settings_store.set(bs.TYPING_SETTING, 10)  # ten characters a second
    w = widget()
    first = typed(w, "recap", 0.0)
    assert len(first) == 1  # the first letter is there at once
    phrase = next(p for p in PHRASES if p.startswith(first))  # the phrase being typed
    assert typed(w, "recap", 0.2) == phrase[:3]  # 10 cps x 0.2 s = 2 more letters
    assert typed(w, "recap", 0.5) == phrase[:6]
    assert typed(w, "recap", 2.0) == phrase  # a ten-letter phrase is whole after a second


def test_typing_starts_again_for_every_new_phrase():
    settings_store.set(bs.TYPING_SETTING, 10)
    w = widget()
    typed(w, "recap", 0.0)
    assert typed(w, "recap", 2.5) in PHRASES  # fully typed before the rotation
    just_rotated = typed(w, "recap", 3.0)
    assert len(just_rotated) == 1  # the new phrase begins again from its first letter


def test_the_literal_text_of_a_real_phase_is_typed_too():
    settings_store.set(bs.TYPING_SETTING, 10)
    w = widget()
    assert typed(w, turn_status.SEARCHING, 0.0) == "S"
    assert typed(w, turn_status.SEARCHING, 1.0) == bs.REAL_STATUS_TEXT[turn_status.SEARCHING][:11]


def test_zero_shows_every_phrase_whole_at_once():
    settings_store.set(bs.TYPING_SETTING, 0)
    w = widget()
    assert typed(w, "recap", 0.0) in PHRASES
    assert typed(w, turn_status.SEARCHING, 5.0) == bs.REAL_STATUS_TEXT[turn_status.SEARCHING]


def test_a_detail_after_the_phrase_is_not_typed_letter_by_letter():
    settings_store.set(bs.TYPING_SETTING, 10)
    w = widget()
    assert step(w, "index", 0.0, " 40%").endswith(" 40%")


@pytest.mark.parametrize("bad", [-5, True, "fast", None, float("nan"), float("inf")])
def test_an_unusable_typing_speed_leaves_the_default(bad):
    settings_store.set(bs.TYPING_SETTING, bad)
    assert bs.chars_per_second() == bs.DEFAULT_CHARS_PER_SECOND


def test_a_usable_typing_speed_is_read():
    settings_store.set(bs.TYPING_SETTING, 12.5)
    assert bs.chars_per_second() == 12.5
    settings_store.set(bs.TYPING_SETTING, 0)
    assert bs.chars_per_second() == 0


# -- the spinner keeps its own pace --------------------------------------------


def test_the_spinner_advances_every_third_frame_whatever_the_typing_speed():
    w = widget()
    frames = [step(w, "recap", 0.0)[0] for _ in range(7)]
    assert frames[0] == frames[1] == frames[2]
    assert frames[3] != frames[2] and frames[3] == frames[4] == frames[5]
    assert frames[6] != frames[5]
