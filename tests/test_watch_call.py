"""The call of a turn that has a video to watch (docs/decisions/089): Google's request first, the captions when Google
will not take the video, and the rest of the turn's calls on whichever worked. Both ways of calling are fakes."""

import pytest

from sympose.engine import captions, gemini_direct, watch_call
from sympose.engine import model as model_mod
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.prompt_text import CAPTIONS, READING_PAGES, READING_SEARCH, WATCHING

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


def test_when_google_refuses_the_lines_about_pages_and_search_go_with_the_video(ways):
    pages = f"Context.\n\n{WATCHING}\n\n{READING_PAGES}\n\n{READING_SEARCH}\n\nUser's message: hi"
    watch_call.for_links((ADDRESS,), ("urlContext",))([{"role": "user", "content": pages}], model="m")

    (sent,) = ways.plain
    assert READING_PAGES not in sent[-1]["content"] and READING_SEARCH not in sent[-1]["content"] and WATCHING not in sent[-1]["content"]
    assert sent[-1]["content"].endswith("User's message: hi") and "\n\n\n" not in sent[-1]["content"]


def test_google_is_given_the_tools_with_the_links(ways, monkeypatch):
    ways.refuse = False
    seen = {}
    monkeypatch.setattr(gemini_direct, "call", lambda messages, **kwargs: seen.update(kwargs) or ModelReply("ok", 1))

    watch_call.for_links((), ("googleSearch", "urlContext"))(messages(), model="m")

    assert seen["links"] == () and seen["server_tools"] == ("googleSearch", "urlContext")


def test_a_page_google_could_not_open_is_said_under_the_answer_and_not_under_a_round_of_tool_calls(ways, monkeypatch):
    from sympose.engine.model_tools import ToolCall

    replies = iter([ModelReply("Let me look.", 1, tool_calls=(ToolCall("c", "search_notes", "{}"),)), ModelReply("It says X.", 1), ModelReply("Again.", 1)])

    def direct(messages, unopened=None, **kwargs):
        unopened.append("https://example.com/")  # Google reports it on each round
        return next(replies)

    monkeypatch.setattr(gemini_direct, "call", direct)
    call = watch_call.for_links((), ("urlContext",))

    first = call(messages(), model="m")
    second = call(messages(), model="m")

    assert first.text == "Let me look." and first.tool_calls
    assert second.text == "It says X.\n\n" + watch_call.PAGE_NOT_OPENED.format(pages="https://example.com/", that="that page")
    # A page opened on every call leaves the answer alone.
    monkeypatch.setattr(gemini_direct, "call", lambda messages, **kwargs: ModelReply("Fine.", 1))
    assert watch_call.for_links((), ("urlContext",))(messages(), model="m").text == "Fine."


PAGE = "https://docs.python.org/3/library/pathlib.html"


def _call_that_reports(monkeypatch, opened=(), unopened=()):
    def direct(messages, **kwargs):
        kwargs["opened"].extend(opened)
        kwargs["unopened"].extend(unopened)
        return ModelReply("It says X.", 1)

    monkeypatch.setattr(gemini_direct, "call", direct)


def test_a_page_google_never_reported_is_said_not_to_have_been_read(monkeypatch):
    _call_that_reports(monkeypatch)  # the model answered from memory: no opening, no failure

    reply = watch_call.for_links((), ("urlContext",), (PAGE,))(messages(), model="m")

    assert reply.text == "It says X.\n\n" + watch_call.PAGE_NOT_READ.format(pages=PAGE, that="that page")


def test_a_page_google_opened_or_a_carried_one_is_left_alone(monkeypatch):
    _call_that_reports(monkeypatch, opened=[PAGE])
    assert watch_call.for_links((), ("urlContext",), (PAGE,))(messages(), model="m").text == "It says X."
    # The same address as Google writes it back: another scheme, `www.`, a closing slash, a fragment.
    _call_that_reports(monkeypatch, opened=["http://www.docs.python.org/3/library/pathlib.html/#x"])
    assert watch_call.for_links((), ("urlContext",), (PAGE,))(messages(), model="m").text == "It says X."
    # A follow-up carries the link from an earlier message and may answer from the conversation: not asked, not said.
    _call_that_reports(monkeypatch)
    assert watch_call.for_links((), ("urlContext",), ())(messages(), model="m").text == "It says X."


def test_a_redirected_page_clears_one_missing_page_and_a_second_unread_page_is_still_said(monkeypatch):
    other = "https://example.org/b"
    _call_that_reports(monkeypatch, opened=["https://elsewhere.test/moved"])

    one = watch_call.for_links((), ("urlContext",), (PAGE,))(messages(), model="m")
    two = watch_call.for_links((), ("urlContext",), (PAGE, other))(messages(), model="m")

    assert one.text == "It says X."
    assert two.text == "It says X.\n\n" + watch_call.PAGE_NOT_READ.format(pages=other, that="that page")


def test_a_page_that_could_not_open_is_not_also_said_not_to_have_been_read(monkeypatch):
    _call_that_reports(monkeypatch, unopened=[PAGE])

    reply = watch_call.for_links((), ("urlContext",), (PAGE,))(messages(), model="m")

    assert reply.text == "It says X.\n\n" + watch_call.PAGE_NOT_OPENED.format(pages=PAGE, that="that page")


def test_the_page_named_as_unread_is_the_one_google_did_not_report_even_when_it_writes_the_other_back_differently(monkeypatch):
    other = "https://example.org/b"
    _call_that_reports(monkeypatch, opened=["http://www.docs.python.org/3/library/pathlib.html/"])

    reply = watch_call.for_links((), ("urlContext",), (other, PAGE))(messages(), model="m")

    assert reply.text == "It says X.\n\n" + watch_call.PAGE_NOT_READ.format(pages=other, that="that page")
    _call_that_reports(monkeypatch, opened=["https://example.org/b/"])  # a closing slash alone
    assert watch_call.for_links((), ("urlContext",), (PAGE, other))(messages(), model="m").text == "It says X.\n\n" + watch_call.PAGE_NOT_READ.format(pages=PAGE, that="that page")
