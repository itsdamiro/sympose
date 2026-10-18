"""The call of a turn that has a video to watch (docs/decisions/089): Google's request first, the captions when Google
will not take the video, and the rest of the turn's calls on whichever worked. Both ways of calling are fakes."""

import pytest

from sympose.engine import captions, gemini_direct, watch_call
from sympose.engine import model as model_mod
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.prompt_text import CAPTIONS, WATCHING

ADDRESS = "https://www.youtube.com/watch?v=8jPQjjsBbIc"


@pytest.fixture
def ways(monkeypatch):
    captions.forget()
    monkeypatch.setattr(captions, "GAP_SECONDS", 0)
    monkeypatch.setattr(captions, "_download", lambda video, ipv6=False: ([(0.0, "Hello there.")], "en", False))

    class Ways:
        direct: list = []
        plain: list = []
        refuse = True

    Ways.direct, Ways.plain = [], []

    def direct(messages, **kwargs):
        Ways.direct.append(messages)
        if Ways.refuse:
            raise gemini_direct.WatchUnavailable("Gemini refused the request (400: no)")
        return ModelReply("Watched.", 1)

    def plain(messages, **kwargs):
        Ways.plain.append(messages)
        return ModelReply("Read.", 1)

    monkeypatch.setattr(gemini_direct, "call", direct)
    monkeypatch.setattr(model_mod, "call_model", plain)
    yield Ways
    captions.forget()


def messages():
    return [{"role": "system", "content": f"sys {WATCHING}"}, {"role": "user", "content": f"Context.\n\n{WATCHING}\n\nUser's message: hi"}]


def test_google_is_asked_first_and_its_answer_is_used(ways):
    ways.refuse = False

    reply = watch_call.for_links((ADDRESS,))(messages(), model="gemini/x")

    assert reply.text == "Watched." and ways.plain == []


def test_when_google_refuses_the_captions_replace_the_line_about_the_video_in_the_user_message_only(ways):
    reply = watch_call.for_links((ADDRESS,))(messages(), model="gemini/x")

    assert reply.text == "Read."
    system, user = ways.plain[0]
    assert system["content"] == f"sys {WATCHING}"  # the system prompt is the persona's, left alone
    assert WATCHING not in user["content"] and CAPTIONS in user["content"] and "[0:00] Hello there." in user["content"]


def test_the_rest_of_the_turn_stays_on_the_captions_without_asking_google_again_or_fetching_again(ways):
    call = watch_call.for_links((ADDRESS,))

    call(messages(), model="gemini/x")
    call(messages(), model="gemini/x")  # a tool round: the same messages and what came after

    assert len(ways.direct) == 1 and len(ways.plain) == 2
    assert all(CAPTIONS in m[1]["content"] for m in ways.plain)


def test_no_captions_either_names_both_troubles(ways, monkeypatch):
    def none(video, ipv6=False):
        raise captions._Absent("the video has no captions")

    monkeypatch.setattr(captions, "_download", none)

    with pytest.raises(EngineModelError, match="would not take the video.*the video has no captions"):
        watch_call.for_links((ADDRESS,))(messages(), model="gemini/x")
    assert ways.plain == []


def test_any_other_error_from_google_goes_up_untouched(ways):
    def quota(messages, **kwargs):
        raise EngineModelError("Gemini refused the request (429: quota)")

    gemini_direct.call = quota  # restored by the fixture's monkeypatch

    with pytest.raises(EngineModelError, match="429"):
        watch_call.for_links((ADDRESS,))(messages(), model="gemini/x")
    assert ways.plain == []
