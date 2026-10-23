"""The cap on the new-note drafts an unattended source leaves waiting (docs/decisions/091 and 093, amended 2026-10-23): the tag a
draft carries, the one limit and where it is set, and the refusal at the limit."""

import threading

import pytest
from helpers import write_persona

from sympose import draft_limit, note_changes as nc, settings_store

H = "samantha"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    directory = write_persona(base, "samantha", "name: Samantha\n")
    (directory / "jobs").mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return directory


def _note(i: int, source: str | None = None) -> dict:
    return nc.propose_create(H, f"new/{i}", f"# Note {i}\n\nWords {i}.\n", say="", filing=draft_limit.Filing(source))


def test_the_default_is_five():
    assert draft_limit.limit() == 5


def test_the_limit_comes_from_the_setting():
    settings_store.set(draft_limit.SETTING, 3)
    assert draft_limit.limit() == 3


@pytest.mark.parametrize("bad", [0, 101, -1, 2.5, "3", True, None])
def test_a_value_that_is_not_a_whole_number_in_range_is_ignored(bad):
    settings_store.set(draft_limit.SETTING, bad)
    assert draft_limit.limit() == 5


def test_the_ends_of_the_range_are_allowed():
    for end in (1, 100):
        settings_store.set(draft_limit.SETTING, end)
        assert draft_limit.limit() == end


def test_a_draft_made_inside_a_source_is_tagged_with_it():
    assert _note(1, "slack")["source"] == "slack"
    assert _note(2, draft_limit.job_source("weekly"))["source"] == "job:weekly"
    assert "source" not in _note(3)


def test_only_the_drafts_of_a_source_count_for_it():
    _note(1, "slack")
    _note(2, "slack")
    _note(3, draft_limit.job_source("weekly"))
    _note(4)
    assert (draft_limit.waiting(H, "slack"), draft_limit.waiting(H, "job:weekly"), draft_limit.waiting(H, "job:other")) == (2, 1, 0)


def test_a_source_at_its_limit_files_no_more_and_says_why():
    settings_store.set(draft_limit.SETTING, 2)
    _note(1, "slack")
    _note(2, "slack")
    with pytest.raises(nc.CannotAnchor, match="2 drafts from Slack are waiting"):
        _note(3, "slack")
    assert draft_limit.waiting(H, "slack") == 2


def test_a_job_and_slack_have_the_same_limit_each_for_itself():
    settings_store.set(draft_limit.SETTING, 2)
    for i, source in enumerate(("slack", "job:weekly", "job:other")):
        _note(2 * i, source)
        _note(2 * i + 1, source)
        assert draft_limit.refusal(H, source) is not None
    assert draft_limit.waiting(H, "slack") == 2


def test_a_job_at_its_limit_says_it_is_the_job():
    settings_store.set(draft_limit.SETTING, 1)
    _note(1, "job:weekly")
    with pytest.raises(nc.CannotAnchor, match="1 draft from this job is waiting"):
        _note(2, "job:weekly")


def test_one_below_the_limit_is_still_filed():
    settings_store.set(draft_limit.SETTING, 2)
    _note(1, "slack")
    assert _note(2, "slack")["source"] == "slack"


def test_the_refusal_is_in_the_plural_only_for_more_than_one():
    settings_store.set(draft_limit.SETTING, 1)
    first = _note(1, "slack")
    assert draft_limit.refusal(H, "slack") == "1 draft from Slack is waiting to be accepted or declined, which is the limit, so no new one was made."
    settings_store.set(draft_limit.SETTING, 2)
    _note(2, "slack")
    assert draft_limit.refusal(H, "slack") == "2 drafts from Slack are waiting to be accepted or declined, which is the limit, so no new one was made."
    nc.discard_proposal(H, "new/1", first["id"])
    assert draft_limit.refusal(H, "slack") is None


def test_a_source_over_its_limit_does_not_stop_another_source_or_the_web_chat():
    settings_store.set(draft_limit.SETTING, 1)
    _note(1, "slack")
    _note(2, "job:weekly")
    _note(3)
    assert [draft_limit.waiting(H, s) for s in ("slack", "job:weekly")] == [1, 1]


def test_deciding_a_draft_makes_room():
    settings_store.set(draft_limit.SETTING, 1)
    first = _note(1, "slack")
    with pytest.raises(nc.CannotAnchor):
        _note(2, "slack")
    nc.discard_proposal(H, "new/1", first["id"])
    assert _note(2, "slack")["source"] == "slack"


def test_a_draft_already_waiting_with_no_tag_is_not_counted():
    settings_store.set(draft_limit.SETTING, 1)
    _note(1)
    assert _note(2, "slack")["source"] == "slack"


def test_a_lowered_limit_does_not_remove_drafts_already_waiting():
    for i in range(3):
        _note(i, "slack")
    settings_store.set(draft_limit.SETTING, 1)
    assert draft_limit.waiting(H, "slack") == 3
    with pytest.raises(nc.CannotAnchor):
        _note(9, "slack")


def test_a_draft_filed_with_no_filing_has_no_source_and_is_never_refused():
    settings_store.set(draft_limit.SETTING, 1)
    _note(1, "slack")
    for i in range(2, 5):
        assert "source" not in nc.propose_create(H, f"new/{i}", f"# Note {i}\n\nWords {i}.\n", say="")


def test_a_filing_lists_each_new_note_it_filed_in_order_and_not_one_that_was_refused():
    settings_store.set(draft_limit.SETTING, 2)
    filing = draft_limit.Filing("slack")
    first = nc.propose_create(H, "new/1", "# One\n\nOne.\n", say="", filing=filing)
    second = nc.propose_create(H, "new/2", "# Two\n\nTwo.\n", say="", filing=filing)
    with pytest.raises(nc.CannotAnchor):
        nc.propose_create(H, "new/3", "# Three\n\nThree.\n", say="", filing=filing)
    assert filing.made == [("new/1", first["id"]), ("new/2", second["id"])]


def test_two_turns_filing_at_once_cannot_both_pass_the_limit():
    settings_store.set(draft_limit.SETTING, 1)
    made, refused = [], []
    barrier = threading.Barrier(8)

    def file(i: int) -> None:
        barrier.wait()
        try:
            made.append(_note(i, "slack"))
        except nc.CannotAnchor:
            refused.append(i)

    threads = [threading.Thread(target=file, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert (len(made), len(refused), draft_limit.waiting(H, "slack")) == (1, 7, 1)
