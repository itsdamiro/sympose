"""Files shared with a Slack message, fetched for the turn (docs/decisions/093, "files attached in Slack"). Slack's file host
is a fake transport here; what is checked is what is sent to it, what is refused before anything is sent, and what the user is told."""

import httpx
import pytest

from sympose import slack_files
from sympose.engine import media
from sympose.slack_events import SlackFile

URL = "https://files.slack.com/files-pri/T1-F1/download/notes.pdf"
PDF = b"%PDF-1.4 a small pdf"


def _fetch(files, handler, token="xoxb-token"):
    return slack_files.fetch(tuple(files), token, httpx.MockTransport(handler))


def _serves(data=PDF, **more):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=data, headers={"content-type": "application/pdf"}, **more)

    handler.seen = seen
    return handler


def test_a_file_is_downloaded_with_the_bot_token_and_becomes_a_media_file():
    handler = _serves()
    (made,) = _fetch([SlackFile("notes.pdf", len(PDF), URL)], handler)
    assert (made.name, made.mime, made.kind, made.data) == ("notes.pdf", "application/pdf", media.PDF, PDF)
    assert [(str(r.url), r.headers["authorization"]) for r in handler.seen] == [(URL, "Bearer xoxb-token")]


def test_several_files_come_back_in_order():
    handler = _serves()
    files = [SlackFile("a.pdf", 10, URL), SlackFile("b.png", 10, URL.replace("notes.pdf", "b.png"))]
    assert [f.name for f in _fetch(files, handler)] == ["a.pdf", "b.png"]
    assert len(handler.seen) == 2


def test_a_name_used_twice_is_numbered_and_the_marker_uses_the_new_name():
    made = _fetch([SlackFile("a.pdf", 10, URL), SlackFile("a.pdf", 10, URL)], _serves())
    assert [f.name for f in made] == ["a.pdf", "a (2).pdf"]
    assert slack_files.with_markers("read", made) == "read\n[attached: a.pdf] [attached: a (2).pdf]"


def test_markers_with_no_words_are_only_the_markers_and_with_no_files_only_the_words():
    made = _fetch([SlackFile("a.pdf", 10, URL)], _serves())
    assert slack_files.with_markers("", made) == "[attached: a.pdf]"
    assert slack_files.with_markers("hello", ()) == "hello"


def test_too_many_files_are_refused_before_any_download():
    handler = _serves()
    with pytest.raises(media.MediaRefused, match=f"At most {media.MAX_FILES} files"):
        _fetch([SlackFile(f"{i}.pdf", 1, URL) for i in range(media.MAX_FILES + 1)], handler)
    assert handler.seen == []


def test_a_type_sympose_cannot_read_is_refused_before_any_download():
    handler = _serves()
    with pytest.raises(media.MediaRefused, match="cannot attach notes.docx"):
        _fetch([SlackFile("a.pdf", 1, URL), SlackFile("notes.docx", 1, URL)], handler)
    assert handler.seen == []


def test_files_that_slack_says_are_too_large_together_are_refused_before_any_download():
    handler = _serves()
    half = media.MAX_BYTES // 2 + 1
    with pytest.raises(media.MediaRefused, match="too large to send together"):
        _fetch([SlackFile("a.pdf", half, URL), SlackFile("b.pdf", half, URL)], handler)
    assert handler.seen == []


def test_a_file_that_turns_out_larger_than_slack_said_is_refused_while_it_downloads(monkeypatch):
    monkeypatch.setattr(media, "MAX_BYTES", 10)
    with pytest.raises(media.MediaRefused, match="notes.pdf is too large to send"):
        _fetch([SlackFile("notes.pdf", 1, URL)], _serves(b"x" * 11))


def test_the_limit_is_for_all_the_files_of_the_message_not_each(monkeypatch):
    monkeypatch.setattr(media, "MAX_BYTES", 15)
    with pytest.raises(media.MediaRefused, match="b.pdf is too large"):
        _fetch([SlackFile("a.pdf", 1, URL), SlackFile("b.pdf", 1, URL)], _serves(b"x" * 10))


@pytest.mark.parametrize("url", [
    "https://evil.example.com/files-pri/T1-F1/notes.pdf",
    "https://files.slack.com.evil.example.com/notes.pdf",
    "http://files.slack.com/files-pri/T1-F1/notes.pdf",
    "https://evil.example.com/https://files.slack.com/notes.pdf",
    "https://[files.slack.com/notes.pdf",
])
def test_the_token_is_never_sent_anywhere_but_slacks_file_host(url):
    handler = _serves()
    with pytest.raises(media.MediaRefused, match="files:read"):
        _fetch([SlackFile("notes.pdf", 1, url)], handler)
    assert handler.seen == []


def test_a_login_page_means_the_app_cannot_read_files():
    def handler(request):
        return httpx.Response(200, content=b"<html>sign in</html>", headers={"content-type": "text/html; charset=utf-8"})

    with pytest.raises(media.MediaRefused, match="files:read permission.*reinstall"):
        _fetch([SlackFile("notes.pdf", 1, URL)], handler)


def test_a_redirect_is_not_followed_and_means_no_permission():
    asked = []

    def handler(request):
        asked.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example.com/login"})

    with pytest.raises(media.MediaRefused, match="files:read"):
        _fetch([SlackFile("notes.pdf", 1, URL)], handler)
    assert asked == [URL]


@pytest.mark.parametrize("status", [401, 403])
def test_a_refusal_by_slack_means_no_permission(status):
    with pytest.raises(media.MediaRefused, match="files:read"):
        _fetch([SlackFile("notes.pdf", 1, URL)], lambda request: httpx.Response(status))


def test_another_failure_says_to_send_it_again_not_to_change_permissions():
    with pytest.raises(media.MediaRefused, match="Send the file again") as e:
        _fetch([SlackFile("notes.pdf", 1, URL)], lambda request: httpx.Response(500))
    assert "files:read" not in str(e.value)


def test_a_connection_that_fails_says_to_send_it_again():
    def handler(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(media.MediaRefused, match="Send the file again"):
        _fetch([SlackFile("notes.pdf", 1, URL)], handler)


def test_an_empty_file_is_refused():
    with pytest.raises(media.MediaRefused, match="notes.pdf is empty"):
        _fetch([SlackFile("notes.pdf", 0, URL)], _serves(b""))


def test_the_token_is_not_in_a_refusal():
    with pytest.raises(media.MediaRefused) as e:
        _fetch([SlackFile("notes.pdf", 1, URL)], lambda request: httpx.Response(403), token="xoxb-secret")
    assert "xoxb-secret" not in str(e.value)


@pytest.mark.parametrize("url", ["https://files.slack.com:abc/notes.pdf", "https://files.slack.com/no\ttab"])
def test_an_address_httpx_cannot_use_is_a_refusal_not_an_error(url):
    with pytest.raises(media.MediaRefused, match="Send the file again"):
        _fetch([SlackFile("notes.pdf", 1, url)], _serves())


def test_a_file_with_no_address_is_not_blamed_on_the_permission():
    handler = _serves()
    with pytest.raises(media.MediaRefused, match="another workspace") as e:
        _fetch([SlackFile("notes.pdf", 1, "")], handler)
    assert "files:read" not in str(e.value) and handler.seen == []
