"""Tests for sympose.engine.memory_refresh (docs/decisions/041's `memory_rewrite`): what the
model is asked, how its reply is parsed, and where the result lands -- staged or applied. The
model is a stub here; what the real one proposes is checked by a live measurement (the ADR)."""

import threading

import pytest
from helpers import write_persona

from sympose import settings_store
from sympose.engine import background_job, budget, memory, memory_refresh, memory_write, prompt, recap
from sympose.engine.model import EngineModelError, ModelReply, ReplyLimitError


@pytest.fixture(autouse=True)
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(budget, "_native_max", lambda model: 8192)
    monkeypatch.setattr(memory_refresh, "_CANNOT_REWRITE", set())
    monkeypatch.setattr(memory_refresh, "_RUNNER", background_job.Runner("memory", "Memory rewrite"))
    return base


class Asked(list):
    def __init__(self):
        super().__init__()
        self.replies: list = [
            ModelReply(f"{prompt.MEMORY_PROFILE_MARK}\nLikes concise replies.\n{prompt.MEMORY_CONTEXT_MARK}\n"
                       "Working on the Atlas migration.", 5)
        ]


@pytest.fixture
def asked(monkeypatch):
    calls = Asked()

    def call_model(messages, model=None, **limits):
        calls.append({"messages": messages, "model": model, **limits})
        reply = calls.replies[min(len(calls), len(calls.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(memory_refresh.model_mod, "call_model", call_model)
    return calls


def _one_recap(handle: str = "samantha", session_id: str = "20260924T090000-aaaaaaaa") -> None:
    recap.write(handle, session_id, 2, "Talked about the Atlas database.")


# -- mode() ----------------------------------------------------------------------


def test_mode_defaults_to_ask():
    assert memory_refresh.mode() == memory_refresh.ASK


def test_mode_is_auto_only_when_set_explicitly():
    settings_store.set(memory_refresh.SETTING, "auto")
    assert memory_refresh.mode() == memory_refresh.AUTO
    settings_store.set(memory_refresh.SETTING, "something else")
    assert memory_refresh.mode() == memory_refresh.ASK


# -- propose(): when nothing is asked at all --------------------------------------


def test_propose_with_no_persona_asks_nothing(asked):
    assert memory_refresh.propose("nobody") == (None, None)
    assert len(asked) == 0


def test_propose_with_no_recaps_yet_asks_nothing(asked):
    assert memory_refresh.propose("samantha") == (None, None)
    assert len(asked) == 0


def test_propose_for_a_cloud_model_not_approved_for_memory_asks_nothing(asked):
    _one_recap()
    assert memory_refresh.propose("samantha", model="anthropic/claude-sonnet-5") == (None, None)
    assert len(asked) == 0


def test_propose_for_a_cloud_model_approved_for_memory_but_not_recaps_asks_nothing(asked):
    """The recaps sent as input need their own approval too, the same as a turn's own gate --
    `memory` alone does not imply `recaps` is also approved."""
    _one_recap()
    settings_store.set("cloud_share", ["memory"])
    assert memory_refresh.propose("samantha", model="anthropic/claude-sonnet-5") == (None, None)
    assert len(asked) == 0


def test_propose_for_a_cloud_model_approved_for_memory_and_recaps_does_ask(asked):
    _one_recap()
    settings_store.set("cloud_share", ["memory", "recaps"])
    memory_refresh.propose("samantha", model="anthropic/claude-sonnet-5")
    assert len(asked) == 1


# -- propose(): the request ---------------------------------------------------------


def test_the_request_carries_the_current_files_and_the_recaps(asked, profiles):
    (profiles / "samantha" / "profile.md").write_text("Likes plain text.\n")
    _one_recap()

    memory_refresh.propose("samantha")

    system, user = asked[0]["messages"]
    assert system == {"role": "system", "content": prompt.MEMORY_REFRESH_INSTRUCTIONS}
    assert "Likes plain text." in user["content"]
    assert "context.md:\nNONE" in user["content"]
    assert "Talked about the Atlas database." in user["content"]


def test_it_asks_the_personas_own_model_in_its_window_with_a_short_reply_limit(asked):
    _one_recap()
    memory_refresh.propose("samantha")
    assert asked[0]["num_ctx"] == 8192 and asked[0]["max_tokens"] == 500


# -- propose(): parsing the reply ---------------------------------------------------


def test_parses_both_proposed_sections(asked):
    _one_recap()
    profile_text, context_text = memory_refresh.propose("samantha")
    assert profile_text == "Likes concise replies."
    assert context_text == "Working on the Atlas migration."


def test_no_change_reads_as_none_per_section(asked):
    asked.replies = [
        ModelReply(f"{prompt.MEMORY_PROFILE_MARK}\n{prompt.MEMORY_NO_CHANGE}\n{prompt.MEMORY_CONTEXT_MARK}\n"
                   "New context.", 5)
    ]
    _one_recap()
    assert memory_refresh.propose("samantha") == (None, "New context.")


def test_a_proposal_identical_to_the_current_file_reads_as_no_change(asked, profiles):
    """Regression: `gemma2:9b`, live, echoed a file's content back verbatim instead of using the
    NO_CHANGE sentinel even when nothing actually changed -- caught structurally by comparing the
    proposal to what is already on disk, not by trying to make the model say NO_CHANGE more often."""
    (profiles / "samantha" / "context.md").write_text("Working on the Atlas migration.\n")
    asked.replies = [
        ModelReply(f"{prompt.MEMORY_PROFILE_MARK}\n{prompt.MEMORY_NO_CHANGE}\n{prompt.MEMORY_CONTEXT_MARK}\n"
                   "Working on the Atlas migration.", 5)
    ]
    _one_recap()
    assert memory_refresh.propose("samantha") == (None, None)


def test_a_reply_missing_the_two_section_shape_is_treated_as_nothing_to_propose(asked):
    asked.replies = [ModelReply("just some prose, no markers", 5)]
    _one_recap()
    assert memory_refresh.propose("samantha") == (None, None)


def test_sections_in_reversed_order_are_still_both_read(asked):
    """Regression: the instructed order is profile.md then context.md, but a model is not
    guaranteed to follow it -- both sections must still be found by their marker's own position,
    not by assuming which one comes first."""
    asked.replies = [
        ModelReply(f"{prompt.MEMORY_CONTEXT_MARK}\nWorking on Atlas.\n{prompt.MEMORY_PROFILE_MARK}\n"
                   "Likes concise replies.", 5)
    ]
    _one_recap()
    assert memory_refresh.propose("samantha") == ("Likes concise replies.", "Working on Atlas.")


# -- propose(): a model that cannot do this ----------------------------------------


def test_a_reply_limit_error_is_not_asked_again(asked):
    asked.replies = [ReplyLimitError("too small")]
    _one_recap()
    assert memory_refresh.propose("samantha") == (None, None)
    assert "ollama_chat/gemma2:9b" in memory_refresh._CANNOT_REWRITE
    memory_refresh.propose("samantha")
    assert len(asked) == 1  # not asked a second time


def test_an_engine_model_error_is_reported_as_nothing_to_propose(asked):
    asked.replies = [EngineModelError("down")]
    _one_recap()
    assert memory_refresh.propose("samantha") == (None, None)


# -- refresh(): where the proposal lands -------------------------------------------


def test_profile_is_always_staged_even_when_memory_rewrite_is_auto(asked):
    settings_store.set(memory_refresh.SETTING, "auto")
    _one_recap()

    assert memory_refresh.refresh("samantha") is True

    assert memory_write.pending_profile("samantha") == "Likes concise replies."
    assert memory.profile("samantha") is None  # never auto-applied


def test_context_is_staged_by_default_ask_mode(asked):
    _one_recap()
    memory_refresh.refresh("samantha")
    assert memory_write.pending_context("samantha") == "Working on the Atlas migration."
    assert memory.context("samantha") is None


def test_context_is_applied_directly_when_memory_rewrite_is_auto(asked):
    settings_store.set(memory_refresh.SETTING, "auto")
    _one_recap()
    memory_refresh.refresh("samantha")
    assert memory.context("samantha") == "Working on the Atlas migration."
    assert memory_write.pending_context("samantha") is None


def test_refresh_with_nothing_proposed_returns_false_and_changes_nothing(asked):
    assert memory_refresh.refresh("samantha") is False
    assert memory_write.has_pending("samantha") is False


# -- last_outcome(): how a refresh ended, so /memory can say what happened (#108) ----------


def test_an_update_is_recorded_as_updated(asked):
    _one_recap()
    memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.UPDATED


def test_a_model_that_saw_nothing_to_change_is_recorded_as_unchanged(asked):
    _one_recap()
    asked.replies = [ModelReply(f"{prompt.MEMORY_PROFILE_MARK}\n{prompt.MEMORY_NO_CHANGE}\n"
                                f"{prompt.MEMORY_CONTEXT_MARK}\n{prompt.MEMORY_NO_CHANGE}", 5)]
    memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.UNCHANGED


def test_a_failed_model_call_is_recorded_as_failed_not_unchanged(asked):
    _one_recap()
    asked.replies = [EngineModelError("down")]
    memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.FAILED


def test_a_reply_limit_failure_is_recorded_as_failed(asked):
    _one_recap()
    asked.replies = [ReplyLimitError("spent it all thinking")]
    memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.FAILED


def test_no_recaps_yet_is_recorded_as_skipped(asked):
    memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.SKIPPED
    assert asked == []


def test_a_cloud_model_not_approved_for_memory_is_recorded_as_skipped(asked):
    _one_recap()
    memory_refresh.refresh("samantha", model="anthropic/claude-sonnet-5")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.SKIPPED


def test_a_failed_write_is_recorded_as_failed(asked, monkeypatch):
    _one_recap()
    monkeypatch.setattr(memory_write, "stage_profile", lambda handle, text: False)
    memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") == memory_refresh.FAILED


def test_a_new_refresh_clears_the_last_outcome_before_it_runs(asked, monkeypatch):
    """A refresh that raises part-way must not leave the previous run's outcome to be read as its own."""
    _one_recap()
    memory_refresh.refresh("samantha")
    monkeypatch.setattr(memory_refresh, "_ask", lambda handle, model=None: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        memory_refresh.refresh("samantha")
    assert memory_refresh.last_outcome("samantha") is None


# -- refresh_in_background() --------------------------------------------------------


def test_the_background_refresh_passes_the_chosen_model_on(monkeypatch):
    seen: list = []
    monkeypatch.setattr(memory_refresh, "refresh", lambda handle, model=None: seen.append((handle, model)))

    memory_refresh.refresh_in_background("samantha", "anthropic/claude-sonnet-5")
    for thread in threading.enumerate():
        if thread.name.startswith("memory-"):
            thread.join(5)

    assert seen == [("samantha", "anthropic/claude-sonnet-5")]


def test_a_second_refresh_for_the_same_handle_while_one_runs_is_refused(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_refresh(handle, model=None):
        started.set()
        release.wait(2)

    monkeypatch.setattr(memory_refresh, "refresh", slow_refresh)

    assert memory_refresh.refresh_in_background("samantha") is True
    started.wait(2)
    assert memory_refresh.refresh_in_background("samantha") is False
    release.set()
    for thread in threading.enumerate():
        if thread.name.startswith("memory-"):
            thread.join(5)


def test_the_recaps_are_listed_oldest_first_as_the_request_says(asked):
    recap.write("samantha", "20260920T090000-aaaaaaaa", 2, "First talk.")
    recap.write("samantha", "20260924T090000-bbbbbbbb", 2, "Latest talk.")

    memory_refresh.propose("samantha")

    body = asked[0]["messages"][1]["content"]
    assert body.index("First talk.") < body.index("Latest talk.")
