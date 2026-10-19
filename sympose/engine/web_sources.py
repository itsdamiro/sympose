"""Where a web answer came from (docs/decisions/089). When Google searches the web for a turn it says which pages the answer
rests on and which sentence of the reply rests on which (`groundingChunks` and `groundingSupports`). This module turns that
into links in the reply, `[1](address)` after the sentence, and into the `source:` property of a note made from the answer.
The addresses are Google's, never the model's to type, so a source cannot be invented.

Google hands each page back as a redirect on its own host, with only the site's name. One `HEAD` request to that host
(it does not open the page) answers with the page's real address, which is what the reply and the note carry: a note's
source must still lead somewhere later. When the lookup fails the redirect stays as it came."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from sympose import markdown_code, note_changes_store
from sympose.engine import network

MAX_SOURCES = 10  # pages one turn lists; a page after these gets no link
MAX_QUERIES = 5
_LOOKUP_SECONDS = 4
_REDIRECT_HOST = "vertexaisearch.cloud.google.com"
_ADDRESS = re.compile(r"https?://[^\s<>\"`\\]+")  # an address that is safe to put in a link and in a property
_SENTENCE_END = ".,;:!?"
_OWNED = re.compile(r"(source|sources|searched)[ \t]*:", re.IGNORECASE)
_FRONT = re.compile(r"---[ \t]*\n(?:(.*?)\n)?---[ \t]*(?:\n|$)", re.DOTALL)


@dataclass(frozen=True)
class Source:
    address: str  # the page, or Google's redirect to it when the lookup failed
    site: str  # the site's name, from the address


@dataclass
class Trail:
    """What the web gave one turn: the searches it ran (`queries`, filled by `gemini_direct.call`) and the pages the answer
    rests on, in the order they were first named, so a number in the reply is a position in `sources`. `owns_source` says
    the turn has no video, page or file of its own, so a note made in it takes its `source:` from here. Google reports the
    pages with the words that rest on them, so a note proposed in a round that ended in a call, before the round of words,
    is proposed before the pages are known: `drafts` lets `settle` give it its source when the turn ends."""

    queries: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    owns_source: bool = True
    drafts: list[tuple[str, str]] = field(default_factory=list)  # the new notes proposed in the turn: (the note's path, the proposal's id)
    _looked_up: dict[str, str] = field(default_factory=dict, repr=False)  # Google's address -> the page's

    def take(self, chunks: list[dict[str, Any]]) -> list[Source | None]:
        """The `Source` of each chunk, in order (`None` for a chunk with no usable address, or past `MAX_SOURCES`), after the
        new ones are looked up, together."""
        uris = [(chunk.get("web") or {}).get("uri") for chunk in chunks]
        titles = [(chunk.get("web") or {}).get("title") for chunk in chunks]
        fresh = list(dict.fromkeys(u for u in uris if isinstance(u, str) and u not in self._looked_up))
        if fresh:
            with ThreadPoolExecutor(max_workers=min(len(fresh), 8)) as pool:
                self._looked_up.update(zip(fresh, pool.map(_lookup, fresh)))
        taken: list[Source | None] = []
        for uri, title in zip(uris, titles):
            address = self._looked_up.get(uri) if isinstance(uri, str) else None
            if not address or not _ADDRESS.fullmatch(address):
                taken.append(None)
                continue
            source = next((s for s in self.sources if s.address == address), None)
            if source is None and len(self.sources) < MAX_SOURCES:
                source = Source(address, _site(address, title))
                self.sources.append(source)
            taken.append(source)
        return taken

    def number(self, source: Source) -> int:
        return self.sources.index(source) + 1


def _lookup(uri: str) -> str:
    """The page `uri` leads to when it is Google's redirect, else `uri` itself; Sympose makes no request to any other host."""
    if urlsplit(uri).hostname != _REDIRECT_HOST:
        return uri
    try:
        with httpx.Client(transport=network.ipv4_transport(), timeout=_LOOKUP_SECONDS, follow_redirects=False) as client:
            where = client.head(uri).headers.get("location", "")
    except (httpx.HTTPError, httpx.InvalidURL):  # a reply with a `Location` httpx cannot read is one of these
        return uri
    return where if _ADDRESS.fullmatch(where) else uri


