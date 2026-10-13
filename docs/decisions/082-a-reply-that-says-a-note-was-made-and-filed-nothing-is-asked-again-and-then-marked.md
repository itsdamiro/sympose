---
type: decision
status: accepted
date: 2026-10-12
projects: [sympose]
concepts: [Persona edits, Grounding]
amends: [72, 77]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/small-models]
---

# 082 — A reply that says a note was made when nothing was filed is asked again once, and then marked

> **Summary.** A model that can call tools sometimes writes "I've drafted it for you" and never calls `propose_note` or `propose_edit`, so the user is told about a draft that does not exist. The engine now reads that claim from the reply and compares it with what the turn did. A turn with tools asks the model once more, privately, to file the note or to say it did not; a reply that still says it, or one from a model without tools, is followed by one line: "(Nothing was filed with this message.)".

> **Status: Accepted (damiro, 2026-10-12).**

## Context

ADR 077 left this open: a model that says it has drafted a note and files none (3 of 12 on `gemma4:e4b`), caught only by the strict drafting cases, not by the engine. It is a grounding failure in the plain sense of the founding rule: a claim about the vault (that a draft is waiting) with nothing behind it. It is a different thing from the model saying it cannot write notes, which is the tool-support probe timing out under load and is still open.

Measured on 2026-10-12 on `gemma4:e4b` (the two drafting cases of `tests/live_skill_cases.py`, tools offered, nothing else running): 5 of 8 runs filed a note before the change, and the three that did not were "I've drafted it for you! This note is ready in the Recipes folder" (twice) and "I can draft a new note…" (once, a promise and not a claim). The sentences of the tests are from those runs.

## Decision

1. `sympose/engine/unfiled.py` reads a reply for a claim that a note or a change was made: first-person past or perfect with a verb that means a proposal on its own ("drafted", "put together"), or with a verb that needs the thing named in the same sentence ("added … the note"), or "is now added". A promise ("I'll draft it", "I can draft one"), a refusal and a statement about notes already in the vault are not claims.
2. The claim is compared with the turn's record of what it did (`lookups`, the tool calls and the marked blocks alike): it stands when no proposal was filed this turn: `propose_note` or `propose_edit`, or a persona or a setting ("I have proposed Ada" is true after `propose_persona`; a first version that counted only notes and edits failed an existing test on exactly that).
3. In a turn that gave the model tools, `lookup.converse` shows each reply that would end the turn to a `recheck` function, once per turn. When it finds an unfiled claim, the reply and one line ("you said a note or a change was made, but `propose_note` was not called … call it now, or tell the user plainly what you did not do") are added to the call's messages and the model is called again. Neither is saved; the second reply is the answer. It costs one round trip, and only in a turn that made the claim.
4. A reply that still has an unfiled claim after that, and one from a model without tools (no second call: a marker model that has no filing to try again), is followed by one blank line and "(Nothing was filed with this message.)". The line says only what is true of this message whatever the earlier ones did, so a reply that mentions a draft filed earlier is not contradicted.
5. In `plan` and in a turn that asks for no edits (the terminal) nothing is read or added.

## Consequences

- Measured on `gemma4:e4b`, 6 runs per drafting case: 12 of 12 filed a note (before, 5 of 8). The check fired in 1 of the 12 turns and the second ask filed the draft. Samples of this size are direction, not a figure; the figure to watch is how often the second ask recovers a draft, and one case does not say.
- The English patterns are a heuristic, and so a claim in another language, or in words they do not cover, is not read. A false reading costs one extra call and, if the second reply still says it, a line that is true anyway.
- `comment_on` and `show_note` ("I've opened it") are not read: the same failure is possible there and has not been seen.
- A promise that is never kept ("I can draft a new note…" and then nothing) is not read either; it is the case the next prompt-level work would take.

## Alternatives rejected

- **The line alone, with no second ask.** True, but the user is left to ask again; the draft was one call away and the model has the text.
- **A second ask in every edit turn that filed nothing.** It would also fire on a turn that only talks, which is most of them, for a model that claimed nothing.
- **Reading the claim with a second model call.** An extra round trip in every turn, against the founding motivation, to replace a pattern that is cheap and tested.
- **A prompt sentence.** A small model weighs each added rule against the ones it has (ADR 072 measured 18 of 36 edits right with one rule and 8 with two more), and a sentence does not catch the miss when it happens.

## Amendment (2026-10-13): the second ask goes on the user's own message and names every proposal tool

> **Status: Accepted (damiro, 2026-10-13).**

A trace of the soul cases on `gemma4:e4b` (32 runs) showed the second ask fire once, on a persona turn where the model had written its `propose_persona` call as text and filed nothing. Two faults of the line showed there, and in about four replies of an earlier run: it named only `propose_note` and `propose_edit`, whatever the turn offered, and it came after the model's own false reply as a message from the user, so the model answered it as if the user had said it ("you caught me out on that one", "thanks for the heads-up") and often repeated the false claim.

Measured with the first reply scripted as the false claim and no tool call, the real model answering from there (three cases, 6 runs each; the two persona cases and the recipe draft; samples, so direction and not a figure):

| Second ask | Filed | The reply talks about the line |
|---|---|---|
| as shipped | 12 of 18 | 8 of 18 |
| names every tool, says it is from Sympose and asks not to mention it | 16 of 18 | 5 of 18, and almost every reply opened with "you're right" |
| the false reply is left out and the line goes on the user's own message | 13 of 18 | 1 of 18 |

The misses of the last row are two empty replies from the model and three runs where it wrote the tool call as text; no wording of the line reaches those.

**Decision (changes items 3 and the text of the line).** When the last message of the call is the user's own, the second ask is made without the first reply: the line is added to the end of that message for this call only, so the model answers the request again with the line in view. When it is not (tools ran earlier in the turn), the reply and the line follow as before. Neither is saved. The line says it is from Sympose and not the user's, names the proposal tools this turn offers (`propose_note`; `propose_edit` when a note is open; `propose_persona` and `propose_setting` when the persona proposes), asks that a thing be said to be made only after one was called, and asks that the line not be mentioned.

The same three cases through the built code (not a scripted variant): 12 of 18 filed, 5 of 18 ended with "(Nothing was filed with this message.)" (the misses, marked), 0 of 18 replies talked about the line. Filing is no better than the line as shipped (12 of 18 both times; the named-tools wording alone reached 16 of 18, a difference this size does not separate from chance); what changed is that the model no longer answers the line as if the user had said it.

Still open: a model that writes its tool call as text is not read by this check (ADR 077 saw it too).
