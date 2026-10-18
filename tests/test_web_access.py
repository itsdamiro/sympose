"""Which turns watch a video (docs/decisions/089): the knob, the model, the link, the user's approval of `web`."""

import pytest

from sympose import settings_store
from sympose.engine import sharing, web_access

CLOUD = "gemini/gemini-flash-latest"
ID = "8jPQjjsBbIc"
ADDRESS = f"https://www.youtube.com/watch?v={ID}"


@pytest.mark.parametrize(
    "text",
    [
        f"https://www.youtube.com/watch?v={ID}",
        f"see https://youtu.be/{ID}?si=abc please",
        f"https://m.youtube.com/watch?feature=share&v={ID}&t=90s",
        f"https://www.youtube.com/shorts/{ID}",
        f"http://youtube.com/live/{ID}",
        f"https://www.youtube.com/embed/{ID}",
    ],
)
def test_each_way_of_linking_a_video_gives_one_watch_address(text):
    assert web_access.links_in(text) == (ADDRESS,)


@pytest.mark.parametrize(
    "text",
    ["", "no link here", "https://example.com/watch?v=8jPQjjsBbIc", f"https://www.youtube.com/watch?v={ID[:10]}", "https://www.youtube.com/@channel"],
)
def test_text_without_a_video_link_gives_none(text):
    assert web_access.links_in(text) == ()


def test_a_video_linked_twice_is_one_and_the_order_written_is_kept():
    second = "aircAruvnKk"
    text = f"https://youtu.be/{ID} and https://youtu.be/{second} and again https://youtu.be/{ID}"
    assert web_access.links_in(text) == (ADDRESS, f"https://www.youtube.com/watch?v={second}")


def test_no_more_than_the_cap_is_watched_for_one_message():
    text = " ".join(f"https://youtu.be/{'abcdefghij'}{n}" for n in range(web_access.MAX_LINKS + 2))
    assert len(web_access.links_in(text)) == web_access.MAX_LINKS


def test_the_default_is_asked_and_off_is_the_users_to_choose():
    assert web_access.mode() == web_access.ASKED
    settings_store.set(web_access.SETTING, "nonsense")
    assert web_access.mode() == web_access.ASKED
    settings_store.set(web_access.SETTING, web_access.OFF)
    assert web_access.mode() == web_access.OFF


def test_a_link_is_watched_only_when_the_user_has_allowed_web():
    assert web_access.resolve(CLOUD, ADDRESS, []) == web_access.Watch(withheld=True)
    sharing.set_approved(sharing.WEB, True)
    assert web_access.resolve(CLOUD, ADDRESS, []) == web_access.Watch((ADDRESS,))


def test_a_message_with_no_link_watches_nothing_and_withholds_nothing():
    sharing.set_approved(sharing.WEB, True)
    assert web_access.resolve(CLOUD, "hello", []) == web_access.Watch()
    sharing.set_approved(sharing.WEB, False)
    assert web_access.resolve(CLOUD, "hello", []) == web_access.Watch()


def test_off_does_nothing_for_any_model():
    sharing.set_approved(sharing.WEB, True)
    settings_store.set(web_access.SETTING, web_access.OFF)
    for model in (CLOUD, "ollama_chat/gemma2:9b", "openai/gpt-4o-mini"):
        assert web_access.resolve(model, ADDRESS, []) == web_access.Watch()


def test_a_model_that_cannot_watch_is_given_the_captions_and_a_local_one_needs_no_approval():
    assert web_access.resolve("ollama_chat/gemma2:9b", ADDRESS, []) == web_access.Watch((ADDRESS,), route=web_access.CAPTIONS)
    assert web_access.resolve("openai/gpt-4o-mini", ADDRESS, []) == web_access.Watch(withheld=True)
    sharing.set_approved(sharing.WEB, True)
    assert web_access.resolve("openai/gpt-4o-mini", ADDRESS, []) == web_access.Watch((ADDRESS,), route=web_access.CAPTIONS)
    assert web_access.resolve(CLOUD, ADDRESS, []) == web_access.Watch((ADDRESS,), route=web_access.WATCH)


def test_a_follow_up_keeps_the_latest_video_of_the_conversation_in_front_of_the_model():
    sharing.set_approved(sharing.WEB, True)
    other = "aircAruvnKk"
    history = [
        {"role": "user", "content": f"watch https://youtu.be/{ID}"}, {"role": "assistant", "content": "ok"},
        {"role": "user", "content": f"and this https://youtu.be/{other}"}, {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "thanks"}, {"role": "assistant", "content": "welcome"},
    ]
    assert web_access.resolve(CLOUD, "what did he say about X?", history) == web_access.Watch((f"https://www.youtube.com/watch?v={other}",))
    assert web_access.resolve(CLOUD, f"now https://youtu.be/{ID}", history) == web_access.Watch((ADDRESS,))


def test_a_carried_link_is_never_watched_unallowed_and_never_nags():
    history = [{"role": "user", "content": ADDRESS}, {"role": "assistant", "content": "ok"}]
    assert web_access.resolve(CLOUD, "what did he say?", history) == web_access.Watch()


