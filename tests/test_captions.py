"""The captions of a video (docs/decisions/089, the transcript route): fetched once and kept, spaced, paused after a
block, cut to the room, and each failure said in plain words. The library is never reached; `_download` is a fake."""

import pytest

from sympose.engine import captions

ADDRESS = "https://www.youtube.com/watch?v=8jPQjjsBbIc"
OTHER = "https://www.youtube.com/watch?v=aircAruvnKk"


def snippets(seconds: int, every: int = 5) -> list[tuple[float, str]]:
    return [(float(t), f"word{t}") for t in range(0, seconds, every)]


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    captions.forget()
    monkeypatch.setattr(captions, "GAP_SECONDS", 0)
    yield
    captions.forget()


@pytest.fixture
def downloads(monkeypatch):
    """`downloads.by_id` maps a video to its raw captions, or to an exception to raise; `downloads.asked` records each fetch."""
    class Fake:
        by_id: dict = {"8jPQjjsBbIc": (snippets(100), "en", False)}
        asked: list[str] = []
        ways: list[bool] = []

    Fake.asked = []
    Fake.ways = []

    def download(video, ipv6=False):
        Fake.asked.append(video)
        Fake.ways.append(ipv6)
        found = Fake.by_id[video]
        if isinstance(found, dict):  # {False: what IPv4 gives, True: what IPv6 gives}
            found = found[ipv6]
        if isinstance(found, Exception):
            raise found
        return found

    monkeypatch.setattr(captions, "_download", download)
    return Fake


def test_snippets_become_timed_lines_of_about_twenty_seconds(downloads):
    got, missing = captions.fetch((ADDRESS,), 10_000)

    assert missing == []
    (c,) = got
    assert c.lines[0] == "[0:00] word0 word5 word10 word15"
    assert c.lines[1].startswith("[0:20] word20")
    assert len(c.lines) == 5 and (c.language, c.generated) == ("en", False)
    assert not c.cut


def test_a_snippet_with_no_words_makes_no_line(downloads):
    downloads.by_id["8jPQjjsBbIc"] = ([(0.0, ""), (30.0, "late")], "en", False)

    (c,), _ = captions.fetch((ADDRESS,), 100)

    assert c.lines == ("[0:30] late",)


def test_an_hour_in_is_stamped_with_hours(downloads):
    downloads.by_id["8jPQjjsBbIc"] = ([(3725.0, "late")], "en", True)

    (c,), _ = captions.fetch((ADDRESS,), 100)

    assert c.lines == ("[1:02:05] late",) and c.generated


def test_a_long_video_keeps_its_start_and_says_where_it_stops(downloads):
    downloads.by_id["8jPQjjsBbIc"] = (snippets(6000), "en", False)

    (c,), _ = captions.fetch((ADDRESS,), 100)

    assert c.cut and c.reached < 6000 - captions.LINE_SECONDS and c.lines[0].startswith("[0:00]")
    assert sum(len(line) + 1 for line in c.lines) <= 100 * captions.TOKEN_CHARS
    assert "stop at" in (captions.render([c], []) or "")


def test_the_room_is_shared_between_the_videos_of_a_message(downloads):
    downloads.by_id["aircAruvnKk"] = (snippets(6000), "en", False)
    downloads.by_id["8jPQjjsBbIc"] = (snippets(6000), "en", False)

    first, second = captions.fetch((ADDRESS, OTHER), 200)[0]

    assert sum(len(x) + 1 for x in first.lines) <= 100 * captions.TOKEN_CHARS
    assert sum(len(x) + 1 for x in second.lines) <= 100 * captions.TOKEN_CHARS


def test_a_video_is_fetched_once_and_a_follow_up_uses_what_was_kept(downloads):
    captions.fetch((ADDRESS,), 1000)
    captions.fetch((ADDRESS,), 1000)

    assert downloads.asked == ["8jPQjjsBbIc"]


def test_no_room_at_all_is_said(downloads):
    got, missing = captions.fetch((ADDRESS,), 0)

    assert got == [] and "no room" in missing[0].reason


