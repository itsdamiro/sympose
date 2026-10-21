"""The jobs that call no chat model (docs/decisions/091). `health` files `sympose vault --health` as a new-note draft;
`refresh` rebuilds the search-by-meaning index (the embedder, not the chat model, so it does nothing when that knob is
`keywords` or the embedder is a cloud one). Each returns a short line for the job's record."""

from datetime import date
from typing import Any

from sympose import note_changes, vault_health, vault_health_report, vault_paths
from sympose.engine import semantic_refresh

FOLDER = "Jobs"


class NothingToDo(Exception):
    """The job could not make its result for a reason the user can act on; the message says it."""


def _folder(profile: dict[str, Any]) -> str:
    """`Jobs` in the first folder of the persona's scope, where a job's own notes are drafted."""
    folder = vault_paths.folder_in_scope(profile, FOLDER)
    if folder is None:
        raise NothingToDo("The persona has no vault to look at.")
    return folder


def health(profile: dict[str, Any], today: date) -> str:
    scanned = vault_health.scan(profile)
    if scanned is None:
        raise NothingToDo("The persona has no vault to look at.")
    scope, results = scanned
    name = f"Vault health {today.isoformat()}"
    report = "\n".join(vault_health_report.render(scope, results))
    text = f"---\ntype: report\ndate: {today.isoformat()}\n---\n\n# {name}\n\n```text\n{report}\n```\n"
    try:
        note_changes.propose_create(profile["handle"], note_changes.new_note_path(), text, say="The vault health report, from a scheduled run.", title=name, folder=_folder(profile))
    except note_changes.CannotAnchor as e:
        raise NothingToDo(str(e)) from e
    return f"Drafted {name}."


def refresh(profile: dict[str, Any]) -> str:
    return "Rebuilt the search index." if semantic_refresh.refresh(profile["handle"]) else "Nothing to rebuild with search by meaning off."
