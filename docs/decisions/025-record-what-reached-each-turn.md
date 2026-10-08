---
type: decision
status: accepted
date: 2026-09-25
projects: [sympose]
concepts: [Conversation history, Cloud privacy]
amends: [6]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/observability, topic/privacy]
---

# 025 — Record which notes and recaps reached each turn

> **Summary.** Each turn in the session log records what the model was actually sent: the path and heading of every note and the ids of the recaps, never the passage text. Earlier the notes could not be recomputed after the vault and retriever changed, so a wrong answer could not be diagnosed. The log grows by a few short lines per turn.

> **Status: Accepted.** Built. Amends ADR 006 (the shape of a turn in the session log) and reverses one rejection in ADR 016 ("storing the display string in the session record"). Nothing here depends on a model, so there are no model figures.

## Context

The session log records what the user said and what she replied, but not what she was given to reply from. ADR 016 rejected storing the grounded notes because they "are recomputable from the vault". In the conversation diagnosed for ADR 024 they were not: the vault had changed since, the retriever's rules have changed since, and the recaps in front of her depended on which earlier sessions had been written up that day. The diagnosis had to be a replay against today's vault, which shows what would happen now, not what did. A wrong answer ("my notes don't mention…") could not be told apart as a bad note, a bad recap or a bad reply.

## Decision

Each turn record in the session log gains a `sent` object, written from what the model was actually sent (after the window was fitted, so a passage or recap that was left out is not in it):

- `notes`: one entry per passage, `{"path", "heading", "source"}`, where `source` is `vault` (the user's own notes) or `sympose` (the Sympose library, ADR 019). The path and heading only, never the passage text: the note is still in the vault, and the log does not become a second copy of it.
- `recaps`: the ids of the sessions whose recaps were shown, newest first. The id is the recap's file name, so the recap can be opened; the text is not copied (a recap may be edited or regenerated later, and what it said then is what the session's own turns already reflect).
- `searched`: the query a follow-up was rewritten into when that is what grounded the reply (ADR 017), otherwise `null`. (When the notes were searched by meaning, each note also says how it was found, `via`, ADR 027.)
- `history_dropped`: how many earlier turns did not fit the window (ADR 015).

A turn record written before this lacks the key, and nothing that reads a session depends on it, as with `ttft_ms` and `model` (ADR 013). **Nothing reads it back into a prompt**: the history sent to the model and the transcript given to the recap writer are still built from `user` and `assistant` alone, so a stored path can never reach the model or a recap as if the user had said it.

## Consequences

- A wrong answer can now be diagnosed from the log alone: the notes and recaps she had, and whether the window pushed anything out. Retrieval changes can be judged against real turns without replaying them.
- The log grows by a few short lines per turn. It still lives only in the persona's own folder, which is gitignored (ADR 001); paths of the user's notes are now in it, beside the messages that already are.
- ADR 016's other point stands: the header line is for display and is still not stored.

## Not built yet

Recording the notes of a turn that failed before its reply (a turn is written only once it has a reply, so a failed call leaves no record, as before).

**Built (2026-09-28), #26: a command that reads `sent` back, and a note's similarity.** `/grounded` (ADR 016 has the CLI-side detail); a dashboard view stays open. A note's `notes` entry now also gains `similarity`, the cosine similarity `by_meaning`/`clear_winner` (ADR 027) computed for it, but only when `via` is `embedding` — a keyword hit's own score is a different, incomparable unit, and a name/value rescue hit's is a fixed placeholder, not a measurement, so neither gets the key at all rather than a misleading number. `TurnResult` gains a `sent` field, set to the exact same object `session.append_turn` is given, so a caller (the CLI's `/grounded`, later a web view) reads back precisely what was persisted instead of rebuilding a second, potentially-drifting version of it from `grounding`/`searched`/etc. separately.

## Note: a note can be listed twice in one turn

A turn's `notes` list has one entry per passage sent, so a long section of a note that was split into two passages (ADR 014) appears twice with the same path and heading. Checked on real turns (12 turns in which it happened, searched again, read-only): all 11 repeated sections were two different passages, not a duplicate. The reply header already shows each note once.


## Update: whether the follow-up rewrite was asked (issue #75, item 4)

**Context.** The follow-up rewrite (ADR 017) is a second model call before the reply. It runs when the first search finds nothing and the chat has earlier turns, and when every hit rests on a single matched word (ADR 021). CLAUDE.md treats round trips as a dial, not an absolute, but nobody knows what share of real turns pay the extra call, so the dial cannot be set from evidence. `searched` does not answer it: it holds the rewritten query only when the rewrite is what grounded the reply, so a rewrite that judged the message had no topic, agreed with the message as it was, or found nothing leaves `searched` empty, though the call was made.

**Decision.** The `sent` object gains `rewrite`, a boolean: `true` when the rewrite step was put to the model for this turn, `false` when it was not needed or is switched off (`grounding_followups`). It is a yes or no and holds no text. It is written on every turn from now on, so a record without the key was written before this and means "unknown", not "no". `followup.ground` returns it beside the passages and the query.

**Known imprecision.** The step counts as asked when it was handed to the rewriter, and the rewriter makes no call in two cases: the model already used its whole reply limit on an earlier rewrite (it is not asked again until the program restarts), and the rewrite prompt would not fit the window. Both are rare and both would show as `true` with no round trip, so a count read from the log is an upper bound on the extra calls.

**How it is read.** Nothing reads it inside the program. To measure, count the turn records in a persona's sessions with `sent.rewrite` true against those with the key present, after about a week of use. The figure feeds the decision about the frugality dial; it changes no behaviour.

**Alternatives rejected.** Counting with a log line: the session record is where every other per-turn fact lives (`searched`, `history_dropped`, how a note was found), and a log line has to be matched back to a turn. Recording the outcome of the rewrite (no topic, unchanged, found nothing) instead of a boolean: it says more, but the question is only how often the call is paid, and the outcome can be worked out for the turns of interest from `searched` and `notes`. Reporting the call exactly by having the rewriter say whether it called the model: it changes the injected `rewriter` signature and every test double for two rare cases.