def test_a_video_without_captions_is_said_and_not_asked_again_for_a_while(downloads):
    downloads.by_id["8jPQjjsBbIc"] = captions._Absent("the video has no captions")

    _, missing = captions.fetch((ADDRESS,), 1000)
    captions.fetch((ADDRESS,), 1000)

    assert [m.reason for m in missing] == ["the video has no captions"]
    assert downloads.asked == ["8jPQjjsBbIc"]


def test_a_failure_is_asked_again_after_it_is_forgotten(downloads, monkeypatch):
    downloads.by_id["8jPQjjsBbIc"] = captions._Absent("the video has no captions")
    captions.fetch((ADDRESS,), 1000)
    monkeypatch.setattr(captions, "FAILED_KEPT_SECONDS", -1)
    downloads.by_id["8jPQjjsBbIc"] = (snippets(30), "en", False)

    got, _ = captions.fetch((ADDRESS,), 1000)

    assert len(got) == 1 and downloads.asked == ["8jPQjjsBbIc", "8jPQjjsBbIc"]


def test_a_block_pauses_every_fetch_and_says_so_in_plain_words(downloads):
    downloads.by_id["8jPQjjsBbIc"] = captions._Blocked()
    downloads.by_id["aircAruvnKk"] = (snippets(30), "en", False)

    _, first = captions.fetch((ADDRESS,), 1000)
    got, second = captions.fetch((OTHER,), 1000)

    assert "not giving captions to this computer" in first[0].reason
    assert got == [] and "not giving captions" in second[0].reason
    assert downloads.asked == ["8jPQjjsBbIc"] * 2  # the two ways of connecting; the second video was not even tried


def test_a_block_over_ipv4_is_tried_again_over_ipv6_and_the_way_that_worked_is_kept(downloads):
    both = {False: captions._Blocked(), True: (snippets(30), "en", False)}
    downloads.by_id["8jPQjjsBbIc"] = both
    downloads.by_id["aircAruvnKk"] = both

    got, missing = captions.fetch((ADDRESS,), 1000)
    captions.fetch((OTHER,), 1000)

    assert len(got) == 1 and missing == []
    assert downloads.ways == [False, True, True]  # the second video went straight to IPv6


def test_once_ipv6_is_the_way_a_block_is_not_tried_a_second_time_over_it(downloads):
    downloads.by_id["8jPQjjsBbIc"] = {False: captions._Blocked(), True: (snippets(30), "en", False)}
    downloads.by_id["aircAruvnKk"] = {False: (snippets(30), "en", False), True: captions._Blocked()}

    captions.fetch((ADDRESS,), 1000)
    _, missing = captions.fetch((OTHER,), 1000)

    assert "not giving captions" in missing[0].reason and downloads.ways == [False, True, True]


def test_a_block_over_both_is_a_block(downloads):
    downloads.by_id["8jPQjjsBbIc"] = {False: captions._Blocked(), True: captions._Blocked()}

    _, missing = captions.fetch((ADDRESS,), 1000)
    captions.fetch((ADDRESS,), 1000)

    assert "not giving captions" in missing[0].reason and downloads.ways == [False, True]


