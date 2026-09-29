"""sympose.engine.turn_status: the real, per-handle phase of an in-flight turn."""

from sympose.engine import turn_status


def test_nothing_set_reads_as_none():
    assert turn_status.phase("samantha") is None


def test_set_then_read_back():
    turn_status.set_phase("samantha", turn_status.SEARCHING)
    assert turn_status.phase("samantha") == turn_status.SEARCHING
    turn_status.set_phase("samantha", None)


def test_clearing_with_none_removes_it():
    turn_status.set_phase("samantha", turn_status.ASKING)
    turn_status.set_phase("samantha", None)
    assert turn_status.phase("samantha") is None


def test_each_handle_is_independent():
    turn_status.set_phase("samantha", turn_status.SEARCHING)
    turn_status.set_phase("aria", turn_status.READING)
    assert turn_status.phase("samantha") == turn_status.SEARCHING
    assert turn_status.phase("aria") == turn_status.READING
    turn_status.set_phase("samantha", None)
    turn_status.set_phase("aria", None)


def test_a_falsy_handle_is_a_no_op():
    """A bare persona dict with no `handle` (some unit tests' fixtures) must not raise or track
    anything under a `None` key."""
    turn_status.set_phase(None, turn_status.SEARCHING)
    assert turn_status.phase(None) is None
