"""Folders and notes the user has hidden from the web app's view (docs/decisions/037). A display
preference only: the persona and the terminal chat never read this, so what is hidden here is still
read, grounded on and (where `cloud_share` allows) sent as before. The list lives in the settings
file, per vault. The rules (a folder hides what is under it, neighbour ids, ghost nodes, definition
notes) live here and nowhere else; the web app only obeys the marks put on the tree and the search
results, and the graph is filtered here."""

import threading
from typing import Any

from sympose import folder_definitions, settings_store, vault_paths

HIDDEN_SETTING = "hidden_paths"  # {vault path: [vault-relative paths]}
DEFINITIONS_SETTING = "show_definition_notes"  # off by default (docs/decisions/037)
USER, DEFINITION = "user", "definition"
_MAX_PATH = 1024
_LOCK = threading.Lock()  # hide and unhide read the whole list and write it back: one at a time


def normalize(path: Any) -> str | None:
    """`a/b` from `a\\b/`, or `None` for anything that is not a plain vault-relative path."""
    if not isinstance(path, str) or "\x00" in path:
        return None
    cleaned = path.replace("\\", "/").strip().strip("/")
    if not cleaned or len(cleaned) > _MAX_PATH:
        return None
    return None if any(part in ("", ".", "..") for part in cleaned.split("/")) else cleaned


def _raw() -> dict[str, Any] | None:
    """The stored setting as it is: `{}` when there is none, `None` when it is something else (a damaged
    or hand-edited value that must not be overwritten with what is left of it)."""
    value = settings_store.get(HIDDEN_SETTING)
    if value is None:
        return {}
    return value if isinstance(value, dict) else None


def _list_of(raw: dict[str, Any], vault: str) -> list[str]:
    paths = raw.get(vault)
    return [p for p in paths if isinstance(p, str)] if isinstance(paths, list) else []


def hidden_paths(vault: str | None = None) -> list[str]:
    """What is hidden in `vault` (the active one when not given), in a stable order."""
    vault = vault or vault_paths.get_master_vault()
    return sorted(_list_of(_raw() or {}, vault or ""), key=lambda p: (p.lower(), p))


def _change(vault: str, edit: Any) -> bool:
    """Writes `edit(this vault's list)` back, leaving every other vault's entry exactly as it is.
    `False` when the setting is damaged (left alone) or the settings file could not be written."""
    with _LOCK:
        raw = _raw()
        if raw is None:
            return False
        paths = sorted(set(edit(_list_of(raw, vault))))
        if paths:
            raw[vault] = paths
        else:
            raw.pop(vault, None)
        return settings_store.set(HIDDEN_SETTING, raw) if raw else settings_store.remove(HIDDEN_SETTING)


def hide(vault: str, path: str) -> bool:
    """Idempotent. `False` when the settings file could not be written."""
    return _change(vault, lambda paths: [*paths, path])


def unhide(vault: str, path: str) -> bool:
    """Idempotent. `False` when the settings file could not be written."""
    return _change(vault, lambda paths: [p for p in paths if p != path])


def rename_folder(vault: str, old: str, new: str) -> bool:
    """A folder was renamed (docs/decisions/073): the folder, and what is hidden inside it, stay hidden under the new
    path. Only this vault's list changes. `False` when the setting is damaged or the file could not be written."""
    prefix = old + "/"
    return _change(vault, lambda paths: [new + p[len(old):] if p == old or p.startswith(prefix) else p for p in paths])


def definitions_shown() -> bool:
    return settings_store.flag(DEFINITIONS_SETTING, False)


def set_definitions_shown(show: bool) -> bool:
    return settings_store.remove(DEFINITIONS_SETTING) if not show else settings_store.set(DEFINITIONS_SETTING, True)


def is_hidden(rel_path: str, hidden: list[str]) -> bool:
    """`rel_path` is a hidden path or sits under one."""
    return any(rel_path == p or rel_path.startswith(p + "/") for p in hidden)


def _is_definition_note(rel_path: str) -> bool:
    folder = folder_definitions.top_folder(rel_path)
    return folder_definitions.can_have_definition(folder) and rel_path == folder_definitions.definition_path(folder)


def for_tree(tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Marks the tree in place: `hidden: "user"` on what the user hid (and so on what is under a folder they hid),
    `hidden: "definition"` on a folder definition note while they are not shown; drops the ids of
    user-hidden notes from every note's neighbours. Nothing is removed: the client resolves links against
    the whole tree and lists only what is not marked."""
    hidden, show_definitions = hidden_paths(), definitions_shown()
    gone: set[str] = set()
    notes: list[dict[str, Any]] = []

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            by_user = is_hidden(node["path"], hidden)  # a folder's children sit under its path, so they are too
            if by_user:
                node["hidden"] = USER
            elif node["type"] == "note" and not show_definitions and _is_definition_note(node["path"]):
                node["hidden"] = DEFINITION
            if node["type"] == "note":
                notes.append(node)
                if by_user:
                    gone.add(node["path"])
            walk(node.get("children") or [])

    walk(tree)
    if gone:
        for note in notes:
            if note.get("links"):
                note["links"] = [link for link in note["links"] if link not in gone]
    return tree


def for_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """The graph without user-hidden notes, the lines to them, and any ghost left with no line; sizes
    (`val`) count only the lines that remain."""
    hidden = hidden_paths()
    gone = {n["id"] for n in graph["nodes"] if n.get("exists", True) and is_hidden(n["id"], hidden)} if hidden else set()
    if not gone:
        return graph
    links = [ln for ln in graph["links"] if ln["source"] not in gone and ln["target"] not in gone]
    linked_before = {end for ln in graph["links"] for end in (ln["source"], ln["target"])}
    degree: dict[str, int] = {}
    for ln in links:
        degree[ln["source"]] = degree.get(ln["source"], 0) + 1
        degree[ln["target"]] = degree.get(ln["target"], 0) + 1
    nodes = [
        {**n, "val": degree.get(n["id"], 0) + 1}
        for n in graph["nodes"]
        if n["id"] not in gone and (n.get("exists", True) or n["id"] not in linked_before or n["id"] in degree)
    ]
    return {"nodes": nodes, "links": links}


def for_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Search hits, in place: `hidden: true` on a hit inside something the user hid, with `hidden_by`, the
    entries of the list that hide it (the note's own, or the folders above it), for Unhide to remove.
    Still returned."""
    hidden = hidden_paths()
    if hidden:
        for hit in results:
            by = [p for p in hidden if is_hidden(hit["rel_path"], [p])]
            if by:
                hit["hidden"] = True
                hit["hidden_by"] = by
    return results
