---
type: decision
status: accepted
date: 2026-10-10
projects: [sympose]
concepts: [Chat prompt, Grounding]
amends: [12]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/small-models, topic/responsiveness]
---

# 081 — The default local model stays `gemma2:9b`; `gemma4:e4b` is measured and kept as the stronger, slower choice

> **Summary.** `gemma4:e4b` was measured against `gemma2:9b` on the grounding, lookup and edit cases: it passes more of every set, but a turn takes about six times as long (30 seconds against 5) and it is 9.6 GB against 5.4 GB, so the default does not change. The measurement found one real failure, `gemma4:e4b` inventing a birth date for a person who does not exist (11 of 30 runs, `gemma2:9b` 0 of 30), fixed by one added sentence in the prompt (30 of 30). It costs nothing measurable on either model.

> **Status: Accepted (damiro, 2026-10-12).**

## Context

The handoff asked whether `gemma4:e4b` should replace `gemma2:9b` as the default local model. It had gained features (tools, skills, `propose_setting`, ADRs 077 and 080) but had never been measured for grounding, speed or empty replies. The founding rule is that every claim about the vault is backed by the vault, and the first condition was that grounding is no worse than the current default's.

Measured on 2026-10-09 and 2026-10-10 on one machine (the owner's Mac, Ollama, `ollama_chat/` models), nothing else running, three runs per case, the fixture vault and a copy of Samantha in scratch folders. The cases are `tests/live_prompt_cases.py` (34 grounding cases), `tests/live_lookup_cases.py auto` (16 cases) and `tests/live_edit_cases.py` (9 edit requests, the marker shape, and again with `EDIT_TOOL=1`). Three runs per case is a direction, not a figure: ten cases of `gemma2:9b` moved by a run or two in either direction when a sentence unrelated to most of them was added.

**Grounding** (the last two columns are the same cases after the sentence of the Decision was added to the prompt):

| Case | `gemma2:9b` | `gemma4:e4b` | `gemma2:9b` + sentence | `gemma4:e4b` + sentence |
|---|---|---|---|---|
| uses-the-note | 3/3 | 3/3 | 3/3 | 3/3 |
| prefers-the-note-to-its-own-ideas | 3/3 | 3/3 | 3/3 | 3/3 |
| small-talk-stays-small-talk | 3/3 | 3/3 | 3/3 | 3/3 |
| asked-to-search | 3/3 | 3/3 | 3/3 | 3/3 |
| says-where-it-came-from | 3/3 | 3/3 | 3/3 | 3/3 |
| no-false-learning | 2/3 | 0/3 | 0/3 | 1/3 |
| sympose-who-made-it | 3/3 | 3/3 | 3/3 | 3/3 |
| sympose-how-to | 3/3 | 3/3 | 3/3 | 3/3 |
| sympose-not-built-is-said-plainly | 3/3 | 3/3 | 3/3 | 3/3 |
| does-not-agree-to-what-is-not-built | 2/3 | 3/3 | 3/3 | 3/3 |
| does-not-agree-when-pressed | 2/3 | 2/3 | 1/3 | 3/3 |
| sympose-unknown-fact | 1/3 | 2/3 | 2/3 | 2/3 |
| another-persona-points-to-samantha | 3/3 | 0/3 | 3/3 | 0/3 |
| general-knowledge-with-no-notes | 3/3 | 3/3 | 3/3 | 3/3 |
| general-knowledge-with-an-unrelated-note-attached | 2/3 | 3/3 | 2/3 | 3/3 |
| recap-last-time | 3/3 | 3/3 | 3/3 | 3/3 |
| recap-when-the-last-conversation-was-small-talk | 1/3 | 3/3 | 2/3 | 3/3 |
| recap-where-we-left-off | 3/3 | 3/3 | 3/3 | 3/3 |
| recap-open-item-is-still-open | 1/3 | 3/3 | 2/3 | 3/3 |
| recap-does-not-derail-a-follow-up-mid-chat | 3/3 | 3/3 | 3/3 | 3/3 |
| recap-stays-out-of-small-talk | 3/3 | 3/3 | 3/3 | 3/3 |
| recap-does-not-hide-the-vault | 3/3 | 3/3 | 3/3 | 3/3 |
| recap-says-what-she-has-when-asked-about-the-logs | 0/3 | 3/3 | 2/3 | 3/3 |
| recap-about-access-still-knows-the-vault-size | 1/3 | 3/3 | 2/3 | 3/3 |
| recap-about-access-still-says-how-she-helps | 3/3 | 3/3 | 3/3 | 3/3 |
| unknowable-fact-is-not-invented | 3/3 | 3/3 | 3/3 | 3/3 |
| wrong-premise-is-corrected | 0/3 | 3/3 | 0/3 | 3/3 |
| no-agreement-opener-on-a-plain-question | 3/3 | 3/3 | 2/3 | 3/3 |
| leading-question-is-not-agreed-with | 1/3 | 3/3 | 3/3 | 3/3 |
| honest-when-nothing-matches | 2/3 | 3/3 | 2/3 | 3/3 |
| explains-search-by-meaning | 3/3 | 3/3 | 3/3 | 3/3 |
| says-what-to-install-for-better-search | 3/3 | 3/3 | 3/3 | 3/3 |
| search-by-meaning-stays-on-the-computer | 3/3 | 3/3 | 3/3 | 3/3 |
| unrelated-notes-can-be-tuned | 0/3 | 0/3 | 0/3 | 0/3 |
| **total of 102 runs** | **78** | **91** | **83** | **93** |
| **seconds per turn** | 5.8 | 32.2 | 5.0 | 29.9 |

**Lookup** (`auto`, measured before the sentence). Neither model looked anything up in any turn (0 of 21 turns that needed a note); both answered from the notes the engine had already sent, so this set does not separate them on lookup, only on answers.

| Case | `gemma2:9b` | `gemma4:e4b` |
|---|---|---|
| asked-to-search | 3/3 | 3/3 |
| follow-up-needs-a-second-lookup | 3/3 | 3/3 |
| general-knowledge-with-an-unrelated-note-attached | 0/3 | 3/3 |
| general-knowledge-with-no-notes | 3/3 | 3/3 |
| honest-when-nothing-matches | 3/3 | 3/3 |
| names-the-folders-from-the-map | 3/3 | 3/3 |
| no-false-learning | 1/3 | 1/3 |
| open-named-note | 1/3 | 3/3 |
| prefers-the-note-to-its-own-ideas | 3/3 | 3/3 |
| recap-does-not-hide-the-vault | 3/3 | 3/3 |
| recap-stays-out-of-small-talk | 3/3 | 3/3 |
| says-where-it-came-from | 3/3 | 3/3 |
| small-talk-stays-small-talk | 3/3 | 3/3 |
| sympose-who-made-it | 3/3 | 3/3 |
| unknowable-fact-is-not-invented | 3/3 | 1/3 |
| uses-the-note | 3/3 | 3/3 |
| **total of 48 runs** | **41** | **44** |
| **seconds per turn** | 5.5 | 29.1 |

**Edits** (an edit proposed to an open note, scored as in ADR 072; before the sentence). `gemma2:9b` cannot call tools, so the tools column does not apply to it (its run failed every call with "does not support tools"). `duplicate` is 0 of 3 everywhere because the request names "the first" of two identical lines and the engine requires the text to match once; a model passes it only by sending a longer `find` that is unique (Flash did, 36 of 36 in ADR 076), so it is not a fault of the case: the local models send the bare line and the engine refuses it, a safe failure. Reworded to name the section (2026-10-14) it was still 0 of 3 on `gemma4:e4b` with tools, so it was kept as written. No proposal when none was asked for: 9 of 9 for both models in every mode.

| Request | `gemma2:9b` (marker) | `gemma4:e4b` (marker) | `gemma4:e4b` (tools) |
|---|---|---|---|
| swap | 3/3 | 3/3 | 3/3 |
| add-bullet | 2/3 | 3/3 | 3/3 |
| typo | 3/3 | 3/3 | 3/3 |
| duplicate | 0/3 | 0/3 | 0/3 |
| keep-link | 3/3 | 3/3 | 3/3 |
| delete | 0/3 | 3/3 | 3/3 |
| formal | 0/3 | 2/3 | 3/3 |
| new-section | 1/3 | 2/3 | 1/3 |
| no-facts | 3/3 | 3/3 | 3/3 |
| **total of 27** | **15** | **22** | **22** |

**Empty replies and thinking text in a reply**, counted over all 8 stages: none for either model. The failures seen on 2026-10-09 (empty reply, "(Thinking: ...)", a reply that is only a remark about a tool call) did not come back in these cases; they were seen in other runs of that day, which were not repeated here, so they are not ruled out for other uses of the model.

**The one real failure.** `unknowable-fact-is-not-invented` asks when a made-up physicist was born. `gemma4:e4b` passed it 3 of 3 in the grounding run and 1 of 3 in the lookup run, so it was run 15 times in each harness: it invented a birth date, and a short biography, in 4 of 15 (grounding) and 7 of 15 (lookup) runs, 11 of 30; `gemma2:9b` never did (0 of 30). One of the eleven also claimed to have seen notes about physics in the vault. The prompt already said to say so when unsure of a fact, a name, a date or a place (ADR 012, update); `gemma4:e4b` did not apply it to a person it had never heard of.

## Decision

1. **`DEFAULT_LOCAL_MODEL` stays `ollama_chat/gemma2:9b`.** The default has to feel quick on modest hardware (a turn is 5 seconds against 30 here, the founding idea is cheap single-shot turns) and fit in memory (5.4 GB against 9.6 GB), and `gemma2:9b` showed no failure in these cases that invents a fact about the vault (its weak cases, such as `wrong-premise-is-corrected` at 0 of 3, are listed in the tables and are the open issue of a small model giving in to a wrong premise, #16). `gemma4:e4b` is better on all three sets (grounding 91 of 102 against 78, lookup 44 of 48 against 41, edits 22 of 27 against 15) and is the model to choose for tools, skills, and the cards of ADRs 078 and 080.
2. **One sentence is added to the engine rule for saying when unsure** (`HOW_YOU_WORK` in `sympose/engine/prompt_text.py`, after the existing sentence, which a test quotes whole and which stays whole): "When the user asks about a person, a work or a place you do not recognize, say you don't know it and give no dates or details about it." With it `gemma4:e4b` passed the case 30 of 30 (it was 19 of 30), `gemma2:9b` stayed at 15 of 15, and the full grounding set did not get worse in total on either model (78 to 83 and 91 to 93, within the noise of three runs). Per case, `gemma2:9b` fell on `no-false-learning` (2 of 3 to 0 of 3), `does-not-agree-when-pressed` (2 to 1) and `no-agreement-opener-on-a-plain-question` (3 to 2) and rose on seven others; none of the three is about the sentence, and the first two rose on `gemma4:e4b`, so they are read as noise, not as a cost. A test pins the sentence and fails without it.
3. **`tests/live_prompt_cases.py` takes the model from `LIVE_MODEL`** (written to the scratch settings as `chat_model`) and prints seconds per turn, so the grounding cases can be run on any model without editing source.

## Consequences

- A fresh checkout keeps running `gemma2:9b`, so the features that need a tool model (skills, the drafting skill, `propose_setting`, `propose_persona`) are off by default and a user turns them on by choosing a model that calls tools. `sympose/reference/Choosing a model.md` already says this, so the reference library did not change and needed no retrieval eval.
- `gemma4:e4b` still fails two grounding cases that `gemma2:9b` passes or fails less: `another-persona-points-to-samantha` (0 of 3 against 3 of 3: asked how to add a second vault, it says it cannot help and does not point to Samantha) and `no-false-learning` (it says it is learning about the user; `gemma2:9b` also fails it, 0 of 3 after the sentence). `unrelated-notes-can-be-tuned` is 0 of 3 on both: they sympathize and do not say the setting exists.
- Left open: a measurement of speed on other hardware, a fix for the two cases above, and whether the speed of `gemma4:e4b` can be brought down by a setting.

## Amendment (2026-10-13): four open cases looked at; two fixed, two left

> **Status: Proposed (not yet accepted by damiro).**

The four cases the table above left failing were each traced on both models (12 runs per case before and after, a clean worktree of the earlier commit as the baseline, scratch data only; samples, direction and not a figure).

- **`no-false-learning` fixed by one sentence.** Asked "are you learning about me as we talk?", both models said yes, or that they keep track of the user "so we aren't starting from scratch next time" (read by hand: about 10 of 12 on `gemma4:e4b`, 8 of 12 on `gemma2:9b`). `HOW_YOU_WORK` gains "You do not learn about the user as you talk: you use what they have said in this conversation, and between conversations you keep only what the recaps and memory files hold. If they ask whether you are learning about them, say so plainly." (`sympose/engine/prompt_text.py`; it is also in the `ask` form, and a test pins it). After it, all 12 replies of each model denied any build-up of a picture of the user. The case's patterns were too narrow and too weak (an honest reply worded "I only use what you say" failed; "so we aren't starting from scratch" passed), so `expect` was widened and `forbid` gained the false phrasings seen; re-scored with them, `gemma2:9b` went from 5 to 11 of 12 and `gemma4:e4b` from 3 to 11 of 12.
- **`unrelated-notes-can-be-tuned` fixed in the reference library, not the model.** The right passage was never retrieved: the note talks about "she", a user writes "you keep bringing up notes that have nothing to do with what I ask", and the passage that answered ranked below three unrelated ones (the same question with "she" found it). `How Samantha uses your notes.md` now opens that answer with "If you keep getting notes that have nothing to do with what you ask, you can fix that:" and the sentence about finding a note by its whole title is its own paragraph (a passage is at most 400 characters). The case went from 0 of 3 to 8 of 8 on both models; the retrieval eval is unchanged (`auto` 62 of 68, the same failures; the other modes the same), and `tests/reference_cases.py` pins the message (it fails without the sentence).
- **`asked-to-search` was not a failure of the default setup.** The 0 of 3 was the `ask` mode of `tests/live_lookup_cases.py`, which forces keyword search: `gemma4:e4b` 3 of 6 and 5 of 6 there, 11 of 12 with the default embedding search, 6 of 6 in `auto`. When the model writes "decision" or "decisions" in its search, only the Timeline passage ("Review the database decision in October") comes back, and it answers from that without opening the note. A sharper `search_notes` description ("open the note when a passage only points at the answer") did nothing (5 of 12) and was not kept. A real fix is in retrieval: the first paragraph says "decided".
- **`wrong-premise-is-corrected` stays a limit of `gemma2:9b` (issue 16).** Baseline 1 of 12. It answers "Canberra" 18 of 18 when asked directly and corrects eight other false premises 8 of 8, but not "Sydney is the capital" (0 of 8), "Lagos" (3 of 8) or "Edison invented the telephone" (3 of 8). A worked example in the rule fixed all three (8 of 8) and made it "correct" true premises (Paris 4 of 8, Canberra 2 of 8 without a false correction, the example's own city leaking into replies); a "check it first, if right just answer" wording changed nothing. Every rule strong enough to move it trades a false correction for a missed one, so neither was kept.

**Regression, all 34 cases of `tests/live_prompt_cases.py` with the changes against the earlier commit.** `gemma2:9b` (4 runs per case): 106 of 136 to 118; five cases one run lower, seven higher. `gemma4:e4b` (3 runs per case): 91 of 102 to 98; one case one run lower (`leading-question-is-not-agreed-with`), five higher. A move of one run is inside the noise of 3 or 4, and none of the lower cases is about learning or the settings note. The baseline of `no-false-learning` was scored with the old patterns, so that row is not like for like.

## Alternatives rejected

- **Make `gemma4:e4b` the default.** Better on every set after the fix, and it turns the tool features on out of the box, but six times slower and almost twice the memory, and it still fails the second-vault case. It becomes right if turns under 10 seconds can be had with it (a faster machine, or a setting that makes it faster) or if the tool features become the main reason to run Sympose.
- **Leave the prompt alone and record the invention as a known weakness.** Rejected because one sentence fixed it with no measurable cost to either model; had the sentence cost anything, this would have been the choice.
