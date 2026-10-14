---
type: decision
status: accepted
date: 2026-09-24
projects: [sympose]
concepts: [Chat prompt]
amends: [15, 20]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/cost, topic/small-models, topic/retrieval]
---

# 022 — Wiring the Sympose reference library into a persona's turns

> **Summary.** A persona uses the Sympose reference library when its `persona.yaml` sets `sympose_reference: true`; the shipped default persona has it unless her file says `false`. She had agreed to things Sympose does not do. The persona's prompt is now about 940 tokens, so the smallest accepted `context_window` rose to 2048.

> **Status: Accepted.** Builds ADR 019 (the library and its strict retrieval) on ADR 020 (the prompt layout). **Scope of the model figures: Ollama and `gemma2:9b` only.**

## Context

ADR 019 built and measured a library of notes about Sympose itself; ADR 020 fixed where the model looks for notes. The library is not yet searched by any turn. The reason it is needed showed in a real conversation: asked "arent you supposed to review our session logs?" and told "theres history and session logs for you to know what we talked last time", the persona agreed twice ("You're right!") to something Sympose does not do, and answered from an unrelated vault note. Nothing in her prompt said what is and is not built, and the library's "Not built yet" note was not in front of her.

## Decision

**Who has it.** A persona has the library when its `persona.yaml` says `sympose_reference: true`, and the shipped default persona (Samantha) has it unless her file says otherwise (an explicit `false` turns it off), so a `persona.yaml` written before the key existed does not silently lose it (found in review). Every other persona needs an explicit true, and the synthetic Samantha used when no `profiles/` directory exists has it. It is a per-persona setting, so a user can give it to another persona, but nothing is on by default except the shipped one.

**How it is searched.** `engine/reference.py` indexes the package's `reference/` notes (cached like the vault's index, rebuilt when a note changes) and searches them with the strict retriever (ADR 019), on the user's message, up to three passages. It returns nothing for a persona without the flag, and nothing (with a logged warning, never a failed turn) if the notes are missing from an install. Its hits are marked `source: "sympose"` and carry the path `Sympose reference/<note>.md`, so the reply header already shows them as `from Sympose reference/Personas.md`, distinct from a vault note. The follow-up rewrite (ADR 017, 021) searches the vault; since the 2026-10-14 amendment its query also searches the library when it found no vault note.

**How the turn carries it.** The two sources take turns in the turn's list of passages, the reference first (its best, then the vault's best, then their seconds, ...), so when the prompt does not fit (ADR 015) and the end of the list goes first, the best passage of each survives longest. Putting the reference wholly first (the first version) would drop the user's own notes before the documentation on a tight window, against the vault-grounding rule (found in review). The roster that names the persona to point to is read once per turn, not once per trimming attempt. In the last user turn they get their own block after the vault's: `Sympose reference (Sympose's own documentation, for the version installed):`, and for a persona that has the library and no passage matched, `No Sympose reference matched this message.`, so it knows a search was done. The vault's wording is unchanged for a vault-only turn.

