"""
Search route handler logic for the web API — split out of
`server_handlers.py` the same way the bin's routes are, to keep each
handler module to one concern (project's 200-LOC-per-file guideline).
"""

from typing import Any

from sympose import vault_hidden, vault_search
from sympose.engine import related
from sympose.server_handlers import require_profile


def search_vault(query: str, persona: str | None) -> dict[str, Any]:
    profile = require_profile(persona)
    return {
        "query": query,
        "results": vault_hidden.for_results(vault_search.search_structured(profile, query)),
    }


def related_notes(path: str, persona: str | None) -> dict[str, Any]:
    """The notes close in meaning to `path` for the notes panel's footer (docs/decisions/066). `enabled` is
    `False` only when the user turned `connections_by_meaning` off, so the panel hides the section; a note with no
    neighbour, or no embedding model to ask, is `enabled` with an empty list. `indexing` is true while the first
    index is still being built, so the panel asks again."""
    profile = require_profile(persona)
    if related.mode() == related.OFF:
        return {"path": path, "enabled": False, "indexing": False, "related": []}
    found = related.neighbours(profile, path, related.FOR_PANEL)
    rows = [{"rel_path": n["path"], "title": n["title"], "percent": n["percent"]} for n in found]
    return {"path": path, "enabled": True, "indexing": related.indexing(profile), "related": vault_hidden.for_results(rows)}
