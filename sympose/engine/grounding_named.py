"""A note named in full, or by a property value (docs/decisions/030, "A note named in full").

A short message that names a note ("tell me about Annie", an alias) scores low against it by meaning, and
`auto` searches the user's notes by meaning alone. So when the search attached nothing and the message says
a note's whole title, file name or alias, that note is attached. The names are in the index: no search and no
embedding is involved, and it changes nothing when the search found a note."""

from typing import Any

from sympose.engine import embeddings
from sympose.engine.grounding_index import _WORD, PASSAGES_PER_NOTE, Index, Passage, index_terms
from sympose.engine.semantic_pick import hit

_MAX_NOTES_PER_NAME = 2  # a name that three or more notes carry is a category, not a note
_MIN_LETTERS = 3
# A name whose rarest informative word is in more than this share of the notes is a topic the vault is about
# ("search" in the Obsidian documentation), not a name; only once the vault is big enough for a share to mean
# anything (the reasoning of `_MAX_NOTE_SHARE` in grounding.py).
_MAX_NOTE_SHARE = 0.10
_MIN_NOTES_FOR_SHARE = 10


def _is_name(words: tuple[str, ...], index: Index, address: frozenset[str]) -> bool:
    terms = index_terms(" ".join(words))
    if len("".join(words)) < _MIN_LETTERS or set(terms) <= address:
        return False  # too short, only filler words (no terms), or only the persona's own name (docs/decisions/021)
    rarest = min(index.note_df.get(term, 0) for term in terms)
    return index.note_count < _MIN_NOTES_FOR_SHARE or rarest <= _MAX_NOTE_SHARE * index.note_count


def _said_in(
    table: dict[tuple[str, ...], list[str]], said: tuple[str, ...], index: Index, address: frozenset[str], cap: int
) -> list[str]:
    """The notes of the entries of `table` (words -> notes) that `said` contains whole, in order, whatever the
    case, those of the longest entries first; an entry that more than `cap` notes carry finds none."""
    if not table:
        return []
    longest = max(map(len, table))
    found: dict[tuple[str, ...], list[str]] = {}
    for start in range(len(said)):
        for end in range(start + 1, min(start + longest, len(said)) + 1):
            paths = table.get(said[start:end])
            if paths and len(paths) <= cap and _is_name(said[start:end], index, address):
                found[said[start:end]] = paths
    paths = [path for words in sorted(found, key=len, reverse=True) for path in sorted(found[words])]
    return list(dict.fromkeys(paths))


def rescue(
    index: Index, message: str, hits: list[dict[str, Any]], address: frozenset[str] = frozenset(), max_results: int = 5
) -> list[dict[str, Any]]:
    """`hits` as they are when the search attached anything (or the knob is `keywords`, which stays today's
    search); otherwise the first passages of the notes the message names in full, then the first passage of
    the notes a property value in it names (docs/decisions/030, "Property values as names"), at most
    `max_results` passages."""
    if hits or not index.names or embeddings.mode() == embeddings.KEYWORDS:  # (a note with values has a name too)
        return hits
    said = tuple(_WORD.findall(message.lower()))
    named = _said_in(index.names, said, index, address, _MAX_NOTES_PER_NAME)
    valued = [path for path in _said_in(index.values, said, index, address, max_results) if path not in named]
    if not named and not valued:
        return hits
    by_path: dict[str, list[Passage]] = {path: [] for path in named + valued}
    for passage in index.passages:
        if passage.rel_path in by_path and len(by_path[passage.rel_path]) < PASSAGES_PER_NOTE:
            by_path[passage.rel_path].append(passage)
    found = [(passage, "name") for path in named for passage in by_path[path]] + [(by_path[path][0], "value") for path in valued if by_path[path]]
    return [{**hit(passage, 0.0, via), "index": n} for n, (passage, via) in enumerate(found[:max_results], start=1)]
