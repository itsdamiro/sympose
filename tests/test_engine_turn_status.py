"""sympose.engine.turn_status: the real, per-handle phase of an in-flight turn."""

import threading

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


# -- one persona, several conversations (docs/decisions/057) --------------------------------------------------


def _reply_in(session_id, phase_after):
    """What a turn of that conversation does on its own thread: bind, set a phase, and report what it sees."""
    seen = {}

    def run():
        turn_status.bind("samantha", session_id)
        turn_status.set_phase("samantha", phase_after)
        seen["after"] = turn_status.phase("samantha", session_id)
        turn_status.unbind()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    return seen["after"]


def test_two_conversations_of_one_persona_each_have_their_own_phase():
    assert _reply_in("a", turn_status.SEARCHING) == turn_status.SEARCHING
    assert _reply_in("b", turn_status.READING) == turn_status.READING
    assert turn_status.phase("samantha", "a") == turn_status.SEARCHING
    assert turn_status.phase("samantha", "b") == turn_status.READING
    assert turn_status.phase("samantha", "c") is None
    for sid in ("a", "b"):
        turn_status.bind("samantha", sid)
        turn_status.set_phase("samantha", None)
    turn_status.unbind()
    assert turn_status.phase("samantha") is None


def test_asked_about_the_persona_alone_it_reports_a_reply_in_flight():
    turn_status.bind("samantha", "b")
    turn_status.set_phase("samantha", turn_status.ASKING)
    assert turn_status.phase("samantha") == turn_status.ASKING  # the persona-level read the CLI and /status use
    turn_status.set_phase("samantha", None)
    turn_status.unbind()


def test_a_turn_bound_to_one_persona_does_not_key_another_persona_under_its_conversation():
    turn_status.bind("samantha", "a")
    turn_status.set_phase("aria", turn_status.READING)  # not the persona this turn runs for
    assert turn_status.phase("aria", "a") is None and turn_status.phase("aria") == turn_status.READING
    turn_status.set_phase("aria", None)
    turn_status.unbind()
