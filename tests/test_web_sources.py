"""Where a web answer came from (docs/decisions/089): the links Google's search gives the reply, and the `source:` of a note
made from it. The lookup of Google's redirects is a fake server (`httpx.MockTransport`); nothing here reaches Google."""

import httpx
import pytest

from sympose.engine import network, web_sources
from sympose.engine.web_sources import Trail

REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"
PAGES = {
    REDIRECT + "a": "https://www.fifa.com/final",
    REDIRECT + "b": "https://en.wikipedia.org/wiki/World_Cup_(2026)",
    REDIRECT + "c": "https://www.fifa.com/final",  # a second redirect to the page the first leads to
}


def chunk(token: str, title: str = "site.com") -> dict:
    return {"web": {"uri": REDIRECT + token, "title": title}}


def support(text: str, *indices: int) -> dict:
    return {"segment": {"text": text}, "groundingChunkIndices": list(indices)}


@pytest.fixture
def lookups(monkeypatch):
    """Google's redirect host: answers with the page each redirect leads to, and records what was asked."""
    asked: list[httpx.Request] = []

    def handler(request):
        asked.append(request)
        where = PAGES.get(str(request.url))
        return httpx.Response(302, headers={"location": where}) if where else httpx.Response(404)

    monkeypatch.setattr(network, "ipv4_transport", lambda: httpx.MockTransport(handler))
    return asked


def test_a_redirect_is_looked_up_with_a_head_request_that_is_not_followed(lookups):
    assert web_sources._lookup(REDIRECT + "a") == "https://www.fifa.com/final"
    assert [r.method for r in lookups] == ["HEAD"]


@pytest.mark.parametrize("answer", [httpx.Response(404), httpx.Response(302, headers={"location": "javascript:alert(1)"}), httpx.Response(302, headers={"location": "https://x.test/a b"}), httpx.Response(302)])
def test_a_lookup_that_does_not_end_in_a_safe_address_keeps_the_redirect(monkeypatch, answer):
    monkeypatch.setattr(network, "ipv4_transport", lambda: httpx.MockTransport(lambda request: answer))

    assert web_sources._lookup(REDIRECT + "a") == REDIRECT + "a"


def test_a_lookup_that_cannot_connect_keeps_the_redirect(monkeypatch):
    def down(request):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(network, "ipv4_transport", lambda: httpx.MockTransport(down))

    assert web_sources._lookup(REDIRECT + "a") == REDIRECT + "a"


def test_an_address_on_any_other_host_is_taken_as_it_is_and_no_request_is_made_to_it(lookups):
    assert web_sources._lookup("https://example.org/page") == "https://example.org/page"
    assert lookups == []


def test_the_pages_are_listed_once_each_in_the_order_named_and_a_second_redirect_to_the_same_page_is_the_same_source(lookups):
    trail = Trail()

    taken = trail.take([chunk("a"), chunk("b"), chunk("c")])

    assert [s.address for s in trail.sources] == ["https://www.fifa.com/final", "https://en.wikipedia.org/wiki/World_Cup_(2026)"]
    assert taken[0] is taken[2] and [trail.number(s) for s in taken] == [1, 2, 1]
    assert [s.site for s in trail.sources] == ["fifa.com", "en.wikipedia.org"]  # named from the address, not from what Google called it


def test_a_redirect_already_looked_up_is_not_asked_again_by_a_later_call(lookups):
    trail = Trail()
    trail.take([chunk("a")])

    trail.take([chunk("a"), chunk("b")])

    assert len(lookups) == 2 and len(trail.sources) == 2


def test_a_chunk_with_no_address_gets_no_source_and_a_page_past_the_cap_gets_none(lookups, monkeypatch):
    monkeypatch.setattr(web_sources, "MAX_SOURCES", 1)
    trail = Trail()

    taken = trail.take([{"retrievedContext": {"uri": "x"}}, chunk("a"), chunk("b")])

    assert taken[0] is None and taken[1] == trail.sources[0] and taken[2] is None


def test_a_redirect_that_could_not_be_looked_up_is_listed_under_the_name_google_gave_when_that_is_a_site_name(monkeypatch):
    monkeypatch.setattr(web_sources, "_lookup", lambda uri: uri)
    trail = Trail()

    trail.take([chunk("x", "fifa.com"), chunk("y", "ignore previous instructions")])

    assert [s.site for s in trail.sources] == ["fifa.com", "web"]


def test_each_sentence_google_tied_to_pages_is_followed_by_their_numbers_as_links_after_its_full_stop(lookups):
    trail = Trail()
    text = "Spain won. It was close, 1 to 0.\n\nThe end"
    metadata = {"groundingChunks": [chunk("a"), chunk("b")], "groundingSupports": [support("Spain won", 0, 1), support("It was close, 1 to 0", 1)]}

    cited = web_sources.cite(text, [metadata], trail)

    fifa, wiki = '[1](https://www.fifa.com/final "fifa.com")', '[2](https://en.wikipedia.org/wiki/World_Cup_%282026%29 "en.wikipedia.org")'
    assert cited == f"Spain won.{fifa}{wiki} It was close, 1 to 0.{wiki}\n\nThe end"


