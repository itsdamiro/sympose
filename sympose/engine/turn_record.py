"""What reached the model besides the messages, as the session log keeps it (docs/decisions/025)."""

from typing import Any


def sent_record(
    grounding: list[dict[str, Any]],
    recaps: list[dict[str, Any]],
    searched: str | None,
    dropped: int,
    rewrite: bool,
    cloud: tuple[list[str], list[str]] | None = None,
    mode: str | None = None,
    lookups: list[dict[str, Any]] | None = None,
    memory: list[str] | None = None,
    chats: list[dict[str, Any]] | None = None,
    chats_mode: str | None = None,
    attached: int = 0,
) -> dict[str, Any]:
    """What reached the model besides the messages, for the session record
    (docs/decisions/025): where each note came from, never its text. `cloud`, for a model that is
    not local, is the categories sent and the categories held back (docs/decisions/031). `rewrite` is
    whether the follow-up rewrite, an extra model call, was asked this turn (docs/decisions/025). `mode`
    is the vault-lookup mode that ran (`ask` or `auto`), left out unless the user chose `ask`
    (docs/decisions/040). `lookups` is what the persona looked up or remembered, one entry per tool
    call, a count and never text (docs/decisions/040 and 041) — present whenever `mode` is, or whenever
    a `remember` tool call or marker happened even though `mode` wasn't (`remember` runs independent of
    `vault_lookup`'s own setting). `memory` is which of the persona's own memory files reached this turn
    (docs/decisions/041) — any of `"profile"`, `"context"`, `"decisions"` — never their text; empty when
    the persona has no memory yet or none of it was allowed to reach this model. `chats` is the earlier
    conversations' exchanges that reached the model (docs/decisions/056), by session id and message number
    and how they were found, never their text; left out when none did. `chats_mode` is the `past_chats` mode that ran (`ask`, or `auto` when
    the model cannot call tools), left out unless the user chose `ask`; the tool calls are in `lookups`."""
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
        **({"mode": mode} if mode else {}),
        **({"lookups": lookups or []} if mode or lookups or chats_mode == "ask" else {}),
        "memory": memory or [],
        **({"chats": [{"session": c["session"], "turn": c["turn"], "how": c.get("how", "auto")} for c in chats]} if chats else {}),
        **({"chats_mode": chats_mode} if chats_mode else {}),
        # How many passages of the open note the user attached (docs/decisions/076): a count, never their words.
        **({"attached": attached} if attached else {}),
    }
