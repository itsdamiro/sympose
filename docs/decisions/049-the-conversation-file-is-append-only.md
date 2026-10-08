---
concepts: [Conversation history, Safe file handling]
---

# 049. The conversation file is append-only

Status: Accepted (damiro, 2026-10-01). Closes #109. Amends ADR 006's "read-modify-write the whole file" posture.

## Context

A conversation is one JSONL file: a meta line, then one line per turn (ADR 006). Every turn rewrote the whole file from what `load_session` had understood. The loader skips a line that is damaged, or a turn record without its text, so the next turn's rewrite deleted those lines for good: a silent loss in the owner's conversation history, found in the review of 2026-09-30. The rewrite also costs more with every turn.

## Decision

- **A turn is appended as one line; nothing already in the file is rewritten.** Before the append, if the file does not end with a line break (a write was cut short), one is added, so a torn line cannot run into the new record. The loader already skips a torn line.
- **The first turn of a session opened on purpose** (`start_session`, with no title yet) appends a second meta line carrying the title. The loader lets a later meta line win, so the file is never rewritten to name it.
- **`updated_at` and `turns_count` are not kept up to date in the file.** `load_session` works them out from the turns (the last turn's time and the number of turns read), so they cannot drift and need no rewrite. The values written at creation stay in the file and are ignored once there are turns.
- **A file that exists but yielded nothing readable** is appended to (a new meta line and the turn), no longer replaced by a session that starts again; what was in it stays.
- A new session's file is created by the same append, meta line first.

## Consequences

Nothing in a conversation file is ever deleted by the app. A file may hold lines the loader skips (kept, never shown). A session that was cut mid-write loses at most the turn being written, as before. Only `load_session` reads these files, so nothing else depends on the stored `updated_at` or `turns_count`.

## Alternatives rejected

- **Keep the raw lines and write them all back.** Still rewrites the whole file every turn, and the skipped lines have to be carried around.
- **Rewrite only the meta line in place.** The file is variable-length lines; an in-place change means rewriting the rest anyway.