**What the persona is told (system prompt, so the same every turn for a persona).**
- *A persona with the library:* questions about Sympose itself (what it can do, how to use it, what is built) are answered only from the Sympose reference in the message, and when it does not cover the question the persona says it does not know that about Sympose; it never agrees that Sympose can do, or should already do, something the reference does not say. Her own notes from the user's vault that describe Sympose's design are the user's plans, not the installed product.
- The rule also says: if the user insists that Sympose does something the reference does not say, do not give in or apologize, and say politely what the reference says.
- *A persona without it, when some persona has it:* a line **with the message** (not in the system prompt): for a message about Sympose itself it has no documentation, should say so, and suggest asking the persona that does (by that persona's name, read from the roster). It sits with the message because in the system prompt the line about vault notes next to the message outweighed it (measured, below). When no persona has the library nothing is said.

## Measured

Real `run_turn`, fixture vault, the shipped persona and a second persona without the library; five to six runs per case; "before" is the commit before this wiring. Two instruments as in ADR 020: `tests/live_prompt_cases.py` and a read-only replay of the recorded conversations.

| case | before | after |
|---|---|---|
| who made Sympose? | 0/5 ("I don't know who made Sympose") | 5/5 |
| how do I add a second vault? | 0/5 (asked what the user wanted to keep in it) | 5/5 |
| does Sympose work in Slack? | 0/5 | 5/5 |
| a question the library cannot answer (licence) | 0/5 (sent the user to a website) | 6/6 |
| "arent you supposed to review our session logs?" | 1/5 | 5/6 (fixture), 6/6 (real vault replay) |
| another persona asked how to add a vault: points to Samantha | 0/5 | 6/6 |
| vault question, small talk, no false learning, honest when nothing matches | unchanged within noise (4 to 5 of 5) | |

Two things had to change to get there, both found by measuring. The library had no passage matching the real question, because the "Not built yet" note said "conversations" and the user said "session logs": the note now has an entry for session logs and past conversations, and the eval has the two real questions (retrieval is by literal words, ADR 014). And the pointer for a persona without the library scored 0 of 5 in the system prompt (it answered "I couldn't find that in the vault") and 6 of 6 next to the message.

**Not solved: a user who insists.** The replayed conversation ends with "theres history and session logs for you to know what we talked last time. arent you aware of that?". Before the rule about not giving in, 3 of 4 replies opened with "you're right" and none said she cannot read the logs (0 of 4). With the rule, one run of four had 3 of 4 saying she cannot read them; a run of six with a stricter check (a false confession such as "I completely forgot about those session logs, my apologies") had 3 of 6 still confessing a lapse and only 1 of 6 saying she cannot read them. The two runs were scored differently and are noisy; the honest reading is that the rule helped somewhat and cannot be called reliable: a small model deferring to a confident user. (The logs do exist, so "you're right, there are logs" is true; the failure is the false confession and not saying she cannot read them.)

The reply to "whats with our table today?" is now a question back ("what do you mean by that?"), as the voice asks for; that comes from the persona rules and not from the library, and is noted because it was one of the recorded failures.

## Consequences

Samantha's prompt is now about 940 tokens (the persona's voice, the rules and an empty turn), measured with the engine's own count. The smallest `context_window` the engine accepted was 1024, which leaves 768 for the prompt, so at that setting every turn of the shipped persona was refused as too small. The floor is now 2048 (1536 for the prompt, about 600 tokens beyond Samantha's own instructions); a smaller setting is raised to it. The default follows the model's own window and was never affected. It is not a setting of its own: it only guards a `context_window` the user typed, who can already choose any number above it, and a persona or message that still does not fit gets the existing message naming the setting.

The header shows a reference passage as `from Sympose reference/<note>.md`.

## Not built yet

- ~~The reference search re-tokenizes each candidate passage's text on every query in strict mode.~~ Measured and closed (see the amendment below).
- ~~The reference search does not use the rewrite step.~~ Built (see the amendment below).
- ~~The passage budget is not split between the two sources beyond the ordering above.~~ Closed (see the amendment below).
- The drift guard beyond the version (ADR 019), a `/help` that lists the same notes, other models and cloud models.
- The insisting-user case (above), and any check on models other than `gemma2:9b`.
- ~~Whether a Sympose question should also suppress the vault's design notes about Sympose.~~ Decided: no (see the amendment below).

## Amendment (2026-10-13): the pointer names setting up, vaults and models

> **Status: Accepted (damiro, 2026-10-13).**

`gemma4:e4b` asked "how do I add a second vault?" by a persona without the library said it could not help, or sent the user to Obsidian, and never named Samantha (0 of 6 runs; `gemma2:9b` 3 of 3). The pointer was in the message, after the line about no notes matching, and the question does not say "Sympose": the model took "vault" for Obsidian's.

