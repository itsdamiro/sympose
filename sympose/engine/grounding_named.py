"""A note named in full, or by a property value (docs/decisions/030, "A note named in full").

A short message that names a note ("tell me about Annie", an alias) scores low against it by meaning, and
`auto` searches the user's notes by meaning alone. So when the search attached nothing and the message says
a note's whole title, file name or alias, that note is attached. The names are in the index: no search and no
embedding is involved. When the search did find notes it changes nothing, except that a note the message names in
full and whose title reads the same as a found note's (a twin: "Workspace" and "Workspaces") is added after them
(docs/decisions/068)."""

from typing import Any

from sympose.engine import embeddings
from sympose.engine.grounding_index import Index, index_terms
from sympose.engine.semantic_pick import hit

_MAX_NOTES_PER_NAME = 2  # a name that three or more notes carry is a category, not a note
_MIN_LETTERS = 3
# A one-word name is weak evidence on its own — an ordinary word ("Layout", "Work") can be a note's whole
# title and still turn up in an unrelated message. It is kept only when the message's other informative
# words are (almost) all accounted for by some name too — either this is most of what the message says, or
# every other word it says is itself another note's name (docs/decisions/030, #6). A multi-word name is
# specific enough that this guard does not apply to it.
_MAX_UNEXPLAINED_WORDS = 1
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


def _matches(
    table: dict[tuple[str, ...], list[str]], said: tuple[str, ...], index: Index, address: frozenset[str], cap: int
) -> dict[tuple[str, ...], list[str]]:
    """The entries of `table` (words -> notes) that `said` contains whole, in order, whatever the case; an
    entry that more than `cap` notes carry finds none. Unfiltered by how much of `said` they explain — a
    name and a value are both checked before that is judged, since either can explain the other's leftover
    words (#6)."""
    if not table:
        return {}
    longest = max(map(len, table))
    found: dict[tuple[str, ...], list[str]] = {}
    for start in range(len(said)):
        for end in range(start + 1, min(start + longest, len(said)) + 1):
            paths = table.get(said[start:end])
            if paths and len(paths) <= cap and _is_name(said[start:end], index, address):
                found[said[start:end]] = paths
    return found


def _ordered_paths(matches: dict[tuple[str, ...], list[str]], unexplained: int) -> list[str]:
    """`matches`, longest entry first, dropping a one-word entry when the message has more than
    `_MAX_UNEXPLAINED_WORDS` informative words that no entry (name or value, of any length) accounts for —
    the rest of a longer, unrelated message (#6)."""
    kept = {words: paths for words, paths in matches.items() if len(words) > 1 or unexplained <= _MAX_UNEXPLAINED_WORDS}
    paths = [path for words in sorted(kept, key=len, reverse=True) for path in sorted(kept[words])]
    return list(dict.fromkeys(paths))


def rescue(
    index: Index, message: str, hits: list[dict[str, Any]], address: frozenset[str] = frozenset(), max_results: int = 5
) -> list[dict[str, Any]]:
    """`hits` as they are when the search attached anything (or the knob is `keywords`, which stays today's
    search), plus the twins of its notes that the message names in full (docs/decisions/068), after them;
    otherwise the first passages of the notes the message names in full, then the first passage of
    the notes a property value in it names (docs/decisions/030, "Property values as names"), at most
    `max_results` passages."""
    if not index.names or embeddings.mode() == embeddings.KEYWORDS:  # (a note with values has a name too)
        return hits
    said = tuple(index_terms(message))
    name_matches = _matches(index.names, said, index, address, _MAX_NOTES_PER_NAME)
    value_matches = _matches(index.values, said, index, address, max_results)
    covered = {word for words in (*name_matches, *value_matches) for word in words}
    unexplained = len(set(said) - covered)
    named = _ordered_paths(name_matches, unexplained)
    valued = [path for path in _ordered_paths(value_matches, unexplained) if path not in named]
    if hits:  # the search found notes: only a missed note named in full and titled like one it found (a twin) joins them
        found_paths = {h["rel_path"] for h in hits}
        found_titles = {frozenset(index_terms(h["title"])) for h in hits}
        twins = [
            index.passages_by_path[p][0] for p in named
            if p not in found_paths and index.passages_by_path.get(p)
            and frozenset(index_terms(index.passages_by_path[p][0].title)) in found_titles
        ]
        merged = hits + [hit(passage, 0.0, "name") for passage in twins]
        return [{**h, "index": n} for n, h in enumerate(merged[:max_results], start=1)] if twins else hits
    if not named and not valued:
        return hits
    by_path = {path: index.passages_by_path.get(path, []) for path in named + valued}
    found = [(passage, "name") for path in named for passage in by_path[path]] + [(by_path[path][0], "value") for path in valued if by_path[path]]
    return [{**hit(passage, 0.0, via), "index": n} for n, (passage, via) in enumerate(found[:max_results], start=1)]
