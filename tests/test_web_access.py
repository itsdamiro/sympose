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
