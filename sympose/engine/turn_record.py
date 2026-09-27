"""What reached the model besides the messages, as the session log keeps it (docs/decisions/025)."""

from typing import Any


def sent_record(
    grounding: list[dict[str, Any]],
    recaps: list[dict[str, Any]],
    searched: str | None,
    dropped: int,
    rewrite: bool,
    cloud: tuple[list[str], list[str]] | None = None,
) -> dict[str, Any]:
    """What reached the model besides the messages, for the session record
    (docs/decisions/025): where each note came from, never its text. `cloud`, for a model that is
    not local, is the categories sent and the categories held back (docs/decisions/031). `rewrite` is
    whether the follow-up rewrite, an extra model call, was asked this turn (docs/decisions/025)."""
    return {
        "notes": [
            {
                "path": hit["rel_path"],
                "heading": hit.get("heading", ""),
                "source": hit.get("source", "vault"),
                **({"via": hit["via"]} if "via" in hit else {}),  # how it was found, when the knob is on (ADR 027)
                # A similarity score means something only for a hit found by meaning, where it is a
                # cosine similarity, 0 to 1; a keyword hit's own "score" is a different, incomparable
                # unit, and a name/value rescue hit's is a fixed 0.0, not a measurement (#26).
                **({"similarity": hit["score"]} if hit.get("via") == "embedding" else {}),
            }
            for hit in grounding
        ],
        "recaps": [r["session"] for r in recaps],
        "searched": searched,
        "history_dropped": dropped,
        "rewrite": rewrite,
        **({"cloud": cloud[0], "withheld": cloud[1]} if cloud else {}),
    }
