"""Notes close in meaning to a note (docs/decisions/066), from the passage vectors search already keeps: no model
call and no store of its own. A note is the average of its passages; the vault's own average note is taken away
from every one, or the common ground every note of a vault shares would put each close to all of them (measured:
the median pair of unrelated notes scored 0.74 before, about 0) and each is scaled to length one again. A
neighbour is kept only above a bar the user chooses as a level, never as a number. These are a guess about
meaning, not a link: they are shown, and told to a model, as "possibly related"."""

import threading
from typing import Any, Sequence

from sympose import settings_store
from sympose.engine import embeddings, grounding, reference, semantic, semantic_refresh, similarity

SETTING = "connections_by_meaning"
AUTO, OFF = "auto", "off"
MODES = (AUTO, OFF)

LEVEL_SETTING = "connections_relevance"
CLOSE, BALANCED, WIDE = "close", "balanced", "wide"
LEVELS = (CLOSE, BALANCED, WIDE)
# The similarity (after the vault's average note is taken away, measured with `nomic-embed-text`) a neighbour
# must reach: close keeps few, nearly all clearly related; balanced is about 85 to 89% right; wide lets looser ones
# in. Another embedding model needs bars of its own (docs/decisions/066).
BARS = {CLOSE: 0.50, BALANCED: 0.40, WIDE: 0.30}
METER_TOP = 0.70  # where the relevance meter reads 100%: about one note in ten has its best neighbour there
FOR_PERSONA, FOR_PANEL = 3, 5

_KEEP = 4  # the note sets kept, one per index (the vault and the persona's sandbox differ)
# `id(passage vectors)` -> (those vectors, the notes made from them); the vectors are held so the id is not reused.
_CACHE: dict[int, tuple[Any, "_Notes"]] = {}
_CACHE_LOCK = threading.Lock()


def mode() -> str:
    """`auto` (the default) or `off`; anything else a hand-edited file holds is `auto`."""
    value = settings_store.get(SETTING)
    return value if value in MODES else AUTO


def level() -> str:
    """`close`, `balanced` (the default) or `wide`; anything else a hand-edited file holds is `balanced`."""
    value = settings_store.get(LEVEL_SETTING)
    return value if value in LEVELS else BALANCED


def percent(score: float, bar: float) -> int:
    """The meter: `bar` reads 0%, `METER_TOP` 100%. A reading of strength, never a probability."""
    return round(100 * min(1.0, max(0.0, (score - bar) / (METER_TOP - bar))))


class _Notes:
    """One centred, unit-length vector per note, in `paths` order (`VectorSet.note_set`)."""

    def __init__(self, passages: list[Any], vectors: similarity.VectorSet) -> None:
        self.position: dict[str, int] = {}
        self.titles: dict[str, str] = {}
        codes = []
        for passage in passages:
            if passage.rel_path not in self.position:
                self.position[passage.rel_path] = len(self.position)
                self.titles[passage.rel_path] = passage.title
            codes.append(self.position[passage.rel_path])
        self.paths = list(self.position)
        self.vectors = vectors.note_set(codes, len(self.paths))

    def scores(self, path: str) -> Sequence[float]:
        return self.vectors.scores(self.vectors.row(self.position[path]))


def _notes_for(profile: dict[str, Any]) -> _Notes | None:
    index = grounding.scope_index(profile)
    vectors = semantic.passage_vectors(index) if index is not None else None
    if vectors is None:
        return None
    with _CACHE_LOCK:  # the notes panel and a chat turn can ask at once
        cached = _CACHE.get(id(vectors))
        if cached is not None and cached[0] is vectors:
            return cached[1]
        notes = _Notes(vectors.passages, vectors.unit_vectors)
        while len(_CACHE) >= _KEEP:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[id(vectors)] = (vectors, notes)
        return notes


def neighbours(
    profile: dict[str, Any], rel_path: str, limit: int, skip: Sequence[str] = ()
) -> list[dict[str, Any]]:
    """Up to `limit` notes close in meaning to `rel_path`, closest first, each `{path, title, score, percent}`,
    none below the chosen level's bar, never the note itself or a path in `skip`. Empty, never an error, when the
    setting is `off`, the embedding model is not usable (`semantic.passage_vectors`) or the note has no vector."""
    if mode() == OFF:
        return []
    notes = _notes_for(profile)
    if notes is None or rel_path not in notes.position:
        return []
    bar = BARS[level()]
    scores = notes.scores(rel_path)
    ranked = sorted(
        (n for n, score in enumerate(scores) if score >= bar and notes.paths[n] != rel_path and notes.paths[n] not in skip),
        key=lambda n: -scores[n],
    )
    return [
        {"path": notes.paths[n], "title": notes.titles[notes.paths[n]], "score": round(float(scores[n]), 3), "percent": percent(scores[n], bar)}
        for n in ranked[:limit]
    ]


def indexing(profile: dict[str, Any]) -> bool:
    """Whether the vectors this reads are being built right now, so an empty answer will fill in on its own
    (a first index of a large vault takes minutes). `False` when the setting is `off`."""
    index = grounding.scope_index(profile) if mode() != OFF else None
    return index is not None and semantic_refresh.building(index, embeddings.model())


def for_hits(profile: dict[str, Any], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`hits` with a `related` field added to each note's own passage: the titles of up to `FOR_PERSONA` notes close
    in meaning, never a note already grounded this turn or already named in the passage's `connections`. A passage
    of the library or of a note's properties, and a note with no neighbour, is returned unchanged; a note found
    through more than one passage is computed once and shared (the line must not be repeated in the prompt or
    counted twice as withheld). It is a separate field from `connections`, so a guess is never told as a link."""
    if mode() == OFF or not hits:
        return hits
    grounded = [h["rel_path"] for h in hits if h.get("rel_path")]
    by_path: dict[str, list[str]] = {}
    updated = []
    for hit in hits:
        path = hit.get("rel_path")
        if not path or hit.get("source") == reference.SOURCE or hit.get("kind") == "properties":
            updated.append(hit)
            continue
        if path not in by_path:
            named = set(hit.get("connections") or [])
            found = neighbours(profile, path, FOR_PERSONA + len(named), skip=grounded)
            by_path[path] = [n["title"] for n in found if n["title"] not in named][:FOR_PERSONA]
        found_titles = by_path[path]
        updated.append({**hit, "related": found_titles} if found_titles else hit)
    return updated


def _forget_for_tests() -> None:
    _CACHE.clear()
