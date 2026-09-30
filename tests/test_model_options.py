"""The list a picker shows (docs/decisions/046): the offered models, plus a row for a model in use that the
list does not hold, so a model named by hand is never invisible."""

from sympose.engine.model_options import MODEL_OPTIONS, offered

HAND = "openrouter/mistralai/mistral-large"


def test_nothing_unlisted_in_use_gives_exactly_the_list():
    assert offered() == MODEL_OPTIONS
    assert offered(MODEL_OPTIONS[1].id, "", MODEL_OPTIONS[0].id) == MODEL_OPTIONS


def test_a_model_in_use_that_is_not_listed_is_added_once_at_the_end():
    rows = offered(HAND, HAND)
    assert rows[:-1] == MODEL_OPTIONS and len(rows) == len(MODEL_OPTIONS) + 1
    assert rows[-1].id == HAND and rows[-1].short == "mistral-large"


def test_the_shared_list_itself_is_not_changed():
    before = list(MODEL_OPTIONS)
    offered(HAND)
    assert MODEL_OPTIONS == before
