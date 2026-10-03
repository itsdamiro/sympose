"""A grounded note's connections to other notes (docs/decisions/035): who it links to or from, who it
shares a tag or alias with, and who shares its top-level folder — real facts already known from the
vault, never invented and never searched. They ride inside the note's own passage (a `connections` field
on the hit, not a separate passage), so a note and its connections are dropped together when the prompt
does not fit the window (docs/decisions/015); properties passages and the Sympose reference are left
untouched. Read fresh from the same mtime-cached snapshot the tree and the Knowledge Nebula already use
(`vault_snapshot`); the link graph itself (`vault_graph.get_vault_graph`) is rebuilt fresh on every one of
its own callers, so its result is cached here by the snapshot's identity too, or every chat turn would
pay a full manifest rebuild that nothing was asking it to pay before."""

from typing import Any

from sympose import folder_definitions, vault_graph, vault_paths
from sympose.engine import reference
from sympose.engine.grounding_index import _aliases_of
from sympose.vault_manifest_build import _stem, _tags_of
from sympose.vault_snapshot import get_vault_snapshot

MAX_PER_NOTE = 3
MAX_LINKS = 5  # names shown per direction of a note's links (docs/decisions/067); the rest is a count

# `(the snapshot list object, the precomputed maps built from it)` per scope: the snapshot is already
# mtime-cached and returns the very same list until the vault changes, so an identity check is enough to
# know these maps are still current (the same trick `grounding._index_for` uses).
_INDEX_CACHE: dict[tuple[str, ...], tuple[list[dict[str, Any]], dict[str, Any]]] = {}


def _title_of(note: dict[str, Any]) -> str:
    meta = note.get("meta") or {}
    return str(meta.get("title") or meta.get("name") or _stem(note["file_name"]))


def _own_labels(note: dict[str, Any]) -> set[str]:
    """A note's tags and aliases, folded to lower case, as one set of weak-connection labels."""
    meta = note.get("meta") or {}
    return {t.lower() for t in _tags_of(meta)} | {a.lower() for a in _aliases_of(meta)}


def _links(profile: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """`(outgoing, incoming)`, real note to real note only: a link to nothing, or to a note the persona
    cannot see, is already left out of the graph the Knowledge Nebula draws (docs/decisions/034)."""
    graph = vault_graph.get_vault_graph(profile)
    real = {n["id"] for n in graph["nodes"] if n.get("exists", True)}
    out: dict[str, set[str]] = {}
    into: dict[str, set[str]] = {}
    for link in graph["links"]:
        source, target = link["source"], link["target"]
        if source in real and target in real and source != target:
            out.setdefault(source, set()).add(target)
            into.setdefault(target, set()).add(source)
    return out, into


def link_graph(profile: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """`(outgoing, incoming)` links between the persona's notes, by path (docs/decisions/058)."""
    return _links(profile)


def _index_of(profile: dict[str, Any], notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-note titles, folders and own tags/aliases, a shared-tag/alias index, and the link graph
    (`_links`), built once from `notes`."""
    titles: dict[str, str] = {}
    folders: dict[str, str] = {}
    labels: dict[str, set[str]] = {}
    by_folder: dict[str, set[str]] = {}
    by_label: dict[str, set[str]] = {}
    for note in notes:
        path = note["rel_path"].replace("\\", "/")
        titles[path] = _title_of(note)
        folder = folder_definitions.top_folder(path)
        folders[path] = folder
        if folder:
            by_folder.setdefault(folder, set()).add(path)
        own = _own_labels(note)
        if own:
            labels[path] = own
        for label in own:
            by_label.setdefault(label, set()).add(path)
    out, into = _links(profile)
    return {
        "titles": titles, "folders": folders, "labels": labels,
        "by_folder": by_folder, "by_label": by_label, "out": out, "into": into,
    }


def _index(profile: dict[str, Any], mv: str, allowed_dirs: list[str]) -> dict[str, Any]:
    notes = get_vault_snapshot(mv, allowed_dirs)
    key = tuple(sorted(allowed_dirs))
    cached = _INDEX_CACHE.get(key)
    if cached is not None and cached[0] is notes:
        return cached[1]
    index = _index_of(profile, notes)
    _INDEX_CACHE[key] = (notes, index)
    return index


def for_hits(profile: dict[str, Any], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`hits` with a `links` field (docs/decisions/067: the notes it links to and from, always, "none" included) and a
    `connections` field (docs/decisions/030: up to `MAX_PER_NOTE` other notes sharing a tag or alias, or its top-level
    folder, ranked in that order, never one already in `links`) added to each note's own text or title passage.
    A passage of the Sympose reference library or of a note's own properties is returned unchanged: the
    reference is not the user's vault, and a properties passage already rides with the note that carries it.
    A note found through more than one passage (`grounding_index.PASSAGES_PER_NOTE`) carries them on its first
    passage only: said again under each, the lines of two notes with alike titles interleave, and a small model
    has been seen to read one note's links as the other's (and the line would be counted as withheld twice)."""
    sandbox = vault_paths.resolve_sandbox(profile)
    if sandbox is None or not hits:
        return hits
    index = _index(profile, *sandbox)
    titles, folders = index["titles"], index["folders"]
    labels, by_folder, by_label = index["labels"], index["by_folder"], index["by_label"]
    out, into = index["out"], index["into"]

    def linked(path: str) -> dict[str, Any]:
        """`{"to": [...], "from": [...], "more_to": n, "more_from": n}`: both directions, always, even empty."""
        sides = {}
        for side, notes in (("to", out.get(path, set())), ("from", into.get(path, set()))):
            names = sorted(titles.get(other, other) for other in notes)
            sides[side], sides[f"more_{side}"] = names[:MAX_LINKS], max(0, len(names) - MAX_LINKS)
        return sides

    def connected(path: str) -> list[str]:
        seen = {path} | out.get(path, set()) | into.get(path, set())  # links are stated on their own line
        found: list[str] = []

        def add(candidates: set[str]) -> None:
            for other in sorted(candidates - seen):
                if len(found) >= MAX_PER_NOTE:
                    return
                seen.add(other)
                found.append(titles.get(other, other))

        own_labels = labels.get(path, set())
        if len(found) < MAX_PER_NOTE and own_labels:
            add({other for label in own_labels for other in by_label.get(label, set())})
        if len(found) < MAX_PER_NOTE:
            add(by_folder.get(folders.get(path, ""), set()))
        return found

    by_path: dict[str, dict[str, Any]] = {}
    updated = []
    for hit in hits:
        path = hit.get("rel_path")
        if hit.get("source") == reference.SOURCE or hit.get("kind") == "properties" or path not in titles:
            updated.append(hit)
            continue
        if path in by_path:  # a note's lines are stated once, with its first (best) passage, not under every passage
            updated.append(hit)
            continue
        by_path[path] = found = {"links": linked(path), "connections": connected(path)}
        updated.append({**hit, "links": found["links"], **({"connections": found["connections"]} if found["connections"] else {})})
    return updated