PAGE = "https://example.com/post"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"read {PAGE}.", (PAGE,)),
        (f"({PAGE})", (PAGE,)),
        (f"[the post]({PAGE}?a=1)", (f"{PAGE}?a=1",)),
        ("https://en.wikipedia.org/wiki/Foo_(bar)", ("https://en.wikipedia.org/wiki/Foo_(bar)",)),
        (f"{PAGE}, then https://b.org/y! and {PAGE}", (PAGE, "https://b.org/y")),
        ("https://www.youtube.com/@channel https://youtu.be/8jPQjjsBbIc https://m.youtube.com/watch?v=8jPQjjsBbIc", ()),
        ("http://localhost:3000/a https://127.0.0.1/a https://192.168.1.4/a https://nas.local/a https://intranet/a https://[::1]/a", ()),
        ("no link, just example.com and obsidian://open?vault=x", ()),
    ],
)
def test_a_page_link_is_the_address_without_the_sentence_around_it_and_a_video_or_a_private_address_is_not_one(text, expected):
    assert web_access.pages_in(text) == expected


def test_no_more_than_the_cap_of_pages_is_read_for_one_message():
    text = " ".join(f"https://example.com/{n}" for n in range(web_access.MAX_LINKS + 2))
    assert len(web_access.pages_in(text)) == web_access.MAX_LINKS


def test_auto_is_a_choice_and_anything_else_is_asked():
    settings_store.set(web_access.SETTING, web_access.AUTO)
    assert web_access.mode() == web_access.AUTO
    settings_store.set(web_access.SETTING, "always")
    assert web_access.mode() == web_access.ASKED


def test_a_page_is_read_only_when_allowed_and_only_by_a_model_with_google_s_tools():
    assert web_access.resolve(CLOUD, f"read {PAGE}", []) == web_access.Watch(withheld=True)
    sharing.set_approved(sharing.WEB, True)
    found = web_access.resolve(CLOUD, f"read {PAGE}", [])
    assert found == web_access.Watch(pages=(PAGE,), asked=(PAGE,)) and found.server_tools == (web_access.PAGE_TOOL,) and found.direct
    # A model without those tools has nothing to read it with, and a local one is not asked.
    assert web_access.resolve("openai/gpt-4o-mini", f"read {PAGE}", []) == web_access.Watch()
    assert web_access.resolve("ollama_chat/gemma2:9b", f"read {PAGE}", []) == web_access.Watch()


def test_a_video_and_a_page_in_one_message_are_both_attached():
    sharing.set_approved(sharing.WEB, True)
    found = web_access.resolve(CLOUD, f"{ADDRESS} and {PAGE}", [])
    assert found.links == (ADDRESS,) and found.pages == (PAGE,) and found.direct
    assert found.asked == (PAGE,)  # the message's own page; a carried one is not asked


def test_a_follow_up_keeps_the_latest_page_in_front_of_the_model_and_a_carried_page_never_nags():
    history = [{"role": "user", "content": f"read {PAGE}"}, {"role": "assistant", "content": "ok"}]
    assert web_access.resolve(CLOUD, "what did it say about X?", history) == web_access.Watch()
    sharing.set_approved(sharing.WEB, True)
    assert web_access.resolve(CLOUD, "what did it say about X?", history) == web_access.Watch(pages=(PAGE,))
    assert web_access.resolve(CLOUD, "what did it say about X?", history).asked == ()


def test_auto_lets_the_model_search_on_every_turn_but_only_when_the_user_has_allowed_the_web():
    settings_store.set(web_access.SETTING, web_access.AUTO)
    assert web_access.resolve(CLOUD, "what is new in python?", []) == web_access.Watch()  # nothing withheld, nothing searched
    sharing.set_approved(sharing.WEB, True)
    found = web_access.resolve(CLOUD, "what is new in python?", [])
    assert found.search and found.outside and found.direct
    assert found.server_tools == (web_access.SEARCH_TOOL, web_access.PAGE_TOOL)
    assert web_access.resolve("openai/gpt-4o-mini", "what is new in python?", []) == web_access.Watch()  # no tools of Google's
    settings_store.set(web_access.SETTING, web_access.ASKED)
    assert web_access.resolve(CLOUD, "what is new in python?", []) == web_access.Watch()
    settings_store.set(web_access.SETTING, web_access.OFF)
    assert web_access.resolve(CLOUD, "what is new in python?", []) == web_access.Watch()


def _conversation(link: str, follow_ups: int) -> list[dict[str, str]]:
    history = [{"role": "user", "content": f"read {link}"}, {"role": "assistant", "content": "ok"}]
    for n in range(follow_ups):
        history += [{"role": "user", "content": f"and point {n}?"}, {"role": "assistant", "content": "it says"}]
    return history


def test_a_link_is_carried_into_five_follow_ups_and_not_the_sixth_whether_it_is_a_video_or_a_page():
    sharing.set_approved(sharing.WEB, True)
    for link, carried in ((ADDRESS, web_access.Watch((ADDRESS,))), (PAGE, web_access.Watch(pages=(PAGE,)))):
        assert web_access.CARRY_TURNS == 5
        assert web_access.resolve(CLOUD, "the fifth?", _conversation(link, 4)) == carried  # the fifth follow-up
        assert web_access.resolve(CLOUD, "the sixth?", _conversation(link, 5)) == web_access.Watch()
        assert web_access.resolve(CLOUD, "the tenth?", _conversation(link, 9)) == web_access.Watch()
    # A new link ahead of the cap starts it again, and a message's own link needs no carrying.
    later = [*_conversation(PAGE, 7), {"role": "user", "content": f"now {ADDRESS}"}, {"role": "assistant", "content": "ok"}]
    assert web_access.resolve(CLOUD, "and?", later) == web_access.Watch((ADDRESS,))
    assert web_access.resolve(CLOUD, f"{PAGE} again", _conversation(PAGE, 9)) == web_access.Watch(pages=(PAGE,), asked=(PAGE,))