Measured on scratch data, four wordings of the pointer on both models, three questions that are about Sympose (a second vault, changing the model, where conversations are kept) and two that are not (the Journal folder, a general fact), 3 runs each (samples, direction and not a figure):

| Pointer | `gemma4:e4b` points | `gemma2:9b` points | Points when it should not |
|---|---|---|---|
| as shipped | 6 of 9 | 9 of 9 | 0 of 12 |
| the list of what counts as a Sympose question gains "how to set it up, adding or choosing vaults, its settings, which model it uses" | 9 of 9 | 9 of 9 | 0 of 12 |
| the same, and "Sympose is the program you run in, not Obsidian" first | 9 of 9 | 9 of 9 | 0 of 12 |
| the same, with the names first | 9 of 9 | 9 of 9 | 0 of 12 |

**Decision.** The second row, the smallest change (`POINT_TO_REFERENCE` in `sympose/engine/prompt_text.py`); the longer wordings did not do better. The live case `another-persona-points-to-samantha` then passed 6 of 6 on `gemma4:e4b`. Only a persona without the library gets this line, so Samantha's turns are unchanged. A test pins the new words.

## Amendment (2026-10-14): a follow-up searches the library by its rewrite; four leftovers closed (#7)

> **Status: Accepted (damiro handed the call to the assistant, 2026-10-14; he can reopen any line).**

**A follow-up now reaches the library through the follow-up rewrite (ADR 017).** "and how do I undo that?", after a talk about the default persona, has nothing to search by. Measured with `gemma2:9b` writing the rewrite (3 runs each, six follow-ups after a Sympose question): the message alone found its answer in 0 of 6, the rewrite found it in 15 of 18 runs (5 of 6 follow-ups; "and in the terminal?" never did, its rewrite is about proposals). The rewrite is the call the vault already makes, so the library costs no extra model call; its query is searched in the library as well, its passages and the message's own take turns, the rewrite's first, three at most and none twice (so a rewrite that lost a word cannot push out the message's own best passage) (`reference.ground(persona, message, rewritten)`).

**When.** Only when the rewrite found no note in the vault (`Followed.rewritten`; a vault follow-up such as "can you expand on that?" after a talk about spend is about the vault, and its rewrite "Q3 cloud costs" shares two words with the library's passage on what Sympose costs, which in keyword mode would attach three passages). A user whose vault holds notes that answer a Sympose follow-up gets what they got before, the message alone. Nothing is asked of the model that was not already. Regression check: the rewrites of the eight follow-up cases of the vault eval attach nothing from the library, and five follow-ups about Sympose are pinned in `reference_cases.py` (`REF_FOLLOW_UPS`) with the rewrite the model gave; they pass in keyword mode, so the test needs no model.

**Not built, and why.**
- *Caching the tokens of the library's passages.* A strict query over the 271 passages of 17 notes takes 0.4 ms (a lenient one 0.02 ms), so a turn pays under a millisecond twice. It would take a library 100 times larger to cost a visible 40 ms. Revisit if the library grows that far.
- *Splitting the passage budget between the two sources.* They already take turns, the library first, so when the window is tight the best passage of each survives longest (above). No case has shown a source starved.
- *Suppressing the user's own notes about Sympose on a Sympose question.* They are the user's notes: hiding them would hide evidence from a persona whose rule is that every claim about the vault is backed by it. Both appear, labelled, and the persona is told which to trust.

## Alternatives rejected

- **The library on for every persona.** The maintainer's rule is that other personas point to Samantha; a persona-specific specialist should not answer for the product.
- **Pointing other personas at "the default persona".** The default can be changed to a persona without the library; the roster is asked instead.
- **Mixing reference passages into the vault's block.** The user could not tell a note of theirs from documentation, and neither could the model.
- **Searching the library only when the message names Sympose.** A word list; the strict retrieval already decides from the message's own words.