def _site(address: str, given: Any) -> str:
    host = (urlsplit(address).hostname or "").removeprefix("www.")
    if host and host != _REDIRECT_HOST:
        return host
    return given if isinstance(given, str) and re.fullmatch(r"[\w.-]{1,80}", given) else "web"


def _linkable(address: str) -> str:
    return address.replace("(", "%28").replace(")", "%29")


def cite(text: str, grounding: list[dict[str, Any]], trail: Trail) -> str:
    """`text` with `[n](address "site")` after each sentence Google tied to a page (after the full stop that ends it), where `n` is
    the page's place in `trail`; the pages are entered in `trail` whether or not `text` has anything to link. A sentence
    that cannot be found in `text` word for word (the reply was tidied after Google counted it), or that is code, gets
    no link."""
    inside = markdown_code.in_code(text)
    after: dict[int, list[int]] = {}
    for metadata in grounding:
        sources = trail.take(metadata.get("groundingChunks") or [])
        looked_from: dict[str, int] = {}
        for support in metadata.get("groundingSupports") or []:
            sentence = (support.get("segment") or {}).get("text")
            chosen = [sources[i] for i in support.get("groundingChunkIndices") or [] if isinstance(i, int) and 0 <= i < len(sources) and sources[i]]
            if not sentence or not chosen or not text:
                continue
            at = text.find(sentence, looked_from.get(sentence, 0))
            if at < 0 or inside(at):
                continue
            end = at + len(sentence)
            looked_from[sentence] = end
            if end < len(text) and text[end] in _SENTENCE_END:
                end += 1
            numbers = after.setdefault(end, [])
            numbers.extend(n for n in (trail.number(s) for s in chosen) if n not in numbers)
    for end in sorted(after, reverse=True):
        links = "".join(f'[{n}]({_linkable(trail.sources[n - 1].address)} "{trail.sources[n - 1].site}")' for n in sorted(after[end]))
        text = text[:end] + links + text[end:]
    return text


def attribute(text: str, trail: Trail) -> str:
    """A new note's `text` with its `source:` property replaced by the pages the turn's search gave (and a `searched:` property
    listing the searches), when the turn has no source of its own and the search gave pages; else `text` as it came. A model
    that wrote a `source:` of its own in such a turn wrote it from memory."""
    if not (trail.owns_source and trail.sources):
        return text
    queries = list(dict.fromkeys(q for q in trail.queries if q.strip()))[:MAX_QUERIES]
    block = "source:\n" + "".join(f"  - {s.address}\n" for s in trail.sources)
    if queries:
        block += "searched:\n" + "".join(f"  - {json.dumps(q, ensure_ascii=False)}\n" for q in queries)
    body = text.lstrip("\n")
    found = _FRONT.match(body)
    if not found:
        return f"---\n{block}---\n\n{body}"
    kept: list[str] = []
    skipping = False
    lines = found.group(1).split("\n") if found.group(1) else []
    for line in lines:
        if _OWNED.match(line):
            skipping = True
        elif skipping and (not line.strip() or line[0] in " \t-"):
            continue
        else:
            skipping = False
            kept.append(line)
    properties = "".join(f"{line}\n" for line in kept)
    return f"---\n{properties}{block}---\n{body[found.end():]}"


def settle(handle: str, trail: Trail) -> None:
    """At the turn's end, the new notes it proposed take their `source:` from the pages its search gave (`attribute`, which
    gives the same text again when it was already done)."""
    if not (trail.owns_source and trail.sources):
        return
    for path, proposal_id in trail.drafts:
        def apply(entry: dict[str, Any], proposal_id: str = proposal_id) -> None:
            for proposal in entry["proposals"]:
                if proposal.get("id") == proposal_id and proposal.get("kind") == "create":
                    proposal["text"] = attribute(proposal["text"], trail)

        note_changes_store.update(handle, path, apply)