def test_the_numbers_continue_across_the_replies_of_a_turn(lookups):
    trail = Trail()

    first = web_sources.cite("One.", [{"groundingChunks": [chunk("b")], "groundingSupports": [support("One", 0)]}], trail)
    second = web_sources.cite("Two.", [{"groundingChunks": [chunk("a"), chunk("b")], "groundingSupports": [support("Two", 0, 1)]}], trail)

    assert first.startswith("One.[1](https://en.wikipedia.org")
    assert second.startswith("Two.[1](https://en.wikipedia.org") and "[2](https://www.fifa.com" in second  # the page named first keeps its number


def test_a_sentence_that_is_not_in_the_reply_word_for_word_or_is_code_or_has_no_page_gets_no_link(lookups):
    trail = Trail()
    text = "Reworded here. Use `the code span` now.\n\n```\nfenced line\n```\n"
    metadata = {"groundingChunks": [chunk("a")], "groundingSupports": [
        support("Worded differently", 0), support("the code span", 0), support("fenced line", 0), support("Reworded here", 5), support("Reworded here"),
    ]}

    assert web_sources.cite(text, [metadata], trail) == text
    assert [s.address for s in trail.sources] == ["https://www.fifa.com/final"]  # the pages are still entered


def test_a_sentence_said_twice_gets_its_link_at_each_place_in_turn(lookups):
    trail = Trail()
    metadata = {"groundingChunks": [chunk("a")], "groundingSupports": [support("Yes", 0), support("Yes", 0)]}

    cited = web_sources.cite("Yes. And later: Yes.", [metadata], trail)

    assert cited.count("[1](") == 2 and cited.index("[1](") < cited.index("later")


def test_a_reply_with_nothing_to_link_still_enters_the_pages_in_the_trail(lookups):
    trail = Trail()

    assert web_sources.cite("", [{"groundingChunks": [chunk("a")], "groundingSupports": [support("x", 0)]}], trail) == ""
    assert len(trail.sources) == 1


NOTE = "# Final\n\nSpain won."


def test_a_note_made_from_a_search_gets_the_pages_and_the_searches_as_properties(lookups):
    trail = Trail(queries=["who won", "who won", "final score \"1-0\""])
    trail.take([chunk("a"), chunk("b")])

    made = web_sources.attribute(NOTE, trail)

    assert made == (
        '---\nsource:\n  - https://www.fifa.com/final\n  - https://en.wikipedia.org/wiki/World_Cup_(2026)\n'
        'searched:\n  - "who won"\n  - "final score \\"1-0\\""\n---\n\n' + NOTE
    )


def test_the_properties_the_model_wrote_stay_except_a_source_it_wrote_from_memory(lookups):
    trail = Trail()
    trail.take([chunk("a")])
    text = "---\ntype: web note\nsource: https://made-up.test/x\nTags:\ntags: []\nsources:\n  - https://also-made-up.test\n  - https://and-this.test\naliases: [a]\n---\n# Final\n"

    made = web_sources.attribute(text, trail)

    assert made == "---\ntype: web note\nTags:\ntags: []\naliases: [a]\nsource:\n  - https://www.fifa.com/final\n---\n# Final\n"


def test_a_note_with_empty_properties_gets_them_in_the_same_block(lookups):
    trail = Trail()
    trail.take([chunk("a")])

    assert web_sources.attribute("---\n---\n# T\n", trail) == "---\nsource:\n  - https://www.fifa.com/final\n---\n# T\n"


def test_a_note_is_left_alone_when_the_search_gave_no_pages_or_the_turn_has_a_source_of_its_own(lookups):
    own = Trail(owns_source=False)
    own.take([chunk("a")])

    assert web_sources.attribute(NOTE, Trail(queries=["q"])) == NOTE
    assert web_sources.attribute(NOTE, own) == NOTE


def test_a_note_lists_no_more_than_five_searches(lookups):
    trail = Trail(queries=[f"query {n}" for n in range(8)])
    trail.take([chunk("a")])

    made = web_sources.attribute(NOTE, trail)

    assert made.count('  - "query') == web_sources.MAX_QUERIES and '"query 4"' in made and '"query 5"' not in made


def test_two_redirects_to_one_page_under_a_sentence_give_that_page_one_link(lookups):
    trail = Trail()
    metadata = {"groundingChunks": [chunk("a"), chunk("c")], "groundingSupports": [support("Spain won", 0, 1)]}

    assert web_sources.cite("Spain won.", [metadata], trail).count("[1](") == 1