def test_fetches_are_spaced(downloads, monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(captions, "GAP_SECONDS", 5)
    monkeypatch.setattr(captions.time, "sleep", waits.append)
    downloads.by_id["aircAruvnKk"] = (snippets(30), "en", False)

    captions.fetch((ADDRESS, OTHER), 1000)

    assert len(waits) == 2 and 0 < waits[1] <= 5


def test_an_address_that_is_not_a_video_is_said():
    got, missing = captions.fetch(("https://example.com/x",), 1000)

    assert got == [] and missing[0].reason == "that is not a video address"


def test_the_prompt_text_names_where_each_video_is_from_and_each_that_failed(downloads):
    downloads.by_id["aircAruvnKk"] = captions._Absent("the video has no captions")

    got, missing = captions.fetch((ADDRESS, OTHER), 1000)
    text = captions.render(got, missing) or ""

    assert text.startswith(captions.CAPTIONS)
    assert f"Video: {ADDRESS} (captions in en, written by the video's makers)" in text
    assert f"{OTHER}: the video has no captions" in text
    assert captions.render([], []) is None


class FakeTrack:
    def __init__(self, language="en", generated=False):
        self.language_code, self.is_generated = language, generated

    def fetch(self):
        from youtube_transcript_api import FetchedTranscript, FetchedTranscriptSnippet

        items = [FetchedTranscriptSnippet("hello\n  there", 1.0, 2.0), FetchedTranscriptSnippet("again", 4.0, 1.0)]
        return FetchedTranscript(items, "x", "language", self.language_code, self.is_generated)


def library(monkeypatch, listing=None, error=None):
    """A stand-in for the caption library: `.list(video)` gives `listing` or raises `error`."""
    import youtube_transcript_api as lib

    class Api:
        def __init__(self, http_client=None):
            pass

        def list(self, video):
            if error:
                raise error
            return listing

    monkeypatch.setattr(lib, "YouTubeTranscriptApi", Api)


def test_the_english_track_is_taken_and_its_words_are_tidied(monkeypatch):
    class Listing:
        def find_transcript(self, languages):
            return FakeTrack("en", True)

    library(monkeypatch, Listing())

    assert captions._download("8jPQjjsBbIc") == ([(1.0, "hello there"), (4.0, "again")], "en", True)


def test_without_an_english_track_the_first_the_video_has_is_taken(monkeypatch):
    from youtube_transcript_api import NoTranscriptFound

    class Listing:
        def find_transcript(self, languages):
            raise NoTranscriptFound("8jPQjjsBbIc", languages, self)

        def __iter__(self):
            return iter([FakeTrack("de")])

        def __str__(self):
            return "tracks"

    library(monkeypatch, Listing())

    assert captions._download("8jPQjjsBbIc")[1] == "de"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("TranscriptsDisabled", "turned captions off"),
        ("AgeRestricted", "age-restricted"),
        ("VideoUnavailable", "private, removed or not available"),
        ("VideoUnplayable", "private, removed or not available"),
        ("YouTubeRequestFailed", "did not give its captions"),
    ],
)
def test_each_way_the_library_fails_is_said_in_plain_words(monkeypatch, name, expected):
    import youtube_transcript_api as lib

    cls = getattr(lib, name)
    error = cls.__new__(cls)  # the library's own errors need arguments that do not matter here
    library(monkeypatch, error=error)

    with pytest.raises(captions._Absent, match=expected):
        captions._download("8jPQjjsBbIc")


@pytest.mark.parametrize("name", ["IpBlocked", "RequestBlocked"])
def test_a_block_by_youtube_is_its_own_failure(monkeypatch, name):
    import youtube_transcript_api as lib

    cls = getattr(lib, name)
    library(monkeypatch, error=cls.__new__(cls))

    with pytest.raises(captions._Blocked):
        captions._download("8jPQjjsBbIc")


def test_a_connection_that_fails_is_said_and_over_ipv6_it_counts_as_the_block_having_no_way_round(monkeypatch):
    import requests

    library(monkeypatch, error=requests.ConnectionError("down"))

    with pytest.raises(captions._Absent, match="could not be reached"):
        captions._download("8jPQjjsBbIc")
    with pytest.raises(captions._Blocked):
        captions._download("8jPQjjsBbIc", ipv6=True)


def test_the_session_never_waits_forever_and_connects_over_ipv4_unless_allowed(monkeypatch):
    seen = {}
    monkeypatch.setattr(captions.requests.Session, "request", lambda self, *a, **kw: seen.update(kw))
    captions._Session().get("https://example.com")
    assert seen["timeout"] == captions._TIMEOUT

    kwargs: dict = {}
    monkeypatch.setattr(captions.HTTPAdapter, "init_poolmanager", lambda self, *a, **kw: kwargs.update(kw))
    captions._Adapter(False).init_poolmanager(1, 2)
    assert kwargs["source_address"] == ("0.0.0.0", 0)
    kwargs.clear()
    captions._Adapter(True).init_poolmanager(1, 2)  # asked for the system's own way
    assert "source_address" not in kwargs
    monkeypatch.setenv("SYMPOSE_ALLOW_IPV6", "1")
    captions._Adapter(False).init_poolmanager(1, 2)
    assert "source_address" not in kwargs
