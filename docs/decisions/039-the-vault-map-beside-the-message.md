---
type: decision
status: accepted
date: 2026-09-29
projects: [sympose]
concepts: [Chat prompt]
amends: [20, 26, 35]
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 039 — The vault map goes with the message, and her rules name it as a source of facts

> **Status: Accepted.** Amends ADR 035 (where the map sits, and a rule it left unchanged) and, for the map only, ADR 026 and ADR 020's layout. **Scope of every model figure: Ollama and `gemma2:9b` only**, the local default; nothing was measured on a cloud model. Restores vault grounding for a question about the vault's own shape, which is a regression to fully restore, not a tradeoff.

## Context

In a real conversation on the local model, a user asked "can you access my vault now? how large my vault is?" and "so how can you help me about my vault?". She answered "I don't have access to your vault or any personal information like its size." The prompt she was given held the vault map ("620 notes in 9 top-level folders", ADR 035) on every turn, so the answer was in front of her and she denied having it.

Rebuilding that exact request and sending it to `gemma2:9b` (8 tries per figure, scored by whether the reply gives the true number and does not claim to lack the information):

| what changed | vault size | folder count |
|---|---|---|
| nothing (as shipped) | 1/8 | 0/8 |
| the map moved to the end of the system prompt | 2/8 | not run |
| the map moved beside the message | 3/8 | not run |
| no recaps at all (the ceiling for "recaps are the cause") | 1/8 | not run |
| the recap of the access conversation left out | 1/8 | not run |
| her grounding rule widened to cover the map | 2/8 | 1/8 |
| that, and her instructions naming the map | 8/8 | 6/8 |
| **both, and the map beside the message** | **8/8** | **8/8** |

Two things follow. The recap that says the user asked whether she has access does push her towards a denial, but removing it does not fix the answer (1 of 8), so it is not the cause. The cause is that her instructions contradicted the map. `GROUNDING_RULE` says to state only facts about the vault "backed by the notes found for their message". The map is not a note found for the message, and ADR 035 added it without widening that rule, so a model that follows the rule literally must say it could not find the size. The instructions also never said she has the map, so the model's own habit ("I'm an AI, I can't see your files") filled the gap. Only when the rule, the instructions and the position all agree does the answer come out right; each alone was not enough.

## Decision

1. **`GROUNDING_RULE`** says a fact about the vault may be backed by "the notes found for their message or by the shape of the vault given with it". A source of facts the prompt supplies has to be named by the rule that limits her to backed facts, or the rule forbids it.
2. **`HOW_YOU_WORK`** says she always knows the shape of the vault (how many notes, its folders and most common tags), given with each message, so she can answer questions about its size and layout without a search.
3. **The map (or, for a cloud model that may not receive it, the line saying so) is the first block of the last user turn**, above the notes found for the message, instead of in the system prompt. It is still computed once per turn, still fixed across every attempt of the fitting loop (ADR 015), and never left out to fit the window, unlike the notes, the recaps and the history. Its label and the withheld line are unchanged.
4. **The context meter's estimate** (ADR 018) counts the map as part of the next turn, since a real turn includes it, so the estimate does not read lower than before.

## Consequences

- The system prompt no longer carries anything that changes when the vault does, so it is the same on every turn unless the recaps or the persona change. That is the property ADR 026 wanted for it.
- A question about the vault's size, its folders, or their counts is answered from facts she has, with the number, instead of a refusal. A question the map does not answer still goes to the notes, and to "I couldn't find that in the vault" (ADR 021's rule is unchanged).
- ADR 035's statement that the map "sits fixed in `build_system_prompt`" is no longer true; it is fixed in the last user turn.

## Checked against the full live-case suite

All 34 cases of `tests/live_prompt_cases.py` (4 tries each), measured with this change isolated in its own worktree from a clean commit, so a concurrent, unrelated change in the same working directory could not affect the count (see below). No case regressed beyond the noise of 4 tries; two moved by one try in opposite directions (`leading-question-is-not-agreed-with` 2→1, `explains-search-by-meaning` 3→4). `wrong-premise-is-corrected` is 0/4 on both this change and a clean `HEAD`: a real, pre-existing gap, not something this record touches.

**A methodological note, worth repeating.** A first pass of this same check, run directly in the day-to-day checkout rather than an isolated worktree, showed `unrelated-notes-can-be-tuned` collapse from 6/8 to 0/12 and flagged two more cases as shaky. All three turned out to be nothing to do with this change: a second Claude Code session was concurrently building an unrelated feature in the same checkout and had, uncommitted, edited the reference note the failing case depends on (`How Samantha uses your notes.md`), which changed which passage the reference search returned. Measuring "before vs. after" by running the live suite against a shared, uncommitted working tree conflates whatever else is uncommitted there with the change actually being measured; an isolated worktree built from the last clean commit, with only the change under test reapplied, is what actually isolates it.

## Not solved

- She still often says "I can't access your vault directly" before giving the right number (in the strict scoring 6 of 8 replies to the size question, 8 of 8 for the others), because a small model's habit is strong. It is half-true, since she reads the notes Sympose puts in the message and cannot browse the vault, and the number that follows is right, so it was left.
- A recap that only records the user asking about her abilities is still written and still sent. Leaving such a recap out did not change the answer; recap writing is left as ADR 023 has it.
- Her own earlier replies in a chat carry into the next turn. A wrong answer earlier in the conversation still pulls a later one towards it, and nothing here removes it.
- No cloud model was measured.

## Alternatives rejected

- **Only moving the map** (to the end of the system prompt, or beside the message): 2/8 and 3/8. The rule contradicted it whichever place it sat.
- **Only widening the rule and the instructions**: 8/8 on size, 6/8 on the folder count; moving the map beside the message closed that gap.
- **Dropping recaps that mention her abilities, or asking the recap writer to leave such talk out**: did not change the answer, and a filter for a topic is a list of wordings to keep up. Left as it is.
- **A rule listing phrases she must not say** ("I can't access"): it would need every wording, and the cause was the contradiction, not the phrase.
- **Removing the map's "always known" label or the map itself**: the map is what lets her answer with a real number without a search (ADR 035).
